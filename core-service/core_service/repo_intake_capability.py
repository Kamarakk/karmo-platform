"""Core-side glue for the repo intake scan: "KARMO, check
github.com/owner/repo" dispatches one repo_intake_scan job to a worker
(worker-runtime/app/repo_intake.py) and turns its report into a plain
answer. The worker only reads the repository -- nothing from it is built,
installed or run -- and the clone is deleted with the job's sandbox.

Runs on KARMO-WORKER02 by default so the brain host never downloads
untrusted code. Same activation boundary as vision_capability.py: needs
worker_dispatch_client.available.
"""

from __future__ import annotations

import re

REPO_INTAKE_TOOL_ID = "repo_intake_scan"
REPO_INTAKE_TOOL_VERSION = "1.0.0"
_DEFAULT_WORKER_ID = "KARMO-WORKER02"
_DEADLINE_SECONDS = 320.0  # worker allows the scan 290s, plus dispatch round trips

REPO_SCAN_REQUEST = re.compile(
    r"^(?:(?:hey\s+)?(?:karmo|jarvis)[,\s]+)?(?:(?:can\s+you|please)\s+)?"
    r"(?:check|scan|vet|inspect|review|look\s+at|look\s+over|is\s+it\s+safe\s+to\s+use)?\s*(?:out\s+)?"
    r"(?:(?:this|the)\s+)?(?:repo(?:sitory)?\s+)?"
    r"(?P<url>(?:https?://)?(?:www\.)?github\.com/[A-Za-z0-9-]+/[A-Za-z0-9._-]+?)(?:\.git)?/?"
    r"(?:\s+(?:for\s+me|please))?[\s!.?]*$",
    re.IGNORECASE,
)


class RepoIntakeCapabilityError(RuntimeError):
    pass


def repo_scan_url(text: str) -> str | None:
    match = REPO_SCAN_REQUEST.match(text.strip())
    return match.group("url") if match else None


def manifest() -> dict:
    return {
        "tool_id": REPO_INTAKE_TOOL_ID,
        "domain": "security",
        "version": REPO_INTAKE_TOOL_VERSION,
        "description": (
            "Look a public GitHub repository over before Kamara decides whether KARMO may use it: "
            "GitHub metadata, OpenSSF Scorecard, then a shallow clone on a worker scanned by Trivy, "
            "GuardDog and OSV-Scanner. Never builds, installs or runs the repository's code."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
            "additionalProperties": False,
        },
        "output_schema": {"type": "object", "properties": {"verdict": {"type": "string"}}},
        "capability_class": "READ",
        "read_scope": "one public GitHub repository, read on a worker",
        "write_scope": "none on Core; the worker's clone lives in the job sandbox and is deleted with it",
        "external_side_effects": "one dispatched job to a worker via the existing worker-coordination path",
        "financial_action": False,
        "destructive_action": False,
        "network_requirements": "none from Core; the worker reaches api.github.com, github.com, api.securityscorecards.dev",
        "secret_requirements": "none beyond the existing worker-dispatch DSN",
        "invocation_identity": "karmo-chat-model",
        "timeout_seconds": 320,
        "retry_policy": "none",
        "idempotent": True,
        "idempotency_mechanism": "read-only scan; repeating it changes nothing",
        "rollback_or_compensation": "not applicable",
        "health_check": "scan a small known-good public repository",
        "deprecation_policy": "explicit version replacement",
        "dependencies": "worker_dispatch_client.available; git and the scanners installed on the worker",
        "observability": "structured operator response",
        "failure_isolation": "a dispatch failure or timeout refuses cleanly, never hangs the chat turn",
    }


def dispatch_repo_scan(worker_dispatch_client, *, worker_id: str, url: str) -> dict:
    if not isinstance(url, str) or not url.strip():
        raise RepoIntakeCapabilityError("url must be non-empty text")
    if not worker_dispatch_client.available:
        raise RepoIntakeCapabilityError("worker dispatch is not activated -- no worker-dispatch DSN configured")
    outcome = worker_dispatch_client.dispatch(
        worker_id=worker_id,
        tool_id=REPO_INTAKE_TOOL_ID,
        tool_version=REPO_INTAKE_TOOL_VERSION,
        arguments={"url": url.strip()},
        total_deadline_seconds=_DEADLINE_SECONDS,
    )
    if outcome.outcome != "SUCCEEDED" or not isinstance(outcome.result, dict):
        raise RepoIntakeCapabilityError(f"{outcome.outcome}: {outcome.error}")
    if not isinstance(outcome.result.get("verdict"), str):
        raise RepoIntakeCapabilityError("worker returned an invalid repo_intake_scan result")
    return outcome.result


def handler(worker_dispatch_client, *, worker_id: str = _DEFAULT_WORKER_ID):
    def _handler(arguments: dict) -> dict:
        return dispatch_repo_scan(worker_dispatch_client, worker_id=worker_id, url=arguments.get("url"))
    return _handler


def _scanner_line(name: str, result: dict) -> str:
    if not result.get("ran"):
        return f"{name}: not run ({result.get('reason', 'unknown')})"
    if name == "Trivy":
        vulns = result.get("vulnerabilities") or {}
        serious = sum(vulns.get(level, 0) for level in ("CRITICAL", "HIGH"))
        return (
            f"Trivy: {sum(vulns.values())} known vulnerabilities ({serious} critical/high), "
            f"{result.get('secrets', 0)} secrets, {result.get('misconfigurations', 0)} config problems"
        )
    if name == "GuardDog":
        rules = result.get("rules") or []
        return f"GuardDog: {result.get('threats', 0)} malware-style patterns" + (f" ({', '.join(rules)})" if rules else "")
    return f"OSV-Scanner: {result.get('vulnerable_packages', 0)} vulnerable dependencies"


def format_report(report: dict) -> str:
    meta = report.get("metadata") or {}
    lines = [f"Repo check: {report.get('repo')} -- {report.get('verdict')}"]
    about = [meta.get("description") or "no description"]
    if meta.get("stars") is not None:
        about.append(f"{meta['stars']} stars")
    about.append(f"license {meta.get('license') or 'none'}")
    if meta.get("language"):
        about.append(meta["language"])
    if meta.get("pushed_at"):
        about.append(f"last change {str(meta['pushed_at'])[:10]}")
    lines.append("About: " + "; ".join(about) + ".")
    reasons = report.get("reasons") or []
    if reasons:
        lines.append("Why:")
        lines.extend(f"- {reason}" for reason in reasons)
    card = report.get("scorecard") or {}
    if card.get("available"):
        lines.append(f"OpenSSF Scorecard: {card.get('score')}/10.")
    scanners = report.get("scanners") or {}
    for key, name in (("trivy", "Trivy"), ("guarddog", "GuardDog"), ("osv", "OSV-Scanner")):
        if key in scanners:
            lines.append(_scanner_line(name, scanners[key]) + ".")
    checks = report.get("checks") or {}
    if checks.get("install_or_build_files"):
        lines.append("Install/build files to read before running: " + ", ".join(checks["install_or_build_files"]) + ".")
    if report.get("cloned"):
        lines.append("Nothing from the repo was installed or run, and the downloaded copy was deleted after the scan.")
    else:
        lines.append("The repo was not downloaded.")
    return "\n".join(lines)

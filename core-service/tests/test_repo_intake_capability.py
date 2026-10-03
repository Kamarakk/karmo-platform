"""Tests for the core side of the repo intake scan: the chat command, the
dispatch to a worker, and the plain-text report."""

from __future__ import annotations

from core_service.operator import KarmoOperator
from core_service.repo_intake_capability import format_report, repo_scan_url
from core_service.worker_dispatch import DispatchOutcome

REPORT = {
    "repo": "github.com/octo/tool",
    "metadata": {"description": "a tool", "stars": 12, "license": "MIT", "language": "Python",
                 "pushed_at": "2026-09-01T00:00:00Z"},
    "scorecard": {"available": True, "score": 6.2},
    "checks": {"install_or_build_files": ["setup.py"]},
    "scanners": {
        "trivy": {"ran": True, "vulnerabilities": {"HIGH": 2, "LOW": 1}, "secrets": 0, "misconfigurations": 0},
        "guarddog": {"ran": True, "threats": 0, "rules": []},
        "osv": {"ran": False, "reason": "not installed on this worker"},
    },
    "verdict": "CAUTION",
    "reasons": ["2 critical/high known vulnerabilities in dependencies"],
    "cloned": True,
}


class FakeWorkerDispatchClient:
    def __init__(self, *, available=True, outcome=None):
        self.available = available
        self._outcome = outcome
        self.calls = []

    def dispatch(self, **kwargs):
        self.calls.append(kwargs)
        return self._outcome


def test_repo_scan_url_matches_check_requests_only():
    assert repo_scan_url("check github.com/octo/tool") == "github.com/octo/tool"
    assert repo_scan_url("KARMO, can you scan https://github.com/octo/tool.git please") == "https://github.com/octo/tool"
    assert repo_scan_url("is it safe to use github.com/octo/tool?") == "github.com/octo/tool"
    assert repo_scan_url("https://github.com/octo/tool") == "https://github.com/octo/tool"
    assert repo_scan_url("what does github.com/octo/tool do and who wrote it") is None
    assert repo_scan_url("check my email") is None


def test_chat_check_dispatches_to_worker02_and_answers_without_a_model():
    client = FakeWorkerDispatchClient(outcome=DispatchOutcome(
        outcome="SUCCEEDED", job_id="job-1", elapsed_seconds=40.0, poll_count=3, result=REPORT,
    ))
    response = KarmoOperator(worker_dispatch_client=client)._handle("check github.com/octo/tool")

    assert client.calls[0]["tool_id"] == "repo_intake_scan"
    assert client.calls[0]["worker_id"] == "KARMO-WORKER02"
    assert client.calls[0]["arguments"] == {"url": "github.com/octo/tool"}
    assert response["model"] is None
    assert response["message"].startswith("Repo check: github.com/octo/tool -- CAUTION")


def test_chat_check_reports_cleanly_when_worker_dispatch_is_off():
    response = KarmoOperator(worker_dispatch_client=FakeWorkerDispatchClient(available=False))._handle(
        "scan github.com/octo/tool"
    )
    assert response["error"] == "repo_scan_failed"
    assert "couldn't check" in response["message"]


def test_format_report_names_the_verdict_reasons_and_scanners():
    text = format_report(REPORT)
    for expected in ("CAUTION", "2 critical/high known vulnerabilities", "license MIT", "Scorecard: 6.2/10",
                     "Trivy: 3 known vulnerabilities (2 critical/high)", "OSV-Scanner: not run (not installed",
                     "setup.py", "nothing from the repo was installed or run"):
        assert expected.lower() in text.lower()

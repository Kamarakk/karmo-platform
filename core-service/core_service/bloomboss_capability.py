"""BloomBoss report capability for KARMO chat.

Wraps bloomboss.history.inspect_history_csv + bloomboss.report.snapshot_report
-- both already-existing, already-tested functions. No new business logic
here; this module is only the thin capability boundary (manifest + handler)
that lets KARMO chat's tool-calling loop reach code that already worked.
See docs/architecture/KARMO_CHAT_TOOL_CALLING_AND_EXTERNAL_DELEGATION.md,
Section 3.2, for the design this implements.
"""

from __future__ import annotations

import sys
from pathlib import Path

from .control import CapabilityClass

BLOOMBOSS_REPORT_TOOL = "karmo.bloomboss.report"
TOOL_VERSION = "1.0.0"

# core_service/ -> core-service/ -> repo root. bloomboss/ is a repo-root
# sibling package, not installed, so it is only importable when the repo
# root is on sys.path -- true when running from the repo root (as
# bloomboss's own tests do) but not when running core-service's own tests
# from core-service/. Adding the repo root here mirrors the existing
# worker-runtime/app/_prototype_paths.py pattern for the same situation.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_HISTORICAL_DATA_DIR = _REPO_ROOT / "docs" / "bloomboss" / "historical_data"


class BloomBossCapabilityError(RuntimeError):
    pass


def manifest() -> dict:
    return {
        "tool_id": BLOOMBOSS_REPORT_TOOL,
        "domain": "bloomboss",
        "version": TOOL_VERSION,
        "description": (
            "Report BloomBoss business analytics (revenue, margin, per-unit outcomes, "
            "supplier summary) computed from the real historical purchase/sale data "
            "currently imported into KARMO. Coverage reflects only what has actually "
            "been imported so far -- see docs/bloomboss/historical_data/README.md -- "
            "never invented or assumed figures."
        ),
        "input_schema": {"type": "object", "additionalProperties": False},
        "output_schema": {"type": "object"},
        "capability_class": CapabilityClass.READ.value,
        "read_scope": "docs/bloomboss/historical_data/*.csv",
        "write_scope": "none",
        "external_side_effects": "none",
        "financial_action": False,
        "destructive_action": False,
        "network_requirements": "none; local filesystem only",
        "secret_requirements": "none",
        "invocation_identity": "karmo-chat-model",
        "timeout_seconds": 15,
        "retry_policy": "none",
        "idempotent": True,
        "idempotency_mechanism": "pure bounded read",
        "rollback_or_compensation": "not applicable",
        "health_check": "invoke and confirm at least one source file is reported",
        "deprecation_policy": "explicit version replacement",
        "dependencies": "bloomboss package (already vendored in this repo)",
        "observability": "structured operator response",
        "failure_isolation": "a missing/invalid CSV refuses cleanly, never partial/invented data",
    }


def handler(arguments: dict) -> dict:
    if not _HISTORICAL_DATA_DIR.is_dir():
        raise BloomBossCapabilityError(
            f"no BloomBoss historical data directory found at {_HISTORICAL_DATA_DIR}"
        )
    csv_files = sorted(p for p in _HISTORICAL_DATA_DIR.glob("*.csv") if p.is_file())
    if not csv_files:
        raise BloomBossCapabilityError(
            f"no BloomBoss historical data CSV files found in {_HISTORICAL_DATA_DIR}"
        )

    repo_root_str = str(_REPO_ROOT)
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)
    from bloomboss.history import inspect_history_csv
    from bloomboss.report import snapshot_report

    reports = []
    errors = []
    for csv_path in csv_files:
        try:
            reports.append(snapshot_report(inspect_history_csv(csv_path)))
        except Exception as exc:  # noqa: BLE001 -- one bad file must never block the others
            errors.append({"file": csv_path.name, "error": f"{type(exc).__name__}: {exc}"})

    if not reports:
        raise BloomBossCapabilityError(f"every BloomBoss data file failed to load: {errors}")

    failed_names = {entry["file"] for entry in errors}
    return {
        "reports": reports,
        "files_loaded": [p.name for p in csv_files if p.name not in failed_names],
        "errors": errors,
        "coverage_note": (
            "This reflects only the historical data files actually imported into KARMO "
            "so far -- not necessarily the complete business history."
        ),
    }

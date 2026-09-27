"""BloomBoss report capability for KARMO chat.

Wraps bloomboss.history.inspect_history_csv + bloomboss.report.snapshot_report
-- both already-existing, already-tested functions. No new business logic
here; this module is only the thin capability boundary (manifest + handler)
that lets KARMO chat's tool-calling loop reach code that already worked.
See docs/architecture/KARMO_CHAT_TOOL_CALLING_AND_EXTERNAL_DELEGATION.md,
Section 3.2, for the design this implements.
"""

from __future__ import annotations

import csv
import re
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


def known_cultivar_names() -> frozenset[str]:
    """Lower-cased cultivar names in the imported historical CSVs, so chat can
    recognize a BloomBoss question that names a plant ("how are the Ninja
    Albos doing?") without any business keyword. Never raises: missing or
    unreadable data just means no names."""
    names = set()
    try:
        for csv_path in _HISTORICAL_DATA_DIR.glob("*.csv"):
            with csv_path.open(newline="", encoding="utf-8") as handle:
                for row in csv.DictReader(handle):
                    name = (row.get("cultivar") or "").strip().lower()
                    if name:
                        names.add(name)
    except (OSError, UnicodeDecodeError, csv.Error):
        pass
    return frozenset(names)


def _pct(value) -> str:
    try:
        return f"{float(value) * 100:.0f}%"
    except (TypeError, ValueError):
        return "unknown"


def _money(value) -> str:
    return "unknown" if value in (None, "") else f"${value}"


def _cultivar_line(name: str, row: dict) -> str:
    line = (
        f"- {name}: {row.get('units', 0)} units, {row.get('sold', 0)} sold "
        f"({_pct(row.get('sell_through_rate'))} sell-through), {row.get('lost', 0)} lost, "
        f"revenue {_money(row.get('revenue'))}"
    )
    if row.get("sold"):
        line += (
            f", profit {_money(row.get('realized_profit_on_known_costs'))}"
            f", margin {_pct(row.get('realized_gross_margin_on_known_costs'))}"
        )
    return line


def chat_digest(result: dict, question: str) -> str:
    """A few plain-text lines of handler()'s result for the chat model to
    answer from. Live measurement (2026-09-27): the full result, even capped
    at 6000 chars, was ~2,800 prompt tokens and took 2.5-3 minutes to read
    on karmo-ai01's CPU. Only real figures from the report; cultivars the
    question names get their line, otherwise every cultivar gets one."""
    lowered = question.lower()
    lines = []
    for report in result.get("reports", []):
        summary = report.get("business_summary") or {}
        lines.append(f"BloomBoss data from {report.get('source', {}).get('name', 'unknown file')}:")
        lines.append(
            f"Totals: {summary.get('unit_count', 0)} units, {summary.get('sale_count', 0)} sold, "
            f"revenue {_money(summary.get('total_revenue'))}, "
            f"gross profit {_money(summary.get('realized_gross_profit_on_known_costs'))}, "
            f"margin {_pct(summary.get('realized_gross_margin_on_known_costs'))}, "
            f"sell-through {_pct(summary.get('sell_through_rate'))}, "
            f"{summary.get('active_inventory_units', 0)} still in inventory "
            f"({_money(summary.get('known_capital_tied_up'))} tied up)."
        )
        cultivars = report.get("cultivar_summary") or {}
        named = {name: row for name, row in cultivars.items() if name.lower() in lowered}
        for name, row in (named or cultivars).items():
            lines.append(_cultivar_line(name, row))
    for error in result.get("errors", []):
        lines.append(f"Could not load {error.get('file')}.")
    lines.append(result.get("coverage_note", ""))
    return "\n".join(line for line in lines if line)


# A plain status lookup ("how are the Ninja Albos doing?", "Melo Albo
# numbers") versus a question that needs judgment ("should I restock...").
_LOOKUP_WORDS = re.compile(
    r"\b(how(?:'s| is| are| did| have)|doing|performing|performance|stats|numbers|figures|sold)\b",
    re.IGNORECASE,
)
_JUDGMENT_WORDS = re.compile(
    r"\b(should|restock|reorder|recommend\w*|advice|advise|why|compare|compared|versus|vs|better|worse"
    r"|best|worst|predict\w*|forecast\w*|plan|strategy|price|pricing|worth)\b",
    re.IGNORECASE,
)


def _named_cultivars(names, question: str) -> list:
    lowered = question.lower()
    return [name for name in names if name.lower() in lowered]


def is_lookup_question(question: str) -> bool:
    """True for a status lookup naming at least one imported cultivar, which
    lookup_answer() can answer from the figures alone. Cheap: reads only the
    cultivar names, not the full report."""
    return bool(
        _named_cultivars(known_cultivar_names(), question)
        and _LOOKUP_WORDS.search(question)
        and not _JUDGMENT_WORDS.search(question)
    )


def lookup_answer(result: dict, question: str) -> str | None:
    """Plain-sentence answer for is_lookup_question() questions, built only
    from handler()'s real figures -- no model involved. None if the question
    names no cultivar in the loaded reports."""
    lines = []
    sources = []
    for report in result.get("reports", []):
        cultivars = report.get("cultivar_summary") or {}
        for name in _named_cultivars(cultivars, question):
            row = cultivars[name]
            line = (
                f"{name}: {row.get('units', 0)} units, {row.get('sold', 0)} sold "
                f"({_pct(row.get('sell_through_rate'))} sell-through), {row.get('lost', 0)} lost. "
                f"Revenue {_money(row.get('revenue'))}"
            )
            if row.get("sold"):
                line += (
                    f", profit {_money(row.get('realized_profit_on_known_costs'))}, "
                    f"{_pct(row.get('realized_gross_margin_on_known_costs'))} margin"
                )
            lines.append(line + ".")
            sources.append(report.get("source", {}).get("name", "unknown file"))
    if not lines:
        return None
    lines.append(f"From {', '.join(sorted(set(sources)))} (imported BloomBoss data only).")
    return "\n".join(lines)


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

"""Kamara's morning brief: one plain message built from KARMO's own real
data -- the date, lab health, BloomBoss totals, open KARMO tasks, and the
facts he asked KARMO to remember. No model call, so it answers in about a
second even on the CPU-only host, and every figure is a real reading.

Each section is optional: a reader that fails or returns nothing simply
drops its line rather than failing the brief.
"""

from __future__ import annotations

import re
from datetime import datetime

MORNING_BRIEF_REQUEST = re.compile(
    r"^(?:good\s*morning|morning|brief\s+me|(?:my\s+)?(?:morning|daily)\s+brief(?:ing)?|catch\s+me\s+up)"
    r"(?:[\s,]+(?:karmo|jarvis))?[\s!.?]*$",
    re.IGNORECASE,
)
MAX_BRIEF_FACTS = 3

_GIB = 1024 ** 3


def is_morning_brief_request(text: str) -> bool:
    return bool(MORNING_BRIEF_REQUEST.match(text.strip()))


def _greeting(local: datetime) -> str:
    part = "morning" if local.hour < 12 else "afternoon" if local.hour < 18 else "evening"
    hour = local.hour % 12 or 12
    return f"Good {part}, Karmo. It's {local:%A}, {local:%B} {local.day}, {hour}:{local:%M} {local:%p}."


def _lab_line(status: dict | None) -> str | None:
    if not status:
        return None
    parts = []
    memory = status.get("memory") or {}
    if memory.get("available") and memory.get("total_bytes") and memory.get("available_bytes") is not None:
        parts.append(f"{memory['available_bytes'] / _GIB:.1f} of {memory['total_bytes'] / _GIB:.1f} GB memory free")
    disk = status.get("disk") or {}
    if disk.get("total_bytes"):
        used = 100 * (1 - disk.get("free_bytes", 0) / disk["total_bytes"])
        parts.append(f"disk {used:.0f}% used")
    load = (status.get("host") or {}).get("load_average")
    if load:
        parts.append(f"load {load[0]}")
    # "inactive" is also what systemctl says for a unit that isn't installed
    # on this host, so only "failed" is reported as down.
    services = status.get("services") or {}
    failed = sorted(unit for unit, info in services.items() if info.get("state") == "failed")
    if any(info.get("state") == "active" for info in services.values()) or failed:
        parts.append("FAILED: " + ", ".join(failed) if failed else "KARMO core up")
    containers = (status.get("containers") or {}).get("containers")
    if containers is not None:
        parts.append(f"{sum(1 for row in containers if str(row.get('status', '')).startswith('Up'))} containers running")
    return "Lab: " + "; ".join(parts) + "." if parts else None


def _bloomboss_line(result: dict | None) -> str | None:
    if not result:
        return None
    units = sold = inventory = 0
    revenue = 0.0
    found = False
    for report in result.get("reports", []):
        summary = report.get("business_summary") or {}
        found = True
        units += summary.get("unit_count") or 0
        sold += summary.get("sale_count") or 0
        inventory += summary.get("active_inventory_units") or 0
        revenue += float(summary.get("total_revenue") or 0)
    if not found:
        return None
    return f"BloomBoss: {units} units on record, {sold} sold (${revenue:,.2f} revenue), {inventory} still in inventory."


def build_morning_brief(
    *,
    local_now: datetime,
    status: dict | None = None,
    bloomboss: dict | None = None,
    open_tasks: int | None = None,
    facts: tuple[tuple[int, str], ...] = (),
) -> str:
    lines = [_greeting(local_now)]
    for line in (_lab_line(status), _bloomboss_line(bloomboss)):
        if line:
            lines.append(line)
    if open_tasks:
        lines.append(f"KARMO tasks: {open_tasks} open.")
    if facts:
        recent = [fact for _id, fact in facts[-MAX_BRIEF_FACTS:]]
        lines.append("You asked me to remember: " + "; ".join(recent) + ".")
    return "\n".join(lines)

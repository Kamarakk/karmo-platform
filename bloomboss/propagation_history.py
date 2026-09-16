from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .models import (
    PlantOrigin,
    PlantStatus,
    PlantUnit,
    PropagationEvent,
    PropagationMethod,
    Provenance,
)


def _blank_to_none(value: str | None):
    if value is None:
        return None
    value = value.strip()
    return value if value else None


def _parse_date(value: str | None):
    value = _blank_to_none(value)
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"invalid ISO date: {value}") from exc


def _parse_decimal(value: str | None):
    value = _blank_to_none(value)
    if value is None:
        return None
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"invalid decimal: {value}") from exc
    if parsed < 0:
        raise ValueError(f"negative money value is not allowed: {value}")
    return parsed


def load_propagation_history_csv(
    path: str | Path,
) -> tuple[list[PropagationEvent], list[PlantUnit]]:
    """Load plant-agnostic propagation evidence and child inventory units.

    This stream intentionally does not create purchase batches. A propagated child
    receives its own canonical PlantUnit identity with batch_id=None. Unknown dates,
    cost allocation, and notes remain unknown rather than being inferred.
    """
    path = Path(path)
    events: list[PropagationEvent] = []
    children: list[PlantUnit] = []
    seen_event_ids: set[str] = set()
    seen_child_ids: set[str] = set()

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {
            "propagation_id",
            "parent_unit_id",
            "child_unit_id",
            "cultivar",
            "method",
        }
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"missing required columns: {sorted(missing)}")

        for rownum, row in enumerate(reader, start=2):
            try:
                propagation_id = (row.get("propagation_id") or "").strip()
                parent_unit_id = (row.get("parent_unit_id") or "").strip()
                child_unit_id = (row.get("child_unit_id") or "").strip()
                cultivar = (row.get("cultivar") or "").strip()
                method_raw = (row.get("method") or "").strip().lower()

                if not propagation_id or not parent_unit_id or not child_unit_id or not cultivar or not method_raw:
                    raise ValueError(
                        "propagation_id, parent_unit_id, child_unit_id, cultivar, and method are required"
                    )
                if propagation_id in seen_event_ids:
                    raise ValueError(f"duplicate propagation_id {propagation_id!r}")
                if child_unit_id in seen_child_ids:
                    raise ValueError(f"duplicate child_unit_id {child_unit_id!r}")

                try:
                    method = PropagationMethod(method_raw)
                except ValueError as exc:
                    raise ValueError(f"unsupported propagation method {method_raw!r}") from exc

                status_raw = (row.get("status") or "unknown").strip().lower() or "unknown"
                try:
                    status = PlantStatus(status_raw)
                except ValueError as exc:
                    raise ValueError(f"unsupported status {status_raw!r}") from exc

                source = Provenance("csv", f"{path.name}:row:{rownum}")
                event_date = _parse_date(row.get("propagation_date"))
                acquired_date = _parse_date(row.get("acquired_date"))

                events.append(
                    PropagationEvent(
                        propagation_id=propagation_id,
                        parent_unit_id=parent_unit_id,
                        child_unit_id=child_unit_id,
                        method=method,
                        event_date=event_date,
                        notes=_blank_to_none(row.get("notes")),
                        provenance=(source,),
                    )
                )
                children.append(
                    PlantUnit(
                        unit_id=child_unit_id,
                        batch_id=None,
                        cultivar=cultivar,
                        status=status,
                        allocated_landed_cost=_parse_decimal(row.get("allocated_landed_cost")),
                        acquired_date=acquired_date,
                        provenance=(source,),
                        origin_type=PlantOrigin.PROPAGATED,
                    )
                )
                seen_event_ids.add(propagation_id)
                seen_child_ids.add(child_unit_id)
            except ValueError as exc:
                message = str(exc)
                if message.startswith("row "):
                    raise
                raise ValueError(f"row {rownum}: {message}") from exc

    return events, children

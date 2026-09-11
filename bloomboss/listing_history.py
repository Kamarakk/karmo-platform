from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .models import ListingHistoryEvent, Provenance


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


def load_listing_history_csv(path: str | Path) -> list[ListingHistoryEvent]:
    """Load optional historical listing evidence without touching sale facts.

    One inventory unit may have multiple listing events. Unknown asking prices or
    dates remain None. The source row is retained as provenance and row-specific
    failures make historical cleanup actionable for a human operator.
    """
    path = Path(path)
    events: list[ListingHistoryEvent] = []
    seen_listing_ids: set[str] = set()

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"listing_id", "unit_id", "channel"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"missing required columns: {sorted(missing)}")

        for rownum, row in enumerate(reader, start=2):
            try:
                listing_id = (row.get("listing_id") or "").strip()
                unit_id = (row.get("unit_id") or "").strip()
                channel = (row.get("channel") or "").strip()
                if not listing_id or not unit_id or not channel:
                    raise ValueError("listing_id, unit_id, and channel are required")
                if listing_id in seen_listing_ids:
                    raise ValueError(f"duplicate listing_id {listing_id!r}")

                listed_date = _parse_date(row.get("listed_date"))
                unlisted_date = _parse_date(row.get("unlisted_date"))
                if listed_date and unlisted_date and unlisted_date < listed_date:
                    raise ValueError("unlisted_date cannot be before listed_date")

                source = Provenance("csv", f"{path.name}:row:{rownum}")
                events.append(
                    ListingHistoryEvent(
                        listing_id=listing_id,
                        unit_id=unit_id,
                        channel=channel,
                        listed_date=listed_date,
                        unlisted_date=unlisted_date,
                        asking_price=_parse_decimal(row.get("asking_price")),
                        provenance=(source,),
                    )
                )
                seen_listing_ids.add(listing_id)
            except ValueError as exc:
                message = str(exc)
                if message.startswith("row "):
                    raise
                raise ValueError(f"row {rownum}: {message}") from exc

    return events

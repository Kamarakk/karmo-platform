from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .models import PlantStatus, PlantUnit, Provenance, PurchaseBatch, Sale


def _blank_to_none(value: str | None):
    if value is None:
        return None
    value = value.strip()
    return value if value else None


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


def _parse_int(value: str | None):
    value = _blank_to_none(value)
    if value is None:
        return None
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"invalid integer: {value}") from exc
    if parsed < 0:
        raise ValueError(f"negative integer value is not allowed: {value}")
    return parsed


def _parse_date(value: str | None):
    value = _blank_to_none(value)
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"invalid ISO date: {value}") from exc


def _batch_signature(row: dict[str, str]) -> tuple:
    return (
        row["cultivar"].strip(),
        _blank_to_none(row.get("supplier")),
        _parse_date(row.get("purchase_date")),
        _parse_int(row.get("batch_quantity")),
        _parse_decimal(row.get("batch_item_cost_total")),
        _parse_decimal(row.get("batch_shipping_total")),
        _parse_decimal(row.get("batch_duties_fees_total")),
    )


def _row_error(rownum: int, exc: ValueError) -> ValueError:
    message = str(exc)
    if message.startswith("row "):
        return exc
    return ValueError(f"row {rownum}: {message}")


def load_history_csv(path: str | Path) -> tuple[list[PurchaseBatch], list[PlantUnit], list[Sale]]:
    """Load BloomBoss history from a canonical CSV.

    Blank cells remain unknown. The loader never substitutes zero for missing money.
    Duplicate IDs and conflicting repeated batch facts fail visibly instead of being
    silently overwritten. Parsing failures include the source row number so a human
    can correct the historical worksheet without guessing where the problem lives.
    """
    path = Path(path)
    batches: dict[str, PurchaseBatch] = {}
    batch_signatures: dict[str, tuple] = {}
    units: list[PlantUnit] = []
    sales: list[Sale] = []
    seen_unit_ids: set[str] = set()
    seen_sale_ids: set[str] = set()

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"batch_id", "unit_id", "cultivar", "status"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"missing required columns: {sorted(missing)}")

        for rownum, row in enumerate(reader, start=2):
            try:
                source = Provenance("csv", f"{path.name}:row:{rownum}")
                batch_id = row["batch_id"].strip()
                unit_id = row["unit_id"].strip()
                cultivar = row["cultivar"].strip()
                if not batch_id or not unit_id or not cultivar:
                    raise ValueError("batch_id, unit_id, and cultivar are required")
                if unit_id in seen_unit_ids:
                    raise ValueError(f"duplicate unit_id {unit_id!r}")
                seen_unit_ids.add(unit_id)

                signature = _batch_signature(row)
                if batch_id in batch_signatures and batch_signatures[batch_id] != signature:
                    raise ValueError(f"conflicting repeated facts for batch_id {batch_id!r}")
                batch_signatures.setdefault(batch_id, signature)

                if batch_id not in batches:
                    batches[batch_id] = PurchaseBatch(
                        batch_id=batch_id,
                        cultivar=cultivar,
                        supplier=_blank_to_none(row.get("supplier")),
                        purchase_date=_parse_date(row.get("purchase_date")),
                        quantity=_parse_int(row.get("batch_quantity")),
                        item_cost_total=_parse_decimal(row.get("batch_item_cost_total")),
                        shipping_cost_total=_parse_decimal(row.get("batch_shipping_total")),
                        duties_fees_total=_parse_decimal(row.get("batch_duties_fees_total")),
                        provenance=(source,),
                    )

                status_raw = (row.get("status") or "unknown").strip().lower()
                try:
                    status = PlantStatus(status_raw)
                except ValueError as exc:
                    raise ValueError(f"unsupported status {status_raw!r}") from exc

                units.append(
                    PlantUnit(
                        unit_id=unit_id,
                        batch_id=batch_id,
                        cultivar=cultivar,
                        status=status,
                        allocated_landed_cost=_parse_decimal(row.get("allocated_landed_cost")),
                        acquired_date=_parse_date(row.get("acquired_date") or row.get("purchase_date")),
                        provenance=(source,),
                    )
                )

                sale_price = _parse_decimal(row.get("sale_price"))
                if sale_price is not None:
                    channel = _blank_to_none(row.get("sale_channel"))
                    if not channel:
                        raise ValueError("sale_channel required when sale_price is present")
                    sale_id = _blank_to_none(row.get("sale_id")) or f"sale:{unit_id}"
                    if sale_id in seen_sale_ids:
                        raise ValueError(f"duplicate sale_id {sale_id!r}")
                    seen_sale_ids.add(sale_id)
                    sales.append(
                        Sale(
                            sale_id=sale_id,
                            unit_id=unit_id,
                            channel=channel,
                            sale_price=sale_price,
                            sale_date=_parse_date(row.get("sale_date")),
                            selling_fees=_parse_decimal(row.get("selling_fees")),
                            shipping_cost=_parse_decimal(row.get("outbound_shipping_cost")),
                            provenance=(source,),
                        )
                    )
            except ValueError as exc:
                raise _row_error(rownum, exc) from exc

    return list(batches.values()), units, sales

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
        return Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"invalid decimal: {value}") from exc


def _parse_int(value: str | None):
    value = _blank_to_none(value)
    return int(value) if value is not None else None


def _parse_date(value: str | None):
    value = _blank_to_none(value)
    return date.fromisoformat(value) if value is not None else None


def load_history_csv(path: str | Path) -> tuple[list[PurchaseBatch], list[PlantUnit], list[Sale]]:
    """Load BloomBoss history from a canonical CSV.

    Blank cells remain unknown. The loader never substitutes zero for missing money.
    """
    path = Path(path)
    batches: dict[str, PurchaseBatch] = {}
    units: list[PlantUnit] = []
    sales: list[Sale] = []

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"batch_id", "unit_id", "cultivar", "status"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"missing required columns: {sorted(missing)}")

        for rownum, row in enumerate(reader, start=2):
            source = Provenance("csv", f"{path.name}:row:{rownum}")
            batch_id = row["batch_id"].strip()
            unit_id = row["unit_id"].strip()
            cultivar = row["cultivar"].strip()
            if not batch_id or not unit_id or not cultivar:
                raise ValueError(f"row {rownum}: batch_id, unit_id, and cultivar are required")

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
                raise ValueError(f"row {rownum}: unsupported status {status_raw!r}") from exc

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
                    raise ValueError(f"row {rownum}: sale_channel required when sale_price is present")
                sales.append(
                    Sale(
                        sale_id=_blank_to_none(row.get("sale_id")) or f"sale:{unit_id}",
                        unit_id=unit_id,
                        channel=channel,
                        sale_price=sale_price,
                        sale_date=_parse_date(row.get("sale_date")),
                        selling_fees=_parse_decimal(row.get("selling_fees")),
                        shipping_cost=_parse_decimal(row.get("outbound_shipping_cost")),
                        provenance=(source,),
                    )
                )

    return list(batches.values()), units, sales

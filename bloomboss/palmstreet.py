from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Optional

from .models import Provenance


@dataclass(frozen=True)
class PalmstreetFieldMap:
    """Explicit mapping from a real Palmstreet export into BloomBoss staging fields.

    We intentionally do not guess Palmstreet column names. Once a real export is
    supplied, its headers can be mapped here and then kept as the verified profile.
    """

    order_id: str
    line_item_id: Optional[str] = None
    item_title: Optional[str] = None
    quantity: Optional[str] = None
    sale_price: Optional[str] = None
    order_date: Optional[str] = None
    selling_fees: Optional[str] = None
    shipping_cost: Optional[str] = None


@dataclass(frozen=True)
class PalmstreetSaleCandidate:
    """Read-only staged Palmstreet sale facts before inventory-unit reconciliation."""

    external_order_id: str
    external_line_item_id: Optional[str]
    item_title: Optional[str]
    quantity: Optional[int]
    sale_price: Optional[Decimal]
    sale_date: Optional[date]
    selling_fees: Optional[Decimal]
    shipping_cost: Optional[Decimal]
    provenance: Provenance


@dataclass(frozen=True)
class PalmstreetExportProfile:
    source_name: str
    source_sha256: str
    source_size_bytes: int
    headers: tuple[str, ...]
    row_count: int


def _blank_to_none(value: str | None) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    return value if value else None


def _source_sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_money(value: str | None) -> Optional[Decimal]:
    value = _blank_to_none(value)
    if value is None:
        return None
    cleaned = value.replace("$", "").replace(",", "").strip()
    try:
        parsed = Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValueError(f"invalid money value: {value!r}") from exc
    if parsed < 0:
        raise ValueError(f"negative money value is not allowed: {value!r}")
    return parsed


def _parse_quantity(value: str | None) -> Optional[int]:
    value = _blank_to_none(value)
    if value is None:
        return None
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"invalid quantity: {value!r}") from exc
    if parsed < 0:
        raise ValueError(f"negative quantity is not allowed: {value!r}")
    return parsed


def _parse_date(value: str | None) -> Optional[date]:
    value = _blank_to_none(value)
    if value is None:
        return None

    # Keep parsing bounded and explicit. These formats cover ISO exports and
    # common US CSV exports without locale inference.
    candidates = (
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%m/%d/%Y %H:%M",
        "%m/%d/%Y %I:%M %p",
    )
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    for fmt in candidates:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"unsupported date format: {value!r}")


def inspect_palmstreet_export(path: str | Path) -> PalmstreetExportProfile:
    """Profile a Palmstreet CSV without guessing business semantics or logging rows."""
    path = Path(path)
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        headers = tuple(reader.fieldnames or ())
        row_count = sum(1 for _ in reader)

    if not headers:
        raise ValueError("Palmstreet export has no CSV headers")

    return PalmstreetExportProfile(
        source_name=path.name,
        source_sha256=_source_sha256(path),
        source_size_bytes=path.stat().st_size,
        headers=headers,
        row_count=row_count,
    )


def _require_header(headers: set[str], field_name: str, column: Optional[str]) -> None:
    if column is not None and column not in headers:
        raise ValueError(f"mapped {field_name} column {column!r} is not present in export")


def load_palmstreet_sales_export(
    path: str | Path,
    field_map: PalmstreetFieldMap,
) -> tuple[PalmstreetExportProfile, list[PalmstreetSaleCandidate]]:
    """Load official Palmstreet seller-export rows into read-only sale candidates.

    This does not create BloomBoss Sale records because a platform line item must
    first be reconciled to a canonical BloomBoss inventory unit. Unknown fields stay
    unknown. Raw source identity and row provenance are preserved.
    """
    path = Path(path)
    profile = inspect_palmstreet_export(path)
    headers = set(profile.headers)

    for field_name, column in (
        ("order_id", field_map.order_id),
        ("line_item_id", field_map.line_item_id),
        ("item_title", field_map.item_title),
        ("quantity", field_map.quantity),
        ("sale_price", field_map.sale_price),
        ("order_date", field_map.order_date),
        ("selling_fees", field_map.selling_fees),
        ("shipping_cost", field_map.shipping_cost),
    ):
        _require_header(headers, field_name, column)

    rows: list[PalmstreetSaleCandidate] = []
    seen_keys: set[tuple[str, Optional[str]]] = set()

    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for rownum, row in enumerate(reader, start=2):
            try:
                order_id = _blank_to_none(row.get(field_map.order_id))
                if not order_id:
                    raise ValueError("mapped order_id is blank")
                line_item_id = (
                    _blank_to_none(row.get(field_map.line_item_id))
                    if field_map.line_item_id
                    else None
                )
                identity = (order_id, line_item_id)
                if identity in seen_keys:
                    raise ValueError(
                        f"duplicate external order/line identity {identity!r}"
                    )
                seen_keys.add(identity)

                source = Provenance(
                    source_type="palmstreet_csv",
                    source_ref=f"{path.name}:row:{rownum}",
                    confidence="reported",
                )
                rows.append(
                    PalmstreetSaleCandidate(
                        external_order_id=order_id,
                        external_line_item_id=line_item_id,
                        item_title=(
                            _blank_to_none(row.get(field_map.item_title))
                            if field_map.item_title
                            else None
                        ),
                        quantity=(
                            _parse_quantity(row.get(field_map.quantity))
                            if field_map.quantity
                            else None
                        ),
                        sale_price=(
                            _parse_money(row.get(field_map.sale_price))
                            if field_map.sale_price
                            else None
                        ),
                        sale_date=(
                            _parse_date(row.get(field_map.order_date))
                            if field_map.order_date
                            else None
                        ),
                        selling_fees=(
                            _parse_money(row.get(field_map.selling_fees))
                            if field_map.selling_fees
                            else None
                        ),
                        shipping_cost=(
                            _parse_money(row.get(field_map.shipping_cost))
                            if field_map.shipping_cost
                            else None
                        ),
                        provenance=source,
                    )
                )
            except ValueError as exc:
                raise ValueError(f"row {rownum}: {exc}") from exc

    return profile, rows

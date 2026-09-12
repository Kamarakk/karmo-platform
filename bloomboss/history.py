from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from .analytics import summarize_batches, summarize_business, summarize_suppliers
from .data_quality import summarize_history_quality, summarize_listing_quality
from .ingest import load_history_csv
from .inventory import summarize_inventory_exposure
from .listing_analytics import summarize_listing_activity
from .listing_history import load_listing_history_csv
from .models import ListingHistoryEvent, PlantUnit, PropagationEvent, PurchaseBatch, Sale
from .outcomes import summarize_channels, summarize_cultivars, summarize_units
from .propagation_history import load_propagation_history_csv
from .validation import (
    ValidationIssue,
    validate_history_relationships,
    validate_listing_relationships,
    validate_propagation_relationships,
)


@dataclass(frozen=True)
class HistoricalImportSnapshot:
    """Reproducible read-only view of historical BloomBoss source evidence."""

    source_name: str
    source_sha256: str
    source_size_bytes: int
    batches: tuple[PurchaseBatch, ...]
    units: tuple[PlantUnit, ...]
    sales: tuple[Sale, ...]
    relationship_issues: tuple[ValidationIssue, ...]
    business_summary: dict
    supplier_summary: dict
    batch_summary: dict
    unit_outcome_summary: dict
    cultivar_summary: dict
    channel_summary: dict
    inventory_exposure_summary: dict
    quality_summary: dict
    listings: tuple[ListingHistoryEvent, ...] = ()
    listing_source_name: str | None = None
    listing_source_sha256: str | None = None
    listing_source_size_bytes: int | None = None
    listing_relationship_issues: tuple[ValidationIssue, ...] = ()
    listing_quality_summary: dict | None = None
    listing_activity_summary: dict | None = None
    propagations: tuple[PropagationEvent, ...] = ()
    propagation_source_name: str | None = None
    propagation_source_sha256: str | None = None
    propagation_source_size_bytes: int | None = None
    propagation_relationship_issues: tuple[ValidationIssue, ...] = ()


def source_sha256(path: str | Path, *, chunk_size: int = 1024 * 1024) -> str:
    """Hash a source file without loading the full file into memory."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_history_csv(
    path: str | Path,
    *,
    listing_path: str | Path | None = None,
    propagation_path: str | Path | None = None,
) -> HistoricalImportSnapshot:
    """Load, validate, and summarize canonical history plus optional evidence streams."""
    path = Path(path)
    batches, purchased_units, sales = load_history_csv(path)

    propagations: list[PropagationEvent] = []
    propagated_units: list[PlantUnit] = []
    propagation_name = None
    propagation_hash = None
    propagation_size = None
    propagation_issues: list[ValidationIssue] = []
    if propagation_path is not None:
        propagation_path = Path(propagation_path)
        propagations, propagated_units = load_propagation_history_csv(propagation_path)
        purchased_unit_ids = {unit.unit_id for unit in purchased_units}
        collisions = sorted(purchased_unit_ids & {unit.unit_id for unit in propagated_units})
        if collisions:
            raise ValueError(
                "propagation child unit_id conflicts with canonical history: "
                + ", ".join(repr(unit_id) for unit_id in collisions)
            )
        propagation_name = propagation_path.name
        propagation_hash = source_sha256(propagation_path)
        propagation_size = propagation_path.stat().st_size

    units = [*purchased_units, *propagated_units]
    issues = validate_history_relationships(batches, units, sales)
    if propagation_path is not None:
        propagation_issues = validate_propagation_relationships(propagations, units)

    listings: list[ListingHistoryEvent] = []
    listing_name = None
    listing_hash = None
    listing_size = None
    listing_issues: list[ValidationIssue] = []
    if listing_path is not None:
        listing_path = Path(listing_path)
        listings = load_listing_history_csv(listing_path)
        listing_name = listing_path.name
        listing_hash = source_sha256(listing_path)
        listing_size = listing_path.stat().st_size
        listing_issues = validate_listing_relationships(listings, units, sales)

    return HistoricalImportSnapshot(
        source_name=path.name,
        source_sha256=source_sha256(path),
        source_size_bytes=path.stat().st_size,
        batches=tuple(batches),
        units=tuple(units),
        sales=tuple(sales),
        relationship_issues=tuple(issues),
        business_summary=summarize_business(units, sales),
        supplier_summary=summarize_suppliers(batches, units, sales),
        batch_summary=summarize_batches(batches, units, sales),
        unit_outcome_summary=summarize_units(units, sales),
        cultivar_summary=summarize_cultivars(units, sales),
        channel_summary=summarize_channels(units, sales),
        inventory_exposure_summary=summarize_inventory_exposure(units, sales),
        quality_summary=summarize_history_quality(batches, units, sales),
        listings=tuple(listings),
        listing_source_name=listing_name,
        listing_source_sha256=listing_hash,
        listing_source_size_bytes=listing_size,
        listing_relationship_issues=tuple(listing_issues),
        listing_quality_summary=summarize_listing_quality(listings) if listing_path is not None else None,
        listing_activity_summary=summarize_listing_activity(listings) if listing_path is not None else None,
        propagations=tuple(propagations),
        propagation_source_name=propagation_name,
        propagation_source_sha256=propagation_hash,
        propagation_source_size_bytes=propagation_size,
        propagation_relationship_issues=tuple(propagation_issues),
    )

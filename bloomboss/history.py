from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from .analytics import summarize_batches, summarize_business, summarize_suppliers
from .data_quality import summarize_history_quality
from .ingest import load_history_csv
from .models import PlantUnit, PurchaseBatch, Sale
from .outcomes import summarize_channels, summarize_cultivars
from .validation import ValidationIssue, validate_history_relationships


@dataclass(frozen=True)
class HistoricalImportSnapshot:
    """Reproducible read-only view of one historical source file.

    The SHA-256 identifies the exact raw evidence used to build the canonical
    in-memory records. Nothing here mutates or rewrites the source file.
    """

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
    cultivar_summary: dict
    channel_summary: dict
    quality_summary: dict


def source_sha256(path: str | Path, *, chunk_size: int = 1024 * 1024) -> str:
    """Hash a source file without loading the full file into memory."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_history_csv(path: str | Path) -> HistoricalImportSnapshot:
    """Load, validate, and summarize one canonical BloomBoss history CSV."""
    path = Path(path)
    batches, units, sales = load_history_csv(path)
    issues = validate_history_relationships(batches, units, sales)

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
        cultivar_summary=summarize_cultivars(units, sales),
        channel_summary=summarize_channels(units, sales),
        quality_summary=summarize_history_quality(batches, units, sales),
    )

from decimal import Decimal

import pytest

from bloomboss.history import inspect_history_csv, source_sha256


def test_history_snapshot_fingerprints_exact_source_and_reports_quality(tmp_path):
    path = tmp_path / "history.csv"
    path.write_text(
        "batch_id,unit_id,cultivar,status,supplier,allocated_landed_cost,sale_price,sale_channel\n"
        "B1,U1,Pink Plumbea,sold,Supplier A,80,185,Palmstreet\n"
        "B1,U2,Pink Plumbea,growing,Supplier A,,,\n",
        encoding="utf-8",
    )

    snapshot = inspect_history_csv(path)

    assert snapshot.source_name == "history.csv"
    assert snapshot.source_sha256 == source_sha256(path)
    assert snapshot.source_size_bytes == path.stat().st_size
    assert len(snapshot.batches) == 1
    assert len(snapshot.units) == 2
    assert len(snapshot.sales) == 1
    assert snapshot.relationship_issues == ()
    assert snapshot.business_summary["total_revenue"] == Decimal("185")
    assert snapshot.supplier_summary["Supplier A"]["sold"] == 1
    assert snapshot.quality_summary["coverage"]["unit_allocated_landed_cost"] == Decimal("0.5")


def test_source_fingerprint_changes_when_raw_evidence_changes(tmp_path):
    path = tmp_path / "history.csv"
    path.write_text("batch_id,unit_id,cultivar,status\nB1,U1,Cuprea,growing\n", encoding="utf-8")
    first = source_sha256(path)

    path.write_text("batch_id,unit_id,cultivar,status\nB1,U1,Cuprea,ready\n", encoding="utf-8")
    second = source_sha256(path)

    assert first != second


def test_source_fingerprint_rejects_invalid_chunk_size(tmp_path):
    path = tmp_path / "history.csv"
    path.write_text("x", encoding="utf-8")

    with pytest.raises(ValueError, match="chunk_size must be positive"):
        source_sha256(path, chunk_size=0)

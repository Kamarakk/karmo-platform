"""Tests for the BloomBoss chat capability -- Phase 2 of
docs/architecture/KARMO_CHAT_TOOL_CALLING_AND_EXTERNAL_DELEGATION.md.

The handler wraps bloomboss.history.inspect_history_csv +
bloomboss.report.snapshot_report, both already-existing and already
tested by bloomboss's own suite -- these tests cover the capability
boundary (manifest correctness, failure handling, real-data proof), not
the report math itself.
"""

from __future__ import annotations

import json

import pytest

from core_service import bloomboss_capability
from core_service.bloomboss_capability import BloomBossCapabilityError, handler, manifest
from core_service.control import ApprovalRequirement, CapabilityClass
from core_service.operator import _CHAT_EXPOSED_TOOLS, KarmoOperator

_REAL_DATA_DIR = bloomboss_capability._HISTORICAL_DATA_DIR

_CSV_HEADER = (
    "batch_id,unit_id,cultivar,status,supplier,purchase_date,batch_quantity,"
    "batch_item_cost_total,batch_shipping_total,batch_duties_fees_total,"
    "allocated_landed_cost,acquired_date,sale_id,sale_price,sale_channel,"
    "sale_date,selling_fees,outbound_shipping_cost,external_order_id,"
    "external_line_item_id\n"
)
_VALID_ROW = (
    "BATCH-T-01,BATCH-T-01-U01,Test Cultivar,sold,TestSupplier,2026-01-01,1,"
    "100,,,100,,SALE-T-01,150,Unknown,,,,,\n"
)


def test_manifest_is_read_class_with_none_approval():
    assert manifest()["capability_class"] == CapabilityClass.READ.value


def test_capability_is_wired_into_the_exposed_tool_list_as_read_only():
    entry = _CHAT_EXPOSED_TOOLS["bloomboss_report"]
    operator = KarmoOperator(model_client=object(), task_store=None)
    record = operator.registry.get(entry["tool_id"], entry["version"])
    assert record is not None
    assert record.computed_approval_requirement == ApprovalRequirement.NONE


def test_refuses_cleanly_when_no_data_directory_exists(tmp_path, monkeypatch):
    monkeypatch.setattr(bloomboss_capability, "_HISTORICAL_DATA_DIR", tmp_path / "does-not-exist")

    with pytest.raises(BloomBossCapabilityError, match="no BloomBoss historical data directory"):
        handler({})


def test_refuses_cleanly_when_directory_has_no_csv_files(tmp_path, monkeypatch):
    monkeypatch.setattr(bloomboss_capability, "_HISTORICAL_DATA_DIR", tmp_path)

    with pytest.raises(BloomBossCapabilityError, match="no BloomBoss historical data CSV"):
        handler({})


def test_one_corrupted_file_does_not_block_a_valid_one(tmp_path, monkeypatch):
    monkeypatch.setattr(bloomboss_capability, "_HISTORICAL_DATA_DIR", tmp_path)
    (tmp_path / "good.csv").write_text(_CSV_HEADER + _VALID_ROW)
    (tmp_path / "bad.csv").write_text("not,a,valid,bloomboss,csv\n1,2,3,4,5\n")

    result = handler({})

    assert result["files_loaded"] == ["good.csv"]
    assert len(result["errors"]) == 1
    assert result["errors"][0]["file"] == "bad.csv"
    assert len(result["reports"]) == 1


def test_all_files_failing_is_a_clean_refusal_not_a_crash(tmp_path, monkeypatch):
    monkeypatch.setattr(bloomboss_capability, "_HISTORICAL_DATA_DIR", tmp_path)
    (tmp_path / "bad.csv").write_text("not,a,valid,bloomboss,csv\n1,2,3,4,5\n")

    with pytest.raises(BloomBossCapabilityError, match="every BloomBoss data file failed"):
        handler({})


def test_coverage_note_is_present_so_the_model_never_implies_full_coverage(tmp_path, monkeypatch):
    monkeypatch.setattr(bloomboss_capability, "_HISTORICAL_DATA_DIR", tmp_path)
    (tmp_path / "good.csv").write_text(_CSV_HEADER + _VALID_ROW)

    result = handler({})

    assert "not necessarily the complete business history" in result["coverage_note"]


@pytest.mark.skipif(not _REAL_DATA_DIR.is_dir(), reason="real historical_data directory not present")
def test_real_committed_emgarden_data_produces_a_correct_report():
    """Proof against the actual repo data, not a synthetic fixture -- the
    same file the Phase 1 BloomBoss spot-check already hand-verified."""
    result = handler({})

    assert "emgarden_invoice_2026040040.csv" in result["files_loaded"]
    assert not result["errors"]
    report = result["reports"][0]
    assert report["record_counts"]["units"] == 75

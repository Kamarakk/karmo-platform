import json

from bloomboss.report import main, render_history_report


def _write_history(tmp_path):
    path = tmp_path / "history.csv"
    path.write_text(
        "batch_id,unit_id,cultivar,status,supplier,purchase_date,batch_quantity,batch_item_cost_total,batch_shipping_total,batch_duties_fees_total,allocated_landed_cost,acquired_date,sale_id,sale_channel,sale_price,sale_date,selling_fees,outbound_shipping_cost\n"
        "B1,U1,Pink Cuprea,sold,Supplier A,2026-01-10,1,100,20,,120,2026-01-10,S1,Palmstreet,250,2026-02-10,25,15\n",
        encoding="utf-8",
    )
    return path


def test_render_history_report_is_json_and_preserves_decimal_precision(tmp_path):
    path = _write_history(tmp_path)
    payload = json.loads(render_history_report(path))
    assert payload["source"]["name"] == "history.csv"
    assert len(payload["source"]["sha256"]) == 64
    assert payload["record_counts"] == {
        "batches": 1, "units": 1, "sales": 1, "relationship_issues": 0,
        "listings": 0, "listing_relationship_issues": 0,
    }
    assert payload["business_summary"]["total_revenue"] == "250"
    assert payload["business_summary"]["known_landed_cost"] == "120"
    assert "listing_source" not in payload


def test_report_can_fingerprint_and_validate_separate_listing_evidence(tmp_path):
    history = _write_history(tmp_path)
    listings = tmp_path / "listings.csv"
    listings.write_text(
        "listing_id,unit_id,channel,listed_date,unlisted_date,asking_price\n"
        "L1,U1,Palmstreet,2026-01-20,2026-02-10,275\n",
        encoding="utf-8",
    )
    payload = json.loads(render_history_report(history, listing_path=listings))
    assert payload["record_counts"]["listings"] == 1
    assert payload["record_counts"]["listing_relationship_issues"] == 0
    assert payload["listing_source"]["name"] == "listings.csv"
    assert len(payload["listing_source"]["sha256"]) == 64
    assert payload["listing_quality_summary"]["coverage"]["asking_price"] == "1"


def test_cli_prints_report_without_modifying_sources(tmp_path, capsys):
    history = _write_history(tmp_path)
    listings = tmp_path / "listings.csv"
    listings.write_text(
        "listing_id,unit_id,channel,listed_date,unlisted_date,asking_price\n"
        "L1,U1,Palmstreet,2026-01-20,,275\n",
        encoding="utf-8",
    )
    before_history = history.read_bytes()
    before_listings = listings.read_bytes()
    assert main([str(history), "--listings", str(listings)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["record_counts"]["units"] == 1
    assert payload["record_counts"]["listings"] == 1
    assert history.read_bytes() == before_history
    assert listings.read_bytes() == before_listings

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
        "batches": 1,
        "units": 1,
        "sales": 1,
        "relationship_issues": 0,
    }
    assert payload["business_summary"]["revenue"] == "250"
    assert payload["business_summary"]["known_landed_cost"] == "120"


def test_cli_prints_report_without_modifying_source(tmp_path, capsys):
    path = _write_history(tmp_path)
    before = path.read_bytes()

    assert main([str(path)]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["record_counts"]["units"] == 1
    assert path.read_bytes() == before

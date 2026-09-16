from bloomboss.ingest import load_history_csv


def test_platform_order_identity_is_preserved_without_replacing_canonical_ids(tmp_path):
    path = tmp_path / "history.csv"
    path.write_text(
        "batch_id,unit_id,cultivar,status,sale_price,sale_channel,external_order_id,external_line_item_id\n"
        "B1,U1,Monstera Light Lime,sold,325,Palmstreet,PS-ORDER-1001,PS-LINE-1\n",
        encoding="utf-8",
    )

    _, units, sales = load_history_csv(path)

    assert units[0].unit_id == "U1"
    assert sales[0].sale_id == "sale:U1"
    assert sales[0].external_order_id == "PS-ORDER-1001"
    assert sales[0].external_line_item_id == "PS-LINE-1"


def test_platform_order_identity_remains_optional(tmp_path):
    path = tmp_path / "history.csv"
    path.write_text(
        "batch_id,unit_id,cultivar,status,sale_price,sale_channel\n"
        "B1,U1,Anthurium Example,sold,150,Etsy\n",
        encoding="utf-8",
    )

    _, _, sales = load_history_csv(path)

    assert sales[0].external_order_id is None
    assert sales[0].external_line_item_id is None

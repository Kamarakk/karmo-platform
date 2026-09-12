from decimal import Decimal

import pytest

from bloomboss.palmstreet import (
    PalmstreetFieldMap,
    inspect_palmstreet_export,
    load_palmstreet_sales_export,
)


def test_profiles_palmstreet_export_without_guessing_fields(tmp_path):
    path = tmp_path / "palmstreet.csv"
    path.write_text(
        "Order ID,Item ID,Title,Price,Date\n"
        "P100,L1,Monstera,$125.00,2026-09-01\n",
        encoding="utf-8",
    )

    profile = inspect_palmstreet_export(path)

    assert profile.headers == ("Order ID", "Item ID", "Title", "Price", "Date")
    assert profile.row_count == 1
    assert profile.source_name == "palmstreet.csv"
    assert len(profile.source_sha256) == 64


def test_loads_palmstreet_rows_as_candidates_not_canonical_sales(tmp_path):
    path = tmp_path / "palmstreet.csv"
    path.write_text(
        "Order ID,Item ID,Title,Qty,Price,Date,Fees,Shipping\n"
        "P100,L1,Monstera Thai Con,2,$125.00,09/01/2026,$12.50,$8.00\n",
        encoding="utf-8",
    )
    mapping = PalmstreetFieldMap(
        order_id="Order ID",
        line_item_id="Item ID",
        item_title="Title",
        quantity="Qty",
        sale_price="Price",
        order_date="Date",
        selling_fees="Fees",
        shipping_cost="Shipping",
    )

    _, rows = load_palmstreet_sales_export(path, mapping)

    assert len(rows) == 1
    row = rows[0]
    assert row.external_order_id == "P100"
    assert row.external_line_item_id == "L1"
    assert row.item_title == "Monstera Thai Con"
    assert row.quantity == 2
    assert row.sale_price == Decimal("125.00")
    assert row.selling_fees == Decimal("12.50")
    assert row.shipping_cost == Decimal("8.00")
    assert row.provenance.source_type == "palmstreet_csv"


def test_unknown_optional_fields_remain_unknown(tmp_path):
    path = tmp_path / "palmstreet.csv"
    path.write_text("Order ID\nP100\n", encoding="utf-8")

    _, rows = load_palmstreet_sales_export(
        path,
        PalmstreetFieldMap(order_id="Order ID"),
    )

    row = rows[0]
    assert row.external_line_item_id is None
    assert row.item_title is None
    assert row.quantity is None
    assert row.sale_price is None
    assert row.sale_date is None


def test_bad_mapping_fails_visibly(tmp_path):
    path = tmp_path / "palmstreet.csv"
    path.write_text("Order ID\nP100\n", encoding="utf-8")

    with pytest.raises(ValueError, match="is not present in export"):
        load_palmstreet_sales_export(
            path,
            PalmstreetFieldMap(order_id="Missing Order Column"),
        )


def test_duplicate_external_identity_fails(tmp_path):
    path = tmp_path / "palmstreet.csv"
    path.write_text(
        "Order ID,Item ID\n"
        "P100,L1\n"
        "P100,L1\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate external order/line identity"):
        load_palmstreet_sales_export(
            path,
            PalmstreetFieldMap(order_id="Order ID", line_item_id="Item ID"),
        )

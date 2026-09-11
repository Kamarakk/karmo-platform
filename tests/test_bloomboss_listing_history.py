from decimal import Decimal

import pytest

from bloomboss.listing_history import load_listing_history_csv


def _write(tmp_path, body):
    path = tmp_path / "listings.csv"
    path.write_text(body, encoding="utf-8")
    return path


def test_listing_history_preserves_multiple_events_and_unknown_values(tmp_path):
    path = _write(
        tmp_path,
        "listing_id,unit_id,channel,listed_date,unlisted_date,asking_price\n"
        "L1,U1,Palmstreet,2026-01-01,2026-01-05,150\n"
        "L2,U1,Etsy,2026-01-06,,\n",
    )
    events = load_listing_history_csv(path)
    assert len(events) == 2
    assert events[0].asking_price == Decimal("150")
    assert events[1].asking_price is None
    assert events[1].unlisted_date is None
    assert events[0].provenance[0].source_ref == "listings.csv:row:2"


def test_listing_history_rejects_duplicate_ids_with_source_row(tmp_path):
    path = _write(
        tmp_path,
        "listing_id,unit_id,channel,listed_date,unlisted_date,asking_price\n"
        "L1,U1,Palmstreet,,,\n"
        "L1,U2,Etsy,,,\n",
    )
    with pytest.raises(ValueError, match="row 3: duplicate listing_id"):
        load_listing_history_csv(path)


def test_listing_history_rejects_impossible_date_order(tmp_path):
    path = _write(
        tmp_path,
        "listing_id,unit_id,channel,listed_date,unlisted_date,asking_price\n"
        "L1,U1,Palmstreet,2026-02-02,2026-02-01,125\n",
    )
    with pytest.raises(ValueError, match="row 2: unlisted_date cannot be before listed_date"):
        load_listing_history_csv(path)


def test_listing_history_rejects_negative_asking_price(tmp_path):
    path = _write(
        tmp_path,
        "listing_id,unit_id,channel,listed_date,unlisted_date,asking_price\n"
        "L1,U1,Palmstreet,,,-1\n",
    )
    with pytest.raises(ValueError, match="row 2: negative money value"):
        load_listing_history_csv(path)

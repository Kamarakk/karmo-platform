from datetime import date
from decimal import Decimal

import pytest

from bloomboss.listing_history import load_listing_history_csv
from bloomboss.models import ListingHistoryEvent, PlantStatus, PlantUnit, Sale
from bloomboss.validation import validate_listing_relationships


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


def test_listing_relationships_report_missing_unit_without_repair():
    listings = [ListingHistoryEvent("L1", "MISSING", "Palmstreet", listed_date=date(2026, 1, 2))]
    issues = validate_listing_relationships(listings, [], [])
    assert [(issue.code, issue.entity_id) for issue in issues] == [("LISTING_UNIT_MISSING", "L1")]


def test_listing_relationships_report_listing_before_acquisition():
    units = [
        PlantUnit(
            unit_id="U1",
            batch_id="B1",
            cultivar="Pink Cuprea",
            status=PlantStatus.LISTED,
            acquired_date=date(2026, 1, 10),
        )
    ]
    listings = [ListingHistoryEvent("L1", "U1", "Palmstreet", listed_date=date(2026, 1, 9))]
    issues = validate_listing_relationships(listings, units, [])
    assert [issue.code for issue in issues] == ["LISTING_BEFORE_ACQUISITION"]


def test_listing_relationships_report_listing_after_known_sale():
    units = [
        PlantUnit(
            unit_id="U1",
            batch_id="B1",
            cultivar="Pink Cuprea",
            status=PlantStatus.SOLD,
            acquired_date=date(2026, 1, 1),
        )
    ]
    sales = [Sale("S1", "U1", "Palmstreet", Decimal("200"), sale_date=date(2026, 1, 15))]
    listings = [ListingHistoryEvent("L1", "U1", "Etsy", listed_date=date(2026, 1, 16))]
    issues = validate_listing_relationships(listings, units, sales)
    assert [issue.code for issue in issues] == ["LISTING_AFTER_SALE"]


def test_listing_relationships_do_not_invent_unknown_date_conflicts():
    units = [PlantUnit("U1", "B1", "Pink Cuprea", status=PlantStatus.UNKNOWN)]
    listings = [ListingHistoryEvent("L1", "U1", "Palmstreet")]
    sales = [Sale("S1", "U1", "Palmstreet", Decimal("200"))]
    assert validate_listing_relationships(listings, units, sales) == []

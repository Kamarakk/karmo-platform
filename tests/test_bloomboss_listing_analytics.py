from datetime import date
from decimal import Decimal

from bloomboss.listing_analytics import summarize_listing_activity
from bloomboss.models import ListingHistoryEvent


def test_listing_activity_summarizes_known_listing_facts_without_sale_inference():
    listings = [
        ListingHistoryEvent(
            listing_id="L1",
            unit_id="U1",
            channel="Palmstreet",
            listed_date=date(2026, 1, 1),
            unlisted_date=date(2026, 1, 6),
            asking_price=Decimal("120"),
        ),
        ListingHistoryEvent(
            listing_id="L2",
            unit_id="U1",
            channel="Etsy",
            listed_date=date(2026, 1, 10),
            unlisted_date=None,
            asking_price=Decimal("140"),
        ),
        ListingHistoryEvent(
            listing_id="L3",
            unit_id="U2",
            channel="Palmstreet",
            listed_date=None,
            unlisted_date=None,
            asking_price=None,
        ),
    ]

    summary = summarize_listing_activity(listings)

    assert summary["listing_count"] == 3
    assert summary["unique_units_listed"] == 2
    assert summary["asking_price_known_count"] == 2
    assert summary["average_known_asking_price"] == Decimal("130")
    assert summary["completed_duration_count"] == 1
    assert summary["average_completed_listing_days"] == Decimal("5")

    assert summary["by_channel"]["Palmstreet"] == {
        "listing_count": 2,
        "unique_units_listed": 2,
        "asking_price_known_count": 1,
        "average_known_asking_price": Decimal("120"),
        "completed_duration_count": 1,
        "average_completed_listing_days": Decimal("5"),
    }
    assert summary["by_channel"]["Etsy"] == {
        "listing_count": 1,
        "unique_units_listed": 1,
        "asking_price_known_count": 1,
        "average_known_asking_price": Decimal("140"),
        "completed_duration_count": 0,
        "average_completed_listing_days": None,
    }


def test_listing_activity_empty_input_keeps_averages_unknown():
    summary = summarize_listing_activity([])

    assert summary == {
        "listing_count": 0,
        "unique_units_listed": 0,
        "asking_price_known_count": 0,
        "average_known_asking_price": None,
        "completed_duration_count": 0,
        "average_completed_listing_days": None,
        "by_channel": {},
    }

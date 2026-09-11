from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Iterable

from .models import ListingHistoryEvent


def _average_decimal(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    return sum(values, Decimal("0")) / Decimal(len(values))


def _average_days(values: list[int]) -> Decimal | None:
    if not values:
        return None
    return Decimal(sum(values)) / Decimal(len(values))


def summarize_listing_activity(listings: Iterable[ListingHistoryEvent]) -> dict:
    """Summarize historical listing evidence without inferring sale outcomes.

    The summary intentionally stays on facts contained in listing history:
    listing volume, unique inventory units exposed, known asking prices, and
    completed listing durations. It does not treat an unlisting as a sale or
    attempt to match listings to realized sale records.
    """
    listings = list(listings)
    asking_prices = [item.asking_price for item in listings if item.asking_price is not None]
    completed_durations = [
        (item.unlisted_date - item.listed_date).days
        for item in listings
        if item.listed_date is not None and item.unlisted_date is not None
    ]

    channel_groups: dict[str, list[ListingHistoryEvent]] = defaultdict(list)
    for item in listings:
        channel_groups[item.channel].append(item)

    by_channel: dict[str, dict] = {}
    for channel in sorted(channel_groups):
        events = channel_groups[channel]
        channel_prices = [item.asking_price for item in events if item.asking_price is not None]
        channel_durations = [
            (item.unlisted_date - item.listed_date).days
            for item in events
            if item.listed_date is not None and item.unlisted_date is not None
        ]
        by_channel[channel] = {
            "listing_count": len(events),
            "unique_units_listed": len({item.unit_id for item in events}),
            "asking_price_known_count": len(channel_prices),
            "average_known_asking_price": _average_decimal(channel_prices),
            "completed_duration_count": len(channel_durations),
            "average_completed_listing_days": _average_days(channel_durations),
        }

    return {
        "listing_count": len(listings),
        "unique_units_listed": len({item.unit_id for item in listings}),
        "asking_price_known_count": len(asking_prices),
        "average_known_asking_price": _average_decimal(asking_prices),
        "completed_duration_count": len(completed_durations),
        "average_completed_listing_days": _average_days(completed_durations),
        "by_channel": by_channel,
    }

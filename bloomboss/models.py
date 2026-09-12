from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional


class PlantStatus(str, Enum):
    GROWING = "growing"
    READY = "ready"
    LISTED = "listed"
    SOLD = "sold"
    LOST = "lost"
    RETAINED = "retained"
    GIVEAWAY = "giveaway"
    UNKNOWN = "unknown"


class PlantOrigin(str, Enum):
    PURCHASED = "purchased"
    PROPAGATED = "propagated"
    TISSUE_CULTURE = "tissue_culture"
    SEED_GROWN = "seed_grown"
    GIFTED = "gifted"
    OTHER = "other"
    UNKNOWN = "unknown"


class PropagationMethod(str, Enum):
    CORM = "corm"
    DIVISION = "division"
    CUTTING = "cutting"
    NODE = "node"
    OFFSET = "offset"
    SEED = "seed"
    TISSUE_CULTURE = "tissue_culture"
    OTHER = "other"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Provenance:
    source_type: str
    source_ref: str
    confidence: str = "reported"


@dataclass(frozen=True)
class PurchaseBatch:
    batch_id: str
    cultivar: str
    supplier: Optional[str] = None
    purchase_date: Optional[date] = None
    quantity: Optional[int] = None
    item_cost_total: Optional[Decimal] = None
    shipping_cost_total: Optional[Decimal] = None
    duties_fees_total: Optional[Decimal] = None
    provenance: tuple[Provenance, ...] = field(default_factory=tuple)

    @property
    def known_landed_cost_total(self) -> Optional[Decimal]:
        parts = (self.item_cost_total, self.shipping_cost_total, self.duties_fees_total)
        if any(v is None for v in parts):
            return None
        return sum(parts, Decimal("0"))


@dataclass(frozen=True)
class PlantUnit:
    unit_id: str
    batch_id: Optional[str]
    cultivar: str
    status: PlantStatus = PlantStatus.UNKNOWN
    allocated_landed_cost: Optional[Decimal] = None
    acquired_date: Optional[date] = None
    provenance: tuple[Provenance, ...] = field(default_factory=tuple)
    origin_type: PlantOrigin = PlantOrigin.UNKNOWN


@dataclass(frozen=True)
class PropagationEvent:
    """One known parent-to-child propagation relationship.

    The method is intentionally plant-agnostic so BloomBoss can represent
    corms, divisions, cuttings, nodes, offsets, seed-grown offspring, tissue
    culture, and future methods without changing the purchase/listing/sale model.
    Unknown dates and notes remain unknown rather than being inferred.
    """

    propagation_id: str
    parent_unit_id: str
    child_unit_id: str
    method: PropagationMethod
    event_date: Optional[date] = None
    notes: Optional[str] = None
    provenance: tuple[Provenance, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ListingHistoryEvent:
    """One historical listing period for a canonical inventory unit.

    Listing history is separate from sale history because asking price/channel
    evidence is not the same fact as a realized sale. Missing dates/prices stay
    unknown rather than being inferred from sale records.
    """

    listing_id: str
    unit_id: str
    channel: str
    listed_date: Optional[date] = None
    unlisted_date: Optional[date] = None
    asking_price: Optional[Decimal] = None
    provenance: tuple[Provenance, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Sale:
    sale_id: str
    unit_id: str
    channel: str
    sale_price: Decimal
    sale_date: Optional[date] = None
    selling_fees: Optional[Decimal] = None
    shipping_cost: Optional[Decimal] = None
    provenance: tuple[Provenance, ...] = field(default_factory=tuple)

    @property
    def known_net_revenue(self) -> Optional[Decimal]:
        if self.selling_fees is None or self.shipping_cost is None:
            return None
        return self.sale_price - self.selling_fees - self.shipping_cost


@dataclass(frozen=True)
class StatusEvent:
    event_id: str
    unit_id: str
    status: PlantStatus
    event_date: Optional[date] = None
    reason: Optional[str] = None
    provenance: tuple[Provenance, ...] = field(default_factory=tuple)

from datetime import date
from decimal import Decimal

from bloomboss.analytics import summarize_batches, summarize_suppliers
from bloomboss.models import PlantStatus, PlantUnit, PurchaseBatch, Sale


def test_supplier_return_includes_known_losses_without_imputing_unknown_costs():
    batches = [
        PurchaseBatch("B1", "Pink Plumbea", "Supplier A"),
        PurchaseBatch("B2", "Cuprea", None),
    ]
    units = [
        PlantUnit("U1", "B1", "Pink Plumbea", PlantStatus.SOLD, Decimal("80"), date(2026, 1, 1)),
        PlantUnit("U2", "B1", "Pink Plumbea", PlantStatus.LOST, Decimal("60"), date(2026, 1, 1)),
        PlantUnit("U3", "B2", "Cuprea", PlantStatus.SOLD, None, date(2026, 1, 1)),
    ]
    sales = [
        Sale("S1", "U1", "Palmstreet", Decimal("200"), date(2026, 1, 11)),
        Sale("S2", "U3", "Etsy", Decimal("150"), date(2026, 1, 6)),
    ]

    supplier = summarize_suppliers(batches, units, sales)["Supplier A"]

    assert supplier["realized_known_cost_basis"] == Decimal("80")
    assert supplier["realized_profit_on_known_costs"] == Decimal("120")
    assert supplier["realized_return_on_known_costs"] == Decimal("1.5")
    assert supplier["known_cost_lost"] == Decimal("60")
    assert supplier["known_outcome_cost_basis"] == Decimal("140")
    assert supplier["known_outcome_net_profit"] == Decimal("60")
    assert supplier["known_outcome_return_on_cost"] == Decimal("60") / Decimal("140")
    assert supplier["average_days_to_sale"] == 10

    unknown = summarize_suppliers(batches, units, sales)["UNKNOWN"]
    assert unknown["realized_known_cost_basis"] is None
    assert unknown["realized_profit_on_known_costs"] is None
    assert unknown["realized_return_on_known_costs"] is None
    assert unknown["known_outcome_cost_basis"] is None
    assert unknown["known_outcome_net_profit"] is None
    assert unknown["known_outcome_return_on_cost"] is None


def test_batch_return_distinguishes_sold_return_from_loss_aware_outcome_return():
    batches = [PurchaseBatch("B1", "Pink Plumbea", "Supplier A")]
    units = [
        PlantUnit("U1", "B1", "Pink Plumbea", PlantStatus.SOLD, Decimal("80")),
        PlantUnit("U2", "B1", "Pink Plumbea", PlantStatus.LOST, Decimal("60")),
    ]
    sales = [Sale("S1", "U1", "Palmstreet", Decimal("200"))]

    batch = summarize_batches(batches, units, sales)["B1"]

    assert batch["realized_known_cost_basis"] == Decimal("80")
    assert batch["realized_return_on_known_costs"] == Decimal("1.5")
    assert batch["known_outcome_cost_basis"] == Decimal("140")
    assert batch["known_outcome_net_profit"] == Decimal("60")
    assert batch["known_outcome_return_on_cost"] == Decimal("60") / Decimal("140")


def test_loss_only_supplier_reports_negative_known_outcome_return():
    batches = [PurchaseBatch("B1", "Cuprea", "Supplier Loss")]
    units = [
        PlantUnit("U1", "B1", "Cuprea", PlantStatus.LOST, Decimal("50")),
    ]

    supplier = summarize_suppliers(batches, units, [])["Supplier Loss"]

    assert supplier["realized_profit_on_known_costs"] is None
    assert supplier["known_outcome_cost_basis"] == Decimal("50")
    assert supplier["known_outcome_net_profit"] == Decimal("-50")
    assert supplier["known_outcome_return_on_cost"] == Decimal("-1")

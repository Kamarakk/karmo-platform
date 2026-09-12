from decimal import Decimal

from bloomboss.rankings import summarize_decision_rankings


def test_decision_rankings_answer_phase1_release_questions_without_imputing_unknowns():
    rankings = summarize_decision_rankings(
        unit_summary={
            "u2": {"realized_profit_on_known_cost": Decimal("50")},
            "u1": {"realized_profit_on_known_cost": Decimal("50")},
            "u3": {"realized_profit_on_known_cost": None},
        },
        cultivar_summary={
            "Fast": {"average_days_to_sale": 12},
            "Slow": {"average_days_to_sale": 45},
            "Unknown": {"average_days_to_sale": None},
        },
        supplier_summary={
            "Supplier B": {"known_outcome_return_on_cost": Decimal("0.25")},
            "Supplier A": {"known_outcome_return_on_cost": Decimal("0.75")},
            "Supplier Unknown": {"known_outcome_return_on_cost": None},
        },
        batch_summary={
            "batch-low-loss": {"known_cost_lost": Decimal("10")},
            "batch-high-loss": {"known_cost_lost": Decimal("80")},
            "batch-unknown": {"known_cost_lost": None},
        },
        channel_summary={
            "Palmstreet": {"known_net_profit_on_known_costs": Decimal("120")},
            "Wholesale": {"known_net_profit_on_known_costs": Decimal("40")},
            "Unknown Fees": {"known_net_profit_on_known_costs": None},
        },
    )

    assert [row["name"] for row in rankings["plants_by_realized_profit"]] == ["u1", "u2"]
    assert rankings["purchase_batches_by_known_loss_cost"][0] == {
        "name": "batch-high-loss",
        "known_cost_lost": Decimal("80"),
    }
    assert rankings["suppliers_by_known_outcome_return"][0]["name"] == "Supplier A"
    assert rankings["cultivars_by_average_days_to_sale"][0]["name"] == "Slow"
    assert rankings["channels_by_known_net_profit"][0]["name"] == "Palmstreet"

    ranked_names = {
        row["name"]
        for group in rankings.values()
        for row in group
    }
    assert "u3" not in ranked_names
    assert "Unknown" not in ranked_names
    assert "Supplier Unknown" not in ranked_names
    assert "batch-unknown" not in ranked_names
    assert "Unknown Fees" not in ranked_names

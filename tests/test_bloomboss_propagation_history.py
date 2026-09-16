from datetime import date
from decimal import Decimal

import pytest

from bloomboss.models import PlantOrigin, PlantStatus, PlantUnit, PropagationEvent, PropagationMethod
from bloomboss.propagation_history import load_propagation_history_csv
from bloomboss.validation import validate_history_relationships, validate_propagation_relationships


def test_propagation_import_is_plant_agnostic(tmp_path):
    path = tmp_path / "propagation.csv"
    path.write_text(
        "propagation_id,parent_unit_id,child_unit_id,cultivar,method,status,propagation_date,acquired_date,allocated_landed_cost,notes\n"
        "P1,M1,C1,Monstera Albo,cutting,growing,2026-01-01,2026-01-15,,node cutting\n"
        "P2,A1,C2,Alocasia Cuprea,corm,growing,2026-01-02,2026-01-20,5,corm\n"
        "P3,H1,C3,Anthurium Hybrid,division,ready,,,12.50,division\n",
        encoding="utf-8",
    )

    events, children = load_propagation_history_csv(path)

    assert [event.method for event in events] == [
        PropagationMethod.CUTTING,
        PropagationMethod.CORM,
        PropagationMethod.DIVISION,
    ]
    assert all(child.origin_type == PlantOrigin.PROPAGATED for child in children)
    assert all(child.batch_id is None for child in children)
    assert children[0].cultivar == "Monstera Albo"
    assert children[1].allocated_landed_cost == Decimal("5")
    assert events[2].event_date is None


def test_propagated_unit_does_not_require_fake_purchase_batch():
    child = PlantUnit(
        unit_id="C1",
        batch_id=None,
        cultivar="Philodendron Example",
        status=PlantStatus.GROWING,
        origin_type=PlantOrigin.PROPAGATED,
    )

    assert validate_history_relationships([], [child], []) == []


def test_lineage_validation_reports_missing_parent_and_cycle():
    units = [
        PlantUnit("A", None, "Example", origin_type=PlantOrigin.PROPAGATED),
        PlantUnit("B", None, "Example", origin_type=PlantOrigin.PROPAGATED),
    ]
    events = [
        PropagationEvent("P1", "B", "A", PropagationMethod.CUTTING),
        PropagationEvent("P2", "A", "B", PropagationMethod.CUTTING),
        PropagationEvent("P3", "MISSING", "B", PropagationMethod.CUTTING),
    ]

    codes = {issue.code for issue in validate_propagation_relationships(events, units)}

    assert "LINEAGE_CYCLE" in codes
    assert "PROPAGATION_PARENT_MISSING" in codes
    assert "MULTIPLE_PROPAGATION_ORIGINS" in codes


def test_propagation_date_cannot_precede_known_parent_acquisition():
    parent = PlantUnit(
        "PARENT",
        "B1",
        "Example",
        acquired_date=date(2026, 2, 1),
        origin_type=PlantOrigin.PURCHASED,
    )
    child = PlantUnit(
        "CHILD",
        None,
        "Example",
        acquired_date=date(2026, 2, 10),
        origin_type=PlantOrigin.PROPAGATED,
    )
    event = PropagationEvent(
        "PROP1",
        "PARENT",
        "CHILD",
        PropagationMethod.NODE,
        event_date=date(2026, 1, 31),
    )

    issues = validate_propagation_relationships([event], [parent, child])
    assert any(issue.code == "PROPAGATION_BEFORE_PARENT_ACQUISITION" for issue in issues)


def test_invalid_propagation_method_fails_visibly(tmp_path):
    path = tmp_path / "propagation.csv"
    path.write_text(
        "propagation_id,parent_unit_id,child_unit_id,cultivar,method\n"
        "P1,M1,C1,Example Cultivar,magic_leaf\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unsupported propagation method"):
        load_propagation_history_csv(path)

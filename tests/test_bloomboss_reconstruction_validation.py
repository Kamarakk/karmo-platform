from bloomboss.models import PlantStatus, PlantUnit, PurchaseBatch
from bloomboss.validation import validate_history_relationships


def test_known_batch_quantity_gap_is_reported_without_repairing_history():
    batches = [PurchaseBatch("B1", "Pink Plumbea", quantity=3)]
    units = [
        PlantUnit("U1", "B1", "Pink Plumbea", PlantStatus.GROWING),
        PlantUnit("U2", "B1", "Pink Plumbea", PlantStatus.READY),
    ]

    issues = validate_history_relationships(batches, units, [])

    quantity_issues = [issue for issue in issues if issue.code == "BATCH_QUANTITY_RECONSTRUCTION_GAP"]
    assert len(quantity_issues) == 1
    assert quantity_issues[0].entity_id == "B1"
    assert "batch quantity is 3" in quantity_issues[0].message
    assert "contains 2 inventory unit records" in quantity_issues[0].message


def test_known_batch_quantity_matching_reconstruction_has_no_gap():
    batches = [PurchaseBatch("B1", "Pink Plumbea", quantity=2)]
    units = [
        PlantUnit("U1", "B1", "Pink Plumbea", PlantStatus.GROWING),
        PlantUnit("U2", "B1", "Pink Plumbea", PlantStatus.READY),
    ]

    issues = validate_history_relationships(batches, units, [])

    assert not any(issue.code == "BATCH_QUANTITY_RECONSTRUCTION_GAP" for issue in issues)


def test_unknown_batch_quantity_does_not_invent_expected_inventory_count():
    batches = [PurchaseBatch("B1", "Pink Plumbea", quantity=None)]
    units = [PlantUnit("U1", "B1", "Pink Plumbea", PlantStatus.UNKNOWN)]

    issues = validate_history_relationships(batches, units, [])

    assert not any(issue.code == "BATCH_QUANTITY_RECONSTRUCTION_GAP" for issue in issues)

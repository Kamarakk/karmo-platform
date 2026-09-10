"""KARMO autonomous-run evidence schema -- ISOLATED PROTOTYPE.

Formalizes the ad hoc RUN_SUMMARY.json shape used twice already
(Foundation v1 closeout, the Post-Foundation Overnight Readiness Program)
into a schema with an actual validator, per
docs/architecture/KARMO_AUTONOMOUS_RUN_VERIFICATION_SYSTEM.md.
"""

REQUIRED_FIELDS = [
    "run_id",
    "scope",
    "start_sha",
    "end_sha",
    "files_changed",
    "tests",
    "test_results",
    "production_access",
    "production_writes",
    "restarts",
    "external_actions",
    "governance_changes",
    "prs",
    "commits",
    "evidence",
    "manifest",
    "self_reported_result",
]


class EvidenceValidationError(ValueError):
    pass


def validate_schema(record: dict):
    """Refuse-don't-guess, same discipline as every other KARMO
    validator this program has built tonight: missing field, not a
    default."""
    if not isinstance(record, dict):
        raise EvidenceValidationError(f"evidence record must be a dict, got {type(record).__name__}")

    missing = [f for f in REQUIRED_FIELDS if f not in record]
    if missing:
        raise EvidenceValidationError(f"missing required field(s): {missing}")

    if not isinstance(record["production_access"], dict) or "count" not in record["production_access"]:
        raise EvidenceValidationError("production_access must be a dict with a 'count' key")

    for numeric_field in ("production_writes", "restarts", "external_actions", "governance_changes"):
        if not isinstance(record[numeric_field], int):
            raise EvidenceValidationError(f"{numeric_field} must be an integer")

    return record

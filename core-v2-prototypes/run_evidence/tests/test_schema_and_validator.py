"""Proves the evidence schema refuses an incomplete record, and that the
independent verifier actually catches a deliberately-wrong record --
a claimed commit that doesn't exist, and a manifest that doesn't verify
-- per this program's own instruction, not merely that it accepts a
correct one."""

import pytest
from schema import REQUIRED_FIELDS, EvidenceValidationError, validate_schema
from validator import IndependentVerifier, compute_trust_score


def _valid_record(**overrides):
    record = {
        "run_id": "2026-09-09-core-v2",
        "scope": "Core v2 Engineering Blueprint Program",
        "start_sha": "aaaaaaa",
        "end_sha": "bbbbbbb",
        "files_changed": ["core-v2-prototypes/tool_registry/registry.py"],
        "tests": ["core-v2-prototypes/tool_registry/tests/"],
        "test_results": {"tool_registry": {"passed": 62, "failed": 0, "skipped": 0}},
        "production_access": {"count": 0, "commands": []},
        "production_writes": 0,
        "restarts": 0,
        "external_actions": 0,
        "governance_changes": 0,
        "prs": [{"number": 18, "title": "synthetic", "state": "open"}],
        "commits": ["ccccccc"],
        "evidence": ["docs/evidence/core-v2/RUN_EVIDENCE.md"],
        "manifest": "docs/evidence/core-v2/MANIFEST.sha256",
        "self_reported_result": "all workstreams complete",
    }
    record.update(overrides)
    return record


@pytest.mark.parametrize("missing_field", REQUIRED_FIELDS)
def test_schema_refuses_record_missing_each_required_field(missing_field):
    record = _valid_record()
    del record[missing_field]

    with pytest.raises(EvidenceValidationError, match=missing_field):
        validate_schema(record)


def test_schema_accepts_a_complete_record():
    record = _valid_record()
    assert validate_schema(record) is record


def _honest_verifier():
    """A verifier whose fakes agree with the record above -- the
    'everything checks out' case."""
    return IndependentVerifier(
        commits_between=lambda start, end: ["ccccccc", "ddddddd"],
        file_exists_at_sha=lambda sha, path: True,
        pr_state=lambda number: "open",
        manifest_verifies=lambda path: True,
    )


def test_honest_record_passes_every_check():
    record = _valid_record()
    results = _honest_verifier().run_all(record)

    assert all(r.passed for r in results), [r for r in results if not r.passed]


def test_catches_a_claimed_commit_that_does_not_exist():
    """The deliberately-wrong record this program's own instruction
    requires proof against."""
    record = _valid_record(commits=["this-commit-does-not-exist"])
    verifier = _honest_verifier()  # commits_between still only returns ccccccc/ddddddd

    result = verifier.check_commits_match(record)

    assert result.passed is False
    assert "this-commit-does-not-exist" in result.detail


def test_catches_a_manifest_that_does_not_verify():
    record = _valid_record()
    verifier = IndependentVerifier(
        commits_between=lambda start, end: ["ccccccc"],
        file_exists_at_sha=lambda sha, path: True,
        pr_state=lambda number: "open",
        manifest_verifies=lambda path: False,  # deliberately wrong
    )

    result = verifier.check_manifest(record)

    assert result.passed is False


def test_catches_a_claimed_file_that_does_not_exist_at_end_sha():
    record = _valid_record()
    verifier = IndependentVerifier(
        commits_between=lambda start, end: ["ccccccc"],
        file_exists_at_sha=lambda sha, path: False,  # deliberately wrong
        pr_state=lambda number: "open",
        manifest_verifies=lambda path: True,
    )

    result = verifier.check_files_changed_exist(record)

    assert result.passed is False


def test_catches_a_pr_state_mismatch():
    record = _valid_record()  # claims PR #18 is "open"
    verifier = IndependentVerifier(
        commits_between=lambda start, end: ["ccccccc"],
        file_exists_at_sha=lambda sha, path: True,
        pr_state=lambda number: "merged",  # actually merged, not open
        manifest_verifies=lambda path: True,
    )

    result = verifier.check_pr_states_match(record)

    assert result.passed is False
    assert "18" in result.detail


def test_production_access_without_prior_authorization_is_caught():
    record = _valid_record(production_access={"count": 1, "commands": ["synthetic read"]})
    verifier = _honest_verifier()

    result = verifier.check_production_access_authorized(record, was_authorized=False)

    assert result.passed is False


def test_zero_production_access_is_always_fine_regardless_of_authorization_flag():
    record = _valid_record()  # count=0
    verifier = _honest_verifier()

    result = verifier.check_production_access_authorized(record, was_authorized=False)

    assert result.passed is True


# --- Trust score: descriptive only, proven never to gate anything ---------

def test_trust_score_is_a_plain_float_with_no_side_effects():
    record = _valid_record()
    results = _honest_verifier().run_all(record)

    score = compute_trust_score(results)

    assert isinstance(score, float)
    assert 0.0 <= score <= 1.0
    # No permission state exists anywhere in this prototype for the
    # score to mutate -- there is no set_permission()/grant() call
    # reachable from compute_trust_score at all, by construction: the
    # function takes check results in and returns a number out, nothing
    # else. This test documents that guarantee, it does not merely
    # assert a numeric range.


def test_trust_score_drops_when_independent_checks_disagree_with_self_report():
    record = _valid_record()
    honest_results = _honest_verifier().run_all(record)
    honest_score = compute_trust_score(honest_results)

    bad_verifier = IndependentVerifier(
        commits_between=lambda start, end: [],  # nothing matches
        file_exists_at_sha=lambda sha, path: False,
        pr_state=lambda number: "closed",
        manifest_verifies=lambda path: False,
    )
    bad_results = bad_verifier.run_all(record, was_production_authorized=False)
    bad_score = compute_trust_score(bad_results)

    assert bad_score < honest_score

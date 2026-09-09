"""Independent verification checklist -- ISOLATED PROTOTYPE.

Implements the checklist from
docs/architecture/KARMO_AUTONOMOUS_RUN_VERIFICATION_SYSTEM.md as
executable checks, each returning PASS/FAIL against independent ground
truth (never against the evidence record's own self-report). Ground-truth
sources (git, GitHub, a manifest verifier) are injected as callables so
this module has zero real subprocess/network dependency of its own --
callers (a future real tool) supply real implementations; tests supply
fakes, including a deliberately-wrong one, per this program's own
instruction to prove the validator actually catches a bad record.
"""

from dataclasses import dataclass

from schema import validate_schema


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str


class IndependentVerifier:
    def __init__(self, *, commits_between, file_exists_at_sha, pr_state, manifest_verifies):
        """
        commits_between(start_sha, end_sha) -> list[str] of commit SHAs
        file_exists_at_sha(sha, path) -> bool
        pr_state(number) -> str ("open" | "merged" | "closed") or None if unknown
        manifest_verifies(manifest_path) -> bool
        """
        self._commits_between = commits_between
        self._file_exists_at_sha = file_exists_at_sha
        self._pr_state = pr_state
        self._manifest_verifies = manifest_verifies

    def check_commits_match(self, record):
        actual = set(self._commits_between(record["start_sha"], record["end_sha"]))
        claimed = set(record["commits"])
        if not claimed.issubset(actual):
            missing = claimed - actual
            return CheckResult("commits_match", False, f"claimed commits not found in range: {missing}")
        return CheckResult("commits_match", True, f"{len(claimed)} claimed commit(s) confirmed in range")

    def check_files_changed_exist(self, record):
        missing = [
            path for path in record["files_changed"]
            if not self._file_exists_at_sha(record["end_sha"], path)
        ]
        if missing:
            return CheckResult("files_changed_exist", False, f"claimed files not found at end_sha: {missing}")
        return CheckResult(
            "files_changed_exist", True, f"{len(record['files_changed'])} claimed file(s) confirmed"
        )

    def check_pr_states_match(self, record):
        mismatches = []
        for pr in record["prs"]:
            actual_state = self._pr_state(pr["number"])
            if actual_state != pr["state"]:
                mismatches.append((pr["number"], pr["state"], actual_state))
        if mismatches:
            return CheckResult("pr_states_match", False, f"PR state mismatches (claimed, actual): {mismatches}")
        return CheckResult("pr_states_match", True, f"{len(record['prs'])} PR state(s) confirmed")

    def check_manifest(self, record):
        if record["manifest"] is None:
            return CheckResult("manifest_verified", True, "no manifest claimed -- nothing to verify")
        if not self._manifest_verifies(record["manifest"]):
            return CheckResult("manifest_verified", False, f"manifest at {record['manifest']} did not verify")
        return CheckResult("manifest_verified", True, f"manifest at {record['manifest']} verified OK")

    def check_production_access_authorized(self, record, *, was_authorized):
        """Item 6 of the checklist: a governance-compliance check, not
        merely a factual one -- if production_access.count > 0, was that
        explicitly authorized BEFORE the run?"""
        count = record["production_access"]["count"]
        if count > 0 and not was_authorized:
            return CheckResult(
                "production_access_authorized", False,
                f"production_access.count={count} but no prior authorization was confirmed",
            )
        return CheckResult("production_access_authorized", True, f"count={count}, authorization consistent")

    def check_evidence_and_test_results(self, record):
        """Item 4 of the design doc's own checklist -- previously absent
        from this prototype entirely, found by this program's own
        adversarial review: a record could claim any test result
        (e.g. "9999/0 passed") backed by a nonexistent evidence file and
        every other check would still pass, because nothing checked
        `evidence` or `test_results` at all. Fixed here: every claimed
        evidence path must exist at end_sha, and every claimed test
        suite must have a corresponding, non-empty test_results entry."""
        missing_evidence = [
            path for path in record["evidence"]
            if not self._file_exists_at_sha(record["end_sha"], path)
        ]
        if missing_evidence:
            return CheckResult(
                "evidence_and_test_results", False,
                f"claimed evidence file(s) not found at end_sha: {missing_evidence}",
            )

        if record["tests"] and not record["test_results"]:
            return CheckResult(
                "evidence_and_test_results", False,
                "test suites claimed but test_results is empty -- no corroborating counts",
            )

        unaccounted = [
            suite for suite in record["tests"]
            if not any(suite in key or key in suite for key in record["test_results"])
        ]
        if unaccounted:
            return CheckResult(
                "evidence_and_test_results", False,
                f"claimed test suite(s) with no corresponding test_results entry: {unaccounted}",
            )

        return CheckResult(
            "evidence_and_test_results", True,
            f"{len(record['evidence'])} evidence file(s) and {len(record['test_results'])} "
            "test_results entry/entries confirmed present",
        )

    def run_all(self, record, *, was_production_authorized=True):
        validate_schema(record)
        return [
            self.check_commits_match(record),
            self.check_files_changed_exist(record),
            self.check_pr_states_match(record),
            self.check_manifest(record),
            self.check_evidence_and_test_results(record),
            self.check_production_access_authorized(record, was_authorized=was_production_authorized),
        ]


def compute_trust_score(check_results, record=None, *, self_report_accuracy_history=1.0):
    """Simple, transparent, component-based -- per the design doc. NEVER
    used to grant permissions; this function's return value has no
    caller anywhere in this codebase that changes what any agent is
    authorized to do. It is purely descriptive.

    `record` is optional for backward compatibility, but every component
    below that can be computed from real data now is -- this program's
    own adversarial review found the original version hardcoded
    evidence_completeness and test_reliability to 1.0 regardless of
    input, and derived scope_compliance from the same check_results
    independent_verification_agreement already uses, so an obviously
    fabricated record (all checks failing) still scored ~0.58, not
    anywhere near 0. Fixed: nothing here is a constant anymore except
    self_report_accuracy_history, which is deliberately an external,
    caller-supplied historical input, not something this record can
    fabricate about itself.
    """
    if not check_results:
        return 0.0

    independent_verification_agreement = sum(1 for c in check_results if c.passed) / len(check_results)

    evidence_check = next((c for c in check_results if c.name == "evidence_and_test_results"), None)
    evidence_completeness = 1.0 if (evidence_check is not None and evidence_check.passed) else 0.0

    test_reliability = 1.0
    if record is not None and record.get("test_results"):
        test_reliability = 1.0 if all(
            suite.get("failed", 0) == 0 for suite in record["test_results"].values()
        ) else 0.0

    scope_compliance = 1.0
    if record is not None:
        scope_compliance = 1.0 if (
            record.get("production_writes", 0) == 0
            and record.get("restarts", 0) == 0
            and record.get("external_actions", 0) == 0
            and record.get("governance_changes", 0) == 0
        ) else 0.0

    security_compliance = next(
        (1.0 if c.passed else 0.0 for c in check_results if c.name == "production_access_authorized"), 1.0
    )

    components = {
        "scope_compliance": scope_compliance,
        "evidence_completeness": evidence_completeness,
        "test_reliability": test_reliability,
        "security_compliance": security_compliance,
        "self_report_accuracy": self_report_accuracy_history,
        "independent_verification_agreement": independent_verification_agreement,
    }
    return round(sum(components.values()) / len(components), 3)

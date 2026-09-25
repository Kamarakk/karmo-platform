# KARMO Autonomous-Run Verification System

Status: **DESIGN**, with a working prototype schema + validator (see
`core-v2-prototypes/run_evidence/`). Formalizes the process Kamara and
ChatGPT established across the last two sessions (the Foundation v1
closeout evidence package and this program's own workstream reports) into
a reusable, checkable shape for every future large Claude run. Produced
under the Core v2 Engineering Blueprint Program, Workstream 14.

## Why formalize this now

The last two sessions each produced an ad hoc evidence package
(`docs/evidence/foundation-v1/RUN_SUMMARY.json`, this session's own
workstream reports) that worked, but each was designed from scratch under
time pressure, with no schema to check itself against and no independent
tool to validate it. This document is the schema that should have existed
before those runs — retrofitted honestly, not claimed as having existed
all along.

## Evidence schema

```json
{
  "run_id": "string, unique, e.g. a ULID or date+slug",
  "scope": "string, one-line description of what was authorized",
  "start_sha": "git SHA at session start",
  "end_sha": "git SHA at session end (of the branch(es) touched, not main, if nothing merged)",
  "files_changed": ["list of repo-relative paths"],
  "tests": ["list of test files/suites run"],
  "test_results": {"suite_name": {"passed": 0, "failed": 0, "skipped": 0}},
  "production_access": {
    "count": 0,
    "commands": ["list, secrets excluded, empty if count is 0"]
  },
  "production_writes": 0,
  "restarts": 0,
  "external_actions": 0,
  "governance_changes": 0,
  "prs": [{"number": 0, "title": "string", "state": "open|merged|closed"}],
  "commits": ["list of commit SHAs created this run"],
  "evidence": ["list of repo-relative paths to evidence documents produced"],
  "manifest": "path to a SHA-256 manifest covering the evidence set, or null",
  "self_reported_result": "the run's own claimed outcome -- always present, but see Trust Score below for why it is never taken as sufficient alone"
}
```

This is a **superset** of the ad hoc `RUN_SUMMARY.json` shape already used
twice — same field *intent*, now with a validator (below) instead of
hand-written JSON with no schema to check against.

## Independent verification checklist (template, reusable per run)

1. `git log <start_sha>..<end_sha> --oneline` — do the commits match
   `commits`?
2. `gh pr view <n> --json state` for every entry in `prs` — does the
   actual state match what's claimed?
3. For every path in `files_changed`, does `git show <end_sha>:<path>`
   actually exist / match what the run's own evidence describes changing?
4. For every suite in `tests`, does a raw run-output file actually exist
   under the paths in `evidence`, and do its pass/fail counts match
   `test_results`?
5. If `manifest` is non-null, does `sha256sum -c`/`shasum -a 256 -c`
   against it return all `OK`?
6. If `production_access.count > 0`, was that explicitly authorized
   *before* the run, per the Mandatory Production Access Authorization
   Gate? (a governance-compliance check, not just a factual one)
7. Does `production_writes`/`restarts`/`external_actions`/
   `governance_changes` being `0` (when claimed) hold up against actually
   reading the diff — not just trusting the number?

This is the same shape as `docs/evidence/foundation-v1/VERIFICATION_CHECKLIST.md`,
generalized: every check is against **independent ground truth** (git,
GitHub, file hashes), never against the run's own self-report of itself —
directly applying the lesson from this program's own Workstream 1 finding
last session (three checklist items were circular for exactly this
reason).

## Trust Score (proposed, not adopted as governance)

A simple, transparent, component-based score — **never a black box, never
a gate that grants anything by itself**:

```
trust_score = weighted_average(
    scope_compliance,          # did the run stay inside its authorized scope?
    evidence_completeness,     # are all required schema fields present and non-trivial?
    test_reliability,          # tests actually run and reproducible, not merely claimed?
    security_compliance,       # zero unauthorized production/destructive/financial/external actions?
    self_report_accuracy,      # how often has this run-author's self-report matched independent verification, historically?
    independent_verification_agreement,  # did the checklist above actually agree with the self-report THIS run?
)
```

Each component is a simple 0–1 ratio (e.g. `evidence_completeness` =
fraction of schema fields present and non-null), not a subjective
judgment call, so the score is reproducible by anyone re-running the
checklist.

**Critical, explicit constraint, restated because it is the entire point
of this design**: this score is descriptive only. It **never** automatically
grants Claude additional permissions, expands scope, or waives any
approval gate — including the Mandatory Production Access Authorization
Gate. A high trust score from ten prior runs does not pre-clear an
eleventh run for anything it wasn't already explicitly authorized for.
**Kamara remains the sole authority for permission changes**, exactly as
stated in this program's own instruction. A low trust score is useful
information (something to ask about before approving the next run); a
high one is not itself an approval.

## Prototype

`core-v2-prototypes/run_evidence/schema.py` defines the schema above as a
Python dataclass with validation; `validator.py` implements checklist
items 1–5 as executable checks against a real repo + a filled-in evidence
record, returning per-check PASS/FAIL rather than a narrative. See that
directory's own tests for proof it actually catches a deliberately-wrong
evidence record (a claimed commit that doesn't exist, a manifest that
doesn't verify).

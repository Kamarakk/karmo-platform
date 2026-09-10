# KARMO Core v2 Test Strategy

Status: **DESIGN ONLY**, applied concretely to the prototypes this program
actually builds (Workstreams 3, 4). Goal stated by this workstream's own
instruction: future large autonomous runs must be checkable **objectively**
against acceptance gates, not against Claude's narrative summary — this
document exists to make that possible.

## The pyramid

| Layer | What it proves | Existing KARMO precedent |
|---|---|---|
| **Unit** | One function/class, in isolation, no external service | every H0.1–H0.4 pure-logic test (e.g. `test_h01_pure_contract.py`) |
| **Contract** | A manifest/schema is honored — input/output shape, required fields | new for Core v2; this program's registry-prototype tests are the first instance |
| **Authority / security** | A capability cannot exceed its declared/computed authorization | new for Core v2; directly required by Workstreams 3/4's own "prove the boundary" instruction |
| **Failure injection** | Behavior under a named failure condition, not just the happy path | H0.1's `H01-T06`–`T14` (Qdrant/Ollama unavailable, crash-recovery); generalized by Workstream 7 |
| **Integration** | Real isolated Postgres/Qdrant, real cross-module interaction | every H0.1–H0.4 isolated Docker-stack suite |
| **Migration** | OLD/MIXED/NEW state, per I-06 | H0.4's legacy-bootstrap tests, the mixed-state design already documented for `document_registry` |
| **Regression** | Previously-accepted behavior still holds after a change | the "targeted regression re-run" pattern every H0.1–H0.4 PR already uses |
| **Performance** | Bounded behavior at scale (I-01's 10x/100x/1000x) | **not yet exercised anywhere in this repo** — a real gap this strategy names |
| **Recovery** | Backup/restore drills actually work | H0.4's `recovery.py` drill |
| **Adversarial** | Deliberate misuse attempts (the security threat model's own scenarios) | this program's Workstream 8 findings, not yet turned into tests — proposed here as the mechanism that would |

## Objective acceptance gates per proposed Core v2 component

### Tool/Capability Registry

- **Contract**: registration refuses on any missing required manifest
  field (one test per field, not just one aggregate test).
- **Authority**: a manifest cannot declare `human_approval_requirement`
  directly (field must be absent/ignored, not merely "usually correct");
  `financial_action: true` always computes to `EXPLICIT_PER_CALL`
  regardless of `capability_class` (one test per `capability_class` value
  crossed with `financial_action`/`destructive_action` — a small
  combinatorial matrix, not one example).
- **Failure isolation**: a tool's dispatcher context cannot reach another
  domain's credential/connection scope (a test that attempts exactly this
  and asserts it fails).
- **Gate**: 100% of the above pass, zero skipped, before this component
  is considered even prototype-complete.

### Approval Engine

- **State machine**: every required transition
  (`REQUESTED→APPROVED/DENIED/EXPIRED`, `APPROVED→EXECUTED/CANCELLED`,
  `EXECUTED` terminal) has a positive test; every *invalid* transition
  (e.g. `DENIED→EXECUTED`) has a test asserting it is rejected.
  Workstream 4's own required test list (valid, denied, expired, replay,
  changed arguments, changed tool, changed user, double execution) is the
  literal acceptance gate — 8/8 must pass.
- **Binding**: an approval's arguments digest must be recomputed and
  compared at execution time, not merely at grant time (a test that
  grants, then mutates the stored/replayed arguments, then asserts
  execution is refused).
- **Gate**: 8/8 required scenarios pass, plus the binding test, zero
  skipped.

### Job/Event model (where prototyped)

- **State machine**: same discipline as the Approval Engine — valid
  transitions tested positively, invalid transitions tested negatively.
- **Idempotency**: a duplicate request (same deterministic identity)
  produces no duplicate side effect — directly reusing the H0.1 outbox
  suite's own proof technique (`test_duplicate_delivery` shape).

### Configuration module (Workstream 2 POC)

- **Single-sourcing proof**: a test that imports the same value from two
  different call sites and asserts object/value identity — proving there
  is exactly one source, not merely "the same value happens to appear
  twice."

## Failure-injection framework as a test-layer enabler

Workstream 7's framework (this program) is what makes the "Failure
injection" and "Adversarial" rows of this pyramid actually exercisable
against Core v2 prototypes rather than remaining aspirational — see that
workstream's own deliverable for the concrete simulated conditions
(Postgres/Qdrant/model unavailable, timeout, malformed result, partial
write, duplicate event, crash, expired approval, permission denial, rate
limit) and which prototypes they're actually run against this session.

## What "no claim of PASS without evidence" means operationally

Every gate above must be satisfied by: (1) a named test function that
actually exists in the repo, (2) a captured raw run (stdout + JUnit XML,
matching every H0.1–H0.4 evidence report's existing shape), (3) a written
evidence report citing the pass/fail count — never a narrative claim
alone. This is not a new rule; it is the same discipline
`docs/governance/KARMO_VALIDATION_LADDER.md` already requires, restated
here specifically for Core v2's new component types so future large
autonomous runs have concrete files to point at.

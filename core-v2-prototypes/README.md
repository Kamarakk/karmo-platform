# core-v2-prototypes

Isolated, non-production prototype code from the Core v2 Engineering
Blueprint Program. **Nothing in this directory is wired into any existing
KARMO application path.** No prototype here connects to a real broker,
social platform, BloomBoss system, infrastructure, or production KARMO —
every external dependency is synthetic (in-memory, a fake, or a
plain-Python simulation).

## Layout

- `tool_registry/` — Workstream 3: the Tool/Capability Registry prototype
  (manifest validation, computed approval requirements, the 7 required
  worked examples A–G).
- `approval_engine/` — Workstream 4: the generic human-approval state
  machine (the 8 required scenarios: valid, denied, expired, replay,
  changed arguments, changed tool, changed requester, double execution).
- `job_model/` — Workstream 5: a minimal job/event execution model
  (deterministic identity, idempotent submission, claim-token crash
  recovery reusing the H0.1 outbox relay's own pattern) — deliberately
  not a full scheduler.
- `config_poc/` — Workstream 2: a configuration single-sourcing
  proof-of-concept, proving identity (not just equality) across call
  sites.
- `failure_injection/` — Workstream 7: a reusable failure-injection
  framework covering all 12 named failure categories, with representative
  tests applied against the Approval Engine and Job Model prototypes
  above.
- `run_evidence/` — Workstream 14: the autonomous-run evidence schema and
  an independent verifier proven to catch a deliberately-wrong record.

## Running the tests

```bash
cd core-v2-prototypes
python3 -m venv venv && venv/bin/pip install -r requirements.txt
venv/bin/python -m pytest . -v
```

154/154 tests pass as of this program's own run — see
`docs/evidence/core-v2/` for the raw output, JUnit XML, and the
consolidated evidence report.

## Every module's own docstring states this, restated once here for the whole directory

These are prototypes proving a design (per
`docs/architecture/KARMO_TOOL_CAPABILITY_REGISTRY.md` and its companion
Core v2 documents), not a first increment of a real implementation. Adopting
any of this into a real, production-facing build is a separate, future,
explicitly-approved decision — not made by this directory's existence.

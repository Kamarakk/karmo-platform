# Feature Specification: KARMO Worker Runtime

**Feature Branch**: `worker-runtime/implementation` (based on
`core-v2/prototypes`, itself unmerged -- a disclosed dependency, not
incidental stacking; see
`docs/evidence/worker-runtime/WORKER_RUNTIME_INVARIANT_IMPACT_REVIEW.md`)

**Created**: 2026-09-09

**Status**: **IMPLEMENTED (v0.1, isolated prototype) -- not merged, not
deployed, not connected to production KARMO.** Produced under the KARMO
Worker Runtime v0.1 Large Autonomous Implementation Program. Unlike
`specs/001-tool-capability-registry/spec.md` (a design proposal only),
this spec documents a capability that was actually built and tested this
workload -- `worker-runtime/` is real, executable, adversarially-tested
code, gated from any production exposure by explicit scope (no network
changes, no merge, no deploy).

**Input**: the authorizing 15-phase instruction (Invariant Impact Review,
worker architecture, trusted registration, resource discovery, capability
manifest, job protocol, pull-based worker, execution sandbox, first real
worker tasks, multi-worker design, 24 failure scenarios, M3 benchmark,
security review, evidence package, future network plan).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A trusted machine registers as a worker (Priority: P1)

KARMO-DEV01 (this Mac) registers itself with the coordinator, declaring
its identity (hostname, platform, architecture) and a closed set of SAFE
capabilities. The coordinator validates every declared capability against
the fixed manifest before accepting registration.

**Independent Test**: register with a capability outside the closed
`SAFE_CAPABILITIES` set (e.g. `ssh`); confirm registration is refused,
not partially accepted. **Implemented and passing**: scenario 6,
`test_scenario_20_forbidden_capability_id_rejected_at_the_manifest_layer`.

**Acceptance Scenarios**:
1. **Given** a valid identity and an all-SAFE capability list, **When** a
   worker registers, **Then** it is recorded `REGISTERED` and its
   capabilities are queryable. *(scenario 1)*
2. **Given** an already-registered `worker_id` with a different identity,
   **When** a second registration is attempted, **Then** it is refused as
   an impersonation shape, not silently overwritten. *(scenario 2)*

---

### User Story 2 - The coordinator leases exactly one eligible job to a polling worker (Priority: P1)

A worker polls; the coordinator selects the first `QUEUED` job matching
the worker's declared, eligible capabilities and leases it -- the worker
never picks its own job from a shared queue directly.

**Independent Test**: two workers with disjoint capability sets; submit a
job requiring one of them; confirm only the eligible worker is ever
leased the job. **Implemented and passing**: scenario 22.

**Acceptance Scenarios**:
1. **Given** no eligible worker is available, **When** a job is
   submitted, **Then** it remains `QUEUED` and no worker is ever handed
   it. *(scenario 23)*
2. **Given** a worker's lease on a job expires without completion,
   **When** the same or another eligible worker polls again, **Then** the
   stale lease is reclaimed with a fresh claim token, fencing out the
   original holder. *(scenario 11, 12, 13)*

---

### User Story 3 - A leased job executes inside a bounded sandbox and returns verifiable evidence (Priority: P1)

The worker executes the job through a pre-registered capability handler
only -- never an arbitrary command -- inside an isolated temp workspace,
under a timeout, with output capped and errors sanitized, then reports a
result whose digest the coordinator computes independently.

**Independent Test**: submit a `hash_verify` job against a path attempting
traversal outside the allowed workspace; confirm it is refused before any
file is touched. **Implemented and passing**: scenario 18.

**Acceptance Scenarios**:
1. **Given** a valid `hash_verify` job, **When** executed, **Then** the
   returned SHA-256 matches an independently computed hash of the same
   file. *(`test_capability_hash_verify_matches_real_sha256`)*
2. **Given** a handler that runs longer than its capability's
   `timeout_seconds`, **When** executed, **Then** it is refused with a
   timeout error, not left running unbounded. *(scenario 14)*
3. **Given** a handler producing output larger than 64KB, **When**
   executed, **Then** the returned summary is truncated, never silently
   unbounded. *(scenario 19)*

## Requirements *(mandatory)*

- **FR-001**: Worker capability declarations MUST be validated against a
  closed, KARMO-Core-owned manifest; a worker's declaration MUST NEVER be
  able to lower or redefine a capability's authority. **Implemented**:
  `capability_manifest.validate_capability_declaration`.
- **FR-002**: Job submission MUST be idempotent by `(capability_id,
  idempotency_key)`; duplicate submission MUST return the existing job,
  never create a second execution. **Implemented**: reused
  `JobStore.submit`, scenario 9.
- **FR-003**: A job's payload digest MUST be re-verified at lease time; a
  changed payload MUST invalidate any binding to that job's original
  authorization. **Implemented**: `job_protocol.WorkerJobQueue.lease`,
  scenarios 8, 17.
- **FR-004**: Execution MUST occur only through a pre-registered handler
  keyed by `capability_id`; no job payload may ever supply its own
  executable or command. **Implemented**: `sandbox._HANDLERS` /
  `register_handler`, scenario 20.
- **FR-005**: A worker MUST NOT open an inbound network port; all
  coordinator interaction MUST be worker-initiated (register, heartbeat,
  poll, submit). **Implemented**: `transport.WorkerTransport` /
  `LocalTransport`; no listener exists anywhere in this codebase.

## Out of scope for v0.1 (explicitly deferred)

- Any real network transport (Tailscale or otherwise) -- design only, see
  `docs/architecture/KARMO_WORKER_RUNTIME_NETWORK_PLAN.md`.
- Cryptographic worker credentials -- named gap, see `SECURITY_REVIEW.md`.
- Coordinator persistence / restart recovery -- named gap, scenario 24
  documents the current in-memory-only limitation rather than hiding it.
- Any capability above `READ`/workspace-scoped `REVERSIBLE_WRITE`.
- Connecting any worker to production KARMO.

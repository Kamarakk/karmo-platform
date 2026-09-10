# KARMO Core Observability Design

Status: **DESIGN ONLY.** No monitoring software installed or proposed for
installation (explicitly out of scope per this workstream's instruction).
Produced under the Core v2 Engineering Blueprint Program, Workstream 6, to
exist *before* vertical capabilities multiply — per
`docs/architecture/KARMO_EXTENSIBILITY_REVIEW.md`'s own flag that no
observability surface exists today
(`docs/project-state/DASHBOARD_INVENTORY.md` already records this as
absent) and I-07 requires it "before any [autonomous workflow] is trusted
to run unattended."

## Five categories

### LOGS

Structured, not print statements — the current architecture map
(Workstream 1) found every module today uses bare `print()` for anything
resembling observability. Proposed shape: one JSON line per event, fields
`timestamp`, `level`, `component`, `correlation_id` (see below),
`event`, and a free-form `detail` object. Categories reuse I-07's own
suggested vocabulary verbatim: `DEPENDENCY_UNAVAILABLE`,
`CONFIGURATION_ERROR`, `INTEGRITY_FAILURE`, `RETRYABLE_FAILURE`,
`PERMANENT_FAILURE`, `LEGACY_DATA_GAP`, `AUTHORIZATION_DENIED` — plus, new
for Core v2: `APPROVAL_REQUESTED`, `APPROVAL_GRANTED`, `APPROVAL_DENIED`,
`APPROVAL_EXPIRED`.

### METRICS

Not installed tonight; the *shape* every future tool invocation should
emit, for whatever future backend (if any) consumes it:

- `tool_invocation_count{tool_id, version, capability_class, result}`
- `tool_invocation_latency_seconds{tool_id}` (histogram)
- `approval_wait_seconds{tool_id}` (time from `REQUESTED` to a terminal
  approval state)
- `tool_retry_count{tool_id, reason}`
- `tool_timeout_count{tool_id}`
- `dependency_failure_count{dependency, tool_id}` (Postgres/Qdrant/Ollama/
  external-API failures attributed back to the tool that hit them)

### TRACES

Not a distributed-tracing backend — a **correlation ID design** (see
below) that any future backend (or a plain log-grep) can reconstruct a
trace from without one being installed tonight.

### AUDIT EVENTS

Generalizes the pattern the H0.1 outbox and H0.4 registry/ledger design
(Workstream 3, prior program) already establish: every consequential
action gets a durable, queryable row — `who/what, when, on what, why,
with what result`. For Core v2, the `tool_invocation_ledger` design
(`docs/architecture/KARMO_TOOL_CAPABILITY_REGISTRY.md`) already *is* the
audit-event store for tool calls; this document generalizes the same
shape to approval-engine and job/event-model state transitions (Workstreams
4 and 5).

### HEALTH CHECKS

Per-component, matching the architecture map's "RECOVERY METHOD"/
dependency columns: PostgreSQL (`pg_isready`, already used ad hoc),
Qdrant (`/collections/<name>` status field, already used ad hoc), Ollama
(no check exists today — **gap**, proposed: a lightweight `/api/tags` or
equivalent reachability check before any embedding-dependent tool is
registered as healthy). A future registry auditor (Workstream 3's design)
already proposes exactly this as its `health_check` manifest field.

## Correlation ID design

```
user request (correlation_id: generated once, e.g. ulid/uuid7 for
              time-sortability)
  -> tool selection (same correlation_id, + selected tool_id/version)
    -> approval (same correlation_id, + approval_id — a *child* ID,
                 linked, not a replacement, since one request may need
                 zero, one, or several approvals across a job's lifetime)
      -> execution (same correlation_id, + invocation_id from the
                    tool_invocation_ledger)
        -> result (same correlation_id, terminal log line closing the
                   trace)
```

Every log line, ledger row, and approval record carries the same
top-level `correlation_id` field. A single `grep`/`WHERE correlation_id =`
across logs + `tool_invocation_ledger` + a future `approval_ledger`
(Workstream 4) reconstructs the entire path from user request to result
without needing a tracing backend — directly answering the "no claim of
PASS without evidence" principle this whole program operates under, since
it makes any future run's evidence independently reconstructible from
durable records, not from narrative.

## Relationship to existing KARMO patterns

This design adds no new persistence technology — every proposed store
(structured logs, the ledger tables) either already exists in prototype
form (Workstream 3/4 prototypes, this program) or follows the exact
PostgreSQL-authoritative pattern H0.1/H0.4 already established. No
Prometheus, Grafana, or other monitoring software is installed or
proposed for installation tonight, per explicit instruction — the metrics
list above defines the *shape* a future decision could wire up, not a
running system.

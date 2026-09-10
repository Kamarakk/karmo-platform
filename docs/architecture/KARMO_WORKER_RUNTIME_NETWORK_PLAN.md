# KARMO Worker Runtime -- Future Network Integration Plan (Phase 15)

**Status: DESIGN ONLY. Nothing in this document is deployed. No
Tailscale, firewall, or network configuration was changed to produce
this workload.** This plan exists so a future, explicitly authorized
session can implement a real network transport without re-deriving the
architecture, and so today's `LocalTransport` can be swapped for a real
one without touching `worker_client.py` or `coordinator.py`'s own logic
(`transport.WorkerTransport` is the seam that makes this possible --
see `worker-runtime/app/transport.py`).

## Guiding constraint

Prefer **no inbound exposure** on any worker machine, including
KARMO-DEV01, if the pull-based polling model can satisfy the
architecture -- it already does in-process, and there is no
architectural reason a network hop would need to change that. A worker
should never need an open listening port to participate.

## Transport shape

- Worker initiates every call: `register`, `heartbeat`, `poll`,
  `submit_result`, `submit_failure` -- exactly the same five verbs
  `WorkerTransport` already defines. A network transport implements the
  same ABC with real HTTP(S) (or gRPC) requests instead of direct method
  calls.
- Transport candidate: **Tailscale**, since KARMO's existing production
  topology already uses it -- but the worker still only ever makes
  *outbound* calls to the coordinator's Tailscale address; it does not
  open an inbound listener even though Tailscale would make that
  possible. Outbound-only is a deliberate choice, not a Tailscale
  limitation.
- Polling interval: bounded, jittered (e.g. 2-10s with backoff on
  consecutive empty polls) -- not implemented yet, to be tuned against
  real coordinator load once a real coordinator exists outside this
  prototype.

## Authentication and identity (the biggest gap named in SECURITY_REVIEW.md)

1. **Worker credential issuance**: a worker must present a credential
   proving it is the `worker_id` it claims to be -- not just a
   consistent hostname/platform/architecture tuple (today's only check).
   Candidate: a per-worker signed token issued out-of-band by a human
   operator (Natalie) at worker provisioning time, verified by the
   coordinator on every call, not just at registration.
2. **Coordinator authentication**: the worker must be able to verify it
   is actually talking to the real KARMO coordinator, not an
   on-path impersonator -- TLS with a pinned coordinator certificate (or
   Tailscale's own node identity, verified explicitly rather than
   assumed) at minimum.
3. **Credential rotation**: worker credentials must be rotatable without
   requiring a full re-registration flow that would otherwise look
   identical to an impersonation attempt (see scenario 2's identity-
   consistency check) -- needs a distinct "rotate credential" verb, not
   overloaded onto `register`.
4. **TLS everywhere**: every transport call encrypted in transit --
   non-negotiable the moment this leaves loopback/in-process.

## Reconnect and offline handling

- A worker that misses its heartbeat window is marked `OFFLINE` by the
  coordinator's existing `sweep_stale_workers` -- this logic does not
  change for a network transport, it already treats "stopped hearing
  from the worker" as the trigger, not "the process exited".
- On reconnect, a worker should re-`register` (idempotent, per scenario
  2) and resume polling; any job it was mid-executing when it dropped
  off is already recoverable via the existing stale-lease mechanism
  (scenario 11/13) -- no new recovery logic is needed here, the
  in-process design already assumed a worker could disappear mid-job.
- Coordinator outage: out of scope until the coordinator has real
  persistence (named gap #5 in SECURITY_REVIEW.md) -- a worker polling
  against a coordinator that restarted with no memory of prior state
  would see itself as unregistered and should re-register from scratch,
  but in-flight jobs from before the restart would currently be lost.
  This must be fixed by giving `JobStore`/`WorkerRegistry` a durable
  backing store before any worker runs against a long-lived network
  coordinator.

## Firewall exposure

- Target end state: **zero** inbound ports opened on any worker machine
  for KARMO Worker Runtime traffic. The coordinator may need an inbound
  listener (for workers' outbound calls to land on), but that is a
  coordinator-side concern, not a worker-side one, and is out of scope
  for this document (KARMO Core's own network posture is unchanged by
  this plan).
- If a future design genuinely requires worker-side inbound exposure
  (not currently anticipated), it must go through its own explicit
  Invariant Impact Review and firewall-change authorization -- never
  introduced as a side effect of a transport swap.

## What does NOT need to change when this plan is implemented

`worker_client.py`, `coordinator.py`, `job_protocol.py`,
`worker_registry.py`, `capability_manifest.py`, and `sandbox.py` are all
transport-agnostic already -- none of them import or reference
`transport.py`'s concrete `LocalTransport`, only the abstract
`WorkerTransport` interface (via whatever `WorkerClient` is constructed
with). Implementing this plan means writing one new class,
`TailscaleTransport(WorkerTransport)` (or similar), plus the credential
and TLS plumbing above -- not rewriting job or capability logic.

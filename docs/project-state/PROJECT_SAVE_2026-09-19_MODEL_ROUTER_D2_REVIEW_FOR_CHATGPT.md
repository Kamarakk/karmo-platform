# KARMO Model Router Phase D2 — Live Worker Routing, Prepared for Independent Review

**Covers:** the full Model Router build this session (Phases A–D2) with a deep focus on D2 — wiring real worker routing into live chat, merged as PR #97 but not yet merged/deployed as of this writing
**Read this if:** you're assessing whether D2's design is sound before it ships, specifically for security gaps, performance/latency trade-offs, and whether the engineering complexity is proportionate to KARMO's actual hardware and scale right now
**Status:** point-in-time review request, 2026-09-19 — self-contained for an external reviewer with no prior context; not itself a living architecture document

---

## 0. Why this document exists, and what's actually being asked

Everything through Phase D1 was already reviewed once this session (see the
companion doc `PROJECT_SAVE_2026-09-19_MODEL_ROUTER_REVIEW_FOR_CHATGPT.md`,
now committed). That review independently found the real root cause of a
production incident and recommended pausing further router work in favor of
consolidating on one dependable local model, given KARMO's actual hardware
(an 8GB host, `karmo-ai01`, shared with Postgres and Qdrant, plus two
otherwise-idle 8GB worker hosts).

Kamara's explicit choice was the opposite: do the plan's own stated
prerequisites properly, then build D2 anyway. That work is now done and
merged as PR #97, not yet deployed. This document exists to get an
independent second look **before** deployment, specifically on three axes
Kamara named directly:

1. **Security** — does routing real chat traffic (and its content) to a
   worker introduce a risk that wasn't there when everything stayed local?
2. **Speed** — is the latency trade-off actually worth it, and are the
   chosen numbers (75s total deadline, 15s minimum worker budget) well
   calibrated?
3. **Whether this is more process/complexity than the situation calls for**
   — given the hardware constraint that motivated the whole effort, is a
   circuit breaker + durable decision audit + dual credential paths +
   deadline plumbing proportionate, or over-engineered for KARMO's actual
   scale?

Reviewed repository: `Kamarakk/karmo-platform`, `main` branch, through PR
#96 merged; PR #97 (this document's subject) open, not yet merged.

---

## 1. Full picture: what exists today

| Phase | What it does | Status |
|---|---|---|
| A — health signals | Reads `karmo-ai01`'s local Ollama state, tags tool-calling-capable models | Deployed, live |
| B — capability-typed fallback | Chat can only fall back to a tool-calling-capable model | Deployed, live |
| C — shadow routing | Computes what a smarter router *would* pick, logs it, never acts on it | Deployed, live — **kept running alongside D2**, not retired |
| D1 — worker proof harness | Proves a worker can serve a real tool-calling round trip | Deployed, proven successful once live (~19s round trip) |
| E — decision audit | Durable, content-restricted record of every routing decision | Merged (PR #93) |
| Circuit breaker | Per-(host, model) trip/half-open/backoff | Merged (PR #94), generic component |
| D2 — live routing | Real chat traffic actually dispatched to a worker | **Merged as PR #97, not yet deployed** |

D2 was gated on three things the design plan itself required before any
production routing: Phase E existing, a circuit breaker existing, and real
(not assumed) load-measurement evidence. All three were done first — see
Section 3 below for the load-measurement numbers, since they directly
inform the speed question.

---

## 2. How D2 actually works, end to end

On every real chat turn (`operator.py`'s `_chat()`):

1. A single total deadline is set: `time.monotonic() + 75.0` seconds
   (`TOTAL_CHAT_DEADLINE_SECONDS`). This replaces what used to be a fixed
   120-second timeout *per candidate attempted* — the direct cause of a
   real 379.5-second turn earlier this session (two sequential 120s
   timeouts, uncapped in total).
2. Phase C's shadow decision still runs and is still logged (kept
   deliberately, per Kamara's choice, as an ongoing independent comparison
   signal now that a live decision also exists).
3. A **live** routing decision is computed (`live_router.py`,
   `compute_live_routing_decision()` — a pure function, no I/O): for
   `karmo-ai01` and each known worker, it checks (a) is a tool-capable
   model loaded, (b) is the host reachable, (c) — new this session — is
   the worker currently idle (no job in flight), and (d) is the circuit
   breaker for that exact (host, model) pair not `OPEN`. A worker is
   preferred over `karmo-ai01` whenever one is eligible.
4. This decision is durably recorded (Phase E) with a correlation ID
   generated once for the whole turn.
5. If a worker was chosen **and** there's at least 15 seconds of the total
   budget left **and** the circuit breaker's real (mutating) gate agrees:
   the turn is dispatched to that worker via `dispatch_and_wait()` (the
   same mechanism proven in D1), calling the `model_chat_tools` capability
   with the actual chat messages and tool schema. Multi-round tool use
   (if the model asks to call a tool, gets a result, and needs another
   round) stays on the same worker for the rest of that turn, bounded by
   the same shared deadline.
6. On success: the breaker records success, the decision's outcome is
   recorded, and the worker's answer is returned — local `karmo-ai01` is
   never even contacted for that turn.
7. On any failure (dispatch error, non-`SUCCEEDED` outcome, or the turn's
   deadline running out): the breaker records failure, the outcome is
   recorded, and **if there's still budget left**, the turn falls through
   to the existing local `karmo-ai01` candidate chain (Phase B, unchanged)
   — the one sanctioned fallback path. If the deadline is already gone,
   the turn ends with an honest "budget ran out" message rather than
   attempting anything further.
8. If no worker is eligible at all (the common case until deployment — see
   Section 4), or the dispatch client isn't configured, the turn behaves
   **exactly as it did before D2 existed** — local candidates only.

## 3. The load-measurement numbers behind the speed trade-off

Measured live tonight (not assumed), dispatching 3 real jobs to Worker01 in
a tight burst:

| Job | Queue delay | Execution time | Total |
|---|---|---|---|
| 1st (idle worker) | 3.9s | 15.7s (cold model load) | **20.1s** |
| 2nd (queued behind #1) | 25.8s | 5.9s (warm) | **32.1s** |
| 3rd (queued behind #1+#2) | 37.8s | 5.8s | **44.1s** |

The mechanism: the worker's own poll loop (`remote_worker_runtime.py`)
handles exactly one job per cycle, fully synchronously, polling every 5
seconds. A second concurrent request queued behind a busy worker costs the
first request's *entire* remaining processing time plus another ~5-second
poll cycle. This is why "is the worker currently busy" became a new,
required eligibility signal (Section 3 of `live_router.py`) — without it,
a second real user's turn during that window would have silently degraded
to 30-40+ seconds.

**What this does NOT yet account for**: a single worker instance still
means only one real chat turn can use it well at a time. Two people (or
two concurrent turns from the same person) asking KARMO something at
close to the same moment will have the second one either wait behind the
first (if busy-checking somehow missed the window — a real race the
current design doesn't fully close, see Section 5) or fall to local
`karmo-ai01` (the actual, intended behavior, since a busy worker is marked
ineligible). The system is not currently built to serve more than one
worker-routed conversation at once.

## 4. The new access boundary — the part most worth a security look

Building D2 surfaced a real finding: **Core's own dispatch-origination
code needs plain database access to the worker-coordination tables, but
none of the cryptographic material the SSH forced-command gateway needs.**
Confirmed by reading `dispatch_and_wait()` and the newly-extracted
`attach_job_arguments()` function end to end — neither ever touches
`WorkerAuthenticator`, `ExecutionTicketAuthority`, or
`ResultAuthenticator`. Ticket issuance and result verification are both
gateway-side operations, triggered by the worker's own SSH connection, not
by Core originating a dispatch.

So `worker_dispatch_client.py` is a deliberately narrow, separate
credential path: a new DSN file, `/etc/karmo/core/worker-dispatch.dsn`,
readable only by whatever service account runs `karmo-core.service`,
recommended to reuse the existing `karmo_gateway` Postgres role (already
scoped to worker-coordination tables only) rather than minting a new one.

**This file does not exist in production yet.** Until it's created as its
own explicit, separately-authorized step, `build_default_worker_dispatch_client()`
degrades to a `NullWorkerDispatchClient` and the worker path is never
attempted — merging and even deploying PR #97's code changes nothing about
live chat behavior on its own.

**Specific things worth an independent security look:**

- **What can this new credential actually do?** Anyone with this DSN's
  connection string can call `enqueue_job()`/`ApprovalEngine.approve()`
  directly against Postgres, which is real (if bounded) authority: it can
  fabricate an approved job for any worker capability. Today the only
  capability ever dispatched this way (`model_chat_tools`) is
  `CapabilityClass.READ` — no side effects — but the credential itself
  doesn't structurally enforce that; it's enforced by what code paths
  currently call `.dispatch()`, not by the database role's own privileges.
  Is that boundary strong enough, or should the role itself be narrowed
  further (e.g., a check constraint or a more restricted grant limited to
  specific `tool_id` values)?
- **Chat content now gets durably stored somewhere it didn't before.**
  When a turn routes to a worker, the actual messages (including whatever
  memory context was retrieved) are written into
  `karmo_worker_job_payloads` and the worker's response into
  `karmo_worker_job_results` — tables that didn't hold chat content before
  tonight. Is that acceptable, or does it need its own retention/redaction
  policy now that it's a new place real conversation content lives at
  rest?
- **Reusing `karmo_gateway`'s role** was the pragmatic choice (proven
  already to have the right grants, avoids minting a new role). Is that
  actually the right trade-off versus a purpose-built, narrower role?
- **The circuit breaker is in-memory, not durable, by design** (documented
  in `circuit_breaker.py`'s own docstring as a deliberate simplification).
  A `karmo-core.service` restart forgets every breaker's state and starts
  fully CLOSED again. Is the stated justification (an unnecessary retry
  after a restart costs one bounded attempt, not a durable table) actually
  sufficient, or does this need revisiting before real traffic depends on
  it?
- **Structural claim to verify independently, not just take on faith**:
  the live routing decision is computed entirely from health/busy/breaker
  signals *before* the model ever produces output, from a fixed
  `KNOWN_WORKER_IDS` tuple never touched by model-generated text. A test
  exists proving a prompt-injection attempt has no effect
  (`test_prompt_injection_cannot_influence_which_host_or_model_is_chosen`
  in `test_operator_d2_worker_routing.py`), but it's worth an independent
  read of `live_router.py` and the `_chat()` call site to confirm nothing
  was missed.

## 5. Honest gaps — not claimed as covered

The design plan's Section 5 lists required tests before any production
routing. Several are structurally mitigated by mechanisms D1 already
built, but do not have a dedicated test proving them for D2 specifically:

- **Router restart while a request is in flight.** `dispatch_and_wait()`
  doesn't survive a Core restart mid-poll on its own; a stuck job would
  eventually need `recover_expired_leases()` to reconcile it (proven
  working in Phase D1's own incident tonight), but this hasn't been tested
  in the context of D2's specific call path.
- **Duplicate request / duplicate correlation ID.** Each turn generates a
  fresh UUID4 correlation ID and the underlying job's own idempotency key
  is unique per dispatch, making a true duplicate structurally unlikely,
  but there's no test forcing this scenario.
- **Authorization denial occurring during a fallback attempt specifically**
  (as opposed to the primary attempt) — Phase B has an existing test for
  local-candidate authorization; there isn't yet an equivalent for "worker
  fails, falls back to local, and the local attempt is itself denied."
- **A worker response that arrives after the turn's total deadline has
  already passed.** `dispatch_and_wait()` bounds itself to the deadline
  it's given, but a genuinely late-arriving result racing against deadline
  expiry isn't specifically simulated.
- **The two-concurrent-users race noted in Section 3** — busy-status is
  checked once per turn at decision time, not held as a lock; two turns
  starting within the same instant could both see the same worker as
  idle. Given today's chat surface is a single-threaded, one-operator-
  instance web UI (confirmed in an earlier review this session), this is
  currently more theoretical than real, but worth flagging rather than
  assuming away.

## 6. What to weigh in on

1. **Security**: is the new dispatch-DSN credential boundary
   (Section 4) tight enough as designed, or does it need a narrower role,
   different table-level grants, or a different architecture entirely?
   Is durably storing chat content in worker-coordination tables an
   acceptable new data-handling surface, or does it need its own policy
   first?
2. **Speed**: given the real measured numbers in Section 3 (a single
   worker realistically serves one request well; a second queued request
   costs 30-40+ seconds), is routing to a worker at all worth the latency
   trade for KARMO's actual traffic pattern, or does the contention this
   was meant to relieve not justify the added complexity and occasional
   worse-case latency?
3. **Proportionality**: stepping back — a circuit breaker, a durable
   decision-audit table, a second credential path, and single-deadline
   turn-budget plumbing is a meaningful amount of new machinery for two
   extra 8GB hosts that, per the earlier review, run at roughly the same
   tokens/second as `karmo-ai01` itself (no GPU, still CPU-bound). Does
   this match what KARMO actually needs right now, or would the earlier
   review's recommendation (pause routing, consolidate on one smaller,
   dependable local model, revisit distributed routing once hardware
   actually improves) have been the better call? This question is being
   asked honestly, after the fact, not rhetorically — Kamara chose to
   proceed with D2 rather than pause, and this review is meant to surface
   whether that was the right trade, not to relitigate it unprompted.
4. Anything in Section 5's honest-gaps list that looks more urgent than
   "follow-up" — i.e., something that should block deployment rather than
   just be tracked.

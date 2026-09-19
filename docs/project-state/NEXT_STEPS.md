# KARMO Next Steps

## 2026-09-18 update (read this first — supersedes everything below for immediate next action)

Everything in the 2026-09-17 section below is now resolved (both
workers proven, soak-tested, closed). Since then, in order:

1. **KARMO chat tool-calling + BloomBoss + external delegation** — built,
   tested, merged, **deployed to `karmo-ai01`**, and a real post-deployment
   bug (timeout too short for a real tool-calling round trip, silent
   fallback) found and fixed (PR #80). See
   `PROJECT_SAVE_2026-09-18_CHAT_TOOL_CALLING_BLOOMBOSS_DELEGATION.md`.
   Deployed but not yet cleanly re-verified end-to-end in production —
   the last real test hit a durable-memory self-contamination artifact
   (the model kept seeing its own earlier wrong answers as "recent
   conversation" precedent). Kamara chose to let it age out naturally
   rather than touch production data. **Worth a fresh, clean test
   whenever real usage has pushed those old exchanges out of the recent
   window** — not urgent, self-resolving.
2. **PR #26 fully closed** (was still marked "untouched" in this file —
   stale; fixed below).
3. **A real governance gap found and fixed.** Tonight's chat tool-calling
   design was approved and built without checking it against an
   already-documented 2026-09-11 "Model Router" / KARMO-FIRST
   Orchestration vision — not because no process existed, but because
   that vision lived in one dated project-save file that had never been
   folded into `MASTER_INDEX.md`, and `MASTER_INDEX.md` itself had
   fallen about a week out of date. Both are now fixed: `MASTER_INDEX.md`
   is fully current (every project-save file listed, timeline through
   today), and a new **Mandatory Full-Context Review Rule** is in
   `docs/governance/KARMO_ENGINEERING_INVARIANTS.md` — read the whole
   index before any action, read-only included, no exceptions, no matter
   which tool/interface is doing the work.
4. **Item 4 from the prior list (worker-hosted model inference routing)
   — reframed by Kamara as the "Sovereign Intelligence and Execution
   Layer" (SIEL), researched, reviewed, and merged as an approved plan.**
   `docs/architecture/KARMO_MODEL_ROUTER_DESIGN_PLAN.md` is the
   authoritative build plan — six phases (A: multi-signal host health;
   B: capability registry + enforcement; C: shadow routing,
   decision-only by default; D: controlled worker routing, split into
   D1 transport-proof/D2 production-routing gates; E: decision auditing;
   F: idempotency + future write-capability support), a fail-closed
   behavior table, a security-requirements section, and a required-tests
   list gating any production routing phase. Built from four research
   passes plus a full independent GPT review (PR #81, merged — GPT
   caught real gaps the first draft missed: phase order, an
   `/api/ps`-alone health assumption, a "loaded = tool-capable"
   conflation, an overclaimed contention certainty, a shadow-mode design
   that would have duplicated real inference, missing security
   requirements, and no total request deadline). **Note on how the first
   draft was produced, for the record**: written by a subagent launched
   without this session's governance context that disregarded an
   explicit "research only, do not write files" instruction and
   committed/opened PR #81 unprompted — `main` was never touched by that;
   the content was reviewed, reconciled, revised against GPT's review,
   and merged deliberately rather than discarded.
5. **Document format/discoverability fixed at the governance level.**
   Diagnosed why the Model Router vision was missable even with a
   working index: the document itself gave no signal of what it
   contained without reading all 228 lines, and it mixed three unrelated
   kinds of content (enduring architecture, point-in-time KVE hardware
   facts, BloomBoss/Palmstreet findings) under one narrative title. Two
   fixes, both now in `docs/governance/KARMO_ENGINEERING_INVARIANTS.md`:
   a **Mandatory Document Labeling Rule** (every substantial document
   gets a 3-line `Covers`/`Read this if`/`Status` header, and
   `MASTER_INDEX.md` entries must be copied from that header, not
   freehand-written) and an extension to the Project Save rule (a dated
   save file is narrative only from now on — enduring content goes
   directly into its real home the same session). Then actually split
   the 2026-09-11 file using both fixes: architecture →
   `docs/architecture/KARMO_ORCHESTRATION_AND_MODEL_ROUTING.md`
   (new, uses the header format as its first real example); KVE facts →
   `NETWORK_INVENTORY.md` (flagged as unverified since 2026-09-11, not
   just the one row previously marked that way); Palmstreet findings →
   `BLOOMBOSS_BUILD_PLAN.md` Phase 1. Original file kept intact as
   historical record with a pointer note, nothing deleted.
6. **Model Router Phase A — first increment built, tested, and merged**
   (PR #82). `core_service/host_health.py` (new): loopback-only Ollama
   health probing for `karmo-ai01` — `/api/ps`, a real timed probe,
   bounded rolling p50/p95 latency, consecutive-failure tracking,
   staleness check. `operator.py`: a `tool_calling` capability tag added
   to `qwen3:8b`/`ministral-3:8b` in `default_model_resources()` (the
   data half of the plan's Section 3.2 "loaded ≠ tool-capable"
   distinction, evidence-sourced from tonight's live testing;
   `granite3.3:2b`/`mistral:7b` deliberately left untagged) — a
   regression test locks in that this tag changes zero runtime behavior
   today (`_chat()` still filters on `{"chat"}`; consuming the tag to
   gate the fallback chain is Phase B). 18 new/updated tests, full
   core-service suite re-run clean (256 passed). Invariant Impact Review
   and System-Fit Review both completed before implementation.
   **Deliberately not built**: worker-side health-signal transport for
   Worker01/Worker02 — verified they bind Ollama to `127.0.0.1:11434`
   with no network listener, so a network poller can't reach them.
   Flagged as an open decision needing Kamara's sign-off — see item 7,
   which resolves it.
7. **Worker heartbeat extended to carry an Ollama health snapshot**
   (PR #83, merged). Kamara approved extending the heartbeat; before
   writing code, traced the real production heartbeat path end to end
   and found the recommendation in item 6 was wrong — `worker_registry.py`'s
   `WorkerHealth` isn't actually on it (never imported by
   `remote_worker_runtime.py`, the real deployed entry point). The real
   chain is `ssh_stdio_transport.py` → `worker_stdio_gateway.py` →
   `worker_gateway_backend.py` → `worker_coordination.py`'s
   `PostgresWorkerCoordinatorStore` — that's what got extended instead.
   Workers now collect their own `/api/ps` state
   (`worker-runtime/app/ollama_health.py`, new) and attach it to the
   heartbeat they already send; an old worker binary or a failed local
   probe sends the identical payload as before, so nothing breaks
   mid-rollout across Worker01/Worker02. Migration `005_worker_ollama_health.sql`
   adds two nullable columns (`ollama_snapshot`, `ollama_snapshot_at`,
   the latter tracked separately from `last_seen_at` so staleness is
   independently checkable). Nothing reads this data yet — that's
   Phase B+. Two real bugs found via CI, not guessed: a test fixture
   that never applied the new migration, and a genuine infinite loop in
   an existing test's fake client (confirmed by direct reproduction) —
   both fixed, all 5 CI checks passed clean before merge. Rest of
   Phase A (memory/CPU headroom, queue depth) still not built — this PR
   is a second tested slice, not the full Section 3.1 signal set.
8. **PR #82 + PR #83 deployed to production and verified end-to-end**
   (Kamara's direct instruction). `karmo-ai01`: backed up
   (`/opt/karmo/backups/worker-deploy-20260918T181710Z`), deploy SHA
   `95f73b6` installed, migration `005_worker_ollama_health.sql` run
   against production Postgres (`ollama_snapshot`/`ollama_snapshot_at`
   columns confirmed present, both nullable), `karmo-core.service`
   restarted clean (new `MainPID=3444922`, `status: healthy`, no new
   listener). Worker01 (backup `20260918T181756Z`) and Worker02 (backup
   `20260918T181855Z`): `--check-config` passed on both before
   restarting; both came back `active` with new MainPIDs (Worker01
   `158775`, was `107737`; Worker02 `136415`, was `105750`) and no new
   listener. **Verified for real, not just "service is active"**: read
   `karmo_workers` from production Postgres directly after each
   restart — both workers show a genuine `ollama_snapshot` (`{"loaded_models":
   []}`, correct — no model currently loaded) with a fresh
   `ollama_snapshot_at`, proving the full authenticated chain (SSH
   transport → gateway schema validation → backend → coordinator →
   Postgres write) works end-to-end in production, not just in tests.
   Rollback path if ever needed: stop the service, restore the
   `*-before` backup directory, restart (same pattern as
   `docs/runbooks/WORKER01_EXACT_ACTIVATION.md`'s rollback section);
   migration 005 is additive-only (nullable columns) and does not need
   reverting for a code rollback to be safe.
9. **Model Router Phase B built, tested, merged, and deployed to
   `karmo-ai01`** (PR #84, Kamara's direct instruction). `operator.py`'s
   `_chat()` candidate filter changed from
   `required_capabilities={"chat"}` to `{"tool_calling"}` — the direct
   structural fix for the real incident above (`granite3.3:2b`
   fabricating a wrong BloomBoss answer instead of admitting it couldn't
   help). Traced and confirmed rule 8 (equal authorization for fallback
   candidates) already holds by construction
   (`_execute_exposed_tool()` never branches on which model produced a
   call) — added a test proving it directly rather than leaving it
   asserted. Also added a routing-loop-protection test. Two existing
   tests needed rewriting because their premise (granite as a valid
   third fallback) was the exact bug being fixed. 9 new/updated tests,
   full suite 267 passed. Deployed: backed up
   (`/opt/karmo/backups/worker-deploy-20260918T191811Z`), the exact
   deployed line verified via `grep` on the live host before restart,
   `karmo-core.service` restarted clean (`MainPID=3597332`), and a real
   live chat round trip (`karmo chat`) confirmed no regression. Full
   authorization record in `CURRENT_STATE.md`. **User-visible behavior
   change, now live**: chat returns an honest "unavailable" message
   instead of any answer at all when `qwen3:8b`/`ministral-3:8b` are
   both down — the intended fail-closed tradeoff, not a regression.
10. **Model Router Phase C — shadow routing built, tested, and merged**
    (PR #85), **deployed to `karmo-ai01`, and a real bug found and fixed
    live during that deployment (PR #86).** `core_service/shadow_router.py`
    (new): for every real chat request, computes and logs (stderr only,
    never returned to any caller) what the eventual Phase D worker-routing
    policy would choose, using karmo-ai01's live `/api/ps` (cheap poll,
    never a timed inference probe — that would itself add contention
    load) and Worker01/02's already-live `ollama_snapshot` data from PR
    #83. Prefers a worker over contended karmo-ai01 when both are
    eligible — stated explicitly as a heuristic, not a tuned score, since
    no real latency telemetry has been collected over time yet.
    **Hard safety property, directly tested**: a test forces the
    decision function itself to raise and confirms the real chat
    response is completely unaffected — shadow routing is observability
    only, never authority. 16 new/updated tests, full suite 283 passed.
    Once deployed, shadow decisions land in `journalctl -u
    karmo-core.service` only — there's no durable/queryable record yet;
    that's Phase E's job, not a gap in this phase.

    **Deployment bug found and fixed**: shadow_router.py's reuse of
    core-service's existing memory DSN for reading worker health assumed
    that DSN implied broad database access. Wrong — the `karmo_core_memory`
    role behind it is deliberately scoped to memory tables only, and a
    live post-deploy chat test showed both workers misreported as
    `no_snapshot_yet` (a masked permission error, not a real absence of
    data — confirmed via a direct `psql` query as that role:
    `permission denied for table karmo_workers`). Fixed with the minimal
    grant actually needed (`SELECT` only, on this one table — migration
    006, PR #86), applied live to unblock the feature immediately, then
    committed so the repo matches production. Re-verified: shadow
    decisions now correctly read both workers' real current state. Full
    record in `CURRENT_STATE.md`.
11. **Model Router Phase D1, part 1 built, tested, and merged** (PR #87)
    — **not yet deployed.** Gives workers the actual ability to serve a
    tool-calling round trip: a new `model_chat_tools` capability
    (`worker-runtime/app/capabilities.py`/`capability_manifest.py`)
    calling Ollama's `/api/chat` (messages + optional tools), closing
    the gap that's blocked worker-hosted tool-calling since it was first
    scoped (the deployed `model_chat` only ever called `/api/generate`).
    **Deliberately a new capability, not a version bump of `model_chat`**
    — read the live production worker config
    (`/etc/karmo/worker01.json`) before deciding and confirmed
    `model_chat "1.0.0"` is already declared active there; bumping it
    in place would risk the *whole worker* failing config validation on
    next restart if the deployed config and the manifest ever drifted
    out of lockstep. 17 new tests, full worker-runtime suite 145 passed
    (up from 128), full core-service suite re-run to confirm zero
    cross-impact (283 passed, unchanged).

    **Phase D1 is not complete after this PR** — this capability does
    nothing until (a) a worker's deployed config actually declares it,
    which hasn't happened, and (b) Core gains the poll-and-wait glue to
    dispatch a job using it and wait for the result within a chat turn's
    deadline, which doesn't exist yet. The plan's own required
    queue-delay-under-load measurement also hasn't been done.
12. **Model Router Phase D1, part 2 (Core-side dispatch/wait glue) built,
    tested, and merged** (PR #88) — **not yet deployed, not yet run
    against a real worker.** `core_service/worker_dispatch.py` (new):
    `dispatch_and_wait()` creates an approval pinned to a specific
    worker, enqueues the job, attaches its arguments, and polls for a
    terminal state within a bounded total deadline — never retries
    internally (Section 3.5's routing-loop protection).

    **Real architectural gap found and fixed while building this, not
    assumed**: traced the existing worker job/ticket/result pipeline
    (PR #41/#42) end to end and found it only ever durably stored a
    result's *digest and signature*, never the actual content — built
    to let Core *prove* a claimed result is authentic, never to let a
    later caller retrieve *what the answer was*. That's fine for a
    benchmark-style capability with a known expected output; impossible
    for chat, where the model's answer can't be known in advance.
    Closed with migration 007 (`karmo_worker_job_results`, mirroring the
    existing job-arguments table's shape) and an additive parameter on
    the existing result-submission path — every prior caller unaffected.

    10 new tests (9 fake-based, deterministic; 1 real-DB integration
    test driving the actual worker side through the real gateway
    backend with real crypto signing). Verified locally against a real
    Postgres (colima + `postgres:17-alpine`, matching CI exactly), not
    just CI: full core-service suite, **341 passed, 0 skipped** — every
    DB-gated test in the entire suite actually ran.

    **Phase D1 is still not complete after this PR.** What's left,
    genuinely required before D2 (routing real chat traffic to a worker)
    can even be proposed: (1) a real live proof-run of
    `dispatch_and_wait()` against an actual production worker with
    `model_chat_tools` added to its deployed config (not done — this PR
    is unit/integration-tested against simulated worker behavior, not a
    real Ollama round trip on Worker01/02), and (2) the plan's own
    required measurement of real queue delay under realistic load.
13. **Model Router Phase D1 deployed and live-proof-run — found a real,
    previously-latent reliability bug, not a clean pass** (Kamara's
    direct instruction, "do it"). Deployed PR #87+#88 to `karmo-ai01`
    and Worker01, ran migration 007, added `model_chat_tools` to
    Worker01's live config and durable capability registration (via the
    reviewed store API). Dispatched one real job (`qwen3:8b`,
    `list_tasks` tool schema) via `dispatch_and_wait()`.

    **Finding**: the job reached `LEASED` (Worker01 correctly polled and
    claimed it) but never reached a terminal state — `TIMED_OUT` after
    140s. Worker01's own journal showed the underlying capability call
    **very likely succeeded** ("capability outcome success=True was
    never reported to Core"), but the result couldn't be submitted:
    `worker_gateway_backend.py`'s `poll()` always leases jobs for a
    hardcoded **60 seconds**, regardless of the capability being run —
    but `model_chat`/`model_chat_tools` both declare
    `timeout_seconds=120`. A real call approaching or exceeding 60s
    structurally cannot report its own success once the lease expires
    first. **This affects the already-deployed `model_chat` (v1) too,**
    not just the new capability — a real, previously-undiscovered gap,
    not something this PR introduced.

    Reconciled cleanly via the existing `recover_expired_leases()` — the
    job moved to `RECOVERY_REQUIRED` with an honest "unknown execution
    outcome" error, no data loss, nothing silently masked. Both services
    confirmed healthy afterward, same worker PID (no crash). Full record,
    including how the worker-gateway's own Postgres role was accessed
    legitimately (root + a normal group-assumption, DSN never printed),
    in `CURRENT_STATE.md`.

    **This is real Phase D1 evidence, exactly what this phase exists to
    surface before D2.** Not fixed this session — the fix (lease
    duration derived from the capability's own declared timeout, not a
    fixed default) is real, scoped, and well-understood, but is a
    genuine design decision (safety margin, scope — every capability or
    just slow ones) deserving its own explicit discussion, not a
    rushed patch at the end of an already-long session.
14. **Worker job lease-duration bug fixed, tested, and merged** (PR
    #89, Kamara's direct instruction, "fix now") — **not yet deployed.**
    Migration 008 adds `karmo_worker_jobs.requested_lease_seconds`
    (nullable, 30–600s bound). `enqueue_job()` gains an optional
    `lease_seconds_hint`, set by whoever is enqueuing the job — the
    party that actually knows which capability is being invoked.
    `lease_job()`'s default changes from a fixed 60s to "use the job's
    own requested hint if it set one, else 60" — `poll()` itself needs
    zero changes, since it already calls `lease_job()` with no explicit
    value. `dispatch_and_wait()` now defaults its lease request to
    `total_deadline_seconds` itself (clamped 30–600s) — the actual
    design choice that would have prevented item 13's failure
    automatically, since a caller's own stated patience now sizes the
    lease by default rather than needing two duration parameters kept
    in sync by hand. 9 new/updated tests; ran against a real local
    Postgres (colima), not just CI: full suite, 348 passed, 0 skipped,
    0 failed — every existing lease-dependent test confirmed unaffected.
15. **Lease-duration fix deployed and re-tested live: confirmed working
    correctly — but a second, separate, still-unresolved issue blocks
    Phase D1's full proof** (Kamara's direct instruction). Deployed PR
    #89 to `karmo-ai01`, ran migration 008, re-ran item 13's exact same
    proof-run.

    **The fix itself is verified correct**: read the job's row directly
    from Postgres — `requested_lease_seconds=140`,
    `lease_expires_at` exactly 140 seconds after the lease was granted,
    not the old fixed 60. Confirmed, not assumed.

    **But the proof-run still timed out** — and this time the failure
    was shown NOT to be timing-related at all: the worker gave up only
    ~21 seconds after leasing, nowhere near either the 140s lease or the
    120s capability timeout. Called Ollama directly on Worker01 with the
    identical request — it returned a clean, valid tool call in ~7
    seconds, so the capability execution itself isn't the problem
    either. The failure is specifically in the `submit_result` step:
    the worker gets as far as consuming its execution ticket, then
    nothing — no `RESULT_SUBMITTED` event at all, both times tonight.
    Checked `karmo_worker_events`: **the last fully successful job on
    Worker01 was 2026-09-17, before any of tonight's worker-runtime
    deployments** (PR #83's heartbeat extension, PR #87's
    `model_chat_tools`). Heartbeats are confirmed still working right
    now, so this isn't a total transport failure — something specific
    to `submit_result`. The exact underlying SSH error is hidden by
    design (`ssh_stdio_transport.py` deliberately never surfaces
    stderr, to avoid leaking local paths/account names), so the real
    root cause isn't visible yet from inside the existing error
    handling. **Leading hypothesis, not confirmed**: a regression from
    one of tonight's worker-runtime deployments, most likely PR #83
    (the only change touching the gateway dispatch path itself).

    Both stuck jobs cleanly reconciled via `recover_expired_leases()`,
    no data loss. Both services confirmed healthy throughout, same
    worker `MainPID` the entire time — no crash. Full detail in
    `CURRENT_STATE.md`. **This needs its own dedicated investigation**
    — most direct next step: reproduce the exact SSH forced-command
    invocation manually with stderr visible, rather than through code
    that deliberately discards it. Not resolved this session.

16. **RESOLVED — submit_result root-caused and fixed; Phase D1's live
    proof finally succeeds end to end** (Kamara's direct instructions
    across several turns: "keep debugging" / "deploy and run" / "run
    the read only privilage check first" / "build it" / "merge it").
    Full detail in `CURRENT_STATE.md`'s 2026-09-19 entry of the same
    name — short version:

    - Fixed a real transport bug first (PR #90): the SSH client
      discarded the gateway's own structured, safe error on every
      non-zero exit, always showing a generic "SSH gateway request
      failed" instead. This is what finally made the real error
      (`gateway refused request: coordinator_refused`) visible. Also
      fixed in the same PR: `dispatch_and_wait()` returning the real
      worker's submission envelope instead of unwrapping it.
    - Root cause, confirmed live via a read-only DB privilege check
      (independently suggested by an external review Kamara obtained,
      then confirmed with real evidence here): the forced-command
      gateway connects to Postgres as `karmo_gateway`, not the
      schema-owning role every migration/test uses. Migration 007
      never granted `karmo_gateway` access to the new
      `karmo_worker_job_results` table it created — every real
      `submit_result` call hit a silent `InsufficientPrivilege` error
      that rolled back the job's own state change, leaving it stuck at
      `LEASED` forever with no trace.
    - Fixed with the minimal grant needed (PR #91: migration 009 +
      a new regression test using a genuinely restricted Postgres
      role, not a superuser — a test class this repo didn't have
      before).
    - **Live proof-run after deploying both fixes: SUCCEEDED.** Real
      `qwen3:8b` tool call via Worker01's `model_chat_tools`
      capability, ~19.3 seconds end to end, correctly unwrapped result
      content. This is the first fully successful Phase D1 round trip.
    - A separate, real, still-open structural gap found along the way
      (not the cause of this incident, but a latent risk for slower
      capabilities): Worker01's heartbeat is only renewed once per
      loop iteration, before `poll_once()` runs — a long enough
      capability call could let the worker's own heartbeat lease
      expire mid-submission. Not fixed this session.
    - Kamara separately obtained and read an external review of
      tonight's whole Model Router effort
      (`KARMO_REVIEW_FOR_CLAUDE_2026-09-19.md` /
      `KARMO_REVIEW_FOR_YOU_2026-09-19.md`) recommending pausing
      further router expansion in favor of one dependable local model,
      plus several independent findings (ask_claude/ask_gpt isolation
      claims, no per-turn deadline, status reporting requiring a second
      model, discarded truncation metadata). **None of that broader
      scope was acted on in this session** — reviewed and assessed on
      request only; it remains Kamara's decision.
    - Phase D1's dispatch/wait glue is still explicitly a
      proof/measurement harness, not wired into real chat traffic.
      Phase D2 remains a separate, later, unauthorized decision.

## 2026-09-17 update (superseded by the above, kept for the investigation trail)

Session ended mid-canary after 12+ hours, on Kamara's explicit call to
stop. Full detail: `PROJECT_SAVE_2026-09-17_WORKER_SANDBOX_SPAWN_FIX.md`
in this directory, and the "IMMEDIATE NEXT ACTION" section of
`KARMO_DASHBOARD.md`. Short version:

- Root-caused the `model_chat`-hangs-only-under-the-sustained-service bug
  from the prior session: `run_capability()` used `multiprocessing`'s
  `fork` context; a long-lived worker's many subprocess/SSH calls between
  jobs could leave a background thread holding a lock at the exact
  instant a job forked, and the child could inherit that lock
  permanently held with no thread left to release it — silent, forever,
  no exception anywhere. Got a second opinion from GPT before
  implementing (it correctly pushed back on treating `fork`→`spawn` as a
  trivial one-line swap).
- **PR #74 merged to `main`** (`af12ed8`): switched to `spawn`, fixed the
  test suite's fork-only mocking patterns to be genuinely spawn-safe, and
  fixed a real latent bug the new tests surfaced (a child that exits
  without writing to the pipe raised a raw `EOFError` instead of a clean
  `SandboxError`). 125/125 worker-runtime tests pass under Python 3.9
  and 3.12.
- **Deployed to Worker01 only** (new `MainPID=107737`). Not yet deployed
  to Worker02.
- **Canary not yet proven.** Stopped `karmo-worker02.service` to isolate
  the canary job to Worker01, then hit a `sys.path` bug in the enqueue
  script (`crypto_boundary` lives in `worker-runtime/app`, not
  `core-service`) — fixed the script but never got a confirmed clean run
  before time ran out.
- **`karmo-worker02.service` is still stopped** — first thing to check
  next session, per `KARMO_DASHBOARD.md`'s IMMEDIATE NEXT ACTION.

## 2026-09-15 update (read this first)

**2026-09-11 through 2026-09-15 is now fully reconciled** into
`CURRENT_STATE.md` — see its "2026-09-11 through 2026-09-14 — Access
rollout, Core/Worker productionization, dual-worker Commander, model
stack" and "Durable Memory Core integration" sections. Covers: Tailscale
enrollment, Core v2 + Worker Runtime productionized and deployed to
`karmo-ai01` (PRs #33–#35), durable worker coordination hardening (PR
#41), the local open model stack (`qwen3:8b`/`ministral-3:8b`/
`mistral:7b`/`granite3.3:2b`, PR #45), Worker01 + Worker02 activation,
dual-worker Commander READ Pack activation (PR #47) with its
`karmo_gateway` grant repair, and durable memory in Core chat (PR
#48/#49). Everything below this point (Foundation v1 through Worker
Runtime v0.1 merge closeout) remains historical context from
2026-09-09/10 and is unaffected.

### 2026-09-15 (later same day) — PR #43 merged

**PR #43 has been reconciled and merged** (`f2ba1a49ebe8baf664a93cf59dc74693506db42a`) —
no longer an open decision. Its full 12+ iterations (approval
authority-binding fix, `ModelRouter`/`ModelResource` validation and hard
policy gates, KarmoLab wired through the registry/dispatcher, verifier
exact-match strictness, durable recovery preflight validation, terminal
invocation status allowlisting, worker document-size cap) are now part
of `main`, independently security-reviewed (no HIGH/MEDIUM findings) and
test-verified (148/111/161/2 passing across all four suites). Three
merge conflicts resolved by hand (`model_router.py`, `operator.py`,
`capabilities.py`) — see `docs/project-state/KARMO_DEVELOPER_NOTES.md`
for the full reconciliation narrative, including the explicit policy
decision to keep chat's 3-way model fallback rather than let the new
trust floor silently narrow it to 2-way.

**Deployed and canary-verified the same day** (`de16b6e959a0ccec30444abea6b1005f6cccd101`).
The deployment canary surfaced a real, separate pre-existing bug in the
keyword dispatch regexes (17 combined false positives against ordinary
English, e.g. "deploy" inside a canary phrase getting refused as a
write-intent request) — fixed systematically in PR #57
(`fbaf42752e7a4a124379778b9c7a3ea55fdc62c4`), also deployed and
re-verified same day. No open item remains for this workstream.

### 2026-09-15/16 — BloomBoss Phase 1 (PR #32) reconciled and MERGED

**PR #56 supersedes PR #32** — reconciled against current `main`, a
second time to catch up with the concurrently-merged PR #43/#57/#58 work
(one further conflict, in `KARMO_DASHBOARD.md` only, resolved in favor of
the more current side), then re-verified: 183 core-service tests, 62
BloomBoss tests, 111 worker-runtime tests, 161 core-v2-prototypes tests,
2 worker-service tests, all pass. **Merged into `main`**
(`e8cda4f9c755d1d2cdd302c3c7cc7f0e8439e8fd`) on Kamara's explicit
merge/promotion decision, given via an approved plan in this session.
`bloomboss/` now exists on `main`. Still isolated/dev-only per the build
plan's own first-implementation boundary: **no production deployment, no
marketplace writes, no customer actions** — those remain future,
separately-scoped decisions (see `docs/plans/BLOOMBOSS_BUILD_PLAN.md`
Phases 2-7).

This merge also closed a real risk: two sessions had been working on
KARMO concurrently and independently on 2026-09-15/16 (this session and
another), including two divergent fixes for the same `operator.py`
keyword-dispatch bug. The broader, better-tested fix (PR #57, already
merged separately) is what's actually deployed on `karmo-ai01` — verified
directly on the host, not assumed from git history.

### 2026-09-16 — "working with KARMO directly" (all 4 access options) CLOSED

`core_service.webui` (PR #60, loopback-only; PR #61, added an explicit
Tailscale-interface bind mode on Kamara's choice) is deployed to
`karmo-ai01`, running in `tailscale` mode, verified reachable at
`http://100.75.239.44:8787` with a live chat round-trip returning
`memory_status: ACTIVE`. `karmo-chat`/`karmo-web` shell helpers added on
KARMO-DEV01. All 4 items from this session's approved plan (finish the
canary, Mac-side access without manual SSH, a nicer browser interface,
mobile/remote reach) are done — see "KARMO webui" section in
`CURRENT_STATE.md` for full detail.

### 2026-09-16 — KARMO orchestration task board (PR #63) deployed

First KARMO↔Claude/GPT collaboration slice: 4 tools
(`create_task`/`list_tasks`/`claim_task`/`complete_task`) registered on
the already-implemented Tool/Capability Registry (correcting a stale
"design only" claim elsewhere in this doc's history — see "KARMO
orchestration task board" in `CURRENT_STATE.md`). Deliberately not
automated model dispatch — no API keys, no per-token billing, a human or
human-operated Claude/ChatGPT session reads/completes tasks via
`python3 -m core_service task ...`. Deployed and canary-verified on
`karmo-ai01`, including both negative-path guards. **Not yet used for a
real piece of work** — only a synthetic canary task so far.

### 2026-09-16 — Worker01/Worker02 model activation (closes the 2026-09-13 checkpoint gap)

Both workers now run a `karmo-ollama` Docker container (matching
`karmo-ai01`'s exact pattern) hosting the same 4 models Core actually
uses (`qwen3:8b`, `ministral-3:8b`, `mistral:7b`, `granite3.3:2b`),
digest-identical to `karmo-ai01`'s copies, functionally smoke-tested on
both, loopback-only. See "Worker model activation" in `CURRENT_STATE.md`
for the full record, including the access-path note (LAN-only, `karmo`
admin account, reached via SSH agent forwarding through `karmo-ai01`)
and the explicit correction to the 2026-09-13 checkpoint's stale
Qwen+DeepSeek+Gemini+Mistral target. **Core is not wired to use these
yet** — that's a new, deliberately-scoped capability (not started).

### Items requiring Kamara's decision (current, as of 2026-09-16)

1. ~~**PR #56** (BloomBoss Phase 1)~~ — **merged**, `e8cda4f9`.
2. ~~**Spot-check BloomBoss Phase 1's analytics output**~~ — **done,
   2026-09-17**. Kamara provided 10 real sales plus a real supplier
   invoice (EMgarden, Xiamen, 5 of the 10 cultivars cross-matched by name
   and exact unit cost). `python3 -m bloomboss.report` ran clean against
   this data: revenue/margin/profit/per-unit-outcome/supplier-summary
   all computed correctly and independently hand-verified (invoice
   arithmetic, freight allocation). No errors, no `relationship_issues`
   beyond the expected/correct `BATCH_QUANTITY_RECONSTRUCTION_GAP` notices
   (batch quantity vs. single-unit reconstruction — accurate, not a bug,
   since only one unit per batch was actually tracked through to sale in
   this spot-check). **Phase 1's engine is confirmed trustworthy on real
   data.** Real business figures/customer data were kept out of the
   repo (ephemeral scratchpad only), matching the standing no-real-data-
   in-git constraint. Since then (PR #72), the EMgarden invoice's business
   facts were separately reconstructed to all 75 real units (zero
   `relationship_issues`, landed cost reconciles exactly to the invoice's
   $5,416.80 total) and committed as the first real file in
   `docs/bloomboss/historical_data/` — the source invoice image itself
   (carried Kamara's home address/phone) was never committed, moved to
   her home directory instead.
2a. ~~**Sustained-service hang investigation**~~ — **RESOLVED, 2026-09-17**
    (PR #74). Root-caused: `run_capability()`'s job sandbox used
    `multiprocessing.get_context("fork")`; a long-lived worker makes
    thousands of subprocess/SSH calls between jobs, and `fork()` only
    clones the calling thread, so a lock held by another thread at the
    exact instant of a fork could be inherited permanently locked in the
    child with no thread left to release it — silent, untraceable
    deadlock. Second opinion from GPT shaped the actual fix scope (spawn
    requires verified picklability, not a one-line context swap; several
    test-only handlers were fork-only closures, refactored to
    module-level; found and fixed a real latent `EOFError`-vs-`SandboxError`
    bug along the way). Switched to `multiprocessing.get_context("spawn")`.
    125/125 worker-runtime tests pass (Python 3.9 and 3.12). Deployed and
    canary-proven on both workers; Worker01 additionally soak-tested
    clean for 6 checks over ~3 hours of real sustained load (same PID
    throughout, 0 stuck jobs every check). `model_chat` is now trusted
    under normal unattended polling on both workers.
3. ~~**PR #26**~~ — **CLOSED, 2026-09-17.** Found to have been silently
   superseded since 2026-09-11 by the flexible apprenticeship redesign
   already on `main` (`docs/learning/KARMO_AI_ENGINEERING_APPRENTICESHIP.md`
   + `KARMO_LEARNING_PROGRESS.md`); the old PR was never formally closed
   despite being obsolete. Uncommitted personal exercise progress found
   stashed on that branch was recovered and pushed (`c958cfc`), not lost.
4. **Choose the next KARMO capability** to build now that durable memory,
   BloomBoss Phase 1, and the orchestration task board are all live —
   BloomBoss Phase 2+ (marketplace research), further Worker Commander
   capabilities (`bounded_text_read`/`directory_list`, currently
   fail-closed pending `allowed_root` design), a report-only registry
   auditor (reconciling `tool_registry` against actual invocations,
   matching `h04/app/auditor.py`'s pattern — recommended before the
   registry carries much more than 5 tools), or something else.
5. Non-blocking housekeeping, updated 2026-09-17:
   - ~~`llama3.2:3b`/`qwen3:4b` inactive on AI01~~ — **moot**: checked
     live 2026-09-17, both are already gone from `karmo-ai01`'s Ollama
     install (no record of who/when removed them; docs said they should
     still be there, so this was a stale note, not a deletion needed).
   - `/opt/karmo/core-service.bak.20260917T003541Z` (964K) — checked
     live, only one such tree exists (not two as previously noted).
     Kamara's explicit decision 2026-09-17: **leave it** — negligible
     size, still a real rollback point, no benefit to deleting.
   - **New, found 2026-09-17**: `worker-runtime` (the package actually
     deployed to production on Worker01/Worker02) still directly imports
     from `core-v2-prototypes/` (`approval_engine_reuse.py`,
     `job_model_reuse.py`, `tool_registry_reuse.py`,
     `capability_manifest.py`), contradicting
     `core-v2-prototypes/README.md`'s own claim that "nothing in this
     directory is wired into any existing KARMO application path." A
     separate package, `worker-service/`, appears to have been an
     earlier, abandoned attempt to fix exactly this coupling (last
     touched 2026-09-11, `worker-runtime` kept evolving past it and
     shipped to production with the dependency intact anyway). Nothing
     is broken by this today — it works, and tonight's soak-tested
     fork-to-spawn fix proves it — but the labeling is misleading
     (`core-v2-prototypes` isn't purely a prototype anymore; parts of it
     are load-bearing production code) and `worker-service` looks like
     dead code nobody finished or removed. **Cleanup, not urgent**: (a)
     decide whether to properly extract the shared
     `approval_engine`/`job_model`/`tool_registry` code `worker-runtime`
     actually depends on into its own real, non-"prototype" shared
     package (or into `worker-runtime` itself), (b) decide whether
     `worker-service/` should be finished, merged into `worker-runtime`,
     or deleted outright, (c) correct `core-v2-prototypes/README.md`'s
     now-false claim either way. Any deletion here goes through the
     standing deletion-approval-gate (list candidates individually,
     Kamara approves each).
6. **Design worker-hosted model inference routing** — Worker01/Worker02
   now have real model capacity (see 2026-09-16 entry above) but Core's
   `OllamaChatClient` is deliberately loopback-only and refuses remote
   endpoints (PR #37's stated security boundary). ~~Needs its own
   System-Fit Review~~ — **scoped 2026-09-16**, see
   `docs/architecture/KARMO_WORKER_MODEL_INFERENCE_ROUTING.md`: a new
   `model_chat` worker capability routed through the existing job/ticket/
   approval path (not a change to `OllamaChatClient`), with a real
   benchmark already run (workers ~13% faster per-token than `karmo-ai01`
   for `qwen3:8b`, confirming the RAM-pressure theory). **Design only —
   not implemented.** Formal Invariant Impact Review and actual
   implementation remain a future decision.

---

See MASTER_INDEX.md for status-tag definitions. **KARMO FOUNDATION v1 was
declared COMPLETE on 2026-09-09.** Two further repository-only,
zero-production-access programs ran the same day: the Post-Foundation
Overnight Readiness Program (PRs #14–#17) and the Core v2 Engineering
Blueprint Program (PRs #18–#21).

**An independent merge-readiness review of PRs #14–#21 completed
2026-09-09** — see
`docs/evidence/autonomous-review/KARMO_PR14_21_MERGE_READINESS.md` for
full PR-by-PR status and `docs/evidence/autonomous-review/MERGE_SEQUENCE.md`
for the recommended merge order (#14, #15, #16, #17, #18, #19, #20, #21 —
#17 before #21 specifically, to resolve a real, documented conflict
between the two PROJECT SAVE PRs). PR #19 was updated in place with 4
adversarial-review fixes (154 → 160 tests); PR #20 and #21 were updated
in place to correct the resulting stale test-count references. No new PR
was created for these fixes — existing PRs were updated directly. **PRs
#14–#25 have all merged into `main`** via the approved KARMO merge
sequence (PR #22 at commit `4877aa967805bf540af0cc5645b2c82024ab11c9`, PR
#23 at commit `11d4f86e04d22aae0072923ec387a11f0e205cbc`, PR #24 at commit
`9f3215ecd3be31d2096273be4afb389edbcbf9f8`, PR #25 at commit
`b95acb603e632855298cc0d454df00b2c3d22286`) — see "Worker Runtime v0.1
final merged-main closeout" in `CURRENT_STATE.md`. **This merge-closeout
thread is now complete — every PR from the Foundation-through-Worker-
Runtime sequence is merged, decided, and closed.**

The primary next action is now **a future user decision on the next
engineering capability** (see item 11 below) — there is no outstanding
foundation-blocking work, no PR left to merge or reject, and nothing
requires an urgent response. Per explicit direction: **infrastructure
churn stops here.** Focus moves to the KARMO AI / Agent Engineering
Learning Program and other directly useful capability work, unless
Kamara explicitly chooses to open a new engineering track.

## Items requiring Natalie's decision

### From the Post-Foundation Overnight Readiness Program (MERGED)
1. ~~Merge/reject PR #14~~ — **merged** into `main`.
2. ~~Merge/reject PR #15~~ — **merged** into `main`.
3. ~~Merge/reject PR #16~~ — **merged** into `main`.
4. ~~Merge/reject PR #17~~ — **merged** into `main`.

### From the Core v2 Engineering Blueprint Program (MERGED)
5. ~~Merge/reject PR #18~~ — **merged** into `main`.
6. ~~Merge/reject PR #19~~ — **merged** into `main`. 160/160 tests pass at
   merge time; nothing wired into production.
7. ~~Merge/reject PR #20~~ — **merged** into `main`.
8. ~~Merge/reject PR #21~~ — **merged** into `main`.

### From the KARMO Large Autonomous Review (MERGED)
9. ~~Merge/reject PR #22~~ (`review/pr14-21-merge-readiness`) — **merged**
   into `main`.

### From the Worker Runtime v0.1 workload (MERGED)
10. ~~Merge/reject PR #25~~ (`worker-runtime/evidence`: evidence package +
    PROJECT SAVE) — **merged** into `main` at commit `b95acb603e632855298cc0d454df00b2c3d22286`.
    PR #23 (implementation + tests, commit `11d4f86e`) and PR #24
    (architecture/security/network docs, commit `9f3215ec`) are also
    merged. All merged into the source tree, **not** deployed or
    connected to production. Final merged-main verification (2026-09-10):
    **68/68** worker-runtime tests, **161/161** core-v2-prototypes
    regression — see `docs/evidence/worker-runtime/RUN_SUMMARY.json` and
    "Worker Runtime v0.1 final merged-main closeout" in `CURRENT_STATE.md`.

### Choices, not just merges
11. **Choose the first post-foundation capability track**, or a
    sequencing alternative (registry-first / domain-first / KarmoLab-
    proving-ground / continue building out Worker Runtime) — see
    `docs/plans/POST_FOUNDATION_CAPABILITY_ROADMAP.md` and
    `docs/plans/CORE_V2_IMPLEMENTATION_DEPENDENCY_GRAPH.md`'s 6 candidate
    batches. Still entirely open; nothing merged so far narrows this
    choice, only informs it.
12. **Weigh the two proposed (not adopted) invariant candidates**:
    configuration single-sourcing and tool-registration review.
13. **Decide whether/when to build any further Core v2 component for
    real** — every design and prototype so far is isolated and
    unimplemented in production (Worker Runtime v0.1 is the one
    exception moving toward real use, still not deployed); Batch 1 of the
    dependency graph is the lowest-risk starting point for anything else.
    This includes the specific Workstream 3 question — whether/when to
    build the Tool/Capability Registry itself — for which only a design
    exists and no phase is authorized to start.

## Worker Runtime v0.1 — named follow-ups before any real network exposure

Not blocking, not started, explicitly deferred per that workload's scope:
cryptographic worker credentials (currently a bare `worker_id` string with
only identity-consistency checking, no proof of possession); subprocess
environment allowlisting for `pytest`/`static_analysis` handlers; a
symlink-escape-specific test to directly prove `resolve_within_sandbox`'s
existing containment check; a result-authenticity binding beyond the
current internal-consistency digest; and coordinator persistence (today
fully in-memory, confirmed by scenario 24 — no restart recovery exists).
Full detail: `docs/evidence/worker-runtime/SECURITY_REVIEW.md`'s "Open
findings" section. None of these block continued isolated-prototype work;
all of them block any real network transport or any capability above
`READ`/workspace-scoped `REVERSIBLE_WRITE`.

## Recommended (non-blocking) follow-ups, in rough priority order

14. Workstream 4's MEDIUM findings from the Post-Foundation program — live
    pagination ceiling in `document_memory.get_document_history` (same bug
    class already fixed elsewhere in H0.4), no connection pooling
    anywhere, no embedding-model provenance on `karmo_semantic_memory`,
    configuration drift across ~10 files. None urgent at current scale;
    all worth addressing before the capability that would first stress
    them. Full detail:
    `docs/evidence/post-foundation-readiness/WORKSTREAM4_ADVERSARIAL_ARCHITECTURE_REVIEW.md`.
    The Core v2 dependency graph
    (`docs/plans/CORE_V2_IMPLEMENTATION_DEPENDENCY_GRAPH.md`, Batch 1)
    already scopes fixes for the first two as small, standalone,
    parallelizable items.

## Keep the two ambiguous legacy hashes unresolved (no action required, active constraint)

`karmo-v05-new.html` hashes
`23646203eed7e187ce2fe0de12c82d5cf83d0a97893a6bdcd2ed30ae3855af9c` and
`5f98126d41381a8a0a4c5034b3402b9a4b763fa043bcfa63f27bdefeb7414c78` remain
**intentionally unresolved** (`AMBIGUOUS_MULTIPLE_HASHES_FOR_SOURCE_FILE`),
reconfirmed present as `ORPHAN_VECTOR` in both the 2026-09-09 production
audit and (structurally) untouched by the Workstream 2 fix. Resolution
requires a human decision on version ordering —
`bootstrap_legacy_registry.py` will not and should not guess. Do not mark
resolved without that explicit decision recorded. Untouched by either
program.

## Completed, no further action

- Foundation Completion Workloads 1–4 (PRs #7, #8, #9, #10) — merged.
- Production Access Authorization Gate (PR #12) — merged, exercised
  successfully the same night.
- Foundation v1 closeout evidence package (PR #13) — merged.
- H0.3 remains NO-PROMOTION — not promoted, not touched by any program.
- Post-Foundation Overnight Readiness Program (PRs #14, #15, #16, #17) —
  merged. H0.4 auditor legacy-active-state gap (Workstream 2) fixed as
  part of PR #15 — no further action.
- Core v2 Engineering Blueprint Program (PRs #18, #19, #20, #21) —
  merged. Nothing wired into production.
- KARMO Large Autonomous Review of PR #14–#21 (PR #22) — merged.
- Worker Runtime v0.1 — implementation + tests (PR #23, commit
  `11d4f86e`), architecture/security/network docs (PR #24, commit
  `9f3215ec`), and evidence + PROJECT SAVE (PR #25, commit `b95acb6`) —
  **all merged** into `main`, **not deployed, not connected to
  production**. Final merged-main verification (2026-09-10): 68/68
  worker-runtime tests, 161/161 core-v2-prototypes regression. This
  closes the entire Worker Runtime v0.1 merge-closeout thread — no item
  remains open in this workload.
- `SOFTWARE_INVENTORY.md`/`NETWORK_INVENTORY.md` current counts —
  reconfirmed during the 2026-09-09 Workload 2 closeout; no further
  action required (routine update from existing evidence deferred, not
  blocking).

## Not next steps (explicitly out of scope, unchanged)

- No production access occurred in either program tonight — zero SSH,
  zero database/Qdrant/container/credential/log/network access.
- No PR was merged *during* either program's own run (PRs #14–#21 were
  all opened, none merged, at that time) — historical, describing that
  night's activity only. PRs #14–#25 have since merged via the separate,
  later approved KARMO merge sequence; see "Completed, no further
  action" above.
- No governance was modified by either program.
- No Voice/Media/BloomBoss/KarmoLab/Personal-Productivity/Finance
  capability was implemented or started.
- No first-capability scope was chosen on Natalie's behalf.

# PROJECT SAVE — 2026-09-17 — Worker sandbox fork→spawn fix

## RESOLVED, 2026-09-17 (later same day) — workstream fully closed

Continuing directly from the mid-canary stop below: both blockers were
mechanical, not fix-related.

1. The enqueue script's job never got leased because `_candidate_jobs()`
   requires an INNER JOIN against an `APPROVED` row in
   `core_approval_records` matching `authorized_executor`, `tool_id`,
   `tool_version`, and `arguments_digest` — the first retry script passed
   `approval_id=None`, which can never satisfy that join. Fixed by
   actually issuing and approving a real `ApprovalEngine` record
   (`authority_class="READ"`, auto-approved by the operator, matching
   `model_chat`'s NONE-approval-requirement policy) before enqueueing.
2. Worker01's canary then succeeded (`SUCCEEDED`, job
   `209f8438-0730-47c8-94c1-575631605aab`, ~51s). Followed with a 6-check,
   ~3-hour soak test (17:15–20:15 UTC) under the real live service:
   every check showed the same `MainPID=107737` (no crash/restart) and
   zero jobs stuck past their lease. The one stale pre-fix orphaned job
   (`8ab2f1dc-...`, left over from before the fix was deployed) was
   reconciled via `recover_expired_leases()` before the soak window
   started, so the 0-stuck-jobs baseline is real, not masked.
3. Worker02 was deployed the same way (backup/install/`--check-config`/
   restart, `MainPID=105750`) and canary-proven independently
   (`SUCCEEDED`, job `6bf6588c-e5df-4311-8f31-9daf8518f3ee`, ~53s) —
   this time using the approval's `authorized_executor` field to target
   Worker02 specifically (`_candidate_jobs()` filters candidates by
   `a.authorized_executor = <polling worker's id>`, so this is the
   correct way to pin a canary to one worker without needing to stop the
   other worker's service, unlike the Worker01 canary which used that
   cruder isolation method before this was understood).

**Outcome: `model_chat` is now trusted under normal, unattended,
long-running polling on both Worker01 and Worker02.** No further action
needed on this workstream. `KARMO_DASHBOARD.md` and `NEXT_STEPS.md`
updated to close item 2a.

---

# Original mid-canary-stop record (superseded by the above, kept for the investigation trail)

Session length: 12+ hours, ended on Kamara's explicit call to stop and
save rather than complete the canary. This is a genuine mid-task
stopping point, not a completed workstream — read "Immediate next
action" at the bottom before doing anything else on Worker01/Worker02.

## What this session investigated and fixed

Carried over from the prior session's open finding: `model_chat` worker
jobs reliably got stuck in `LEASED` state past lease expiry, with **zero
trace anywhere** (no journalctl entry despite PR #70's logging fix being
deployed, no forked child process visible, no crash/restart) —
specifically and only when the job was picked up by the long-running,
always-on `karmo-worker0{1,2}.service` systemd process. A one-shot
manual `--once` invocation succeeded cleanly every time. Reproduced 4x
prior session (3x Worker01, 1x Worker02), 0x under `--once`.

### Live investigation (this session, before the fix)

- Confirmed via `systemctl show ... -p MainPID` that Worker01's service
  process never crashed or restarted around the time a job got stuck —
  same PID throughout.
- Widened `journalctl` queries around the exact stuck-job window
  (04:26:00–04:34:30 UTC) — zero entries, ruling out an exception being
  thrown and simply misrouted.
- Confirmed only one `remote_worker_runtime` process existed on Worker01
  (no stray leftover manual invocation).
- Read `crypto_boundary.py`'s `WorkerAuthenticator.issue()` — confirmed
  it's a stateless pure function of wall-clock time plus a fresh random
  nonce, ruling out credential/token staleness from long uptime.
- Live 3-minute process monitor (`/proc/<pid>/wchan`, fd count, child
  PIDs, sampled every 2s) around a fresh reproduction attempt showed
  the worker cycling completely normally (`hrtimer_nanosleep` idle /
  `do_poll.constprop.0` active, short-lived SSH children only) — by the
  time monitoring started, the stuck job (leased ~3 minutes earlier) had
  already been abandoned with the service having moved on, unaware.

### Root cause

`sandbox.py`'s `run_capability()` executed every job in a
`multiprocessing.get_context("fork")` child. A long-lived worker process
makes thousands of `subprocess.run()` calls to the SSH transport between
jobs over its lifetime. `fork()` only clones the calling thread — if any
other thread (e.g. one of CPython's own internal reader threads from a
prior `subprocess.run()` call with dual `PIPE`s) held a lock at the
exact instant a job triggered a fork, the child inherits that lock
permanently held with no thread left alive in the child to release it.
The child deadlocks before it ever reaches its own error handling —
silently, forever, invisible to every diagnostic above. A short-lived
`--once` process makes at most 1-2 such calls before its single fork,
so the race essentially never lands there; the always-on service will
eventually hit it.

### Second opinion (GPT)

Diagnosis and a "what to ask GPT" prompt were prepared
(`python_fork_hang_diagnosis.md`, repo root — not committed, scratch
reference). GPT's recommendation (saved by Kamara as
`KARMO_CLAUDE_FORK_DEADLOCK_RECOMMENDATION.md`) confirmed the direction
but corrected overconfident framing: `fork`→`spawn` is not a one-line
swap; it requires verified picklability of the handler/payload, and it
also corrected that `subprocess.run(..., stdout=PIPE, stderr=PIPE)`
isn't necessarily proven to be the exact thread source (the broader risk
is any thread/lock in a long-lived process at fork time). It gave a
specific implementation/test checklist that shaped this fix's actual
scope rather than a naive context-string change.

### The fix — PR #74 (merged to `main` as `af12ed8`)

- `worker-runtime/app/sandbox.py`: `run_capability()` now uses
  `multiprocessing.get_context("spawn")` instead of `"fork"`. Added a
  clean `SandboxError` around `process.start()` for pickling/serialization
  failures (previously would have leaked a raw `PicklingError`/
  `AttributeError`).
- Found and fixed a **real latent bug** via a new test: a child that
  exits (e.g. `os._exit()`) before ever writing to the pipe makes
  `parent_conn.poll()` report "ready" (EOF counts as ready), but the
  subsequent `parent_conn.recv()` then raised a raw `EOFError` instead of
  the intended clean "produced no result" `SandboxError`. Fixed with an
  explicit `try/except EOFError` around that `recv()`.
- `worker-runtime/app/capabilities.py`: `model_chat`'s Ollama URL is now
  resolved at call time via `_ollama_generate_url()`, optionally
  overridden by the `KARMO_OLLAMA_GENERATE_URL` env var. Necessary
  because a spawned child re-imports `capabilities.py` fresh and cannot
  see a parent-process monkeypatch of a function or constant — only
  real, externally observable state (env vars, actual sockets) crosses
  that boundary. Production behavior is unchanged (env var unset).
- `worker-runtime/tests/test_worker_runtime.py`: refactored 4 test-only
  handlers from nested closures (fork-only; genuinely unpicklable under
  spawn) to module-level functions, with per-test data passed through
  the payload dict instead of closure capture. Rewrote the 2 `model_chat`
  tests that depended on the mock taking effect inside the executed
  handler to use a real local loopback HTTP test double
  (`_FakeOllamaServer`, 127.0.0.1, ephemeral port, this process only —
  not a real network dependency). Added 4 new tests: unpicklable-handler
  refusal, child-exit-before-result, and two repeated-execution-from-one-
  long-lived-caller tests (success and timeout paths), each asserting no
  leaked `multiprocessing.active_children()`.
- **125/125 worker-runtime tests pass**, verified twice: once under the
  repo's local Python 3.9 venv, once under Python 3.12 in an isolated
  venv matching what CI (`karmo-full-predeploy.yml`) actually uses.

## Deployment status (as of session end)

- PR #74 merged to `main` at `af12ed8ab9f457bc09c824e79cab65e88378265a`.
- **Deployed to Worker01 only**, following the exact backup/install/
  restart pattern from `docs/runbooks/WORKER01_EXACT_ACTIVATION.md`
  (worker-runtime-only variant — `karmo-core.service` untouched, since
  Core/gateway code did not change). `--check-config` passed cleanly.
  Service restarted: new `MainPID=107737` (was `101639`), confirmed
  `active`. Pre-deploy backup preserved at
  `/opt/karmo/backups/worker-deploy-<timestamp>/worker-runtime-before`
  on Worker01 (rollback path: restore that directory, restart the
  service — no data loss risk, durable job/event tables untouched).
- **NOT deployed to Worker02** — deliberately, per GPT's own "one worker
  at a time" recommendation and the plan agreed with Kamara: prove
  Worker01 clean under real sustained load first.
- **Canary NOT yet proven.** Plan: since jobs aren't pre-assigned to a
  specific worker (any eligible worker's next poll can claim a queued
  job — confirmed by reading `worker_gateway_backend.py`'s `poll()` /
  `_candidate_jobs()`), `karmo-worker02.service` was deliberately
  **stopped** on Worker02 to isolate the canary to Worker01 only. The
  first enqueue attempt (as `karmo-gateway` on `karmo-ai01`, via
  `core_service.worker_gateway_runtime.build_backend()`) failed with
  `WorkerGatewayRuntimeError: gateway runtime dependency unavailable`
  because the script only added `/opt/karmo/core-service` to `sys.path`,
  not `/opt/karmo/worker-runtime/app` (where `crypto_boundary.py`
  actually lives — confirmed by reading `worker_gateway_runtime.py`'s
  `build_backend()` import). The corrected script (both `sys.path.insert`
  lines) was handed back but the session ended before a confirmed clean
  run.

## IMMEDIATE NEXT ACTION (resume point)

1. **`karmo-worker02.service` is currently STOPPED.** This was a
   deliberate, temporary, reversible action (pausing it so it couldn't
   steal the canary job), not a code or config change — but it was never
   restarted before the session ended. Decide: restart it now, or leave
   it stopped intentionally until the Worker01 canary window (below) is
   done, then restart it.
2. Re-run the fixed canary enqueue script (as `karmo-gateway` on
   `karmo-ai01`, with `sys.path.insert` for BOTH
   `/opt/karmo/core-service` and `/opt/karmo/worker-runtime/app`) —
   exact corrected script is in this session's transcript
   (`~/.claude/projects/-Users-sdcity-KARMO-DEV/6b9897bb-2f63-4a7e-8f78-c2aeb85f423e.jsonl`,
   near the end).
3. Confirm the resulting job reaches `SUCCEEDED`/`FAILED` cleanly (check
   `karmo_worker_jobs.state` in Postgres, and Worker01's
   `journalctl -u karmo-worker01.service` for a clean run, no silent
   hang).
4. **One clean job is necessary but not sufficient** — the original bug
   was a rare race needing hours of uptime and many poll cycles to
   surface. Leave Worker01's service running under its normal polling
   cadence for a few hours (ideally longer) before treating the fix as
   proven, matching GPT's and this session's agreed plan.
5. Only once that window is clean: deploy the identical PR #74 code to
   Worker02 (same backup/install/restart pattern), then restart
   `karmo-worker02.service` if not already done in step 1, then do a
   follow-up PROJECT SAVE closing this out.

## Files touched this session

- `worker-runtime/app/sandbox.py`, `worker-runtime/app/capabilities.py`,
  `worker-runtime/tests/test_worker_runtime.py` — the fix (PR #74,
  merged).
- `docs/project-state/KARMO_DASHBOARD.md`, `NEXT_STEPS.md` — refreshed
  for this stopping point.
- `python_fork_hang_diagnosis.md` (repo root, untracked scratch file) —
  the prompt used to get GPT's second opinion. Not part of the fix;
  fine to leave or delete next session.

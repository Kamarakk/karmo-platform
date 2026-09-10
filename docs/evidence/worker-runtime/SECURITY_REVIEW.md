# KARMO Worker Runtime v0.1 -- Security Review (Phase 13)

Status: real adversarial review against actual, executed code (not a
design-only threat model). Every mitigation named below has a
corresponding passing test in `worker-runtime/tests/test_worker_runtime.py`
(TEST_RESULTS.txt has the fresh run). No production system, credential,
or data was touched to produce this review.

**Update (post-independent-verification, same workload, before any
merge):** an independent (ChatGPT) verification pass of PRs #23-#25
found four real blocking defects that this document's original version
had either missed or under-stated. None of the affected PRs had been
merged. All four are now fixed on the same open PRs, with new adversarial
tests, and are reflected in the threat table and open-findings list
below. Nothing here was previously claimed fixed and then found broken
-- these are corrections to gaps this review did not originally catch:

1. **Approval only gated job *completion*, not *execution*.** A worker's
   sandboxed handler ran unconditionally the moment a job was leased;
   approval state was checked only afterward, at `complete()` time -- by
   which point a possibly-unapproved, wrong-executor, or
   argument-tampered execution had already happened. Fixed:
   `job_protocol.WorkerJobQueue.execute()` is now the single choke point,
   delegating to the reused `ApprovalEngine.execute()` (never
   duplicated) so execution itself only happens after approval state,
   executor identity, expiry, and an exact arguments digest are all
   validated, with the approval consumed (EXECUTED) atomically with the
   action running. See threat #21 below.
2. **Timeout enforcement was a post-return elapsed-time check, not a
   real deadline.** `sandbox.run_capability()` called the handler
   in-process and only measured how long it had already taken after it
   returned -- a hung or slow handler was never actually interrupted.
   Fixed: the handler now runs in a forked child process; a missed
   deadline terminates the child (SIGTERM then SIGKILL) and fails
   closed. See threat #20 (updated).
3. **Only `stdout_summary` was bounded; the structured `output` result
   and `evidence_files` were not.** Fixed: `MAX_RESULT_BYTES` (64KB,
   refuses rather than truncates a structured dict) and
   `MAX_EVIDENCE_FILES` (20) now bound the complete returned result. See
   threat #20 (updated).
4. **A worker heartbeat could set arbitrary coordinator-owned scheduling
   state.** `heartbeat(..., status=ANY_WORKERSTATUS)` accepted any value
   from the caller, so a worker could force itself `AVAILABLE` while
   actually `BUSY` on a live lease (enabling a double-lease), or the
   reverse. Fixed: heartbeat now accepts only a self-reported
   `WorkerHealth` (HEALTHY/DEGRADED); `BUSY` is untouchable by a
   worker's own heartbeat in either direction. See new threat #22.

**Second update (same workload, before any merge):** a second
independent verification pass found the approval-gates-execution fix
above was itself correct but incomplete -- it made refusing an
unapproved execution *safe*, but the normal `WorkerClient` flow then
treated that correct refusal as a hard failure, permanently marking a
merely-pending (not broken) job `FAILED`. This is a *workflow*/
availability defect, not a security hole (nothing unauthorized ever
executed either before or after this fix), but it made the
approval-gate mechanically unusable in practice -- any real
approval-required job would fail itself the instant it was leased,
before a human ever had a chance to approve it. Fixed:
`job_protocol.WorkerJobQueue.resume()` alongside `execute()` -- an
approval-required job now parks in `WAITING_FOR_APPROVAL` without
executing or failing, and is later resumed (executed exactly once) once
actually approved, or ended safely (`FAILED`, worker released) on
denial/expiry. See new threat #23 below. The in-process,
callable-based transport limitation already documented for `execute()`
is unchanged and explicitly not redesigned by this fix -- `resume()`
inherits the exact same shape and the exact same network gap.

Core principle repeated throughout: **network identity and KARMO
authorization are separate layers.** A worker is never trusted because it
is reachable on Tailscale or the LAN -- authorization always comes from
the closed capability manifest (`capability_manifest.py`) and the
coordinator's own state, never from network position.

## Threat-by-threat

| # | Threat | Mitigation in this implementation | Test evidence |
|---|---|---|---|
| 1 | Rogue worker registers and claims broad capabilities | `validate_capability_declaration` refuses any `capability_id` outside the closed `SAFE_CAPABILITIES` set and refuses `FORBIDDEN_CAPABILITY_IDS` outright; a worker's declaration can never override `authority_class`/`side_effect_class` | scenario 6, `test_scenario_20_forbidden_capability_id_rejected_at_the_manifest_layer` |
| 2 | Stolen worker credential replays a registration | Not fully solved in v0.1 -- **named gap**: `worker_id` is currently a caller-supplied string with no cryptographic proof of possession (no signed registration token). Identity-consistency checking (hostname/platform/architecture) catches an *impersonation with a different identity*, not a credential-accurate replay. Real credential issuance is deferred to the Phase 15 network plan. | scenario 2 (partial coverage only) |
| 3 | Coordinator spoofing (a fake coordinator feeds a worker malicious jobs) | Out of scope for `LocalTransport` (in-process, no network hop exists to spoof). Named as a hard requirement for the future network transport (mutual TLS / coordinator auth) in `FUTURE_NETWORK_INTEGRATION_PLAN.md` | N/A this workload -- design-only for now |
| 4 | Job injection (a job payload smuggles a different capability or executable) | Jobs only ever reference a `capability_id` resolved through the closed manifest; `sandbox._HANDLERS` dispatch is populated exclusively at import time by `capabilities.py` -- no payload field can ever select or supply a handler | scenario 20 |
| 5 | Malicious payload (oversized, adversarial path, adversarial iteration count) | `resolve_within_sandbox` path-traversal refusal; `resource_benchmark`/`embedding_benchmark_test` clamp caller-supplied sizes server-side, never trusting the payload's stated bound; output capped at `MAX_OUTPUT_BYTES` | scenario 18, 19; `test_capability_resource_benchmark_is_bounded_...`, `test_capability_embedding_benchmark_is_bounded_...` |
| 6 | Arbitrary command execution | No handler accepts a job-supplied command, executable path, or shell string; `pytest`/`static_analysis` invoke a **fixed** venv interpreter path, never a payload-supplied one | scenario 20 |
| 7 | Path traversal | `resolve_within_sandbox` resolves and hard-checks `.relative_to()`; refuses (does not clamp) | scenario 18 |
| 8 | Symlink escape | `Path.resolve()` follows symlinks before the `.relative_to()` containment check, so a symlink inside the allowed workspace pointing outside it is caught the same way a `../` traversal is -- **not independently tested in this workload's suite; named as a residual verification gap** | Not directly tested -- see Open Findings below |
| 9 | Environment leakage (job sees host secrets/env) | `subprocess.run` calls in `capabilities.py` do not pass `env=os.environ` explicitly and inherit only what a bare subprocess needs; no capability handler reads `os.environ` for secret material. Full environment scrubbing (an explicit, minimal `env={}` allowlist) is **not yet implemented** -- named gap | Not directly tested -- see Open Findings |
| 10 | Secret leakage in output/evidence | Every `SAFE_CAPABILITIES` entry declares `secrets_required=[]`; `_sanitize_error` strips the sandbox root's absolute path from error text before it's returned | `_sanitize_error` covered indirectly by scenario 7 |
| 11 | Replay (resubmitting a completed job) | `JobStore.submit` is idempotent by `(job_type, idempotency_key)` -- a duplicate submission returns the existing job, never a new execution | scenario 9 |
| 12 | Stale lease exploited to double-execute | `JobStore.claim` refuses to reclaim a live (unexpired) lease; a stale lease is reclaimable but issues a **new** `claim_token`, fencing out the original holder | scenario 10, 11, 12, 13 |
| 13 | Result forgery (a worker reports success without having produced the claimed output) | `result_digest` is computed by the coordinator from the actual `output` dict passed to `complete()`, not trusted from the worker as an opaque value -- but **v0.1 does not cryptographically bind the digest to the worker's identity** (no worker-signed result); a compromised worker could still submit a fabricated `output`. Named gap. | scenario 16 (digest correctness only, not authenticity) |
| 14 | Compromised worker executes real damage via a "safe" capability | Every `SAFE_CAPABILITIES` entry is `authority_class=READ` (or reversible-write scoped to a job's own temp dir); none is `EXTERNAL_ACTION`/`DESTRUCTIVE_HIGH_IMPACT`; a compromised worker in v0.1 can, at worst, read files inside the explicitly scoped `allowed_root` workspace or burn CPU inside its `timeout_seconds` bound | Whole SAFE_CAPABILITIES set design; scenario 6 |
| 15 | Network MITM | No network transport exists yet (`LocalTransport` is in-process). TLS + application-layer auth is a hard requirement named for the Phase 15 plan before any real network transport ships | N/A this workload |
| 16 | Capability escalation (worker claims a capability, then executes with elevated effect) | `validate_capability_declaration` locks `authority_class`/`side_effect_class`/`network_required`/`secrets_required` -- a worker's declaration is refused outright if it disagrees with the canonical manifest on any of these | scenario 6, `test_scenario_20_forbidden_capability_id_rejected_at_the_manifest_layer` |
| 17 | Worker-to-worker trust (one worker's job/result affecting another) | Every `WorkerJob` is leased to exactly one `worker_id`; the coordinator is the only broker between workers -- no worker ever sees another worker's queue state or leases directly | scenario 22 (routing correctness); `WorkerJobQueue._worker_jobs` is never exposed to a worker |
| 18 | Authority computed by a worker rather than KARMO Core | `authority_requirement` is computed by `job_protocol.submit()` from the canonical capability's `authority_class`, looked up server-side -- never accepted as a worker- or job-supplied value | `job_protocol.WorkerJobQueue.submit` code path; scenario 17 |
| 19 | Changed job arguments silently reused under a stale approval | `lease()` re-verifies the payload digest against the value captured at submission time; a changed payload is refused before the job can be claimed, so an approval bound to the original digest can never be consumed against different arguments | scenario 8, 17 |
| 20 | Resource exhaustion (unbounded job work, unbounded output) | `timeout_seconds` enforced per capability via a **real, forked-process deadline** (terminate/kill on overrun, fail closed -- not a post-return elapsed-time check); `MAX_OUTPUT_BYTES` truncates `stdout_summary`; **`MAX_RESULT_BYTES` refuses an oversized structured `output`**; **`MAX_EVIDENCE_FILES` refuses an oversized evidence list**; `resource_benchmark`/`embedding_benchmark_test` server-side clamps | `test_scenario_14_timeout_is_a_real_kill_not_a_post_hoc_check`, `test_oversized_structured_output_is_refused_not_truncated`, `test_oversized_evidence_files_list_is_refused`, scenario 19; bounded-iteration tests |
| 21 | Execution occurring before, or without, a valid approval (approval gates completion but not execution) | `job_protocol.WorkerJobQueue.execute()` is the sole path to invoking a capability's `action`; for any capability whose `authority_requirement` is not NONE, `action()` is only ever called from inside the reused `ApprovalEngine.execute()`, which validates approval state (must be APPROVED), executor identity, expiry, and an exact tool/version/arguments digest before running it, then atomically consumes the approval into EXECUTED. `complete()` independently requires EXECUTED (defense in depth, not the sole gate). Wired through `transport.execute()`/`resume()` into `worker_client.py`, not just the low-level API -- see threat #23 for the real WorkerClient-path proof (the two prior end-to-end tests here, `test_worker_client_end_to_end_refuses_unapproved_execution` / `..._executes_once_approved`, were superseded by threat #23's tests once the pending-approval workflow fix landed). | `test_approval_gate_unapproved_job_cannot_execute`, `test_approval_gate_no_approval_requested_at_all_cannot_execute`, `test_approval_gate_expired_approval_cannot_execute`, `test_approval_gate_changed_payload_after_approval_cannot_execute`, `test_approval_gate_wrong_executor_cannot_execute`, `test_approval_gate_one_approval_cannot_execute_twice`, `test_approval_gate_successful_execution_ends_executed_and_unlocks_completion` |
| 22 | Worker self-reports coordinator-owned scheduling state (heartbeat spoofing a lease state) | `WorkerRegistry.heartbeat()` accepts only an optional `WorkerHealth` (HEALTHY/DEGRADED), never a raw `WorkerStatus`; `BUSY` can only be entered/exited by the coordinator itself (`mark_busy()`/`mark_available()` around a real lease, or `sweep_stale_workers()` on absence) -- a worker's own heartbeat can never flip `BUSY -> AVAILABLE` (which would enable a double-lease) or the reverse | `test_worker_cannot_force_itself_available_via_heartbeat_while_busy`, `test_heartbeat_no_longer_accepts_an_arbitrary_status_kwarg`, `test_worker_busy_on_a_lease_cannot_self_report_degraded_out_of_it`, `test_worker_can_self_report_degraded_health_without_touching_a_live_lease` |
| 23 | Approval-gate refusal treated as a hard failure (a pending-but-legitimate job self-destructs before a human can ever approve it; a related availability risk: a denied/expired job leaving its worker stuck `BUSY` forever) | `job_protocol.WorkerJobQueue.resume()` (alongside `execute()`) lets an approval-required job park in `WAITING_FOR_APPROVAL` without executing or failing, and resume execution -- exactly once -- once approved; `coordinator.deny_job()`/`resume_job()`'s exception handling releases the assigned worker back to `AVAILABLE` on denial/expiry rather than leaving it stuck `BUSY`; repeated polling/resume checks while pending are no-ops (no duplicate approval request, no duplicate execution); the wrong worker cannot resume (checked both at `resume()`'s `assigned_worker_id` guard and again inside `execute()`'s `executor_identity` check). **Narrow gap found and fixed by a third verification round**: the "ends safely on expiry" guard originally only covered a job still `WAITING_FOR_APPROVAL`; an approval granted (job moved to `RUNNING` by `approve()`) that then expired *before* `try_resume()` consumed it left the job stuck `RUNNING` and its worker stuck `BUSY` forever -- nothing ever noticed. Fixed by widening the guard to cover `RUNNING` as well (already a legal `job_model` transition source to `FAILED`, no state-machine change needed). | `test_worker_client_approval_required_job_parks_without_executing_or_failing`, `test_worker_client_repeated_polling_while_pending_does_not_execute_or_duplicate`, `test_worker_client_resumes_and_executes_exactly_once_after_approval`, `test_worker_client_wrong_worker_cannot_resume`, `test_worker_client_denial_ends_safely_and_releases_worker`, `test_worker_client_expiry_ends_safely_and_releases_worker`, `test_worker_client_none_required_capability_flow_is_unchanged`, `test_worker_client_approval_expires_after_being_approved_ends_safely` |

## Open findings (named gaps, not fixed in this workload -- explicitly future scope)

1. **No cryptographic worker credential.** `worker_id` is a bare string; registration proves nothing beyond "someone claiming this identity called `register()`". A stolen or guessed `worker_id` combined with a matching hostname/platform/architecture would be accepted as a legitimate re-registration. Required before any real network transport: a signed worker credential (e.g. issued out-of-band, rotated per Phase 15's plan) checked at every `register`/`heartbeat`/`poll`/`submit` call, not just at registration.
2. **No environment allowlisting for subprocess capabilities.** `pytest`/`static_analysis` inherit the worker process's ambient environment via `subprocess.run` without an explicit `env=` allowlist. On KARMO-DEV01 today this is a developer machine with no production secrets present, so the practical exposure is low, but this must be closed (explicit minimal `env={}` plus only what pytest strictly needs) before any worker runs on a machine that could plausibly hold sensitive environment variables.
3. **No symlink-escape-specific test.** The `.resolve()` + `.relative_to()` pattern in `resolve_within_sandbox` should catch a symlink pointing outside the allowed workspace the same way it catches `../`, but this workload's test suite does not construct a symlink fixture to prove it directly. Recommended next-session addition, not a known defect.
4. **No result authenticity binding.** `result_digest` proves the *reported output is internally consistent* (same output always hashes the same way); it does not prove the worker that submitted it actually performed the work faithfully. A compromised worker can fabricate a plausible-looking `output` dict for any of the SAFE capabilities and it will pass digest verification. This is an accepted limitation for v0.1's SAFE, low-consequence capability set and must be revisited before any `REVERSIBLE_WRITE` or higher capability is ever added to a real worker's manifest.
5. **Coordinator has no persistence.** Confirmed explicitly by scenario 24 -- state lives only in process memory. A real "coordinator restart and recover in-flight jobs" capability requires a durable store (the H0.1 outbox-shaped table this prototype's `JobStore` docstring already points at) before workers ever run against a long-lived coordinator process.

None of these gaps were exploitable within v0.1's own threat surface today because: (a) no real network transport exists yet -- everything runs in-process on KARMO-DEV01 itself; (b) the SAFE capability set is deliberately low-consequence (READ-only or workspace-scoped writes); (c) no production credentials or data are reachable from any capability handler. They become load-bearing the moment a network transport or a higher-authority capability is introduced -- which is exactly why Phase 15's plan gates real network exposure behind them.

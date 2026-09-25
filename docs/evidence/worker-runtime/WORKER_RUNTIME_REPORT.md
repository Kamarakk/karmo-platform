# KARMO Worker Runtime v0.1 -- Implementation Report

**Update (three rounds of post-independent-verification, before any
merge):**

**Round 1** -- an independent (ChatGPT) verification pass of PRs #23-#25
found four real blocking findings not caught by this workload's own
original review: approval gated job completion but not execution;
timeout enforcement was a post-return check, not a real deadline; only
`stdout_summary` was bounded, not the full result; and a worker
heartbeat could set coordinator-owned scheduling state directly. All
four were fixed at implementation commit `5906f61`, with 18 new
adversarial tests (62/62 passing, up from 44/44).

**Round 2** -- a second independent verification pass found round 1's
approval-gate fix was correct (nothing unauthorized ever executed) but
incomplete: the normal `WorkerClient` flow had no way to represent
"legitimately waiting on approval" as anything but a hard failure, so an
approval-required job was marked `FAILED` the instant it was leased,
before a human ever had a chance to approve it. Fixed at implementation
commit `08c501e`: an approval-required job now parks in
`WAITING_FOR_APPROVAL` and resumes execution -- exactly once -- once
approved, or ends safely (worker released) on denial/expiry. 7 more
tests (67/67 passing, up from 62/62).

**Round 3** -- a third independent verification pass found one narrow
gap remaining in round 2's fix: an approval granted (job moved to
`RUNNING` by `approve()`) that then expired *before* `try_resume()`
consumed it left the job stuck `RUNNING` and its worker stuck `BUSY`
forever -- round 2's expiry guard only covered a job still
`WAITING_FOR_APPROVAL`. Fixed at implementation commit `a2a1619` by
widening that guard to cover `RUNNING` too (already a legal `job_model`
transition to `FAILED`, no state-machine change needed). 1 targeted test
(68/68 passing, up from 67/67), verified to actually catch the bug by
temporarily reverting the fix and confirming the test failed first.

All three rounds are reflected throughout this report, `SECURITY_REVIEW.md`
(threat #23 updated for round 3), and `WORKER_RUNTIME_INVARIANT_IMPACT_REVIEW.md`.
See `RUN_SUMMARY.json`'s `independent_verification_round_1_findings_and_fixes`,
`..._round_2_findings_and_fixes`, and `..._round_3_findings_and_fixes` for
full detail. **PRs #23-#25 remain unmerged, awaiting re-verification.**

## 1. Architecture

`Coordinator → Job Queue → Worker Lease/Poll → Capability Validation →
Approval Validation (where required) → Isolated Execution → Result/Evidence
→ Coordinator`, exactly as specified. KARMO Core (`Coordinator`) remains
the sole authority: it owns `WorkerRegistry` and `WorkerJobQueue`, and is
the only component that decides which worker gets which job. Workers
(`WorkerClient`) never see each other's leases and never talk to the
coordinator's internals directly -- only through `WorkerTransport`
(`LocalTransport` today, an in-process implementation; a future network
transport is a drop-in replacement of the same interface).

Worker lifecycle: `UNREGISTERED → REGISTERED → AVAILABLE ⇄ BUSY/DEGRADED →
OFFLINE`, with `DISABLED` as an admin-only terminal-ish state a worker can
never assign itself. Job lifecycle reuses the existing Core v2 job model
verbatim (`QUEUED → RUNNING → SUCCEEDED/FAILED/CANCELLED/TIMED_OUT`, with
`WAITING_FOR_APPROVAL` as an optional detour) -- no competing lifecycle
was created.

## 2. Files created/modified

**New (`worker-runtime/`):**
- `app/`: `_prototype_paths.py`, `tool_registry_reuse.py`,
  `approval_engine_reuse.py`, `job_model_reuse.py`, `capability_manifest.py`,
  `worker_registry.py`, `resource_discovery.py`, `job_protocol.py`,
  `sandbox.py`, `capabilities.py`, `transport.py`, `coordinator.py`,
  `worker_client.py`
- `tests/conftest.py`, `tests/test_worker_runtime.py`
- `tests/fixtures/allowed_workspace/sample_document.txt`,
  `tests/fixtures/allowed_workspace/sample_tests/test_synthetic.py`
- `scripts/m3_benchmark.py`
- `venv/` (pytest 8.4.2)

**New (`docs/`):**
- `docs/evidence/worker-runtime/WORKER_RUNTIME_INVARIANT_IMPACT_REVIEW.md`
- `docs/evidence/worker-runtime/SECURITY_REVIEW.md`
- `docs/evidence/worker-runtime/WORKER_RUNTIME_REPORT.md` (this file)
- `docs/evidence/worker-runtime/TEST_RESULTS.txt`
- `docs/evidence/worker-runtime/BENCHMARK_RESULTS.json`
- `docs/evidence/worker-runtime/VERIFICATION_CHECKLIST.md`
- `docs/evidence/worker-runtime/RUN_SUMMARY.json`
- `docs/evidence/worker-runtime/MANIFEST.sha256`
- `docs/architecture/KARMO_WORKER_RUNTIME_NETWORK_PLAN.md`
- `specs/003-worker-runtime/spec.md`

**Modified (pre-existing, reused code -- see RUN_SUMMARY.json for why):**
- `core-v2-prototypes/job_model/jobs.py` (`VALID_TRANSITIONS` fix)
- `core-v2-prototypes/job_model/tests/test_jobs.py` (new test case for the fix)

## 3. Worker identity/registration result

`KARMO-DEV01` registers successfully with `worker_id=dev01`,
`hostname=karmo-dev01.local`, `platform=Darwin`, `architecture=arm64`.
Duplicate registration under the same identity is idempotent; a
conflicting identity under the same `worker_id` is refused as an
impersonation shape (scenario 2). See VERIFICATION_CHECKLIST.md command 3.

## 4. Resource-discovery result for KARMO-DEV01 (VERIFIED live on this machine)

- CPU: `arm64`, 8 logical cores, Apple M3 brand string -- VERIFIED
- Memory: 8,589,934,592 bytes (8 GB) -- VERIFIED
- Disk (`/`): ~460 GB total, ~33 GB free -- VERIFIED
- OS: macOS 14.8.7 (Darwin 23.6.0) -- VERIFIED
- Python runtime: CPython 3.9.6 -- VERIFIED
- Uptime: VERIFIED via `sysctl kern.boottime`
- Metal: VERIFIED, "Metal 3" reported by `system_profiler`
- Neural Engine: AVAILABLE-IN-PRINCIPLE only (no unprivileged, install-free
  path confirms actual ANE usability from Python -- never claimed VERIFIED)
- MLX: NOT_INSTALLED (not installed by this workload, per instruction)
- Ollama: NOT_INSTALLED (no binary on PATH)

Full machine-readable report: `resource_discovery.full_report()`,
exercised by `test_resource_discovery_full_report_runs_without_error`.

## 5. Capabilities implemented

Nine SAFE capabilities, all `authority_class=READ` (or workspace-scoped
`REVERSIBLE_WRITE`-shaped local writes), all `network_required=False`,
`secrets_required=[]`: `hash_verify`, `pytest`, `static_analysis`,
`repository_analysis`, `resource_benchmark`, `document_processing_test`,
`embedding_benchmark_test`, `media_probe_test`, `local_model_probe`.
Nine `FORBIDDEN_CAPABILITY_IDS` are permanently excluded and raise
`CapabilityManifestError` if ever declared. A worker's own declaration
can never override a capability's `authority_class`/`side_effect_class`/
`network_required`/`secrets_required` -- capabilities are availability
claims, never authorization grants, enforced as code
(`capability_manifest.validate_capability_declaration`), not just design.

## 6. Job lifecycle implemented

Reused verbatim from `core-v2-prototypes/job_model/jobs.py`
(`JobStore`/`JobState`). `job_protocol.WorkerJobQueue` wraps it with
worker-specific fields (`payload_digest`, `authority_requirement`,
`assigned_worker_id`, `result`, `evidence`) and, genuinely (not just
conceptually), wires it to the reused `ApprovalEngine` for any capability
whose computed authority requires approval -- closing the integration gap
the prior session's adversarial review flagged between the Tool Registry
and Approval Engine prototypes. None of the nine SAFE capabilities
actually require approval (all `authority_class=READ`), but the mechanism
is real and tested against a synthetic `REVERSIBLE_WRITE` capability
(scenario 17 and the dedicated approval-gate test block).

**Approval now gates execution, not merely completion** (round-1
independent-review fix). `WorkerJobQueue.execute()` is the sole path to
invoking a capability's action; for any `authority_requirement != NONE`,
the action is only ever called from inside the reused
`ApprovalEngine.execute()` (never duplicated), which validates approval
state, executor identity, expiry, and an exact arguments digest before
running anything, and atomically consumes the approval into `EXECUTED`.
`complete()` independently requires `EXECUTED` (was `APPROVED`) as
defense in depth, not the sole gate.

**An approval-required job now parks instead of failing, and resumes
later** (round-2 independent-review fix). `WorkerJobQueue.resume()`
(alongside `execute()`) lets a job leased into an approval requirement
transition RUNNING -> WAITING_FOR_APPROVAL without ever calling its
action, then later be checked on and executed -- exactly once -- once
approved, or ended safely (FAILED, worker released back to AVAILABLE)
on denial/expiry. Wired through `transport.execute()`/`request_approval()`/
`resume()` into `worker_client.py`'s `poll_and_execute_once()` (parks
instead of executing/failing) and new `try_resume()` (checks on /
executes a parked job) -- not just the low-level API.

## 7. Sandbox protections

- Capability dispatch only through handlers registered at import time
  (`sandbox._HANDLERS`) -- no job payload can ever supply its own
  executable or command.
- `resolve_within_sandbox`: hard containment check via
  `Path.resolve()` + `.relative_to()`; refuses (never silently clamps)
  any path escaping the allowed workspace.
- Per-job ephemeral temp directory, always cleaned up (`finally:
  shutil.rmtree`).
- **`timeout_seconds` is now a real, enforced deadline** (independent-
  review fix): each handler runs in a forked child process; a missed
  deadline terminates the child (SIGTERM then SIGKILL) and fails closed
  -- not the prior post-return elapsed-time check, which could not
  actually stop a hung or CPU-bound handler.
- **The full result is bounded, not just `stdout_summary`** (independent-
  review fix): `stdout_summary` is still truncated at 64 KB
  (`MAX_OUTPUT_BYTES`), but the structured `output` dict is now refused
  (not silently truncated, which would corrupt it) above `MAX_RESULT_BYTES`
  (64 KB), and `evidence_files` is refused above `MAX_EVIDENCE_FILES` (20).
- Errors sanitized: sandbox root's absolute path stripped, message capped
  at 2000 chars, no raw traceback ever returned.
- `pytest`/`static_analysis` invoke a fixed venv interpreter path, never
  a job-supplied one.

## 8. Failure/adversarial test results

All 24 required scenarios implemented and passing, plus supporting
capability/integration tests, 18 round-1, 7 round-2, and 1 round-3
fix-verification tests -- **68/68 passing** (was 44/44 -> 62/62 -> 67/67
-> 68/68). Full list and output in `TEST_RESULTS.txt`. Ten real defects
have now been found and fixed across this workload (not merely
reproduced from a checklist): 4 during initial build (see
`RUN_SUMMARY.json`'s `defects_found_and_fixed_prior_to_independent_verification`),
4 blocking findings from round-1 independent verification plus a real
multiprocessing deadlock found while fixing the timeout issue (see
`independent_verification_round_1_findings_and_fixes`), 1 blocking
workflow finding from round-2 independent verification plus a worker-
stuck-BUSY-after-denial/expiry bug found while fixing it (see
`independent_verification_round_2_findings_and_fixes`), and 1 narrow
blocking finding from round-3 independent verification -- an approval
expiring *after* being granted (job already `RUNNING`) left the job and
its worker stuck, since round-2's expiry guard only covered a job still
`WAITING_FOR_APPROVAL` (see `independent_verification_round_3_findings_and_fixes`).

## 9. M3 benchmark results

Re-run after the sandbox's fork-based real-timeout fix (each capability
call now costs a small, fixed fork overhead vs. the prior in-process
call -- visible below as a few ms of increase, not a meaningful
regression). See `BENCHMARK_RESULTS.json` (raw) -- summary:
- `resource_benchmark` (hash-loop CPU work): 100K iterations in ~7ms, 1M in
  ~57ms, 5M (the enforced cap) in ~280ms.
- `hash_verify` (real SHA-256 of the fixture file): ~1.4ms.
- `pytest` (real subprocess: interpreter startup + collect + run 2 tests):
  ~89ms wall.
- `embedding_benchmark_test` (synthetic vector dot-products): 100 vectors
  ~4ms, 1,000 ~34ms, 10,000 (cap) ~332ms.
- `media_probe_test`: Metal 3 confirmed present (~124ms, dominated by
  `system_profiler` subprocess cost).
- `local_model_probe`: MLX and Ollama both NOT_INSTALLED, as expected.

**Interpretation**: the M3's 8 cores handle bounded, single-threaded CPU
work (hashing, small synthetic vector ops, short-lived subprocess
execution) comfortably within the second-scale timeouts these capabilities
declare. This machine class is well-suited to short, bounded
verification/analysis jobs (hash checks, test runs, static analysis,
small synthetic benchmarks) -- exactly the SAFE capability set built here.
No claim is made about larger workloads (real embedding models, larger
test suites, sustained parallel load) since none were run, and no
comparison against KARMO production is made, per explicit instruction.

## 10. Security findings

Full threat-by-threat table in `SECURITY_REVIEW.md` (23 threats, up from
the original 20 -- 3 new rows across rounds 1-2, plus round 3's
correction to threat #23's own claim). Round 1 found and this workload
fixed 4 blocking security gaps (approval-gated-completion-not-execution,
non-enforced timeout, unbounded structured result, heartbeat-settable
scheduling state). Round 2 found and fixed 1 blocking
workflow/availability gap (approval-gate refusal treated as a hard
failure instead of a legitimate pending state -- see
`SECURITY_REVIEW.md` threat #23; nothing unauthorized ever executed at
any point, before or after). Round 3 found and fixed a narrower gap in
round 2's own fix: expiry detected *after* approval had already moved
the job to `RUNNING` left the job and its worker stuck rather than
ending safely. Five previously-named open gaps remain, unaffected by
any round's fixes and none exploitable within this workload's actual
threat surface today (no network transport exists yet; capability set
is deliberately low-consequence; no production credentials reachable):
no cryptographic worker credential, no subprocess environment
allowlisting, no symlink-escape-specific test, no
result-authenticity binding beyond internal-consistency digest, no
coordinator persistence.

## 11. Future Tailscale/network plan

Design-only, in `docs/architecture/KARMO_WORKER_RUNTIME_NETWORK_PLAN.md`.
Target end state: zero inbound ports on any worker machine; outbound-only
polling over Tailscale; TLS + signed worker credentials + coordinator
authentication before any real network transport ships. No network,
firewall, or Tailscale configuration was changed to produce this plan.

## 12. PRs/commits

PR #23 (implementation + tests, `worker-runtime/implementation`), PR #24
(architecture/security/network docs, `worker-runtime/docs`), PR #25
(evidence + PROJECT SAVE, `worker-runtime/evidence`) -- all against
`core-v2/prototypes`, disclosed explicitly in the Invariant Impact
Review. Updated after three rounds of independent verification: PR #23
at implementation commit `a2a1619` (round 1: `5906f61`, the 4-fix
commit; round 2: `08c501e`, the pending-approval workflow fix; round 3:
`a2a1619`, the expiry-after-approve fix), PR #24 and PR #25 updated to
match each round. None merged.

## 13. Production access: 0
No SSH, no production database, no production Qdrant, no production
credentials were touched at any point in this workload.

## 14. Network changes: 0
No Tailscale, firewall, or network configuration was changed.

## 15. Merges: 0
No branch was merged to `main` or to `core-v2/prototypes`.

## 16. PROJECT SAVE status
See `docs/project-state/{CURRENT_STATE.md,NEXT_STEPS.md,CHANGE_LOG.md}`
(updated this round) and the final chat report for the exact PROJECT
SAVE confirmation (files updated, commit hash, stopping point, next
action).

## 17. Independent verification commands
`VERIFICATION_CHECKLIST.md` -- 13 commands (10 original + 1 round-1
addition proving the approval-gates-execution fix + 1 round-2 addition
proving the pending-approval park/resume workflow + 1 round-3 addition
proving the expiry-after-approve fix), all re-executed live against the
fixed code with output matching what's documented there.

## 18. Blockers
None -- but only as of this update. Three rounds of independent
(ChatGPT) verification of PRs #23-#25 found blocking findings before
merge (see section 10 and `RUN_SUMMARY.json`): round 1 found 4 security
gaps, round 2 found 1 workflow/availability gap in round 1's own fix,
round 3 found 1 narrow gap in round 2's own fix (expiry detected after
approval had already moved the job to RUNNING). All are now fixed,
tested (68/68 passing), and re-verified live via the updated
`VERIFICATION_CHECKLIST.md`. PRs remain open, unmerged, awaiting
re-verification. All 15 phases were completed within the explicit scope
and prohibitions of this workload; no new prohibited action (production
access, network/firewall change, merge, new PR) was taken while fixing
either round's findings.

## 19. Recommendation for a future controlled KARMO-AI <-> M3 integration test

Once (a) a real network transport implementing `WorkerTransport` exists
per the Phase 15 plan -- including the redesigned `execute()` (an
execution-ticket exchange, not a callable-over-the-wire; see
`KARMO_WORKER_RUNTIME_NETWORK_PLAN.md`'s new section on this), (b) worker
credentials are cryptographically verified (not just
identity-consistency-checked), and (c) the coordinator has durable
persistence -- run a controlled test where KARMO-AI (the real
coordinator) submits exactly one `hash_verify` or `pytest` job against a
synthetic, explicitly-scoped test file, and KARMO-DEV01 polls, executes,
and returns a result over the real network path, with a human (Kamara)
watching the exchange live and able to kill it immediately. Do not expand
the SAFE capability set beyond `READ`/workspace-scoped
`REVERSIBLE_WRITE` for that first real integration test.

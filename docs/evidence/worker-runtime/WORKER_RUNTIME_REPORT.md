# KARMO Worker Runtime v0.1 -- Implementation Report

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
(scenario 17).

## 7. Sandbox protections

- Capability dispatch only through handlers registered at import time
  (`sandbox._HANDLERS`) -- no job payload can ever supply its own
  executable or command.
- `resolve_within_sandbox`: hard containment check via
  `Path.resolve()` + `.relative_to()`; refuses (never silently clamps)
  any path escaping the allowed workspace.
- Per-job ephemeral temp directory, always cleaned up (`finally:
  shutil.rmtree`).
- `timeout_seconds` enforced per capability.
- Output capped at 64 KB (`MAX_OUTPUT_BYTES`), truncated with a marker.
- Errors sanitized: sandbox root's absolute path stripped, message capped
  at 2000 chars, no raw traceback ever returned.
- `pytest`/`static_analysis` invoke a fixed venv interpreter path, never
  a job-supplied one.

## 8. Failure/adversarial test results

All 24 required scenarios implemented and passing, plus 20 supporting
capability/integration tests -- **44/44 passing**. Full list and output
in `TEST_RESULTS.txt`. Four real defects were found and fixed while
building this suite (not merely reproduced from a checklist) -- see
`RUN_SUMMARY.json`'s `defects_found_and_fixed_this_workload`.

## 9. M3 benchmark results

See `BENCHMARK_RESULTS.json` (raw) -- summary:
- `resource_benchmark` (hash-loop CPU work): 100K iterations in ~7ms, 1M in
  ~63ms, 5M (the enforced cap) in ~309ms.
- `hash_verify` (real SHA-256 of the fixture file): <1ms.
- `pytest` (real subprocess: interpreter startup + collect + run 2 tests):
  ~144ms wall.
- `embedding_benchmark_test` (synthetic vector dot-products): 100 vectors
  ~3ms, 1,000 ~27ms, 10,000 (cap) ~269ms.
- `media_probe_test`: Metal 3 confirmed present (~212ms, dominated by
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

Full threat-by-threat table in `SECURITY_REVIEW.md`. Five named open gaps,
none exploitable within this workload's actual threat surface today
(no network transport exists yet; capability set is deliberately
low-consequence; no production credentials reachable): no cryptographic
worker credential, no subprocess environment allowlisting, no
symlink-escape-specific test, no result-authenticity binding beyond
internal-consistency digest, no coordinator persistence.

## 11. Future Tailscale/network plan

Design-only, in `docs/architecture/KARMO_WORKER_RUNTIME_NETWORK_PLAN.md`.
Target end state: zero inbound ports on any worker machine; outbound-only
polling over Tailscale; TLS + signed worker credentials + coordinator
authentication before any real network transport ships. No network,
firewall, or Tailscale configuration was changed to produce this plan.

## 12. PRs/commits

See the final chat report for the exact PR numbers/URLs opened at the end
of this workload (branch: `worker-runtime/implementation`, based on
`core-v2/prototypes`, disclosed explicitly in the Invariant Impact
Review).

## 13. Production access: 0
No SSH, no production database, no production Qdrant, no production
credentials were touched at any point in this workload.

## 14. Network changes: 0
No Tailscale, firewall, or network configuration was changed.

## 15. Merges: 0
No branch was merged to `main` or to `core-v2/prototypes`.

## 16. PROJECT SAVE status
See the final chat report for the exact PROJECT SAVE confirmation
(files updated, commit hash, stopping point, next action).

## 17. Independent verification commands
`VERIFICATION_CHECKLIST.md` -- 10 commands, all executed live during this
workload with output matching what's documented there.

## 18. Blockers
None. All 15 phases were completed within the explicit scope and
prohibitions of this workload.

## 19. Recommendation for a future controlled KARMO-AI <-> M3 integration test

Once (a) a real network transport implementing `WorkerTransport` exists
per the Phase 15 plan, (b) worker credentials are cryptographically
verified (not just identity-consistency-checked), and (c) the coordinator
has durable persistence -- run a controlled test where KARMO-AI (the real
coordinator) submits exactly one `hash_verify` or `pytest` job against a
synthetic, explicitly-scoped test file, and KARMO-DEV01 polls, executes,
and returns a result over the real network path, with a human (Natalie)
watching the exchange live and able to kill it immediately. Do not expand
the SAFE capability set beyond `READ`/workspace-scoped
`REVERSIBLE_WRITE` for that first real integration test.

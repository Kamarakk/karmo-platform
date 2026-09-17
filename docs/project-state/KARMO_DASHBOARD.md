# KARMO Mission Control

Human-friendly working dashboard for keeping the active project stage visible during long engineering sessions.

`CURRENT_STATE.md` remains the authoritative detailed state record. This file is a concise cockpit view and must not contradict it.

## KARMO CURRENT STAGE

- Foundation & Reliability Layer (Foundation v1) — ✅ COMPLETE
- KARMO Control & Approval Layer (Core) — ✅ DEPLOYED TO KARMO-AI01
- Trusted Computer Worker System (Worker Runtime local service boundary) — ✅ DEPLOYED TO KARMO-AI01
- Direct remote network path to KARMO-AI01 over Tailscale — ✅ ACTIVE (`100.75.239.44`)
- Real Worker Runtime network transport / remote job execution — ✅ ENABLED (SSH stdio gateway; corrected 2026-09-15 — this line was stale since ~2026-09-13/14; see `CURRENT_STATE.md`'s reconciliation section for verification of all 5 previously-deferred security items, all now closed: cryptographic worker credential, subprocess env allowlisting, symlink-escape test, result-authenticity binding, durable Postgres-backed coordinator persistence)
- KARMO Access & Connection Registry — ✅ MERGED
- KARMO System Stewardship design — ✅ MERGED; workers not yet implemented/deployed
- Durable Memory Core integration (conversation/semantic/document recall in `chat`) — ✅ DEPLOYED TO KARMO-AI01 (2026-09-15), canary-verified
- KARMO PR #43 hardening (approval authority binding, model routing policy, recovery hardening) — ✅ DEPLOYED TO KARMO-AI01 (2026-09-15), canary-verified
- Keyword dispatch false-positive fix (PR #57) — ✅ DEPLOYED TO KARMO-AI01 (2026-09-15), canary-verified
- BloomBoss Historical Data Intelligence (Phase 1) — ✅ MERGED to `main` (PR #56, 2026-09-16); isolated dev/GitHub scope only, no production deployment
- KARMO webui (loopback + Tailscale-interface bind modes) — ✅ DEPLOYED TO KARMO-AI01 (2026-09-16), running in `tailscale` mode at `http://100.75.239.44:8787`, verified reachable and chat-round-trip tested; `karmo-chat`/`karmo-web` shell helpers added on KARMO-DEV01
- KARMO orchestration task board (first KARMO↔Claude/GPT slice, no API keys/billing) — ✅ DEPLOYED TO KARMO-AI01 (2026-09-16), full create→list→claim→complete canary verified via `python3 -m core_service task ...`, including both negative-path guards (double-claim, wrong-claimant completion)
- Worker01/Worker02 local model hosting (`qwen3:8b`/`ministral-3:8b`/`mistral:7b`/`granite3.3:2b` via `karmo-ollama` Docker container) — ✅ DEPLOYED (2026-09-16), functional smoke-tested on both, loopback-only, closes the 2026-09-13 checkpoint's "next infrastructure phase" gap
- `model_chat` worker capability (PRs #68/#69/#70) — ✅ GRANTED to both Worker01 and Worker02, **real `SUCCEEDED` job proven on each** via manual `--once` invocation; 4 orphaned jobs reconciled via `recover_expired_leases()` → `RECOVERY_REQUIRED`
- **Sustained-service hang root-caused and fixed (PR #74, 2026-09-17)** — `run_capability()`'s job sandbox switched `multiprocessing` context from `fork` to `spawn`. Root cause: a long-lived worker makes thousands of subprocess/SSH calls between jobs; `fork()` only clones the calling thread, so a lock held by another thread at the instant of a fork could be inherited permanently locked in the child with no thread left to release it — a silent, untraceable deadlock, matching every observed symptom (service-only, zero exceptions, no crash). Diagnosed jointly with GPT (second opinion shaped the fix's actual scope — spawn requires verified picklability, not just a context-string swap). 125/125 worker-runtime tests pass (Python 3.9 and 3.12). Merged to `main` (`af12ed8`). **Deployed to Worker01 only** (new `MainPID=107737`, `--check-config` clean) — ⚠️ NOT YET CANARY-VERIFIED under the live service (see CURRENT ISSUE below). Worker02 not yet touched with this fix.

## WHAT THE MAJOR KARMO SYSTEMS ACTUALLY DO

- Reliable Event Delivery (H0.1 Transactional Outbox) — protects event delivery across failures.
- Document Memory & Versioning (H0.2 Knowledge Lifecycle) — manages active versions and provenance.
- Experimental Hybrid Search (H0.3 Hybrid Retrieval) — evaluated and intentionally not promoted to production.
- Integrity & Consistency Checker (H0.4 Integrity/Reconciliation) — detects state mismatches across KARMO data systems.
- KARMO Control & Approval Layer (Core) — production control boundary for capability classes and approval requirements; local-only, no network listener.
- Trusted Computer Worker System (Worker service boundary) — production-local Worker shell bound to Core; no network listener, no real worker transport, no capability execution, no persistent writes.
- KARMO Access & Connection Registry — durable machine-readable host, route, authentication-reference, and recovery knowledge for humans and agents.
- KARMO System Stewardship — planned QA, Security, Reliability/Maintenance, Housekeeping/Data-Hygiene, and Agent-Governance roles implemented over existing Core/Worker architecture rather than separate infrastructure stacks.
- BloomBoss Historical Data Intelligence — normalizes purchase, sales, listing, propagation, and Palmstreet staging history; preserves unknowns and provenance; validates contradictions; fingerprints raw evidence; and calculates reproducible business/quality metrics.
- KARMO-FIRST Orchestration — target control plane where KARMO owns durable task state, routing, capabilities, approvals, execution authority, verification evidence, and audit while ChatGPT/Claude/local/future models remain replaceable intelligence adapters.

## CURRENT TASK

**Stopped mid-canary, 2026-09-17, end of a 12+ hour session — pick this
up first.** The fork→spawn fix (PR #74) is merged and deployed to
Worker01, but the canary that proves it under the real live service has
NOT yet succeeded — the session ended before a working enqueue attempt
completed. See "IMMEDIATE NEXT ACTION" below for the exact resume point.

Once that canary is clean and Worker02 also gets the fix: spot-check
BloomBoss's analytics output against known real sales (candidate first
real task for the orchestration board), or choose the next KARMO
capability track — see `NEXT_STEPS.md`.

## IMMEDIATE NEXT ACTION (resume point, 2026-09-17)

1. **Worker02's service is currently STOPPED** (`karmo-worker02.service`,
   deliberately, to isolate the canary to Worker01 — this was NOT
   restarted before the session ended). Restart it first:
   `ssh -i ~/.ssh/karmo_admin_ed25519 karmo@192.168.1.252 'sudo systemctl start karmo-worker02.service && systemctl is-active karmo-worker02.service'`
   — unless you specifically want it to stay down to keep isolating the
   Worker01 canary a while longer, in which case restart it once the
   canary below succeeds.
2. Re-run the `model_chat` canary enqueue against `karmo-gateway` on
   `karmo-ai01` — the last attempt failed with
   `WorkerGatewayRuntimeError: gateway runtime dependency unavailable`
   because only `/opt/karmo/core-service` was on `sys.path`, not
   `/opt/karmo/worker-runtime/app` (where `crypto_boundary.py` lives).
   Fixed script (both `sys.path.insert` lines, `-t` for the sudo TTY
   prompt) is in the session transcript ending
   `...KARMO-DEV/6b9897bb-2f63-4a7e-8f78-c2aeb85f423e.jsonl` — not yet
   confirmed to run clean end-to-end.
3. Once a `JOB_ID` comes back, check its state and Worker01's journal
   (`sudo journalctl -u karmo-worker01.service`) to confirm a clean
   `SUCCEEDED`/`FAILED` outcome with no silent hang.
4. Since the original bug was a rare race needing hours of uptime to
   surface, one clean job is necessary but not sufficient — leave
   Worker01's service running under normal load for a few hours (or
   overnight) before calling it proven, per the plan already agreed
   with GPT's recommendation.
5. Only after that window is clean: deploy the identical fix to
   Worker02, then PROJECT SAVE.

## CURRENT ISSUE

`karmo-worker02.service` is stopped (see IMMEDIATE NEXT ACTION above) —
not a code blocker, a deliberate paused state from tonight's canary
isolation that still needs to be resolved (restarted, or left stopped
intentionally) next session.

Otherwise: no active code blocker. KARMO-AI01, KVE01–03, and both
workers are all verified reachable and healthy as of the 2026-09-11–15
reconciliation (`CURRENT_STATE.md`) — the Sept-11-era Remote Desktop
Commander/Proxmox reachability concern previously noted here is
resolved.

Palmstreet's built-in order export was unreliable/unavailable as of the
Phase 1 build session; Seller Hub table evidence remains staged as a
fallback source pending re-verification, not the long-term primary
ingestion design.

## NEW GOVERNING RULE

**KARMO FIRST:** Before recommending an app, SaaS product, manual export, cloud folder, phone shortcut, or third-party workflow, first determine whether KARMO can own the capability using infrastructure already available.

External systems should be sources, destinations, or adapters — not KARMO's brain, workflow engine, authority layer, or source of truth.

## NEXT GATE

1. ~~Kamara's merge/promotion decision on BloomBoss Phase 1~~ — done, merged (PR #56).
2. Spot-check BloomBoss Phase 1's analytics output against known real sales/purchases.
3. Choose the next KARMO capability track.

## AFTER THIS

- Extend Palmstreet staging so all verified Seller Hub fields, including Buyer Note and Seller Note, are represented and tested without storing unnecessary customer PII in source control.
- Keep Palmstreet purchases and sales as structured platform evidence when possible; screenshots/invoices remain fallback evidence only.
- Continue BloomBoss reconciliation only when source evidence can be reliably mapped to canonical inventory without invented matches.
- Production remains separately approval-gated.

## ACTIVE SAFETY / AUTHORITY BOUNDARY

- Core is production-deployed, local-only, and has no network listener.
- Worker service boundary is production-deployed with real SSH-stdio Worker network transport enabled (corrected 2026-09-15) and bounded READ-only capability execution (`commander.system_snapshot`/`service_status`/`listener_snapshot`, `local_model_probe`) — still no arbitrary shell, no write/destructive capability, no inbound listener on either worker.
- Tailscale provides direct network reachability only; Tailscale SSH is not enabled.
- KVE02 remains the documented fallback remote path.
- Production access remains task-specific and approval-gated.
- BloomBoss (PR #56, merged 2026-09-16) remains isolated dev/GitHub scope only: no production DB implementation, no marketplace writes, no customer actions, no OBS, no production deployment.

## CLOSED (2026-09-15 correction) — previously listed as deferred before real Worker network exposure

All 5 previously-named blockers were closed between roughly 2026-09-13 and
2026-09-14, verified present in code 2026-09-15: cryptographic worker
credential (`worker-runtime/app/crypto_boundary.py`), subprocess
environment allowlisting (fixed `env={...}` on every Commander subprocess
call), a dedicated symlink-escape test
(`worker-runtime/tests/test_runtime_file_security.py`,
`test_predeploy_security_hardening.py`), result-authenticity
cryptographic binding (`ResultAuthenticator`), and durable
Postgres-backed coordinator persistence (`PostgresWorkerCoordinatorStore`
— not in-memory). Real Worker network transport (SSH stdio gateway) is
now enabled and production-proven for Worker01/Worker02's Commander READ
path. This section previously listed these as still deferred; that was
stale.

## SESSION STATUS FORMAT

For consequential KARMO work, ChatGPT should keep a compact orientation line near the top of the response when useful:

`KARMO │ <plain-English current stage> (<technical name>) │ <current task> │ <step/gate> │ Next: <next action>`

Plain-English purpose comes first. Engineering names remain in parentheses so Kamara can learn the real terminology without losing context.

## PROJECT SAVE REFRESH RULE

Refresh this dashboard during every meaningful PROJECT SAVE whenever any of the following changes:

- current project stage
- current task
- active blocker/issue
- next approval or verification gate
- immediate post-task direction

Keep it short. Historical detail belongs in `CHANGE_LOG.md`, `CURRENT_STATE.md`, and dated PROJECT SAVE files.

Last refreshed: 2026-09-17

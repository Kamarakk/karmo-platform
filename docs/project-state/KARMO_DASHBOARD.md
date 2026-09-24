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
- **Sustained-service hang root-caused and fixed (PR #74, 2026-09-17)** — `run_capability()`'s job sandbox switched `multiprocessing` context from `fork` to `spawn`. Root cause: a long-lived worker makes thousands of subprocess/SSH calls between jobs; `fork()` only clones the calling thread, so a lock held by another thread at the instant of a fork could be inherited permanently locked in the child with no thread left to release it — a silent, untraceable deadlock, matching every observed symptom (service-only, zero exceptions, no crash). Diagnosed jointly with GPT (second opinion shaped the fix's actual scope — spawn requires verified picklability, not just a context-string swap). 125/125 worker-runtime tests pass (Python 3.9 and 3.12). Merged to `main` (`af12ed8`). **✅ DEPLOYED AND PROVEN ON BOTH WORKERS (2026-09-17)**: Worker01 (`MainPID=107737`) canary-proven, then soak-tested clean for 6 consecutive checks over ~3 hours of real sustained load (17:15–20:15 UTC — same PID throughout, zero stuck jobs every check); Worker02 (`MainPID=105750`) deployed and canary-proven (`SUCCEEDED`, ~53s, job `6bf6588c-...`). **This workstream is closed** — no further action needed on either worker.
- **KARMO chat tool-calling + BloomBoss + external delegation (PRs #75/#79/#77/#78, 2026-09-17/18)** — full implementation of `docs/architecture/KARMO_CHAT_TOOL_CALLING_AND_EXTERNAL_DELEGATION.md`, all 4 phases, merged to `main` (`ed5ecd7`). `operator.py`'s `_chat()` now has a real, bounded tool-calling loop (Ollama native function-calling, 4-round cap) restricted at definition time to `CapabilityClass.READ`-only tools (`_CHAT_EXPOSED_TOOLS`), the dispatcher itself refusing anything else as defense in depth. Four tools live: `list_tasks` (proof, no new logic), `bloomboss_report` (wraps existing `bloomboss.report.snapshot_report()` — closes the exact "KARMO can't answer BloomBoss questions" gap that started this plan), `ask_claude` and `ask_gpt` (delegate to Anthropic/OpenAI's own CLIs under Kamara's existing subscriptions, verified zero extra cost against each vendor's own docs — Claude's docs actively endorse this pattern, OpenAI's recommend against it for automation though it works the same way; built anyway at Kamara's explicit choice). Every tool proven with a **real** local model actually choosing to call it and a real result flowing back — not mocked — including catching and fixing a real null-argument bug (`list_tasks`) and two real `codex` CLI bugs (missing `--skip-git-repo-check`, stdin hang risk) via live testing before merge. 240/240 core-service tests pass (Python 3.9 and 3.12). **Deployed to `karmo-ai01` (PR #80, 2026-09-18)** — a real timeout/silent-fallback bug found post-deployment and fixed same day.
- **Model Router Phases D1/D2/E (2026-09-19/20)** — D1 (worker tool-calling round trip) proven live end-to-end after root-causing a missing DB grant (migration 009). D2 (routing real chat traffic to a worker) built, wired, **independently reviewed twice, merged but deliberately held dormant** (over-privileged credential, no data-retention policy, a selection race, and an unproven speed benefit — none accepted yet). E (durable decision audit) built, merged, deployed live. Circuit breaker built/merged, not yet wired into live routing.
- **BloomBoss chat-integration reliability fixes (PRs #102–#106, 2026-09-19/20)** — four real live bugs found and fixed in sequence (model guessing instead of calling a tool; chat deadline too tight for cold model load; oversized tool results fed back to the model; tool-schema token inflation), ending in selective tool-offering (only offer a tool's schema when the message matches its trigger keywords). All deployed and confirmed with a real successful chat answer.
- **Chat performance/cost work (PRs #107–#112, 2026-09-20)** — trivial-message short-circuit (skips the model entirely for a plain greeting/ack), configurable `num_predict` cap, an exact-match cache for `ask_claude`/`ask_gpt`, and router-config cleanup after deleting unused `ministral-3:8b`/`granite3.3:2b` from `karmo-ai01`.
- **KVE hardware fully verified live (PR #100, 2026-09-19)** — KVE01/02/03 are identical-spec hosts (i7-10700, 8c/16t, 15GiB RAM, no GPU). `karmo-ai01` itself is a VM (VM100/KVE02, 7.8GB RAM). Worker01/Worker02 confirmed to have 9.7GB each — more headroom than the brain machine — and had `ministral-3:8b`/`granite3.3:2b` deleted (PRs #108, #116) to match.
- **Local eyes/coding-helper/ears/voice capabilities (PR #117, merged 2026-09-20)** — Moondream2 (vision), qwen2.5-coder:7b (coding helper, wired into real chat), faster-whisper (transcription), and Piper (speech synthesis), all built and live-verified on Worker01, zero Claude/GPT dependency. **Inert in production** — require the worker-dispatch DSN, which does not yet exist.
- **D2/worker-dispatch decoupling + least-privilege credential (PR #118, merged 2026-09-20)** — a real coupling finding (the one DSN file that activates the four local capabilities above also silently re-activated Model Router D2's held-back chat routing) fixed with a second, independent gate file D2 now also requires. A dedicated least-privilege Postgres role (`karmo_core_dispatch`, migration 011) replaces the flagged role-reuse design for the dispatch credential — code merged, role not yet provisioned in production.
- **`ask_claude` optional image input — reverted, then restored with corrected policy (PRs #113/#114/#115, 2026-09-20)** — built, briefly reverted on an over-strict reading of "don't depend on Claude/GPT," then restored once Kamara clarified the actual standing rule: Claude/GPT may be an explicit, optional supplementary tool for any capability, but never the sole/main source of one.

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

As of 2026-09-20: chat tool-calling/BloomBoss/delegation is deployed and
live; Model Router Phases D1/E are live, D2 is merged but deliberately
held dormant; four local capabilities (eyes/coding-helper/ears/voice,
PR #117) are merged but inert; the DSN-coupling gap between D2 and the
local capabilities is fixed (PR #118). See the dashboard entries above
and `PROJECT_TODO_LIST.md` for full detail.

Two real open decisions, in the order they'd naturally come up:
1. Whether/when to create the worker-dispatch DSN (activates the four
   local capabilities; does NOT by itself re-activate D2 routing anymore,
   per PR #118's fix) — the `karmo_core_dispatch` role from PR #118 still
   needs provisioning in production first.
2. The client-surface build (browser mic/speaker + phone) needed before
   vision/ears/voice are reachable from a real conversation — not
   started. The coding helper is already wired into chat and needs no
   client surface, only the DSN above.

Parked, not cancelled: an ethical-hacking/pentest capability (Kamara's
own request, cybersecurity student, authorized self-testing), deferred
pending an isolated lab network decision (target date 2026-09-22).

## CURRENT ISSUE

No active code blocker. KARMO-AI01, KVE01–03, and both workers are all
verified reachable and healthy (KVE hardware fully verified live
2026-09-19, PR #100).

Palmstreet's built-in order export was unreliable/unavailable as of the
Phase 1 build session; Seller Hub table evidence remains staged as a
fallback source pending re-verification, not the long-term primary
ingestion design.

## NEW GOVERNING RULE

**KARMO FIRST:** Before recommending an app, SaaS product, manual export, cloud folder, phone shortcut, or third-party workflow, first determine whether KARMO can own the capability using infrastructure already available.

External systems should be sources, destinations, or adapters — not KARMO's brain, workflow engine, authority layer, or source of truth.

## NEXT GATE

1. ~~Kamara's merge/promotion decision on BloomBoss Phase 1~~ — done, merged (PR #56).
2. ~~Spot-check BloomBoss Phase 1's analytics output~~ — done, 2026-09-17.
3. Provision the `karmo_core_dispatch` role in production (PR #118, code merged, role not yet created) and decide whether to create the worker-dispatch DSN.
4. Build the client surface (browser mic/speaker + phone) needed for vision/ears/voice.
5. Decide the ethical-hacking/pentest lab-network question (parked to 2026-09-22).

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

Last refreshed: 2026-09-20 (Model Router D1/D2/E, local eyes/coding-helper/ears/voice, D2/worker-dispatch decoupling)

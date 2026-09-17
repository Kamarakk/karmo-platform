# KARMO Current State

Last reconciled: 2026-09-10 (Worker Runtime v0.1 final merged-main
closeout — PRs #22, #23, #24, and #25 all merged into `main`), following
the KARMO Large Autonomous Review of PR #14–#21 and the Post-Foundation
Overnight Readiness/Core v2 Engineering Blueprint programs earlier in
this sequence. See MASTER_INDEX.md for status-tag definitions.

**Full reconciliation of 2026-09-11 through 2026-09-15 added 2026-09-15**
— see "2026-09-11 through 2026-09-14 — Access rollout, Core/Worker
productionization, dual-worker Commander, model stack" and "Durable
Memory Core integration" below. Source records for the reconciliation:
the eleven `PROJECT_SAVE_2026-09-1{1,2,3,4}_*.md` checkpoints in this
directory, cross-checked against `git log`/`gh pr view` for exact merge
commits and current PR state (not taken on the checkpoint files' word
alone).

## 2026-09-11 through 2026-09-14 — Access rollout, Core/Worker productionization, dual-worker Commander, model stack

**VERIFIED (repo + operator-attested production checkpoints), reconciled
2026-09-15.** This section covers the gap between the 2026-09-10 Worker
Runtime v0.1 merge closeout above and the 2026-09-15 Durable Memory
section below. Chronological summary; each PROJECT SAVE checkpoint cited
remains the detailed source.

### 2026-09-11 — Tailscale enrollment, Core v2 and Worker Runtime deployed to `karmo-ai01`

- KARMO-AI01 enrolled in the existing tailnet at `100.75.239.44`
  (production DNS acceptance disabled, Tailscale SSH not enabled, no
  subnet routes/exit-node). KVE02 `100.75.39.34` retained as fallback.
- **PR #33** (`feat: productionize Core v2 for approved rollout`) merged
  (`cdbe704e577919c2f63569df41dc3f777dc47c4f`): consolidated the rollout
  branch onto one canonical `core-service/` implementation (the
  `core-v2-prototypes/` tree remains design/evidence only, never copied
  into production), local-only, no listener, no DB/Qdrant writes.
- Read-only host preflight found no path/service-name collisions but
  also found `lofason` lacks non-interactive sudo on `karmo-ai01` —
  privileged install required an interactive session, deferred one
  checkpoint rather than proceeding unattended.
- Once performed: `karmo-core.service` installed to
  `/opt/karmo/core-service`, enabled, active. Deployment automation
  gated Worker install on Core's health check passing first.
- **PR #34** (`feat: productionize Worker Runtime behind Core`) merged
  (`21019c1e2833b0f797e09d225639305530c48f3e`): new `worker-service/`
  restricted production boundary — hard dependency on Core binding,
  fail-closed if Core is unavailable, no listener, no DB/Qdrant writes,
  no capability/job execution yet (this predates Commander). Gate C
  evidence: `docs/evidence/worker-runtime/PRODUCTIONIZATION_GATE_C.md`.
  `karmo-worker.service` installed, enabled, active.
- **PR #35** (`docs: add access registry and system stewardship
  framework`) merged (`d158fc4d252af1daf03dd77c57b066a29446ec44`):
  `docs/access/*` registry (hosts, auth methods, connection paths,
  recovery tree), and the Mandatory System-Fit & Reuse Review adopted
  into agent workflow (`docs/governance/KARMO_SYSTEM_FIT_REVIEW.md`,
  referenced from `CLAUDE.md`/`AGENTS.md` item 8).
- A Remote Desktop Commander npm install attempt on `karmo-ai01` failed
  (`ERR_REQUIRE_ESM`, host Node `18.19.1` too old for the current
  dependency chain) — a tooling compatibility issue, not a KARMO defect;
  no production change resulted from the attempt.
- **Controlled reboot performed** (to load already-installed kernel
  `6.8.0-139-generic`, previously running `6.8.0-138-generic`).
  Post-reboot verification: `tailscaled`, `karmo-core.service`,
  `karmo-worker.service`, `docker.service` all active; `loginctl
  show-user lofason -p Linger` = `yes`; the H0.1 relay process survived
  reboot (closing that previously-open reboot-persistence gap).
- **Not done in this rollout**: real Worker network transport, Worker
  capability/job execution, any DB schema change, Qdrant mutation, or
  existing-service restart beyond Core/Worker themselves.

### 2026-09-12 — Durable worker coordination hardening merged; H0.1 test-hardening pushed (not merged)

- **PR #41** (`harden durable worker coordination boundaries`) merged
  (`879b242c801f10fc141e68874847d9b9315dd304`): fail-closed current-key
  checks, drain-before-key-rotation, live-lease ticket fencing,
  authenticated heartbeat requirement, transactional worker audit
  events, fail-closed finalization, bounded terminal-ticket cleanup.
  Pre-merge CI green (Core Productionization #63, KARMO Full Predeploy
  #124). Post-merge read-only check: both `karmo-core.service` and
  `karmo-worker.service` active; app listeners still loopback-only
  (5433/6333/6334/11434) plus SSH; no worker-network listener opened.
- KVE02's host key was independently re-fingerprinted and confirmed
  matching before being (re-)pinned on `karmo-ai01` — strict host-key
  checking never relaxed; root SSH AI01→KVE02 remains refused by design.
- Branch `feat/worker-transport-activation` opened from the PR #41 merge
  point to begin Worker01/Worker02 activation, reusing the durable Core
  coordinator rather than building a second one.
- The H0.1 isolated failure-matrix test-hardening pass (3 real test-code
  robustness fixes, frozen `test/h01/app/` untouched, 19 passed/2
  skipped/0 failed) — already reconciled in this file's H0.1 section
  above — was pushed to `staging/karmo-full-predeploy-20260912` per
  explicit instruction not to merge that session. See
  `PROJECT_SAVE_2026-09-12_H01_TEST_HARDENING.md`.

### 2026-09-13 — Local model stack activated; Worker01 and Worker02 activated (bounded READ)

- **PR #45** (`feat: activate local open model stack`) merged
  (`37cfc110b32fde9898b7d90aa1855b1f608ab18f`): deterministic ranked
  chat routing `qwen3:8b → ministral-3:8b → granite3.3:2b`, independent
  verifier `mistral:7b`. DeepSeek and Gemini were evaluated and
  explicitly dropped (reasoning-path fit and no-cloud-dependency
  decisions respectively) — not merely unmentioned. CI green (Core
  Productionization #117, KARMO Full Predeploy #210). Staged production
  deploy completed all markers (`SOURCE_DEPLOY_PASS` through
  `MODEL_STACK_CONTINUOUS_DEPLOY_PASS`); independent post-deploy recheck
  confirmed the exact routing order, verifier, loopback-only Ollama, and
  matching deployed source hashes. `deepseek-r1:7b`/`deepseek-r1:8b`
  removed from AI01; `llama3.2:3b`/`qwen3:4b` remain installed but
  inactive (not part of routing; not deleted — a deferred cleanup
  decision).
- **KARMO-WORKER01** activated: registered through the durable
  coordinator, authenticated heartbeat active, capability scope limited
  to `local_model_probe`. Required bounded READ proof job succeeded in
  one attempt (`JOB_LEASED → EXECUTION_TICKET_ISSUED →
  EXECUTION_TICKET_CONSUMED → RESULT_SUBMITTED → JOB_SUCCEEDED`). No new
  listener introduced.
- **KARMO-WORKER02** activated the same way: host fingerprint
  `SHA256:HBMp5Pf16lETJFEBEnixIfCHaBGKBCY3fmisk24QHAg` confirmed,
  registered as `KARMO-WORKER02` (`local_model_probe`, transport
  `ssh_stdio`, no inbound listener), proof job `25236308-...`
  `SUCCEEDED` in one attempt, result digest
  `b9c2f3d672633f918fddd9863a378c129152c317b943feec07adc8ecfa7e8bde`.
  Temporary transfer secret and temporary proof-job grants both removed
  after activation. **Both workers independently production-proven** for
  the bounded READ path as of this checkpoint.

### 2026-09-14 — Dual-worker Commander READ Pack activated

- Reviewed Commander activation merged: `1423bc7ef82ca0bb9d9f421f3be5c25dcf52c002`
  (PR #47; PR #46 was the review-only precursor). Both workers hold the
  identical durable capability claim: `local_model_probe 1.0.0`,
  `commander.system_snapshot 1.0.0`, `commander.service_status 1.0.0`,
  `commander.listener_snapshot 1.0.0`. `commander.bounded_text_read` and
  `commander.directory_list` remain disabled — their `allowed_root`
  wiring is not production-complete and they fail closed by design (do
  not enable with `allowed_root=/` or `/etc` as a shortcut).
- Worker01 canary (`commander.system_snapshot`): approval
  `f8d15b7f-1591-40fb-8269-8d875bade029`, job
  `f00c7b5a-cab6-43c3-83d1-256688202409`, `SUCCEEDED` in 1 attempt,
  approval final state `EXECUTED`, result digest
  `d3e012370e73bdae4eeda0dd85698e4059a1a22d4ddbaccf699be1c184cd5132`.
- Worker02 canary: approval `8b75487c-f5f2-4d61-b9b3-4e93890b4958`, job
  `65797770-00a2-4cfd-95e9-c6bbc1a45589`, `SUCCEEDED` in 1 attempt,
  result digest
  `3c944c6611cd209129cd0c3530942320a845d49da347146fe864d70fa5317976`.
- **Production permission repair** (real change, recorded here as the
  authoritative record — matches the operator's own session log):
  ```sql
  GRANT INSERT ON TABLE public.core_approval_records TO karmo_gateway;
  GRANT INSERT ON TABLE public.karmo_worker_jobs TO karmo_gateway;
  ```
  Least-privilege, additive only — no broader role expansion. Required
  because the already-reviewed gateway API needed these two INSERT
  grants to actually persist the real approval/job path in production
  (the isolated tests had not exercised the production role's actual
  grant set).
- No new listener on AI01 or either worker; no cloud credential
  introduced; no arbitrary shell or unrestricted file capability
  enabled; SSH host-key verification enforced throughout; admin private
  key stayed on KARMO-DEV01; root SSH remains disabled on both workers.
- **Gate closed**: both workers independently production-proven for
  Commander READ through the full approval → job → payload → lease →
  ticket → execution → authenticated result → event/ledger path.

### Still open from this period — not yet merged, not yet deployed

**PR #43** (`draft: stage KarmoLab, routing + durable recovery
hardening`, opened 2026-09-13, base `main`, still **OPEN/DRAFT** as of
2026-09-15) — a substantial, separate body of hardening work on the same
`staging/karmo-full-predeploy-20260912` branch, continued past what PR
#36 already merged from it. Four iterations, each with its own CI
evidence per the PR description: (1) wiring the KarmoLab READ probe
through the authoritative `CapabilityRegistry`/`CapabilityDispatcher`
path with a closed manifest; (2) `ModelRouter` hardening (rejects
malformed resources, frozen/normalized capabilities, hard trust-tier and
exclusion gates); (3) operator policy hardening (explicit local-model
trust floor, fail-closed exact-`PASS` verifier matching — no more
prefix-match false acceptance); (4) durable restart/reconciliation
hardening (a validation pass before the first task write, so a bad
ledger row can no longer let earlier valid tasks be mutated first). **Do
not treat any of this as merged, deployed, or reviewed for this
reconciliation** — it is accurately tracked only as open in this
section and in `NEXT_STEPS.md`, pending Kamara's decision to bring it
through review and merge.

## PR #43 reconciliation — approval authority binding, model routing policy, recovery hardening (2026-09-15) — VERIFIED, merged, DEPLOYED

**Update: deployed and canary-verified on `karmo-ai01` the same day**
(merge commit `de16b6e959a0ccec30444abea6b1005f6cccd101`). The
deployment canary found a real, separate bug — `_WRITE_WORDS`/
`_STATUS_WORDS` (pre-existing keyword dispatch, unrelated to PR #43's
own content) had 17 combined false positives against ordinary English
phrases, including "healthy" silently reappearing via an unconflicted
merge line. Fixed systematically in PR #57
(`fbaf42752e7a4a124379778b9c7a3ea55fdc62c4`), deployed and re-verified
the same day. Full narrative:
`docs/project-state/KARMO_DEVELOPER_NOTES.md`'s second 2026-09-15 entry.
Also reconciled BloomBoss Phase 1 (PR #56) in parallel — a second
reconciliation pass was needed once this PR #43 work (and PR #57/#58)
landed on `main` after PR #56 was first opened, since both were being
worked concurrently in different sessions the same night; resolved
(one dashboard-doc conflict only), re-verified (183 core-service, 62
BloomBoss, 111 worker-runtime, 161 core-v2-prototypes, 2 worker-service
tests, all pass), and **merged** on Kamara's explicit merge/promotion
decision (`e8cda4f9c755d1d2cdd302c3c7cc7f0e8439e8fd`, 2026-09-16) per
PR #32's original stated gate. `bloomboss/` is now on `main`, still
isolated/dev-only — no production deployment, marketplace write, or
customer-facing action authorized or performed.

## KARMO webui — loopback and Tailscale-interface bind modes (2026-09-16) — VERIFIED, merged, DEPLOYED

Closes the remaining two items of "working with KARMO directly" (a
nicer browser interface, and mobile/remote access) from this session's
approved plan.

- **PR #60** (`core_service.webui`, loopback-only): a stdlib-only
  (`http.server`, zero new dependencies) local chat page, every request
  routed through the exact same `KarmoOperator.handle()` the CLI `chat`
  command uses — no separate authority path. `serve()` refuses any
  non-loopback bind by raising `ValueError`; not a systemd unit, manually
  started. 7 new tests (page served, 404 routing, chat round-trip,
  malformed/oversized/non-string body rejection, bind guard). Merged
  `5051875a630c2ac92c9212cdf5c492f385d4e4c3`.
- **PR #61** (Tailscale bind mode, Kamara's explicit choice after being
  shown the SSH-tunnel-only alternative): adds a second, explicitly-named
  mode (`"tailscale"`) that resolves this host's own Tailscale interface
  IP via `tailscale ip -4` (never a caller-supplied address) and binds
  only that — no wildcard/`0.0.0.0` bind is possible; any mode string
  other than `"loopback"`/`"tailscale"` raises `ValueError`. This reuses
  the already-VERIFIED `karmo-ai01-direct-tailscale` path in
  `docs/access/CONNECTION_PATHS.yaml` (`TRAVEL_REMOTE` context) rather
  than opening a new network boundary — still no public internet
  exposure. 2 new tests (mocked `tailscale ip -4` success and
  empty-output-rejected paths). Merged
  `f64b44ea2dce3982b4ec036f6dce5c199443a6e8`.
- **Deployed and verified on `karmo-ai01`**: running in `tailscale` mode,
  bound to `100.75.239.44:8787` only (confirmed via `ss -H -lntu`, not
  `0.0.0.0`). A direct chat round-trip from KARMO-DEV01 over the tailnet
  returned `memory_status: ACTIVE`. Reachable from any device already
  enrolled in the same tailnet (Mac or phone) with no SSH client needed
  for the browser path.
- `karmo-chat` and `karmo-web` shell functions added to KARMO-DEV01's
  `~/.zshrc` (a new file — none existed before) for one-command access
  from the Mac.
- One operational note recorded for future deploys: `pkill -f
  "core_service webui"` run over the same SSH invocation that contains
  that literal string in its own script text will self-match and kill
  the invoking shell (happened once this session, recovered cleanly, no
  data/service impact) — use a PID captured from `pgrep` instead, never a
  broad `pkill -f` string that could match the deploying script itself.
- Core service tests: 192 passed, 33 skipped (no local Postgres in dev
  environment; those run and pass in CI against a real container).
- **Production access this work**: deploy (file replace + process
  start/stop) only, within the same session-scoped authorization already
  covering this session's durable-memory deployment work. No schema
  change, no new credential, no change to `karmo-core.service` itself
  (webui is a separate, manually-managed process).

## KARMO orchestration task board (2026-09-16) — VERIFIED, merged, DEPLOYED

First slice of KARMO↔Claude/GPT collaboration, on Kamara's explicit
request and explicit constraint: stays entirely within her existing
Claude/ChatGPT subscriptions, no API keys, no per-token billing anywhere
in this feature.

**Correction to prior project-state records**: the Tool/Capability
Registry was documented (Post-Foundation Overnight Readiness Program,
2026-09-09) as "DESIGN ONLY, not implemented." That was true at the time
but is now stale — `core_service.control`/`registry`/`dispatcher`
(`CapabilityClass`, `ApprovalRequirement`, `compute_approval_requirement`,
`CapabilityRegistry`, `CapabilityDispatcher`, `ApprovalEngine`) are
production code, already serving `karmolab.read_status` since the Core
v2 productionization work. This session's orchestration work is the
first *new* domain registered on that existing machinery, not a
from-scratch registry build.

- **PR #63**: 4 new tools in a `karmo-orchestration` domain —
  `create_task`/`claim_task`/`complete_task` (`REVERSIBLE_WRITE`,
  `EXPLICIT_PER_SESSION_OR_TASK` floor per I-09, verified by test) and
  `list_tasks` (`READ`, `NONE` floor). `financial_action`/
  `destructive_action` both `False` on all four (verified by test).
  Deliberately **not** automated model dispatch: no outbound model API
  call, no API key, anywhere in `core_service/orchestration.py`. A human
  (Kamara) or a human-operated Claude Code/ChatGPT session reads a task
  via `KARMO_ACTOR=<actor> python3 -m core_service task list` and
  reports back via `task complete` — every write still goes through the
  exact same registry/dispatcher/`ApprovalEngine` path already proven for
  `karmolab.read_status`, no new governance mechanism.
  `KarmoOperator._dispatch_write` performs request+approve+execute in one
  trusted call, the same pattern `__main__.health()` and the worker-
  canary scripts already established — the human-in-the-loop gate is
  invoking the CLI at all (SSH to `karmo-ai01` with the admin key), not a
  second interactive approval step; approver/executor identity is always
  the explicit named actor, never a model's own identity standing in for
  a human's. Own least-privilege `karmo_orchestration` DB role and DSN
  file, separate from `durable_memory`'s — matches the registry
  architecture doc's own failure-isolation requirement. Merged
  `bbd091b1bc0bc64ff33274f774079b5219b016eb`.
- **Deployed and verified on `karmo-ai01`** via a full CLI canary: create
  → list(OPEN) → claim (as `claude-code`) → a second claim attempt (as
  `chatgpt`) correctly refused (`TaskStateError`) → complete attempted by
  the wrong actor correctly refused → complete by the actual claimant
  succeeds → confirmed durable in `public.karmo_orchestration_tasks` via
  direct query. No new listener introduced (`ss -H -lntu` baseline
  unchanged); `karmo-core.service`/`karmo-worker.service` both remained
  `active`.
- Core service tests: 205 passed (was 192), 38 skipped (5 new
  Postgres-contract tests skip without local Postgres in dev; all 5 ran
  and passed in CI against a real container).
- **Next step, not done yet**: a real KARMO→Claude/GPT task actually
  worked end-to-end through this mechanism (the canary task above was a
  synthetic proof, not a real piece of work) — e.g. routing the pending
  BloomBoss Phase 1 spot-check itself through `task create`/`task
  complete` once Kamara provides the real sales data.

## Worker model activation — Worker01/Worker02 (2026-09-16) — VERIFIED, DEPLOYED

Closes the gap named in `docs/checkpoints/KARMO_ACTIVATION_CHECKPOINT_20260913.md`
("KARMO-AI01 has approximately 8 GB RAM. Loading both local activation
models materially saturates available memory... this is the reason the
next infrastructure phase is the two approved HP worker nodes") — the
two worker nodes were reachable and Commander-active since 2026-09-14
but had never actually been given any model workload; that checkpoint's
step 2 ("Activate the approved worker-model target") was never done
until now.

**Correction to that checkpoint's stated target**: it named "Qwen +
DeepSeek + Gemini + Mistral." That's stale — a later decision explicitly
removed DeepSeek and rejected Gemini (a cloud model, conflicting with
KARMO's local-first principle), and the model set actually shipped in
`core_service.operator.default_model_resources()` is `qwen3:8b` /
`ministral-3:8b` / `mistral:7b` / `granite3.3:2b`. That's the set
installed here, matching what's live, not the superseded list.

- **Access path note**: Worker01 (`192.168.1.251`)/Worker02
  (`192.168.1.252`) are LAN-only, not Tailscale-enrolled, and use a
  distinct admin account (`karmo`, not `lofason`) with the same
  `karmo_admin_ed25519` key — reached from KARMO-DEV01 via SSH agent
  forwarding through `karmo-ai01` (`ssh -A lofason@100.75.239.44` then
  `ssh karmo@192.168.1.25{1,2}`), since KARMO-DEV01 has no direct LAN
  route to the workers. Documented here because it wasn't recorded
  anywhere and took real trial-and-error to find (see
  `docs/runbooks/WORKER01_EXACT_ACTIVATION.md` for the original
  provisioning record that named the `karmo` account).
- **Docker + `karmo-ollama` container installed on both workers**,
  matching `karmo-ai01`'s exact existing pattern (`ollama/ollama:latest`,
  loopback-bound `127.0.0.1:11434`, named volume) rather than a native
  install — reuses the proven approach instead of introducing a second
  deployment pattern. `docker.io` installed via `apt-get` (Ubuntu
  24.04.4, same as `karmo-ai01`).
- All 4 models pulled on both workers, digests verified byte-identical
  to `karmo-ai01`'s copies (`ministral-3:8b` `1922accd5827`, `qwen3:8b`
  `500a1f067a9f`, `mistral:7b` `6577803aa9a0`, `granite3.3:2b`
  `07bd1f170855`).
- **Functional smoke test passed on both**: a real `granite3.3:2b`
  generate call against each worker's own loopback Ollama API returned a
  real completion (not just a successful pull).
- **Listener boundary verified unchanged** on both workers (`ss -H
  -lntu`): Ollama bound to `127.0.0.1:11434` only, no new LAN/tailnet-
  facing port on either host.
- **Explicitly NOT done**: Core's `OllamaChatClient` remains
  loopback-only by deliberate security design (refuses remote endpoints,
  refuses HTTP redirects — PR #37's stated boundary, "no remote model
  endpoint"). Installing models on the workers does **not** by itself let
  `KarmoOperator` route inference to them — that would require a new,
  deliberately-designed capability (most likely worker-hosted inference
  routed through the existing Worker Runtime job/ticket/approval path,
  the same pattern Commander already uses, rather than relaxing the
  Ollama client's existing remote-endpoint refusal). Not started; a
  separate, security-relevant design decision for later, not something
  to build by extension of tonight's provisioning work.
- **Production access this work**: install (apt package, Docker
  container, model pull) + one read-only generate call per worker, within
  the same broad authorization already covering tonight's session. No
  KARMO application code changed, no listener beyond loopback, no
  approval/authority boundary touched.

## Worker model_chat activation on both workers, and a new deferred finding (2026-09-17)

Phase 1 of `docs/architecture/KARMO_WORKER_MODEL_INFERENCE_ROUTING.md`
(PR #68's `model_chat` capability) plus PR #70's submit_result fix
(#70) were carried through to a full, real, end-to-end proof on **both**
Worker01 and Worker02 — not just designed and merged, actually exercised
against live infrastructure:

- `update_capabilities` (PR #69) granted `model_chat` to both workers via
  the real gateway identity (Kamara ran the grant script interactively,
  since `sudo -u karmo-gateway` isn't in the `root`-only NOPASSWD sudoers
  list — a real, pre-existing access gap, documented rather than worked
  around by weakening anything).
- Each worker's flat `timeout_seconds` config (used for *every*
  capability on the SSH remote transport, not looked up per-capability
  from the manifest — a real, separate, pre-existing limitation) was
  raised from 30 to 150 to accommodate `model_chat`'s real generation
  time.
- **Both workers proven `SUCCEEDED` on a real `model_chat` job**, run
  manually via `python3 -m remote_worker_runtime ... --once` (not just
  the systemd service) — a real Ollama-generated response, signed,
  reported back to Core, durable `SUCCEEDED` state confirmed by direct
  query.
- **New deferred finding, not root-caused tonight**: `model_chat` jobs
  dispatched to the *long-running systemd service* (not a fresh `--once`
  invocation) got stuck in `LEASED` past lease expiry multiple times
  (3× Worker01, 1× Worker02), with **zero trace in `journalctl`** even
  with PR #70's new logging in place — meaning `run_loop`'s exception
  handler was never entered; something blocks without raising. Every
  time, a fresh manual `--once` run on the same host succeeded cleanly
  within the expected ~1 minute. This points at something specific to
  *sustained* operation of the polling loop (a resource/fd leak across
  many poll cycles is the leading hypothesis) rather than the capability
  or the fix from tonight. **Needs its own dedicated investigation**
  before `model_chat` (or any future long-running capability) is trusted
  under normal unattended service operation — right now it only has a
  manual-invocation proof, not an unattended-service proof.
- The 4 jobs orphaned by that finding were reconciled via the existing
  `PostgresWorkerCoordinatorStore.recover_expired_leases()` method
  (already built, never exercised in anger before tonight) — moved to
  `RECOVERY_REQUIRED`, not blindly marked `FAILED`, per that method's own
  explicit "never guess a stale job's outcome" design. All 4 confirmed
  moved; zero non-terminal `karmo_worker_jobs` rows remain.
- `docs/bloomboss/historical_data/emgarden_invoice_2026040040.csv` (PR
  #72) — first real BloomBoss historical import, extracted from a real
  supplier invoice with all personal contact information stripped before
  it ever reached the repo. BloomBoss Phase 1's spot-check (`NEXT_STEPS.md`
  item 2) is now closed against this real data plus 10 real sales:
  `python -m bloomboss.report` ran clean, all figures independently
  hand-verified.

29 commits of staged Core/Worker hardening work (open since
2026-09-13, no rejection ever recorded — just never brought to a
promotion decision) reconciled against 94 commits of diverged `main`
history and merged at `f2ba1a49ebe8baf664a93cf59dc74693506db42a`. Key
content: a real approval-reuse security fix (an approval could
previously be consumed across a different requester or authority-class
than it was issued under — now bound and independently checked at both
the dispatcher and the durable execution coordinator),
`ModelRouter`/`ModelResource` hard policy gates and validation, KarmoLab
wired through the registry/dispatcher, exact-match verifier strictness,
durable recovery preflight validation, terminal-status allowlisting, and
a worker document-size cap. 3 merge conflicts resolved (see
`docs/project-state/KARMO_DEVELOPER_NOTES.md` for full detail, including

29 commits of staged Core/Worker hardening work (open since
2026-09-13, no rejection ever recorded — just never brought to a
promotion decision) reconciled against 94 commits of diverged `main`
history and merged at `f2ba1a49ebe8baf664a93cf59dc74693506db42a`. Key
content: a real approval-reuse security fix (an approval could
previously be consumed across a different requester or authority-class
than it was issued under — now bound and independently checked at both
the dispatcher and the durable execution coordinator),
`ModelRouter`/`ModelResource` hard policy gates and validation, KarmoLab
wired through the registry/dispatcher, exact-match verifier strictness,
durable recovery preflight validation, terminal-status allowlisting, and
a worker document-size cap. 3 merge conflicts resolved (see
`docs/project-state/KARMO_DEVELOPER_NOTES.md` for full detail, including
the explicit decision to keep chat's 3-way model fallback rather than
let the new trust floor silently narrow it). Independent security
review: no HIGH/MEDIUM findings. All four test suites green post-merge.
**Not yet deployed to `karmo-ai01`** — code merge only.

## Durable Memory Core integration (2026-09-15) — VERIFIED, deployed

PR #48 (`feat/durable-memory-core-integration`, merge commit
`7b50a381b2e19e1b12aecd59182df3fd4215216b`) wired the existing H0.1
PostgreSQL (`conversation_memory`, `karmo_outbox`) and H0.2 Qdrant
(`karmo_semantic_memory`, `karmo_documents`) memory stack into the Core
`chat` operator. No new service, listener, datastore, or schema
migration. Independent security review (this session) found no
HIGH/MEDIUM issues before merge.

Production deployment to `karmo-ai01` surfaced 3 real defects, none
caught by the isolated test suite (which mocks the memory backend):

1. a pre-existing dispatch bug where `_STATUS_WORDS` matched the bare
   word "memory" inside hyphenated text, hijacking any chat message
   mentioning memory into the KarmoLab status tool instead of `_chat()`;
2. a status-masking bug where a write failure silently overwrote a
   simultaneous read failure in `memory_status`;
3. a missing production runtime dependency — `qdrant_client` was never
   installed for the system Python interpreter `chat` actually runs
   under; `core-service` had no `requirements.txt` declaring it.

All three fixed in PR #49 (`fix/durable-memory-deploy-gaps`, merge
commit `6cee676e5516075f2c81b6be2f2480f24c0042c0`), CI green (5/5 checks),
81 tests passing locally (2 new regression tests added). Full narrative,
exact commands, and evidence:
`docs/project-state/KARMO_DEVELOPER_NOTES.md` (2026-09-15 entry) and
`docs/review/KARMO_DURABLE_MEMORY_DEPLOYMENT_GATE.md`.

**Redeployed and verified on `karmo-ai01` (2026-09-15):** a bounded
production canary proved `memory=ACTIVE` on both a write turn and a
separately-started `chat` process's read turn (survives process
exit/reopen); `conversation_memory` gained the 2 expected rows;
`karmo_outbox` gained 1 `semantic_memory.upsert.v1` row, delivered by the
existing H0.1 relay; a second independent `chat` invocation correctly
recalled the canary phrase; the listener set (`ss -H -lntu`) was
unchanged from the pre-deploy baseline; `karmo-worker.service` was
unaffected throughout.

**Production Access Authorization (acted on, per
`docs/governance/KARMO_ENGINEERING_INVARIANTS.md`):**
```
PRODUCTION ACCESS AUTHORIZATION
Task: Durable memory Core integration deployment (PR #48/#49)
Target system/environment: karmo-ai01 — karmo-postgres (conversation_memory,
  karmo_outbox tables, and the conversation_memory_id_seq sequence only),
  /opt/karmo/core-service, /etc/karmo/core/, karmo-core.service
Purpose: deploy merged, tested, security-reviewed durable-memory Core
  integration
Permitted operations: read-only host/service/listener audit; create scoped
  Postgres role karmo_core_memory + grants; write
  /etc/karmo/core/postgres.dsn; backup + replace /opt/karmo/core-service
  (two deploy attempts); install psycopg/qdrant-client to the lofason user
  site-packages; restart karmo-core.service; bounded chat canaries +
  read-only verification queries
Authority: READ-ONLY + WRITE — CREATE ROLE/GRANT (scoped as above), file
  writes under /etc/karmo/core/ and /opt/karmo/core-service, one pip
  install, two service restarts. No other write.
Commands/command class: the numbered commands in
  docs/review/KARMO_DURABLE_MEMORY_DEPLOYMENT_GATE.md
Granted: 2026-09-15, by Kamara (in-session, read-only audit authorized
  first, then write/deploy authorized separately)
Expires: automatically on task completion (complete as of this entry)
```

Known non-blocking residuals: `qdrant-client`/`psycopg` are installed
per-user via pip (`--break-system-packages`, required by Ubuntu 24.04's
PEP 668 guard), not a project-pinned venv — fine at this scale, worth a
dedicated venv if dependencies grow. Two `/opt/karmo/core-service.bak.*`
trees exist from the two deploy attempts, not cleaned up (harmless).
Document retrieval was exercised by the code path but not independently
canaried with a real document match this session.

**KARMO FOUNDATION v1: DECLARED COMPLETE, 2026-09-09.** See
`docs/evidence/foundation-v1/FOUNDATION_V1_CLOSEOUT_REPORT.md` for the full
closeout report and `docs/evidence/foundation-v1/` for the complete
independent-verification evidence package.

**Post-Foundation Overnight Readiness Program run 2026-09-09** (same day,
repository-only, zero production access): independent re-verification of
the Foundation v1 evidence (one checklist correction), a fix for the
recorded H0.4 auditor gap, a repository-wide adversarial architecture
review, a Tool/Capability Registry design (design only, not implemented),
and a post-foundation capability roadmap (no capability chosen). PRs #14,
#15, #16 have since merged into `main` as part of the approved KARMO
merge sequence. See "Post-Foundation Overnight Readiness Program" section
below.

**Core v2 Engineering Blueprint Program run 2026-09-09** (same day,
repository-only, zero production access, zero merges): a full
architecture map of Foundation v1, a Tool/Capability Registry + Approval
Engine + Job/Event model + configuration single-sourcing + failure-
injection framework + autonomous-run evidence validator — all designed
and prototyped in isolation (160/160 tests passing) — a security threat
model, a Core v2 test strategy, and readiness specs for BloomBoss,
Voice/Media, and Finance/Trading, consolidated into a proposed KARMO Core
v2 specification. **No Core v2 component is implemented in production; no
domain capability is chosen or started.** See "Core v2 Engineering
Blueprint Program" section below and PRs #18, #19, #20, #21.

**Independent merge-readiness review of PRs #14–#21 completed 2026-09-09**
(same day, repository-only, zero production access): fresh reproduction
of every test claim, a real cross-PR conflict found and documented (PR
#17 vs. #21, both editing the same `docs/project-state/` files), and an
adversarial security re-review of the Core v2 prototypes that found and
fixed **4 real defects** in PR #19 (154 → 160 tests) plus 2 stale
test-count references in PR #20/#21 — all fixed **in the existing PRs**,
no new PR created for fixes (`review/pr14-21-merge-readiness` was opened
only for the review's own cross-cutting evidence). Full detail:
`docs/evidence/autonomous-review/KARMO_PR14_21_MERGE_READINESS.md`, plus
`MERGE_SEQUENCE.md`, `OPEN_FINDINGS_TRIAGE.md`,
`SPEC_PROTOTYPE_CONFORMANCE.md`, and `CAPABILITY_DECISION_MATRIX.md` in
the same directory. **PRs #14–#21 have since been merged into `main` by a
separate, later approved merge sequence** — the findings above reflect
the review's own conclusions as they stood at review time, before that
merge sequence ran.

## Top-line

- KARMO v0.5 baseline: **HISTORICAL** — frozen, superseded in production by
  H0.1–H0.4 cutovers below. Baseline reference preserved at
  `workspace/app-v05-reference` per H0.0/H0.1 handoff (host-side path, not in
  this repo).
- H0.0: **VERIFIED** complete (per H0.1 handoff doc, `MANIFEST-H0-FINAL.sha256`).
- H0.1: **VERIFIED** production cutover complete (see below).
- H0.2: **VERIFIED** production implementation installed (see below).
- H0.3: **VERIFIED** evaluated, **explicitly APPROVED AS NO-PROMOTION** — not
  part of the active production architecture.
- H0.4: **VERIFIED** production integration complete (see below).
- KARMO Engineering Invariants (I-01–I-09): **VERIFIED** established in
  `docs/governance/KARMO_ENGINEERING_INVARIANTS.md`, mandatory for all future
  phases.
- Legacy registry bootstrap: **VERIFIED** partially applied; 2 records
  intentionally left unresolved (see "Legacy registry bootstrap" below).
- Spec Kit: **VERIFIED** — brownfield initialization completed 2026-09-08
  (`specify init --here --force --integration claude`, v1.0.4);
  `feat/h05-spec-kit-adoption` merged 2026-09-09 (PR #9, `cd72938`). See
  "Spec Kit decision" below.
- Production Access Authorization Gate: **VERIFIED** adopted and merged
  2026-09-09 (PR #12, `e3443e8`, superseding closed PR #11) — see
  "Production Access Authorization Gate adopted" below.
- Foundation Closeout Program: **VERIFIED COMPLETE** (2026-09-09). Workload
  1 merged (PR #7, `db4ff2f`). Workload 2 executed under Natalie's
  temporary, task-specific Production Access Authorization and **PASSED**
  both defined checks (H01-T01, H01-T18) — see
  `docs/evidence/foundation-v1/PRODUCTION_READONLY_VERIFICATION.md`.
  Workload 3 merged (PR #8, `06ab726`). Workload 4 merged (PR #9,
  `cd72938`). Workload 5 remains not started, per explicit instruction —
  not required for Foundation Complete (see below).
- Active/next phase: **KARMO FOUNDATION v1 — COMPLETE** (declared
  2026-09-09; see `docs/evidence/foundation-v1/FOUNDATION_V1_CLOSEOUT_REPORT.md`).
  H0.5's scope remains undefined and **NEEDS VERIFICATION** — it is the
  first post-foundation capability phase, not a required foundation
  increment, and was explicitly not started or invented tonight. See also
  NEXT_STEPS.md.
- Project Save Completion Rule: **VERIFIED** adopted (2026-09-08) — appended
  to `docs/governance/KARMO_ENGINEERING_INVARIANTS.md`, referenced from
  `AGENTS.md` and `CLAUDE.md`. Applies to this and every future session,
  phase, and workload, including Spec Kit work. This reconciliation itself
  is being closed under that rule — see the PROJECT SAVE report accompanying
  this update.
- ChatGPT Session Persistence: **VERIFIED** adopted (2026-09-08, same day) —
  extends the Project Save Completion Rule (same section, not a separate
  rule) to cover Natalie's ChatGPT KARMO planning sessions: ChatGPT
  conversation history is explicitly **not** the authoritative KARMO project
  record; a ChatGPT session's consequential decisions/approvals/requirements
  only count as durably recorded once a repository-capable agent reconciles
  the session's handoff against `docs/project-state/` and commits the
  result, per the same PROJECT SAVE steps already in force. No AGENTS.md or
  CLAUDE.md change was needed — both already reference the rule as a whole
  rather than enumerating its sub-parts.
- KARMO Worker Runtime v0.1: **MERGED into `main` (PR #23 at commit
  `11d4f86e04d22aae0072923ec387a11f0e205cbc`, PR #24 at commit
  `9f3215ecd3be31d2096273be4afb389edbcbf9f8`, 2026-09-10) — but NOT
  deployed, NOT connected to production KARMO, NOT running anywhere
  outside this isolated prototype.** Merged into the repository's source
  tree is not the same claim as deployed or live — nothing here has been
  installed on, or connected to, `karmo-ai01`. First real post-foundation
  capability, built 2026-09-09/10 on branch `worker-runtime/implementation`
  (based on `core-v2/prototypes`, PR #19, also merged into `main`).
  **Three rounds** of independent (ChatGPT) verification of PRs #23–#25,
  before any merge: round 1 found 4 real blocking findings (approval
  gated job completion but not execution; timeout enforcement was a
  post-return check, not a real deadline; only `stdout_summary` was
  bounded, not the full result; a worker heartbeat could set
  coordinator-owned scheduling state directly) — fixed at commit
  `5906f61`. Round 2 found round 1's approval-gate fix was correct but
  left the normal WorkerClient flow with no way to represent "legitimately
  waiting on approval" other than a hard failure — an approval-required
  job was marked FAILED the instant it was leased — fixed at commit
  `08c501e` (approval-required jobs now park in `WAITING_FOR_APPROVAL`
  and resume execution exactly once approved, or end safely on
  denial/expiry). Round 3 found a narrower gap in round 2's own fix: an
  approval expiring *after* being granted (job already `RUNNING`) left
  the job and its worker stuck, since round 2's expiry guard only
  covered a job still `WAITING_FOR_APPROVAL` — fixed at commit `a2a1619`.
  **68/68 tests passing** (was 44/44 → 62/62 → 67/67 → 68/68), including
  all 24 required failure/adversarial scenarios plus all three
  fix-verification suites. **PRs #22, #23, #24, and #25 are all merged
  into `main`** (PR #25 at commit
  `b95acb603e632855298cc0d454df00b2c3d22286`, 2026-09-10) — Worker Runtime
  v0.1's full source, tests, docs, and evidence are now in `main`. **Still
  NOT deployed, NOT connected to production KARMO.** See "KARMO Worker
  Runtime v0.1" and "Worker Runtime v0.1 final merged-main closeout"
  sections below and `docs/evidence/worker-runtime/WORKER_RUNTIME_REPORT.md`.

## H0.1 — Transactional Outbox

**VERIFIED**, from `docs/evidence/h01/H01_FAILURE_MATRIX_REPORT.md`
(committed) plus this session's operator attestation:

- Isolated build and H01-T02–T17 failure-matrix acceptance: PASS (repo-evidenced).
- H01-T01 and H01-T18 (live production/host reverification components):
  recorded BLOCKED/NOT EXECUTED; Natalie accepted this residual risk on
  2026-09-06 and cleared H0.1 to proceed — **not** itself an authorization for
  cutover.
- **Production cutover completed** (operator-attested, this session):
  - `karmo_outbox` migration applied to production PostgreSQL.
  - `karmo-h01-relay` systemd **user** service created and enabled for user
    `lofason`.
  - Persistent startup enabled via `loginctl enable-linger lofason` (survives
    logout; reboot persistence depends on systemd user-instance-on-boot,
    flagged **NEEDS VERIFICATION** — not independently re-checked this
    session).
  - Production functional test produced one delivered outbox event.
- No repository evidence file documents the production cutover itself (by
  design — production actions are not recorded in this repo per `AGENTS.md`);
  the above is recorded as VERIFIED on Natalie's direct, specific attestation,
  not on independently re-read production state.
- H01-T01/H01-T18's production-read-only components (referenced above as
  BLOCKED at 2026-09-06) were subsequently performed and PASSED on
  2026-09-09 under Foundation v1 closeout Workload 2 —
  `docs/evidence/foundation-v1/PRODUCTION_READONLY_VERIFICATION.md`.
- 2026-09-12 (branch `staging/karmo-full-predeploy-20260912`, not yet
  merged): three test-code robustness/coverage gaps found by review in the
  isolated `test/h01/tests/test_h01_failure_matrix.py` suite (clock-skew-
  sensitive latency check, weak duplicate-delivery coverage,
  environment-dependent socket-based fault injection) were fixed; no
  frozen `test/h01/app/` file changed; full matrix re-run 19 passed/2
  skipped/0 failed. Detail:
  `docs/project-state/PROJECT_SAVE_2026-09-12_H01_TEST_HARDENING.md`.

## H0.2 — Knowledge Lifecycle & Vector Versioning

**VERIFIED**:

- Isolated acceptance: PASS, 3/3 (`docs/evidence/h02/H02_LIFECYCLE_REPORT.md`).
- `fix/h02-legacy-active-compat` (PR #4, commit `e3cdca8`) merged: legacy
  vectors without an `is_active` field remain retrievable — existing legacy
  vectors were **not** rewritten to conform to H0.2.
- Production `document_ingest.py` and `document_memory.py` were backed up
  before install (operator-attested).
- H0.2 production implementation installed (operator-attested).
- `karmo_documents` remained green at 8 points during validation
  (operator-attested; matches the pre-H0.1 baseline count of 8 recorded in
  the H0.1 handoff doc).

## H0.3 — Hybrid Retrieval (Dense + BM25 + RRF)

**VERIFIED as evaluated / NO-PROMOTION**:

- Benchmark (`docs/evidence/h03/h03_hybrid_vs_dense_benchmark.md`, synthetic
  corpus, non-authoritative per its own header): Hybrid RRF improved
  Recall@3 (0.800→1.000), MRR (0.517→0.908), and top-1 correct-source rate
  (0.300→0.850) over dense-only, on a synthetic 10-document corpus.
- **Explicitly approved as NO-PROMOTION. Not deployed to production.** H0.3
  is retained as evaluated/retained evidence only and is **not** part of the
  active production retrieval architecture.

**Conflict/gap found during the 2026-09-08 reconciliation, resolved the same
day:** the H0.3 implementation (`h03/app/hybrid_ingest.py`,
`hybrid_memory.py`, `sparse_bm25.py`) and its benchmark evidence
(`docs/evidence/h03/*`, including `H03_EVALUATION_STATUS.md`) previously
existed only as untracked working-tree files. This was Workload 1 in
`docs/plans/KARMO_FOUNDATION_COMPLETION_PLAN.md`, approved and merged
2026-09-08 (PR #7, `db4ff2f`) — the files are now committed to `main`,
byte-for-byte identical to their pre-commit working-tree content (verified
empty diff at commit time, per Workload 1's own acceptance criteria). This
does not change, and must not be read as changing, the NO-PROMOTION
decision — H0.3 remains explicitly not promoted to production; only its
evidence durability gap is closed.

## H0.4 — Integrity, Reconciliation & Production Integration

**VERIFIED**, plus a 2026-09-15 update: `registry_repair.py` (merged
since 2026-09-09 but never actually run against production) was deployed
and run in dry-run mode, and a fresh full `auditor.py` pass was taken —
both confirmed **no new or real data-integrity problem exists**; every
finding (18 `LEGACY_PROVENANCE_UNVERIFIED`, 2 `ORPHAN_VECTOR`, 3
`ACTIVE_STATE_MISMATCH`) traces to the same 5 known pre-H0.2 legacy
documents behaving exactly as already understood. Full detail:
`docs/evidence/h04/H04_2026-09-15_FULL_AUDIT_AND_REPAIR_DRY_RUN.md`.

- Isolated acceptance: 10/10 PASS
  (`docs/evidence/h04/H04_INTEGRITY_RECONCILIATION_REPORT.md`), plus a
  targeted pagination-fix test after approval (post-approval fix, not a
  reopening of the frozen suite).
- PR #5 (`feat/h04-integrity-reconciliation`) and PR #6
  (`feat/h04-production-integration`) merged to `main`
  (`58daa3d` confirms PR #5; `5b97ddc` confirms PR #6).
- `docs/governance/KARMO_ENGINEERING_INVARIANTS.md` (I-01–I-09) established
  and committed (`db260de`); Mandatory Phase Invariant Impact Review is now
  required before substantial implementation on every future phase.
- H0.4 Invariant Impact Review performed retrospectively on PR #6
  (`docs/evidence/h04/H04_INVARIANT_IMPACT_REVIEW.md`); one defect found and
  fixed (I-01/I-05 pagination ceiling in `document_ingest_h04.py`); one
  follow-up documented, not a blocker (I-04: no automatic registry-gap repair
  tool yet — see NEXT_STEPS.md).
- **Production cutover backup created** (operator-attested):
  `/home/lofason/karmo-ai/hardening/h0.4/cutover-20260907T063744Z/` containing
  `core-app-pre-h04.tar.gz` and `karmo-postgres-pre-h04.dump`.
- **Qdrant `karmo_documents` snapshot created** before H0.4 changes
  (operator-attested).
- **`public.document_registry` migration successfully applied** to production
  (operator-attested).
- H0.4 production modules transferred, SHA-256 verified, installed, and
  `py_compile`-validated (operator-attested); `document_registry` existence
  verified in production (operator-attested).

**Conflict found during the 2026-09-08 reconciliation, corrected and
committed the same day:** the migration file
`h04/app/migrations/001_h04_document_registry.sql` carried a stale header
comment ("Isolated build artifact only. Not applied to any production
database.") contradicted by the verified H0.4 cutover. The comment was
corrected to state that the migration was applied to production as part of
the H0.4 cutover, pointing back to this record. This was part of Workload 1
in `docs/plans/KARMO_FOUNDATION_COMPLETION_PLAN.md`, merged 2026-09-08
(PR #7, `db4ff2f`). No other content in that migration file was changed.

## Legacy registry bootstrap — current stopping point

**VERIFIED** (operator-attested production run of
`h04/app/bootstrap_legacy_registry.py`):

- Dry run: `READY_TO_REGISTER: 3`, `REFUSED: 2`.
- The 2 refused records both belong to source file `karmo-v05-new.html`,
  reason `AMBIGUOUS_MULTIPLE_HASHES_FOR_SOURCE_FILE` (per the script's own
  documented refusal rule: more than one distinct `document_hash` maps to the
  same `source_file` among legacy points, so version ordering cannot be
  assigned without guessing).
  - Hash `23646203eed7e187ce2fe0de12c82d5cf83d0a97893a6bdcd2ed30ae3855af9c`
  - Hash `5f98126d41381a8a0a4c5034b3402b9a4b763fa043bcfa63f27bdefeb7414c78`
  - **These were intentionally not guessed or registered and remain
    unresolved.** Do not mark them resolved without an explicit human
    decision on version ordering.
- Apply run (3 verified-unambiguous legacy documents only):
  `REGISTERED_COUNT: 3`, `REGISTER_FAILED_COUNT: 0`.
  - `0754fbca9b7dd45b7db7d983fe529227ca70fe83d9c67df68cc39513496251ca`
  - `5d1b22a02341bff11ac8bd9f68d6b8ce340418fc7177da752f6307bfc980a7fc`
  - `bac7c97bbfa8e2311bcd67bd81abab5598c551e4ff6fe62bca8b62261d33395e`

## Spec Kit decision

**VERIFIED** (recorded this session, no repository code changed):

- GitHub Spec Kit (v1.0.4) is **approved for evaluation/integration**,
  operating strictly **under** KARMO governance, never above or in
  competition with it.
- `docs/governance/KARMO_ENGINEERING_INVARIANTS.md`, `AGENTS.md`, and
  `CLAUDE.md` remain authoritative; Spec Kit's constitution must reference,
  not duplicate or weaken, the invariants document.
- H0.0–H0.4 will **not** be retroactively reorganized for Spec Kit; adoption
  is prospective, starting with the next development phase (H0.5).
- Brownfield/existing-project integration path is required; no
  force/overwrite initialization is authorized without review.
- **Inspection completed** (CLI version, files added, brownfield workflow,
  constitution mechanism, collision check — no repo files changed).
- **Brownfield initialization plan formalized** as
  `docs/plans/SPEC_KIT_BROWNFIELD_PLAN.md`, including the exact
  `specify init` command, the constitution content plan, and the KARMO
  governance-hierarchy diagram Spec Kit must operate beneath.
- **Initialization completed 2026-09-08** (Foundation Closeout Program,
  Workload 4), on Natalie's explicit pre-authorization to run the exact
  command already prepared in `docs/plans/SPEC_KIT_BROWNFIELD_PLAN.md`:
  `uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@v1.0.4`
  then `specify init --here --force --integration claude`, on branch
  `feat/h05-spec-kit-adoption`. Diff inspected immediately after: only
  `.claude/skills/speckit-*/` and `.specify/` appeared, exactly as the
  brownfield plan's own acceptance criterion required — no other file was
  touched. `.specify/memory/constitution.md` was filled in (replacing the
  placeholder template) with content subordinating it to
  `docs/governance/KARMO_ENGINEERING_INVARIANTS.md`, per the brownfield
  plan's constitution content plan, plus principles drawn from the
  repository's own existing conventions (isolated-before-production,
  report-only-by-default for audit/repair tools, no overlapping test
  suites). Merged to `main` 2026-09-09 (PR #9, `cd72938`).

## Foundation Closeout Program (2026-09-08)

**VERIFIED** — Natalie approved a consolidation review's recommendation to
run Workloads 2, 3, and 4 of `docs/plans/KARMO_FOUNDATION_COMPLETION_PLAN.md`
as one autonomous program, with pre-authorization for the two standing-gate
actions each carried (read-only production access for Workload 2;
`specify init` for Workload 4).

- **Workload 2 (production verification closeout): PASS, executed
  2026-09-09.** Natalie's temporary, session-scoped, task-specific
  Production Access Authorization (2026-09-09) lifted the default
  prohibition for exactly this task, per the newly-adopted Mandatory
  Production Access Authorization Gate (see below). Both defined checks
  executed and passed: H01-T01 (manifest presence/hash) and H01-T18
  (baseline counts). Full detail, exact commands, and observed values:
  `docs/evidence/foundation-v1/PRODUCTION_READONLY_VERIFICATION.md`. No
  write, restart, deployment, or configuration change was performed.
- **Workload 3 (registry integrity repair tool): complete, merged.**
  `h04/app/registry_repair.py` + `h04/tests/test_h04_registry_repair.py`
  (4/4 PASS) + targeted regression re-run (11/11 PASS, existing suite
  unchanged) + Invariant Impact Review, all per
  `docs/evidence/h04/H04_REGISTRY_REPAIR_REPORT.md`. PR #8 merged
  2026-09-09, `06ab726`. Still isolated-only — no production execution
  performed or authorized (that remains separate, future work).
- **Workload 4 (Spec Kit brownfield adoption): complete, merged.** See
  "Spec Kit decision" above. PR #9 merged 2026-09-09, `cd72938`.
- **Workload 5 (H0.5 scope definition): not started**, per explicit
  instruction not to invent H0.5's scope. Not required for Foundation
  Complete (see below).

### KARMO FOUNDATION v1 status: **COMPLETE, declared 2026-09-09**

Per the consolidation review's own criterion (Foundation Complete =
Workload 1 merged + an explicit Natalie decision on Workloads 2/3), applied
without modification: Workload 1 merged (PR #7); Workload 2 executed under
explicit authorization and passed; Workload 3 merged. PRs #8, #9, #10, and
the governance gate (PR #12, superseding closed PR #11) are all merged to
`main`. Full closeout report and independent-verification evidence package:
`docs/evidence/foundation-v1/`. H0.5/Workload 5 was correctly not required
and not started — it is the first post-foundation capability phase, not a
foundation increment.

One genuinely new, non-blocking finding surfaced during closeout: a
read-only H0.4 production audit (beyond Workload 2's own defined scope,
run as a directly-relevant supporting check) found `ORPHAN_VECTOR` (2,
matching the already-known ambiguous legacy hashes exactly — not new) and
`ACTIVE_STATE_MISMATCH` (3, traced to a `reconciliation.check_active_version_state`
design gap for legacy-bootstrapped documents — an auditor blind spot, not
a data problem; recommended, not required, future follow-up). Full detail:
`docs/evidence/foundation-v1/PRODUCTION_READONLY_VERIFICATION.md`.

## Production Access Authorization Gate adopted (2026-09-08, governance correction)

**VERIFIED** — Natalie explicitly approved resolving the conflict this
session's Workload 2 attempt surfaced: `CLAUDE.md` item 4 and `AGENTS.md`'s
"Authority and boundaries" section both stated an unconditional,
no-exception prohibition on any production access, leaving no path for
Natalie's own explicit, task-specific authorizations (the same kind that
already governed the H0.1/H0.2/H0.4 production cutovers) to actually apply.

- Added the **Mandatory Production Access Authorization Gate** to
  `docs/governance/KARMO_ENGINEERING_INVARIANTS.md` (new section, between
  the existing Mandatory Phase Invariant Impact Review and Mandatory
  Project Save Completion Rule sections — same non-duplicating pattern as
  both) — the single canonical rule: production access prohibited by
  default; lifted only by an explicit, task-specific authorization defining
  target system, purpose, permitted operations, read-only vs. write
  authority, and applicable commands; read-only never implies write;
  writes/deployment/destructive actions/migrations/restarts/config
  changes/data repair/deletion each need their own separate grant;
  single-task scope, auto-expires on completion; defined STOP conditions
  (unexpected state, scope ambiguity, contradictory evidence, insufficient
  granted authority); secrets never exposed/printed/persisted; does not
  override any other invariant, review, validation, or approval gate; the
  narrower rule always wins; a general workload approval never substitutes.
  Includes a copy-pasteable authorization-record shape.
- `CLAUDE.md` item 4 and `AGENTS.md`'s equivalent bullet both rewritten to
  reference this gate rather than stating an unconditional, no-exception
  prohibition (`AGENTS.md` was not named in Natalie's request but carried
  the identical unresolved conflict in an even more absolute form — leaving
  it as-is would have left the conflict only partially resolved).
  `docs/governance/KARMO_AUTONOMOUS_EXECUTION_CONTRACT.md`'s existing
  "access production when not explicitly authorized" bullet cross-referenced
  to the same gate, not restated.
- Invariant Impact Review performed before this change:
  `docs/evidence/governance/PRODUCTION_ACCESS_AUTHORIZATION_GATE_INVARIANT_IMPACT_REVIEW.md`.
- No production was accessed and no Production Access Authorization was
  issued or acted on by the governance-drafting task itself — a purely
  canonical-governance documentation change. Merged 2026-09-09 as PR #12
  (`e3443e8`) — the original PR #11 was auto-closed when its base branch
  (PR #10's, deleted on merge) disappeared; PR #12 carries identical
  content, rebased onto `main`. First actually exercised the same night,
  for Workload 2 — see "Foundation Closeout Program" above and
  `docs/evidence/foundation-v1/`.
- This does **not** retroactively require re-justifying the already-accepted
  H0.1/H0.2/H0.4 production cutover history (I-01: those predate this gate
  and remain VERIFIED as recorded); it governs future production access
  only.

## Post-Foundation Overnight Readiness Program (2026-09-09)

**VERIFIED** — Natalie authorized one large, repository-only autonomous
program the same night Foundation v1 was declared complete, explicitly
prohibiting any production access. Five workstreams:

- **Workstream 1 (Foundation verification review): complete.** Independent
  claim-by-claim audit of `docs/evidence/foundation-v1/` — no claim found
  false; two evidence-quality gaps named plainly (raw production command
  output was never saved as a file, consistent with existing
  operator-attestation precedent). Three circular checks in
  `VERIFICATION_CHECKLIST.md` (items 4, 5, 10 — verified the closeout
  session's own documents against themselves, not independent ground
  truth) corrected in place; `MANIFEST.sha256` regenerated and reverified.
  Full review: `docs/evidence/post-foundation-readiness/WORKSTREAM1_FOUNDATION_VERIFICATION_REVIEW.md`.
  PR #14, merged into `main`.
- **Workstream 2 (H0.4 auditor gap): fixed, merged.** Root cause
  determined from evidence (`docs/handoff/h04/document_memory.py`'s own
  documented definition of "active" disagreed with
  `reconciliation.check_active_version_state`'s narrower one).
  One-comparison fix (`is True` → `is not False`), proven in both
  directions by two new targeted tests (removes a false-positive, adds
  detection of a previously-missed real gap); 15/15 existing tests
  unchanged; `auditor.py` untouched. Full evidence:
  `docs/evidence/h04/H04_ACTIVE_STATE_LEGACY_FIX_REPORT.md`. PR #15,
  merged into `main`.
- **Workstream 3 (Tool/Capability Registry): designed, not implemented.**
  Built directly on I-09's existing classification; `financial_action`/
  `destructive_action` structurally force `EXPLICIT_PER_CALL` approval,
  computed, never independently declarable. Architecture:
  `docs/architecture/KARMO_TOOL_CAPABILITY_REGISTRY.md`. Spec-Kit-shaped
  proposal (not an approved H0.5 scope): `specs/001-tool-capability-registry/spec.md`.
  Phased implementation proposal:
  `docs/plans/KARMO_TOOL_CAPABILITY_REGISTRY_IMPLEMENTATION_PROPOSAL.md`.
- **Workstream 4 (adversarial architecture review): complete.**
  Repository-wide review grounded in code actually read this session.
  Findings: a live-production pagination ceiling in
  `document_memory.get_document_history` (MEDIUM, same bug class already
  fixed elsewhere in H0.4, never applied here); its dead-code echo in the
  superseded `h02/app/document_ingest.py` (LOW/INFORMATIONAL); no
  connection pooling anywhere in the codebase (MEDIUM); no
  embedding-model provenance on `karmo_semantic_memory` (MEDIUM);
  configuration drift — Qdrant/Postgres endpoints duplicated across ~10
  files (LOW–MEDIUM); two further LOW/INFORMATIONAL findings; several
  categories checked with no credible issue found, named explicitly (race
  conditions, TOCTOU, swallowed exceptions, secret persistence, backup/
  restore assumptions, irreversible operations, implicit authority
  escalation). One candidate invariant proposed (configuration
  single-sourcing) — **not adopted**, governance unchanged. Full review:
  `docs/evidence/post-foundation-readiness/WORKSTREAM4_ADVERSARIAL_ARCHITECTURE_REVIEW.md`.
- **Workstream 5 (post-foundation capability roadmap): complete.**
  Dependency graph, shared Core requirements (tying to Workstream 4's
  findings), per-domain complexity/risk/prerequisites for Voice, Media,
  BloomBoss, KarmoLab, Personal Productivity, and Finance/Trading, and
  three sequencing alternatives.  **Does not choose Natalie's first
  capability.** `docs/plans/POST_FOUNDATION_CAPABILITY_ROADMAP.md`.

Workstreams 3–5 committed together: PR #16, merged into `main`.

**Production access this program: zero.** No SSH to `karmo-ai01`, no
database/Qdrant/container/file/credential/service/log/network access of
any kind — verified by this session's own command history (every action
was a local repository read, edit, test, or `git`/`gh` operation).
**Merges this program: zero at the time it ran** — PRs #14–#16 were
merged later, as part of the approved KARMO merge sequence (see "Worker
Runtime v0.1 merge closeout" below). No governance modified. No financial
transaction. No external post. No Voice/Media/BloomBoss/KarmoLab/Finance
capability implementation begun.

## Core v2 Engineering Blueprint Program (2026-09-09)

**VERIFIED** — Natalie authorized one large, repository-only autonomous
planning/prototyping/validation program the same day Foundation v1 was
declared complete and the Post-Foundation Overnight Readiness Program ran
(that program's PRs #14–#17 were not touched or merged by this program,
per explicit instruction — they were merged later, separately). No
production access authorized or performed. 15 workstreams, grouped into 4
PRs per explicit PR-discipline instruction (max 4):

- **PR #18** — architecture map (Workstream 1: PostgreSQL/Qdrant/Ollama/
  semantic memory/document memory/outbox/integrity-auditing/recovery/
  configuration/governance/Spec Kit/service boundaries, VERIFIED/INFERRED/
  PROPOSED labeled, Mermaid diagrams), observability design (Workstream
  6), Core v2 security/threat model (Workstream 8: 16 threats, 12 mapped
  to existing invariants, 1 genuine gap with a proposed-not-adopted
  addition), Core v2 test strategy (Workstream 13), and the autonomous-run
  verification system design (Workstream 14 design portion: evidence
  schema, independent checklist, a Trust Score explicitly proven never to
  grant permissions).
- **PR #19** — isolated, non-production prototypes (Workstreams 2–5, 7,
  14 prototype portion): Tool/Capability Registry (manifest validation,
  computed-never-declarable approval requirements, all 7 required worked
  examples), Approval Engine (state machine, arguments-digest binding,
  all 8 required scenarios), a minimal Job/Event model (deterministic
  identity, idempotency, claim-token crash recovery reusing the H0.1
  outbox relay's pattern), a configuration single-sourcing proof of
  concept, a failure-injection framework covering all 12 named
  categories applied against the other prototypes, and the run-evidence
  schema/validator prototype. **160/160 tests pass** — see
  `docs/evidence/core-v2/core-v2-prototypes-run.txt` and
  `-junit.xml`. Nothing here is wired into any KARMO production path.
- **PR #20** — BloomBoss readiness spec (Workstream 9: 14-entity model,
  multi-channel sales, READ/BUSINESS MUTATION/EXTERNAL COMMUNICATION
  separation), Voice/Media readiness spec (Workstream 10: identifies
  wake/listen and streaming as genuinely new Core abstractions not yet
  designed), Finance/Trading safety spec (Workstream 11: 8 capability
  tiers, the propose→approve→bind→execute flow specified against the
  Approval Engine's own proven test behavior), the implementation
  dependency graph (Workstream 12: 6 candidate batches for a future
  autonomous run), and the consolidated Core v2 specification (Workstream
  15: EXISTING/PROPOSED/FUTURE separated explicitly, plus
  `specs/002-core-v2-platform/spec.md`).
- **PR #21** — this PROJECT SAVE.

**No capability was chosen. No Core v2 component was implemented in
production. No governance was modified** (one candidate invariant —
configuration single-sourcing, carried over from the prior program — and
one new candidate — tool-registration review — both proposed, neither
adopted). **Production access: zero. Merges: zero at the time this
program ran** — PRs #18–#21 were merged later, as part of the approved
KARMO merge sequence (see "Worker Runtime v0.1 merge closeout" below).

## KARMO Worker Runtime v0.1 (2026-09-09, isolated prototype)

- **VERIFIED (repo, this workload)** — full worker runtime built on
  `worker-runtime/implementation` (based on `core-v2/prototypes`): worker
  registry, resource discovery, capability manifest, job protocol
  (genuinely wiring the reused Tool Registry + Approval Engine
  prototypes together), execution sandbox, 9 SAFE capability handlers,
  pull-based transport (`LocalTransport`, in-process), coordinator, and
  worker client.
- KARMO-DEV01 (this Mac, Apple M3/arm64) registers, heartbeats, is leased
  a job, executes it sandboxed, and returns a verified result — proven
  end-to-end in `test_end_to_end_pull_based_hash_verify`.
- 68/68 tests passing (`worker-runtime/tests/test_worker_runtime.py`,
  was 44/44 → 62/62 → 67/67 → 68/68), covering all 24 required
  failure/adversarial scenarios plus supporting capability/integration
  tests plus all three rounds' fix-verification tests (see below).
- 4 real defects found and fixed while building this workload's own test
  suite (not pre-existing production bugs): a missing
  `WAITING_FOR_APPROVAL → FAILED` transition in the reused
  `core-v2-prototypes/job_model/jobs.py` state machine (fixed at the
  source, +1 test, core-v2-prototypes now 161/161); `job_protocol.py`
  leaking a raw `JobStateError` instead of `JobProtocolError`;
  `coordinator.finalize_success` crashing if a worker wasn't exactly
  `BUSY`/`DEGRADED`; and no runtime module actually importing
  `capabilities.py`, meaning no handler would ever be registered in
  practice. Full detail: `docs/evidence/worker-runtime/RUN_SUMMARY.json`.
- **VERIFIED — independent (ChatGPT) verification, 2026-09-09, before any
  merge**: found 4 additional real blocking findings this workload's own
  review had missed — (1) approval gated job *completion*, not
  *execution* (a worker's sandboxed handler ran unconditionally at lease
  time); (2) timeout enforcement was a post-return elapsed-time check,
  not a real deadline (a hung handler was never actually interrupted);
  (3) only `stdout_summary` was bounded, not the full structured `output`
  result or `evidence_files`; (4) a worker heartbeat could set
  coordinator-owned scheduling state (`BUSY`/`AVAILABLE`) directly,
  bypassing lease tracking. **All 4 fixed** on the same open PRs
  (implementation commit `5906f61`): `job_protocol.WorkerJobQueue.execute()`
  now gates execution through the reused `ApprovalEngine.execute()`
  (never duplicated); `sandbox.run_capability()` now runs each handler in
  a forked child process under a real, killed-on-overrun deadline (a real
  multiprocessing deadlock was found and fixed while building this —
  waiting via `process.join()` before draining the result pipe hangs on
  any oversized result; fixed by waiting on the connection instead);
  `MAX_RESULT_BYTES`/`MAX_EVIDENCE_FILES` now bound the full result;
  `WorkerRegistry.heartbeat()` now accepts only a self-reported
  `WorkerHealth`, never a raw `WorkerStatus`. Full detail:
  `docs/evidence/worker-runtime/RUN_SUMMARY.json`'s
  `independent_verification_round_1_findings_and_fixes`.
- **VERIFIED — second round of independent (ChatGPT) verification,
  2026-09-10, before any merge**: found round 1's approval-gate fix was
  itself correct (nothing unauthorized ever executed, before or after)
  but the normal `WorkerClient` flow treated its correct refusal as a
  hard failure — an approval-required job reached `execute()`, was
  refused because approval wasn't present yet, and
  `poll_and_execute_once()` then called `submit_failure()`, permanently
  marking a merely-pending job `FAILED` before a human ever had a chance
  to approve it. **Fixed** at implementation commit `08c501e`:
  `job_protocol.WorkerJobQueue.resume()` (alongside `execute()`) lets an
  approval-required job park in `WAITING_FOR_APPROVAL` without executing
  or failing, then resume execution — exactly once — once approved
  (delegating to `execute()`, never duplicated), or end safely (`FAILED`,
  worker released) on denial/expiry. Also fixed while building this: a
  denied/expired job's worker was left stuck `BUSY` forever —
  `coordinator.deny_job()`/`resume_job()` now release it. Wired through
  new `coordinator`/`transport` `request_approval()`/`resume()` verbs
  into `worker_client.py`'s `poll_and_execute_once()` (now parks instead
  of failing) and new `try_resume()`. Explicitly not done: no redesign of
  the future network transport — `resume()` inherits `execute()`'s exact
  same callable-based, in-process-only limitation. Full detail:
  `docs/evidence/worker-runtime/RUN_SUMMARY.json`'s
  `independent_verification_round_2_findings_and_fixes`.
- **VERIFIED — third round of independent (ChatGPT) verification,
  2026-09-10, before any merge**: found one narrow gap remaining in
  round 2's fix — `resume()`'s "ends safely on a terminal approval
  outcome" guard only transitioned the job to `FAILED` if it was still
  `WAITING_FOR_APPROVAL`; if `approve()` had already run (moving the job
  to `RUNNING`) and the approval *then* expired before `try_resume()`
  ever consumed it, the job was left stuck `RUNNING` and its worker
  stuck `BUSY` forever, since nothing ever noticed. **Fixed** at
  implementation commit `a2a1619`: the guard now covers both
  `WAITING_FOR_APPROVAL` and `RUNNING` (`RUNNING → FAILED` was already a
  legal transition in the reused `job_model` state machine — no change
  to `jobs.py` needed, `ApprovalEngine` logic still not duplicated
  anywhere). One targeted test proves all 7 required points (park,
  approve, expire, no action invoked, job `FAILED`, worker `AVAILABLE`,
  a second resume also cleanly refused) — verified to actually catch the
  bug by temporarily reverting the fix and confirming the test failed
  first. Full detail: `docs/evidence/worker-runtime/RUN_SUMMARY.json`'s
  `independent_verification_round_3_findings_and_fixes`.
- M3 benchmark run (bounded, local, no production comparison), re-run
  after the fork-based timeout fix (numbers essentially unchanged, a few
  ms of fork overhead): `docs/evidence/worker-runtime/BENCHMARK_RESULTS.json`.
  Metal 3 confirmed present; MLX and Ollama confirmed NOT installed
  (neither was installed by this workload, per instruction).
- Security review with 23 threats (was 20 — 3 new rows across both
  verification rounds) and 5 previously-named open gaps, unaffected by
  either round's fixes (no cryptographic worker credential, no subprocess
  env allowlisting, no symlink-escape test, no result-authenticity
  binding, no coordinator persistence) — none exploitable within this
  workload's actual threat surface today (no network transport exists;
  capability set is READ-only/workspace-scoped).
  `docs/evidence/worker-runtime/SECURITY_REVIEW.md`.
- Future network plan (Tailscale transport, worker credentials, TLS,
  coordinator auth) is design-only —
  `docs/architecture/KARMO_WORKER_RUNTIME_NETWORK_PLAN.md`. **No network,
  firewall, or Tailscale configuration was changed.**
- **Production access: 0. Network changes: 0. Merges: 0.** Not connected
  to production KARMO. See "Next action" in NEXT_STEPS.md for what a
  future, separately-authorized controlled integration test would require.

## Worker Runtime v0.1 merge closeout — PRs #22, #23, #24 merged; PR #25 pending (2026-09-10, HISTORICAL — superseded by "final merged-main closeout" below; PR #25 has since merged)

**VERIFIED (repo)** — the approved KARMO merge sequence proceeded: PR #22
(`review/pr14-21-merge-readiness`) merged into `main`; PR #23 (Worker
Runtime implementation + tests) merged into `main` at merge commit
`11d4f86e04d22aae0072923ec387a11f0e205cbc`; PR #24 (architecture/
security/network docs) merged into `main` at merge commit
`9f3215ecd3be31d2096273be4afb389edbcbf9f8`. Both commits confirmed as
ancestors of `origin/main` via `git merge-base --is-ancestor` before this
entry was written. PRs #14–#21 (Post-Foundation, Core v2, and the
independent review) were also merged as part of the same approved
sequence — the "open, not merged" language in the sections above
describes each program's status **at the time it ran**, not current
status; see this section for the current merge status.

**PR #25 (evidence + PROJECT SAVE) remains OPEN and NOT merged.** It was
retargeted to `main` and, before this commit, was not mergeable due to
the expected conflicts in these same three `docs/project-state/` files —
resolved here on the `worker-runtime/evidence` branch. This resolution
does not merge PR #25 itself.

Authoritative Worker Runtime verification remains **68/68** tests
(`worker-runtime/tests/test_worker_runtime.py`) and **161/161**
core-v2-prototypes regression — unchanged by this merge-conflict
resolution; no executable code was touched, so the suite was not rerun.
**Production access: 0. Network/Tailscale/firewall changes: 0.
Deployment: 0.**

## Worker Runtime v0.1 final merged-main closeout (2026-09-10)

**VERIFIED (repo) — current, authoritative status.** PR #25 (evidence +
PROJECT SAVE, `worker-runtime/evidence`) has merged into `main` at merge
commit `b95acb603e632855298cc0d454df00b2c3d22286`. **PRs #22, #23, #24,
and #25 are now all merged.** Confirmed via `git checkout main && git
pull --ff-only origin main` (fast-forwarded cleanly from `3f61424` to
`b95acb6`) and `git merge-base --is-ancestor` for all four merge commits
(`4877aa9`, `11d4f86e`, `9f3215ec`, `b95acb6`) against the resulting
`main` HEAD.

One final integrated verification was run directly against this merged
`main` HEAD (not a stale branch):
- `worker-runtime/venv/bin/python -m pytest worker-runtime/tests/ -q` —
  initially **66 passed, 2 failed**. Diagnosis: not a Worker Runtime code
  defect. `resource_discovery.discover_acceleration()` was working
  correctly; two tests hardcoded the historical assumption that Ollama
  was absent from KARMO-DEV01. That assumption is no longer true — Ollama
  was separately and intentionally installed on this machine for the
  unrelated KARMO AI / Agent Engineering Learning Program (localhost-only,
  documented in `docs/learning/SETUP_VERIFICATION.md`). Runtime discovery
  behavior itself was correct and was **not** changed.
- **Fix applied**: the two tests
  (`test_capability_local_model_probe_reports_truthful_model_status`,
  renamed from `..._reports_no_models_installed`, and
  `test_resource_discovery_full_report_runs_without_error`) were
  corrected to validate environment-independent, truthful detection
  (`X_installed` is a bool; `X_status` is `VERIFIED` iff `X_installed`,
  else `NOT_INSTALLED`) instead of hardcoding absence. No mocking of real
  host detection; no change to `resource_discovery.py` or any other
  Worker Runtime source file.
- After the fix: `worker-runtime/tests/` — **68/68 passed**.
  `core-v2-prototypes/` regression — **161/161 passed**. Both run fresh,
  directly against merged `main`.

`git diff --check`: clean. Conflict-marker scan: clean. Secret scan of
changed files: clean. No unexpected tracked generated files. **Production
access: 0. Deployment: 0. Network/Tailscale/firewall changes: 0.**

**MERGED ≠ DEPLOYED, restated one more time for this closeout**: Worker
Runtime v0.1's full source, tests, docs, and evidence are merged into
`main`'s repository tree. It remains **NOT deployed, NOT connected to
production KARMO, NOT running anywhere outside this isolated,
now-merged-but-inert prototype.** No real network transport is enabled —
`LocalTransport` (in-process) is the only implementation that exists.

The five previously-named deferred gaps remain accurately documented and
**deferred, not started** (see `docs/evidence/worker-runtime/SECURITY_REVIEW.md`
"Open findings" and `NEXT_STEPS.md`): (1) cryptographic worker credential,
(2) subprocess environment allowlisting, (3) dedicated symlink-escape
test, (4) result-authenticity cryptographic binding, (5) coordinator
persistence. These are follow-ups for a future real network transport,
not blockers for the merged isolated v0.1.

This is the final entry for the Worker Runtime v0.1 merge-closeout
thread. **Worker Runtime v0.1 source merge closeout: COMPLETE.**

## Confirmed data-state baselines (for reference, HISTORICAL unless restated)

- Pre-H0.1 production PostgreSQL: `conversation_memory=14`, `karmo_memory=1`,
  no `public.karmo_outbox` (H0.1 handoff doc).
- Pre-H0.1 production Qdrant: `karmo_semantic_memory=4`, `karmo_documents=8`,
  `karmo_h00_dense_baseline=8` (H0.1 handoff doc).
- `karmo_documents=8` reconfirmed green during H0.2 validation (operator-attested,
  VERIFIED, matches the baseline above).

# KARMO Orchestration and Model Routing — Target Architecture

**Covers:** the KARMO-FIRST governing rule, the orchestration layer / Model Router target architecture, the authority model, planned orchestration components, and performance/reliability principles for multi-model work
**Read this if:** you're designing anything that routes work to a model, a worker, or an external AI resource — including chat tool-calling, delegation, or worker-hosted inference
**Status:** enduring target architecture, originally captured 2026-09-11, still not implemented as a general layer — individual pieces (KARMO chat tool-calling, `ask_claude`/`ask_gpt`, worker `model_chat`) exist as narrower, separately-built slices; no unifying Model Router exists yet

Extracted from `docs/project-state/PROJECT_SAVE_2026-09-11_KARMO_FIRST_ORCHESTRATION_PALMSTREET_KVE.md`, which mixed this enduring architecture with point-in-time hardware facts and BloomBoss-specific findings — see the Mandatory Document Labeling Rule and the "narrative versus enduring content" addition to the Mandatory Project Save Completion Rule in `docs/governance/KARMO_ENGINEERING_INVARIANTS.md` for why this was split out. That original file remains as historical record with a pointer to this document.

## The KARMO FIRST governing rule

Before recommending an app, SaaS product, manual export, cloud folder, phone shortcut, or third-party workflow, first determine whether KARMO can own the capability using infrastructure already available.

External systems should be treated as **sources, destinations, or adapters** — never as KARMO's brain, workflow engine, authority layer, or source of truth.

Practical consequences:
- Prefer extending KARMO over adding consumer workflows.
- Prefer existing infrastructure over buying hardware or adding agents/services.
- Third-party services must earn their place through a system-fit review.
- Do not let ChatGPT, Claude, Shopify, Palmstreet, Google Drive, ShipStation, or another external system become the canonical business/control layer.

## Communication and control-plane direction

Target interaction model:

`Kamara -> KARMO -> Orchestration Layer -> Model Router -> Common KARMO Capability Interface -> Core Approval -> Worker Execution -> Independent Verification -> Durable Memory/Audit`

KARMO is the trusted coordinator. ChatGPT, Claude, local models, and future providers are replaceable intelligence resources.

### Authority model

KARMO should own:
- task identity and durable state;
- policy and risk classification;
- approvals;
- capability/tool permissions;
- credential references;
- canonical memory/business truth;
- execution records;
- verification evidence;
- audit history.

Models may reason, propose, review, and use scoped KARMO capabilities. Models must not gain standing production authority merely because they can reach a tool.

Security principle remains:

`model suggestion != trusted command != approved execution`

## Planned orchestration components

1. **KARMO Orchestration Layer** — durable task ID, objective, risk, authorized capabilities, checkpoints, evidence, state, and result.
2. **Model Router** — route routine work to local models; coding/reasoning to the best-fit external model when justified; allow multi-model review for higher-risk work.
3. **Common KARMO Capability Interface** — one KARMO-owned tool contract rather than separate SSH/tool universes per model.
4. **Core Approval** — classify reads, safe writes, privileged writes, external actions, and production changes; models cannot self-promote authority.
5. **Worker Execution** — workers touch machines/files/APIs only after authorization.
6. **Independent Verification** — deterministic tests and evidence outrank model votes; a second model may review important changes.
7. **Durable Memory/Audit** — persist request, interpretation, models consulted, tools used, commands, file changes, tests, approvals, rollback path, and final verification.

**Progress against this list as of 2026-09-18**: components 4 (Core Approval), 5 (Worker Execution), and 7 (Durable Memory/Audit) exist and are production-proven, but were built independently for other purposes (the Tool/Capability Registry, Worker Runtime, and durable memory work) rather than as pieces of a deliberate Model Router build-out. Component 2 (Model Router) has two narrow, non-unified instances — KARMO chat's tool-calling loop can call `ask_claude`/`ask_gpt`, and Worker01/02 can serve local models via `model_chat` — but nothing routes between them based on task fit; a human or a hardcoded tool choice decides, not a router. Components 1, 3, and 6 do not exist as named things, though pieces of their intent are scattered across the existing Capability Registry/dispatcher pattern.

## Concrete evidence for the reliability argument (2026-09-18)

The "relieve `karmo-ai01`'s resource contention" case for worker-hosted
routing (see "Progress against this list" above) moved from hypothesis
to observed fact tonight. Two real chat questions against production
`karmo-ai01`, after the tool-calling timeout was already raised from 45s
to 120s and after a separate durable-memory contamination issue was
found and fixed:

- Both attempts: `qwen3:8b` timed out at the full 120s, then
  `ministral-3:8b` also timed out at the full 120s, before falling back
  to `granite3.3:2b` (which does not reliably use tools). One attempt
  took 379.5 seconds end-to-end for a single chat turn.
- This is not the memory-contamination bug (that was independently
  confirmed fixed — the fallback model's wrong answer changed from a
  flat "I have no access" to an aware-but-non-invoking "I recommend
  using the `bloomboss_report` function," showing the poisoned context
  was gone). This is `karmo-ai01` itself failing to complete a
  tool-calling generation with two different capable models, twice in a
  row, within a generous timeout.
- `karmo-ai01` runs Postgres, Qdrant, Ollama, and the worker gateway
  concurrently on the same 8GB host. Worker01/Worker02 run only Ollama,
  dedicated, currently idle for this kind of work.

Raising the timeout further would be treating a symptom. This is now
concrete, reproduced evidence for the contention-relief argument, not
speculation — worth weighing more heavily than the original 13%-
per-token benchmark when this design actually gets built.

## Performance / reliability decisions

- Do not route every task through every model.
- Use a fast path for routine work and a deeper multi-model path only when risk/complexity warrants it.
- Long-running work must not depend on one continuous model conversation.
- KARMO must persist resumable task state, checkpoints, retries, evidence, and next-action state so work can continue after model/session interruption.

## Model-verifier direction

Treat any DeepSeek/OpenAI/Anthropic/local model as a replaceable model adapter behind KARMO. Do not trust a second model merely because it agrees with the first. Verification priority is:

`tests / deterministic evidence -> independent review -> human escalation when required`

A DeepSeek-family coding model was discussed once (2026-09-11) as a possible independent code-review/verifier resource; any specific version/capability claims from that discussion must be revalidated before implementation or procurement.

## Remote-access / security direction

Remote security architecture remains KARMO-owned.

Preferred pattern:

`KARMO -> approved management path -> managed systems`

Do not install a remote-control agent on every managed host merely for convenience. Prefer an existing secure management path (e.g. `karmo-ai01` or another approved bastion) when system-fit supports it.

Credentials/secrets must not be handed to ChatGPT/Claude as task context. Models should receive scoped capabilities through KARMO.

## System-level correction to prior consumer recommendations

A prior suggestion to use Google Drive/Dropbox/Box/SharePoint for historical uploads is superseded by KARMO FIRST.

Target system process:

`source -> KARMO Universal Intake -> immutable/raw evidence -> fingerprint/provenance -> source adapter -> staging -> validation -> canonical state`

Cloud storage may be used later only as a deliberate adapter/source/destination if system-fit justifies it.

## Safe next engineering work (as originally scoped, 2026-09-11 — re-confirm still accurate before resuming)

Non-production work to define and test, when this is picked back up:
- orchestration task/job state model;
- model-provider abstraction/router;
- capability/tool registry contract;
- Core approval/risk contract;
- Worker job contract;
- verification-result contract;
- durable audit/event format;
- three-node capacity/deployment design (see `NETWORK_INVENTORY.md`'s KVE section for current hardware facts, separately maintained from this document);
- authority-separation tests.

## Safety boundary

No production deployment, no PR merge, no marketplace writes, no customer-facing actions, no secret publication, and no infrastructure changes are authorized by this document alone. This is a target architecture record, not an implementation order — building any of it requires its own System-Fit Review and Invariant Impact Review at the time it's actually undertaken, per the standing rules in `docs/governance/KARMO_ENGINEERING_INVARIANTS.md`.

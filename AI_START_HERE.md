# KARMO AI Start Here

Status: **DURABLE AI BOOTSTRAP / CONTEXT MAP**

Purpose: let a new AI assistant, coding agent, automation system, or future chat join KARMO without forcing Kamara to retrain it from scratch.

This file is deliberately a **map, not a giant encyclopedia**. Dynamic project truth belongs in the existing authoritative project-state and workstream documents. This file tells an AI what to read, how to interpret it, how Kamara works, and how to preserve continuity when the current chat or model has no memory.

---

## 1. First rule: repository before chat memory

Conversation history, model memory, summaries, and prior assistant recollections are useful hints but are **not authoritative project state**.

**Context loading is tiered by task** (exact tiers in `CLAUDE.md`):

- **Tier 1 — small, scoped tasks** (edits/fixes/tests in known files, read-only checks): no mandatory reads beyond `CLAUDE.md` / `AGENTS.md`.
- **Tier 2 — feature/phase work:** read `docs/project-state/STATE_NOW.md` (one page), grep `docs/project-state/CURRENT_STATE.md` / `NEXT_STEPS.md` only for the topic at hand, and read the relevant plan/spec located via `docs/project-state/MASTER_INDEX.md`.
- **Tier 3 — architecture, new service/tool/integration/datastore, migration, access/routing, deployment, or anything touching production:** the full bootstrap chain below.

Full bootstrap chain (Tier 3):

1. Read this file.
2. Read `AGENTS.md`.
3. If using Claude Code, read `CLAUDE.md`.
4. Read `docs/project-state/MASTER_INDEX.md` in full.
5. Read `docs/project-state/CURRENT_STATE.md`.
6. Read `docs/project-state/KARMO_DASHBOARD.md`.
7. Read `docs/project-state/NEXT_STEPS.md`.
8. Read `docs/governance/KARMO_ENGINEERING_INVARIANTS.md`, including its **Mandatory Full-Context Review Rule** — read in full anything `MASTER_INDEX.md` flags as relevant, not just the obviously applicable plan.
9. Read the plan/spec/evidence for the workstream — including dated `docs/project-state/PROJECT_SAVE_*.md` checkpoints `MASTER_INDEX.md` points to; a target architecture can live only in a project-save record.

Do **not** ask Kamara to repeat facts that are already available in these records.

When unsure of the tier, use the higher one. Lesson retained: on 2026-09-17/18 a capability was designed without checking an already-documented target architecture (Model Router / KARMO-FIRST Orchestration, 2026-09-11) — any design-shaped task is Tier 3, even if it feels read-only.

If two sources disagree:

- governance/invariants win for permanent engineering rules;
- `CURRENT_STATE.md` wins for detailed current project state;
- the relevant approved workstream plan/spec wins for that workstream's agreed design;
- `KARMO_DASHBOARD.md` is a concise cockpit, not the deep source of truth;
- stale chat memory never overrides committed project records.

If something cannot be verified, label it **NEEDS VERIFICATION** instead of guessing.

---

## 2. What KARMO is

KARMO is Kamara's long-term private, model-agnostic AI/automation platform and home-lab project.

Stable design intent:

- private/local-first where practical;
- models are replaceable workers, not unrestricted administrators;
- PostgreSQL holds durable structured state/conversation data;
- Qdrant provides vector/semantic memory;
- document intelligence and retrieval remain provenance-aware;
- tools and agents operate through explicit capability/approval boundaries;
- consequential actions are auditable and human-approved;
- personal KARMO data/secrets must remain separate from reusable or customer/business deployments;
- security matters, but security engineering must support a working system rather than create endless infrastructure churn.

KARMO should evolve by building useful capabilities on top of its verified foundation, not by repeatedly rebuilding the foundation.

---

## 3. Current orientation — read the authoritative files before relying on this summary

At the time this bootstrap was created:

- **Foundation & Reliability Layer (Foundation v1): complete.**
- **KARMO Control & Approval Layer (Core v2 prototypes): merged/tested, not production-deployed.**
- **Trusted Computer Worker System (Worker Runtime v0.1): merged/tested, not production-deployed or connected to live KARMO.**
- **Experimental Hybrid Search (H0.3): retained as NO-PROMOTION / learning and research material, not production retrieval.**
- BloomBoss is the leading practical capability direction.
- The AI/Agent Engineering learning program exists on its own learning branch/PR and should be reconciled carefully before any merge.

Do not treat this section as permanently current. Always read `CURRENT_STATE.md` and `KARMO_DASHBOARD.md` first.

---

## 4. Plain-English naming rule

Kamara learns the real engineering terminology but does not want project orientation buried under cryptic labels.

Use:

**Plain-English purpose first (technical name in parentheses)**

Examples:

- Reliable Event Delivery (H0.1 Transactional Outbox)
- Document Memory & Versioning (H0.2 Knowledge Lifecycle)
- Experimental Hybrid Search (H0.3 Hybrid Retrieval)
- Integrity & Consistency Checker (H0.4 Integrity/Reconciliation)
- KARMO Control & Approval Layer (Core v2 prototypes)
- Trusted Computer Worker System (Worker Runtime v0.1)

Do not replace real terminology; teach it while keeping the purpose obvious.

---

## 5. How Kamara wants AI systems to work

### Follow the intent, not only the literal sentence

When Kamara gives a broad idea, determine the larger project goal from the repository and conversation before answering.

Do not merely produce a feature list when the real goal is an operating system, business workflow, learning outcome, or end-to-end capability.

At the same time, do not invent scope or silently authorize new work. Distinguish:

- **ACTIVE NOW**
- **BLOCKING**
- **DEFERRED**
- **PENDING DECISION**

### Action first

When Kamara asks to research, check, verify, inspect, or perform an action, do the action first when tools permit. Avoid long progress narration such as "I will look into that."

### Keep execution concise

Default to concise instructions.

For hands-on technical work:

- about 5 commands/tasks per batch unless Kamara asks otherwise;
- when she asks for the "next exact command only," give only that command;
- give the next task promptly after completion;
- do not drown simple execution in unnecessary background.

### Do not test forever

The project exists to work and be used.

Preferred pattern:

**build -> test the requirement -> deploy safely when authorized -> verify once -> record -> use -> learn -> improve**

Use one meaningful acceptance test per requirement. Repeat testing only when there is a materially justified reason, such as a fix that changes the failure mode or a final integration check.

Do not create new infrastructure merely because it is technically interesting. New infrastructure should support a real user-facing or operational capability.

### Human approach

When Kamara says **"human approach"**, model how a competent human team would actually perform the job before automating it.

For each major capability:

1. identify the human role/job;
2. identify what information that person needs;
3. map the normal workflow;
4. identify likely failure modes and where the human would look;
5. automate only the parts that add value;
6. keep health/status visible;
7. preserve a manual fallback;
8. measure the real-world outcome;
9. record the decision and result for future learning.

A failure should be understandable in human terms: **what broke, what it affects, whether work can continue, what to do next, and where to troubleshoot.**

---

## 6. Engineering collaboration model

Preferred division of labor:

- **Claude Code:** implementation in the approved isolated branch/workspace.
- **ChatGPT:** independent architecture/review/verification and planning.
- **Git + pull requests:** durable boundary between AI agents.
- **Kamara:** final authority for scope, merge, production access, deployment, secrets, and meaningful exceptions unless she explicitly delegates otherwise.

Never let one AI agent's unsupported claim become project truth merely because another AI repeats it. Verify through repository evidence, tests, or an explicitly authorized read-only check.

---

## 7. Security and production boundaries

Security is a permanent priority, but production restrictions must be applied precisely rather than used as a reason to stall indefinitely.

Permanent defaults:

- production access is prohibited without explicit task-specific authorization;
- a read-only grant never implies write permission;
- do not request, print, or commit secrets;
- do not weaken access controls to make development easier;
- do not merge, deploy, restart, migrate, delete, or repair production unless the approval boundary permits it;
- work in isolated development/test space and approved feature branches by default.

For consequential commands/configuration changes, explain or record:

- **WHAT** it does;
- **WHY** it is needed;
- **WHAT CHANGES**;
- **RISK**;
- **HOW TO VERIFY**;
- **HOW TO ROLLBACK**.

Read the engineering invariants instead of reconstructing these rules from memory.

---

## 8. Historical home-lab context

This section exists to prevent future assistants from restarting old infrastructure conversations. It is historical context, not a substitute for the current inventories.

Earlier KARMO home-lab work included:

- three HP EliteDesk 800 G6 Desktop Mini systems intended as Proxmox nodes;
- a NETGEAR GS108E managed lab switch;
- a three-node Proxmox/KVE direction;
- a powerline uplink used/considered for management connectivity, with the explicit understanding that it is not ideal for high-bandwidth cluster migration/shared-storage/Ceph traffic;
- remote-access planning centered on Tailscale rather than exposing management/services directly to the Internet;
- significant Secure Boot/EFI/Proxmox troubleshooting, including successful hardware diagnostics and evidence pointing toward boot-chain/verification rather than SSD failure;
- later separation of the AI runtime from the broader Proxmox infrastructure, with `karmo-ai01` becoming the production KARMO AI host and KARMO-DEV01 becoming the dedicated Apple M3 development/learning workstation.

Do not repeat old BIOS, EFI, storage, or networking troubleshooting unless current evidence shows the same problem still exists.

For current hosts, addresses, software, services, and ports, read:

- `docs/project-state/NETWORK_INVENTORY.md`
- `docs/project-state/SOFTWARE_INVENTORY.md`

---

## 9. KARMO AI foundation history that matters

The important lesson from the early build is the progression, not every old command:

1. local model serving / routing;
2. PostgreSQL durable memory;
3. Qdrant semantic/vector memory;
4. Docling/document ingestion;
5. retrieval evaluation;
6. reliability hardening;
7. knowledge lifecycle/versioning;
8. integrity/reconciliation;
9. governed Core control/approval concepts;
10. trusted worker execution.

The project intentionally preserved rollback evidence and provenance through hardening. Legacy data was not rewritten merely to make a new design look cleaner.

Do not restart from "install a local model and a vector database" unless the current state explicitly says those components were removed.

---

## 10. BloomBoss workstream

BloomBoss is a licensed plant business and is the leading practical KARMO business capability.

The authoritative plan is:

`docs/plans/BLOOMBOSS_BUILD_PLAN.md`

Read that file before proposing BloomBoss architecture or implementation.

Stable BloomBoss principles:

- build it like a competent human business team, not disconnected automations;
- BloomBoss/KARMO master data should remain the business source of truth;
- supported integrations are preferred in this order: official API -> official integration -> official import/export -> authorized browser workflow only when necessary;
- historical data is a major advantage: Kamara can reconstruct roughly 7–9 months and approximately 90–98% of plants bought/sold;
- unknown historical financial values remain explicitly unknown; never silently invent them;
- marketplace research should compare external signals with BloomBoss's own realized outcomes;
- one authoritative inventory identity should support multiple sales channels;
- build operational reliability before risky live-production automation;
- **OBS/live production is intentionally last** and must never become required for a live sale to continue.

Current approved BloomBoss phase order:

1. Historical Data Intelligence
2. Marketplace Research Workers
3. Pricing + Product Recommendations
4. Multi-Channel Commerce Hub
5. Customer + Marketing Intelligence
6. Operations & Reliability
7. OBS / Live Production

The nine long-term intelligence areas are defined in the BloomBoss plan; do not recreate or reorder them casually.

---

## 11. Learning / study workstream

Kamara is not only building KARMO; she is learning the engineering behind it.

Study style:

**learn -> see it in KARMO -> build -> break -> debug -> explain -> challenge the architecture**

When study is active:

- teach one concept at a time;
- use plain language first, then real terminology;
- connect the concept to KARMO;
- let Kamara write/run the core Python rather than turning the lesson into passive copy/paste;
- use local/dev systems only unless a separate production action is explicitly approved;
- avoid derailing study time with repo rescans, environment setup, or unrelated infrastructure work unless genuinely blocking.

The AI/Agent Engineering learning program is currently represented by PR #26 / branch `learning/ai-agent-engineering-program`; reconcile it against current `main` before attempting to merge because it predates newer project-state changes.

Experimental Hybrid Search (H0.3) is intentionally useful as a later training/research case study for embeddings, dense retrieval, BM25, reciprocal-rank fusion, and evaluation rather than something to promote automatically.

---

## 12. Context preservation protocol

The repository is KARMO's durable memory layer.

### At session start

A new AI should:

1. load context per the tier in Section 1;
2. identify the active workstream;
3. read only the relevant deeper documents;
4. state the current stage, active task, blockers, safety boundary, and next authorized action;
5. continue from that point instead of rebuilding context from scratch.

### During the session

Record meaningful discoveries, decisions, configuration changes, commands, results, failures, fixes, hardware/software changes, and next steps in the appropriate durable project record or PR evidence.

Do not save important project truth only in chat.

### At session end

For any major KARMO session, follow the repository's mandatory **PROJECT SAVE** rule.

A complete save should leave enough durable context that another AI can resume without needing the previous chat.

Update this `AI_START_HERE.md` only when a **stable working principle, project identity, bootstrap rule, or long-term workstream relationship** changes. Do not turn it into a minute-by-minute status log.

Dynamic state belongs in `docs/project-state/`.

---

## 13. No-memory AI starter prompt

When starting a fresh ChatGPT/Claude/Codex/other AI session that can access the repository, Kamara can use this short prompt:

> You are joining my existing KARMO project. Do not start from scratch. Open the repository and read `AI_START_HERE.md` first, then follow its bootstrap/read order. Treat committed project records as the source of truth over chat memory. Before proposing changes, tell me the current stage, active workstream, safety/approval boundary, and next authorized action. Follow the intent of my request using the project context, but do not invent scope or repeat work already completed.

For a coding agent, add:

> Follow `AGENTS.md` and your tool-specific repository instructions. Work only in the approved non-production branch/workspace unless I explicitly authorize otherwise.

If the AI cannot access the repository, provide this file first. It should then ask only for the specific authoritative files it needs, rather than asking Kamara to retell the entire project history.

---

## 14. What a good handoff looks like

A new AI is successfully oriented when it can answer, without Kamara retraining it:

- What is KARMO trying to become?
- What is actually live versus merely merged/tested?
- What must never be touched without production authorization?
- What is the current active workstream?
- What has already been completed so it should not be rebuilt?
- How does Kamara prefer to work and learn?
- What does "human approach" mean?
- Where is the authoritative BloomBoss plan?
- What should happen next, and what is deferred?

If it cannot answer these from the repository, it should retrieve the relevant documents before giving consequential guidance.

---

## 15. Maintenance rule

This bootstrap is not a replacement for `MASTER_INDEX.md`, `CURRENT_STATE.md`, governance, plans, evidence, or the dashboard.

Think of it as the **front door to the KARMO brain**:

`AI_START_HERE.md -> authoritative map/state -> relevant workstream docs -> evidence/code`

That structure is intentional. A short durable map is easier for new AI systems to use and maintain than one enormous prompt that becomes stale.

Last created/reviewed: 2026-09-10

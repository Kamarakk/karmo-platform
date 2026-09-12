# PROJECT SAVE — KARMO-FIRST Orchestration, Palmstreet Intake, and KVE Recovery

Date: 2026-09-11
Branch: `feat/bloomboss-historical-intelligence`
Status: SESSION STATE CAPTURED — no production deployment authorized

## Why this save exists

This file captures the meaningful decisions, verified facts, unresolved gaps, and next-step direction established after the prior BloomBoss project save. It is intended to prevent loss of architectural intent between ChatGPT, Claude, KARMO, and future sessions.

## New governing rule: KARMO FIRST

Before recommending an app, SaaS product, manual export, cloud folder, phone shortcut, or third-party workflow, first determine whether KARMO can own the capability using infrastructure already available.

External systems should be treated as **sources, destinations, or adapters** — not as KARMO's brain, workflow engine, authority layer, or source of truth.

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

## Performance / reliability decisions

- Do not route every task through every model.
- Use a fast path for routine work and a deeper multi-model path only when risk/complexity warrants it.
- Long-running work must not depend on one continuous model conversation.
- KARMO must persist resumable task state, checkpoints, retries, evidence, and next-action state so work can continue after model/session interruption.

## Hardware / compute direction

The project started with three matching KVE PCs; the user explicitly reaffirmed that KVE1, KVE2, and KVE3 are the original three-machine design and should not be treated as random spare PCs.

Do **not** buy or recommend replacement hardware before reconstructing and measuring the existing three-node capacity.

Future target concept: use KARMO as the control plane and distribute suitable workloads across the existing KVE compute fabric. Permanent node roles are **NOT YET ASSIGNED** and require inventory/verification first.

## Model-verifier direction

A DeepSeek-family coding model was discussed as a possible independent code-review/verifier resource for Claude-generated changes.

Decision: treat any DeepSeek/OpenAI/Anthropic/local model as a replaceable model adapter behind KARMO. Do not trust a second model merely because it agrees with the first. Verification priority is:

`tests / deterministic evidence -> independent review -> human escalation when required`

Exact DeepSeek version/capability claims discussed in chat must be revalidated before implementation or procurement decisions.

## Remote-access / security direction

Remote security architecture remains KARMO-owned.

Preferred pattern:

`KARMO -> approved management path -> KVE hosts / managed systems`

Do not install Remote Desktop Commander or another agent on every Proxmox host merely for convenience. Prefer an existing secure management path (for example KARMO-AI01 or another approved bastion) when system-fit supports it.

Credentials/secrets must not be handed to ChatGPT/Claude as task context. Models should receive scoped capabilities through KARMO.

## KVE management facts captured this session

User-supplied current management targets:
- KVE01: `root@192.168.1.20`
- KVE02: `root@192.168.1.21`
- KVE03: `root@192.168.1.22`

Observed in user screenshot:
- KVE01 accepted SSH from KARMO-DEV01/Mac at `192.168.1.20`.
- KVE03 accepted SSH from KARMO-DEV01/Mac at `192.168.1.22`.
- KVE01 showed `vmbr0` at `192.168.1.20/24`.

KVE02 `.21` was supplied directly by the user and remains **NEEDS LIVE VERIFICATION** before consequential use.

User stated `karmolab1` had been disconnected from the network; therefore any apparent Proxmox/cluster outage must be separated into:
- host actually down; versus
- host/cluster unreachable because a management/network dependency is disconnected.

Do not infer that all Proxmox hosts are down when individual SSH endpoints are reachable.

## Remote Desktop Commander state observed this session

Remote Desktop Commander listed only one registered device:
- `karmo-ai01`

At the time checked it was **offline**; no KVE host was registered directly in that remote-control layer.

This does not mean KVE01/02/03 are offline. It only describes that specific management tool's registered-device state.

## Palmstreet historical-data findings

Palmstreet Seller Hub showed an All Orders view with **446 results across 18 pages**.

The built-in export action failed to produce a usable export even when the user tried multiple date ranges including a single day. Therefore the export path is currently treated as **unavailable/unreliable for this account/session**, not as a reason to redesign BloomBoss around screenshots.

Verified Seller Hub table fields observed:
- Order ID
- Customer
- Full Name
- Item QTY
- Order Value
- Paid Shipping Fee
- Purchase Date
- Order Status
- Order Source
- Buyer Note
- Seller Note

Additional observed values included LIVE, Marketplace, Long-form Auction, Finished, Refunded/Canceled, and Partially refunded states.

Screenshots covering the order-history pages were captured in the ChatGPT conversation, including page 10 coverage. Raw customer names/order identifiers from screenshots are **not copied into this Git repository** in this save; the repo records schema/system facts only to avoid unnecessarily persisting customer PII in source control.

## Palmstreet importer work completed in branch during this session

The BloomBoss Palmstreet staging code was expanded to support verified Seller Hub semantics including:
- item title;
- quantity values such as `1 item`;
- money values;
- dates such as `Sep 07, 2026`;
- customer username/full name;
- order status;
- order source;
- read-only staging before canonical inventory reconciliation.

The current code still requires follow-up to ensure **Buyer Note** and **Seller Note** are explicitly included in the verified source mapping and tests.

Important rule remains: do not fabricate PlantUnit matches. Platform/order evidence is staged first; canonical Sale creation requires reliable reconciliation.

## Historical purchase direction

BloomBoss should ingest historical **buys as well as sells** from each connected marketplace when supported.

Desired normalized source flow:

`platform purchases + platform sales + fees + shipping + platform IDs + provenance -> KARMO/BloomBoss canonical business state`

Screenshots/invoices are fallback evidence for purchases when no cleaner structured source exists; they are not the intended long-term primary workflow.

## System-level correction to prior consumer recommendations

A prior suggestion to use Google Drive/Dropbox/Box/SharePoint for historical uploads is superseded by KARMO FIRST.

Target system process:

`source -> KARMO Universal Intake -> immutable/raw evidence -> fingerprint/provenance -> source adapter -> staging -> validation -> canonical state`

Cloud storage may be used later only as a deliberate adapter/source/destination if system-fit justifies it.

## Next safe engineering work

Safe non-production work may proceed in GitHub/dev to define and test:
- orchestration task/job state model;
- model-provider abstraction/router;
- capability/tool registry contract;
- Core approval/risk contract;
- Worker job contract;
- verification-result contract;
- durable audit/event format;
- read-only KVE inventory collector;
- three-node capacity/deployment design;
- authority-separation tests;
- PROJECT SAVE / Mission Control updates.

## Deployment / infrastructure gate

Do **not** yet:
- install new software on KVE01/02/03;
- alter Proxmox cluster membership/configuration;
- move VMs/LXCs;
- change networking/firewall/Tailscale;
- expose Worker remotely;
- add credentials;
- install DeepSeek services;
- deploy a new daemon.

First verify live KVE state and available management path from KARMO-controlled infrastructure.

## Immediate next verification sequence

1. Restore/verify KARMO-AI01 remote-management availability.
2. From KARMO-controlled infrastructure, perform read-only reachability checks to `192.168.1.20`, `.21`, `.22`.
3. Verify hostnames and Proxmox/cluster state on all three nodes.
4. Inventory CPU, RAM, storage, NICs, bridges, Proxmox version, kernel, VM/LXC inventory, storage pools, load, and free capacity.
5. Persist verified hardware/network truth in KARMO project records.
6. Only then assign worker/compute roles and decide whether any hardware upgrade is justified.

## Safety boundary

No production deployment, no PR merge, no marketplace writes, no customer-facing actions, no secret publication, and no Proxmox/network changes are authorized by this project save.

This save records intent and verified/qualified state so future ChatGPT, Claude, and KARMO work resumes from the same system-level architecture rather than reverting to consumer-level workarounds.

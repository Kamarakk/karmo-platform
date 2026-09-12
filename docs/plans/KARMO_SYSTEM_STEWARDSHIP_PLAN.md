# KARMO System Stewardship Plan

Status: **APPROVED DIRECTION / DESIGN BEFORE IMPLEMENTATION — 2026-09-11**

## Purpose
KARMO needs continuous operational care, but not a pile of unrelated always-on daemons. The preferred design is one **System Stewardship capability** implemented through the existing KARMO Core + Worker execution model, with several logical steward roles sharing the same scheduling, approval, evidence, and observability framework.

This serves the same intent as separate QA, HR, maintenance, security, and housekeeping workers while reducing software/process sprawl and avoiding duplicate polling, credentials, logs, and lifecycle burden.

## Logical steward roles

### 1. QA Steward
Human analogue: quality assurance / release engineering.
Responsibilities:
- verify changed behavior at the smallest justified scope;
- enforce the Validation Ladder and acceptance criteria;
- detect stale or contradictory project-state claims;
- confirm release/deployment evidence before promotion;
- track failed checks and regression risk.

Boundary: does not endlessly rerun unchanged full suites; follows I-08.

### 2. Security Steward
Human analogue: security engineering / vulnerability management.
Responsibilities:
- review host/package/security-update posture;
- check exposed services, access-control drift, credential references, and secret leakage indicators;
- track known security findings and patch relevance;
- verify least privilege and production-access boundaries;
- produce recommended remediation with severity and evidence.

Boundary: security updates, firewall changes, credential rotation, package upgrades, and service restarts are proposals by default, not autonomous production writes unless separately approved.

### 3. Reliability & Maintenance Steward
Human analogue: SRE / systems administrator.
Responsibilities:
- service health and restart-state visibility;
- disk, memory, CPU, swap, storage-growth, queue/backlog, and capacity trend checks;
- backup/snapshot freshness and restore-readiness checks;
- dependency/runtime version awareness;
- reboot/startup persistence verification;
- scheduled maintenance recommendations.

Boundary: inspect/propose first; repair/restart/update only within explicit authority.

### 4. Housekeeping & Data-Hygiene Steward
Human analogue: operations hygiene / data steward.
Responsibilities:
- identify stale temporary files, orphaned artifacts, oversized logs, unused branches, expired staging data, duplicate records, and retention-policy violations;
- check repository and evidence cleanliness;
- flag storage that can be safely reclaimed;
- preserve provenance and historical evidence.

Boundary: deletion is never implied by detection. Cleanup should normally be proposed as a bounded reversible or separately approved action.

### 5. Agent Governance Steward
Human analogue: HR + access governance for AI workers.
Responsibilities:
- maintain worker/agent job descriptions, ownership, allowed capability classes, training/read-order requirements, and access scope;
- review onboarding/offboarding of workers and tools;
- check whether agents are following the Mandatory System-Fit Review, invariants, approval gates, PROJECT SAVE, and domain-separation rules;
- flag workers with stale permissions, unclear ownership, missing evidence, or unnecessary access;
- maintain an auditable roster of active/deferred/retired workers.

Why not call this simply HR: KARMO's immediate need is governance of agents, roles, permissions, and accountability, not human-employment administration. A separate BloomBoss human-HR capability can be added later if the business actually needs one.

## Shared Stewardship Coordinator
The five roles above should be logical profiles behind one coordinator, not five independent background services unless future scale proves isolation is necessary.

Reuse:
- productionized KARMO Core approval semantics;
- Trusted Computer Worker System for execution;
- Tool/Capability Registry when promoted;
- existing systemd scheduling/timers where appropriate;
- existing GitHub/project-state evidence model;
- existing PostgreSQL/Qdrant only where a declared stewardship data model genuinely requires persistence.

Do not add a new workflow engine, monitoring suite, task queue, secrets manager, or scheduler merely to implement stewardship unless the Mandatory System-Fit Review proves an existing component cannot satisfy the requirement.

## Operating model
Each steward check should declare:
- purpose and owner;
- target systems/data;
- capability class;
- cadence or trigger;
- input evidence;
- expected output;
- severity/failure classification;
- whether it may only observe, may propose, or may execute;
- approval requirement;
- rollback/fallback where applicable;
- last run / last success / current finding status.

Recommended default authority:
- routine inspections: READ;
- reports/remediation plans: DRAFT/PROPOSE;
- safe repository housekeeping: bounded REVERSIBLE_WRITE only when explicitly delegated;
- production patching/restarts/network/firewall/credential work: separate production authorization;
- destructive cleanup: explicit per-call approval.

## Suggested cadence
Cadence is a policy decision, not hard-coded implementation:
- continuous/event-triggered: release QA checks on changed code;
- daily: lightweight health/capacity/security signal check where useful;
- weekly: maintenance, backup, access, patch, and repository hygiene review;
- monthly: deeper configuration drift, lifecycle, permission/worker roster, restore-readiness, and dependency review;
- event-driven: after deployment, host addition/removal, access-path change, dependency upgrade, incident, or major architecture change.

Avoid high-frequency polling unless a requirement actually needs it.

## Relationship to KarmoLab
This stewardship capability is the operational evolution of the roadmap's KarmoLab read-only visibility concept. KarmoLab remains the infrastructure-observation domain; System Stewardship defines the human-team roles and recurring responsibilities that consume that visibility. Controlled administration stays behind Core approvals and the Production Access Authorization Gate.

## Implementation sequence
1. Documentation + worker roster schema only.
2. Deploy Core, then Worker under the existing rollout.
3. Implement read-only QA/Reliability/Security checks first as Worker capabilities.
4. Add a unified stewardship report/dashboard surface before unattended recurring execution.
5. Add housekeeping proposals and agent-governance reviews.
6. Only then consider bounded automatic remediation for repetitive, low-risk, reversible tasks.

## Success criteria
The system should answer, without Kamara manually checking everything:
- Is KARMO healthy and performing within expected bounds?
- Is anything security-relevant out of date or exposed?
- Are backups, services, access paths, and persistent jobs working?
- Did a recent change meet its acceptance standard?
- Is technical debt, stale data, or clutter accumulating?
- Are agents/workers still operating within their assigned roles and permissions?
- What needs human attention now, and what can safely wait?

The goal is dependable operational stewardship using KARMO's existing control plane, not another independent infrastructure stack.
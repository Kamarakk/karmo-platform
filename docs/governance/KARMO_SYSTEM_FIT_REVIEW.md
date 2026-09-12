# KARMO Mandatory System-Fit & Reuse Review

Status: **APPROVED PROCESS — 2026-09-11**

Purpose: prevent KARMO from accumulating avoidable tools, duplicate services, disconnected architecture, or changes that solve a local symptom while working against the whole-system goal.

This review is mandatory before recommending or implementing a meaningful new tool, package, service, daemon, integration, worker, access method, datastore, network path, or production configuration change. It complements the Engineering Invariant Impact Review; it does not replace it.

## Required review
Before agreeing with or implementing an idea, answer these questions from current repository evidence:

1. **Goal alignment** — What KARMO goal does this advance? Is it user-facing value, reliability, security, learning, or a required dependency?
2. **Reuse first** — Can the requirement be met with software, services, workers, libraries, protocols, or infrastructure already present? If yes, reuse them unless there is a documented reason not to.
3. **Current-state facts** — Read the authoritative current state, inventories, active workstream, access registry, known gaps, and applicable evidence. Do not reason from chat memory alone.
4. **Existing-system impact** — Check execution user, CPU/RAM/disk, ports, network routes, DNS, firewall/netfilter, Docker/container interactions, systemd/user services, persistence, credentials, data stores, backups, logging, updates, and failure visibility.
5. **Duplication/conflict** — Does this overlap an existing capability, worker, service, access path, or governance mechanism?
6. **Lifecycle cost** — Who patches it, monitors it, backs it up, upgrades it, documents it, removes it, and diagnoses it when it fails?
7. **Security/authority** — What new privilege, credential, attack surface, external connectivity, or approval boundary does it introduce?
8. **Failure and fallback** — What happens when it is unavailable? Can KARMO or the human workflow continue? What is the manual fallback?
9. **Simpler alternative** — Is there a smaller change using the existing stack that serves the same purpose with less operational burden?
10. **Decision** — PROCEED / PROCEED WITH CONSTRAINTS / DEFER / REJECT, with a short reason.

## Required agent behavior
- Do not simply agree with Kamara's proposed technical implementation because the business/operational goal is valid. Evaluate whether the proposed implementation is the best fit for the whole system.
- Preserve Kamara's intent while improving the implementation when a safer, simpler, more reusable path exists.
- New software is not prohibited, but it must earn its place by solving a real gap that the current stack cannot reasonably cover.
- Unknown system facts that could materially alter the decision must be labeled `NEEDS_VERIFICATION` and checked before consequential implementation.
- Prefer one shared platform capability over several domain-specific daemons when the jobs share lifecycle, permissions, scheduling, observability, and execution infrastructure.

## Output shape
For consequential proposals, agents should report briefly:

```text
SYSTEM-FIT REVIEW
Goal served:
Existing capability reused:
New software/services added:
Important current-system facts:
Main risks/lifecycle burden:
Simpler alternative considered:
Decision:
Constraints/verification needed:
```

The review should be concise. Its job is to prevent avoidable architecture mistakes, not create paperwork.
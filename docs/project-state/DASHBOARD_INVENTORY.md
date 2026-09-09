# KARMO Dashboard Inventory

See MASTER_INDEX.md for status-tag definitions.

## Current state: none established

**VERIFIED (as an absence):** no dashboard, monitoring UI, or visualization
surface for KARMO is referenced anywhere in this repository's committed
evidence, handoff docs, or governance files, and none was described as
existing in this session's reconciliation input. `run_auditor.py`
(`h04/app/run_auditor.py`) produces a report-only, on-demand text/CLI output
(`STATUS`: `CLEAN` / `CLEAN_WITH_KNOWN_LEGACY_GAPS` / `INTEGRITY_FINDINGS_PRESENT`,
plus finding counts) — this is the closest thing to an observability surface
that currently exists, and it is invoked manually, not a persistent dashboard.

## Relevance to I-07 (Observability Before Automation)

`docs/governance/KARMO_ENGINEERING_INVARIANTS.md` I-07 requires sufficient
observable state before any autonomous/background workflow is promoted.
`karmo-h01-relay` (the one production background service, H0.1) and the H0.4
auditor are the two candidates that would benefit from a real dashboard or
alerting surface as KARMO's automation surface grows. No such surface exists
yet — this is a **NEXT_STEPS.md** candidate, not a current-state item.

## Action

If/when a dashboard is introduced (Grafana, a custom status page, log
aggregation UI, etc.), record it here with: purpose, data source, owner, and
whether it is read-only or can trigger any action (per I-09 capability
classification).

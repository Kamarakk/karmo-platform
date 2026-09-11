# PROJECT SAVE — 2026-09-11 Access + Core/Worker Rollout

Status: **COMPLETE FOR EXECUTED WORK; CURRENT_STATE.md detailed reconciliation remains follow-up**

## Approved scope
Kamara approved Tasks 1–4 as scoped: direct KARMO-AI01 Tailscale enrollment, Core deployment, Worker deployment after Core health success, Access/Stewardship registry promotion, rollback within those boundaries, and PROJECT SAVE. Stop conditions applied to conflicts or scope expansion.

## Production results
- KARMO-AI01 enrolled in the existing tailnet at `100.75.239.44`.
- Tailscale production DNS acceptance disabled (`--accept-dns=false`).
- Tailscale SSH not enabled.
- No subnet routes or exit-node capability configured.
- Existing OpenSSH authentication retained.
- `tailscaled` verified active after enrollment.
- `karmo-core.service` installed to `/opt/karmo/core-service`, enabled, and active.
- Deployment automation required the Core health check to pass before Worker installation could proceed.
- `karmo-worker.service` installed to `/opt/karmo/worker-service`, enabled, and active.
- Worker remains local-only: no network listener, no real Worker transport, no capability execution, no persistent writes.
- No DB schema changes, Qdrant mutation, secret changes, or existing KARMO service restart were authorized/performed as part of the Core/Worker deployment boundary.

## Repository results
- PR #34 (`feat: productionize Worker Runtime behind Core`) merged at `21019c1e2833b0f797e09d225639305530c48f3e`.
- PR #35 (`docs: add access registry and system stewardship framework`) reconciled with the live Tailscale result and merged at `d158fc4d252af1daf03dd77c57b066a29446ec44`.
- Access registry records `100.75.239.44` as KARMO-AI01's direct Tailscale address and retains KVE02 `100.75.39.34` as fallback.
- Mandatory System-Fit & Reuse Review is now part of agent workflow.
- System Stewardship design keeps QA, Security, Reliability/Maintenance, Housekeeping/Data-Hygiene, and Agent Governance as logical roles over existing Core/Worker rather than separate always-on infrastructure.

## Maintenance finding
During package installation, Ubuntu reported running kernel `6.8.0-138-generic` while `6.8.0-139-generic` is installed/expected. A controlled reboot is needed later to load the newer kernel. No reboot was performed during this rollout. `needrestart` also reported deferred service restarts including Docker/systemd-logind/unattended-upgrades; no containers required restart at that time.

## Remaining verification
- Direct client-side OpenSSH smoke from KARMO-DEV01 to `lofason@100.75.239.44` remains **NEEDS VERIFICATION** at the next convenient remote-use opportunity.
- At the planned kernel reboot maintenance window, verify once after reboot: Tailscale, Core, Worker, existing KARMO services, and H0.1 user-service persistence.

## Persistent records updated
- `docs/access/*` via PR #35
- `docs/project-state/KARMO_DASHBOARD.md`
- `docs/project-state/NETWORK_INVENTORY.md`
- `docs/project-state/SOFTWARE_INVENTORY.md`
- this PROJECT SAVE record

## Stopping point
Direct Tailscale networking, Core, and the restricted Worker service boundary are live on KARMO-AI01. Real Worker network transport remains disabled. The next project direction is useful capability work rather than further infrastructure expansion by default.

## Reconciliation note
`CURRENT_STATE.md` predates this live rollout and still contains older not-deployed wording. Until that large detailed record is reconciled, this PROJECT SAVE plus the refreshed Mission Control and inventories are the authoritative 2026-09-11 delta. Do not interpret the stale deployment wording in `CURRENT_STATE.md` as evidence that this completed rollout did not occur.

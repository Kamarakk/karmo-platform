# PROJECT SAVE — Core Host Preflight

Saved: 2026-09-11
Target: KARMO-AI01 production

## Rollout state

- PR #33 (`feat: productionize Core v2 for approved rollout`) is merged to `main` at merge commit `cdbe704e577919c2f63569df41dc3f777dc47c4f`.
- Core Productionization workflow for PR head `26cc194f6e4132323ecfcf9c94b440f6f0a3839d` completed successfully; targeted tests passed.
- Remote Desktop Commander is connected to KARMO-AI01 and verified online.

## Read-only production host preflight results

Verified on KARMO-AI01 as user `lofason`:

- host: `karmo-ai01`;
- Python: `/usr/bin/python3`, Python `3.12.3`;
- systemd: `/usr/bin/systemctl`, systemd `255`;
- proposed target path `/opt/karmo/core-service`: absent, so no path collision;
- proposed service name `karmo-core.service`: absent, so no unit-name collision;
- `/opt/karmo`: absent;
- `/opt` exists and is root-owned; it is not writable by `lofason`;
- non-interactive sudo is not available (`sudo -n true` failed), so privileged installation cannot safely continue unattended;
- production app root `/home/lofason/karmo-ai` exists;
- available root filesystem capacity is about 63 GiB free; memory headroom is ample for the bounded Core service.

A read-only `systemctl --user` check from the remote MCP process could not attach to the user bus (`Failed to connect to bus: No medium found`). No existing service was changed or restarted.

## Safety boundary preserved

No Core or Worker production files were installed.
No existing KARMO service was restarted or modified.
No PostgreSQL or Qdrant mutation occurred.
No secret, network exposure, or worker transport change occurred.

## Current blocker

The Core host preflight itself is otherwise clean, but deployment to the approved `/opt/karmo/core-service` path requires privileged writes and system service installation. Because `lofason` does not have non-interactive sudo in the Remote Desktop Commander session, proceeding unattended would require requesting or handling an interactive sudo password, which is intentionally not done.

## Next exact phase

When Kamara is available at a terminal:

1. authorize/complete the bounded privileged Core install to `/opt/karmo/core-service` and `/etc/systemd/system/karmo-core.service`;
2. start only the new `karmo-core.service`;
3. run the single approved Core smoke/health check;
4. if healthy, continue to Worker Runtime productionization/deployment review;
5. if unhealthy, disable/remove only the new Core service/files and stop.

Worker remains blocked until Core passes its production smoke check.

# PROJECT SAVE — 2026-09-11 Post-Reboot Verification

Status: **COMPLETE**

## Scope
Controlled KARMO-AI01 reboot and the single approved post-reboot verification following the Tailscale + Core + Worker rollout.

## Verified production state
- Host: `karmo-ai01`
- Running kernel: `6.8.0-139-generic`
- `tailscaled`: active
- Tailscale IPv4: `100.75.239.44`
- `karmo-core.service`: active
- `karmo-worker.service`: active
- `docker.service`: active
- `loginctl show-user lofason -p Linger --value`: `yes`
- Existing H0.1 relay process present after reboot: `/home/lofason/karmo-ai/core/venv/bin/python outbox.py --loop --worker-id karmo-h01-relay`

## Interpretation
The reboot successfully loaded the new kernel and preserved the newly deployed access/control/worker services plus Docker. The existing H0.1 user-level relay also persisted across reboot, closing its previous reboot-persistence verification gap.

## Boundaries preserved
- No database schema change.
- No Qdrant mutation.
- No Tailscale SSH.
- No subnet routing or exit-node configuration.
- No unrelated production service restart or configuration change after reboot.
- Worker network transport remains disabled.
- Worker capability execution remains disabled.

## Rollback
No rollback required. All verified services returned active after reboot.

## Stopping point
The approved Tailscale → Core → Worker → access/stewardship → controlled reboot sequence is complete and verified.

## Next action
Resume normal KARMO roadmap work from the updated Mission Control / project-state records. Direct OpenSSH-over-Tailscale client smoke from KARMO-DEV01 remains a useful convenience verification, not a blocker to the completed rollout.

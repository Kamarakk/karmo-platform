# PROJECT SAVE — PR #41 Post-Merge / Worker Activation Start

Date: 2026-09-12 PDT
Status: IN PROGRESS — post-merge checkpoint captured; Worker01/Worker02 activation track opened.

## Verified repository checkpoint

- PR #41, `harden durable worker coordination boundaries`, merged into `main`.
- Merge commit: `879b242c801f10fc141e68874847d9b9315dd304`.
- Pre-merge validation was green:
  - Core Productionization #63: PASS.
  - KARMO Full Predeploy #124: PASS, including Worker Runtime, Core service with real PostgreSQL, Worker production-boundary, and Core-v2 regression jobs.
- The durable worker coordinator now includes fail-closed current-key checks, drain-before-key-rotation, live-lease ticket fencing, authenticated heartbeat requirement, transactional worker audit events, fail-closed finalization, and bounded terminal ticket cleanup.

## Verified production checkpoint after merge

Read-only verification from KARMO-AI01 after the repository merge:

- Hostname: `karmo-ai01`.
- `karmo-core.service`: active.
- `karmo-worker.service`: active.
- Existing application dependencies remain loopback-only:
  - PostgreSQL: `127.0.0.1:5433`.
  - Qdrant: `127.0.0.1:6333` / `127.0.0.1:6334`.
  - Ollama: `127.0.0.1:11434`.
- SSH remains the only observed non-loopback listener in this checkpoint (`:22`).
- KVE01 `192.168.1.20`, KVE02 `192.168.1.21`, and KVE03 `192.168.1.22` are reachable from KARMO-AI01 over the LAN.
- No KARMO worker-network listener was opened and no production application code was deployed by PR #41.

## Access finding

- KARMO-AI01 did not yet trust KVE02's host key in `/home/lofason/.ssh/known_hosts`.
- A fresh ED25519 scan was independently fingerprinted before trust was added.
- Observed fingerprint exactly matched the already-verified KVE02 fingerprint:
  `SHA256:Sw5YUmfYdX3qQawpQJoxHuR3w5dAdbBVp2jRPLgfrVU`.
- That exact host key was pinned for user `lofason` on KARMO-AI01.
- Strict host-key checking remains enabled.
- Root SSH authentication from KARMO-AI01 to KVE02 is still refused (`Permission denied (publickey,password)`); no password reset, root-key copy, auth weakening, or SSH policy change was attempted.

## Worker hosts / VM target state

Previously established target topology remains:

- KVE01 (`192.168.1.20`) → VM 101 `KARMO-WORKER01`.
- KVE03 (`192.168.1.22`) → VM 102 `KARMO-WORKER02`.
- Each worker VM target: 8 vCPU, 10 GiB fixed RAM, 120 GiB local-lvm disk, host CPU, VirtIO networking on `vmbr0`, firewall enabled, QEMU guest agent enabled, autostart enabled.
- Secure NoCloud seed ISOs were already attached; SSH password auth and root login were disabled by seed policy, with KARMO-DEV01's dedicated admin public key provisioned.
- Current guest-install completion / IP assignment for VM 101 and VM 102 remains to be reverified from Proxmox/guest state before network-worker activation.

## Architecture decision for this activation track

The older Worker Runtime Phase 15 network plan remains useful background but is partially superseded by the durable Core worker coordinator now merged through PR #41.

Activation will reuse the durable Core authority path rather than build a second coordinator. Requirements:

1. KARMO-AI01 remains the sole Core/Commander authority.
2. Worker01 and Worker02 initiate outbound connections; workers receive no new inbound KARMO listener.
3. Network reachability never grants execution authority.
4. Worker authentication, heartbeat leases, execution tickets, result authentication, approval bindings, and recovery state remain Core-controlled and durable.
5. Unknown execution outcomes go to reconciliation / `RECOVERY_REQUIRED`; never automatic replay.
6. Direct LAN transport is preferred for local worker dependencies; Tailscale is not required for Worker01/Worker02 LAN operation.
7. No production listener, firewall change, database migration execution, or worker enrollment will occur until its reviewed implementation and activation gate are explicitly cleared.

## Activation track opened

Repository branch created from the PR #41 merge commit:

`feat/worker-transport-activation`

Immediate sequence:

1. Reverify VM 101 / VM 102 installation state, guest-agent state, hostnames, IPs, SSH policy, resources, and time sync.
2. Reconcile the old local `WorkerTransport` callable-based prototype seam with the now-durable execution-ticket coordinator; do not duplicate coordinator authority.
3. Implement and test a bounded outbound worker transport with authenticated coordinator/worker identity and no worker inbound listener.
4. Validate reconnect, stale heartbeat, lease expiry, ticket replay, key rotation, result binding, coordinator restart/recovery, and fail-closed transport errors in isolation.
5. Review/merge the transport PR only after green full predeploy validation.
6. Then provision/enroll Worker01 and Worker02 one at a time, verifying evidence after each before enabling scheduling.

## Current blocker / next operator-visible gate

KARMO-AI01 can reach all three KVE nodes but does not currently possess an authorized credential to query Proxmox as root. Therefore the next infrastructure verification must use an already-authorized Proxmox access path (KARMO-DEV01 SSH / Proxmox Web UI / existing cluster-authorized host path) rather than weakening authentication.

No production worker transport is active yet.

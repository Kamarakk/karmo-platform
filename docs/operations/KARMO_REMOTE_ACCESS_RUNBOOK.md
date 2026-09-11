# KARMO Remote Access Runbook

Status: **VERIFIED WORKING ACCESS PATTERN — 2026-09-11**

Purpose: give ChatGPT, Claude Code, Codex, or another authorized agent a durable record of how remote access to the KARMO production host is reached when KARMO-DEV01 is away from the home LAN.

## Read this before troubleshooting SSH

Do not assume `karmo-ai01` is directly reachable from KARMO-DEV01 when the Mac is on a different LAN. Do not reset passwords, regenerate SSH keys, edit SSH configuration, or change production networking merely because a direct connection to `192.168.1.235` times out.

The established remote path is:

`KARMO-DEV01 -> KVE02 over Tailscale -> KARMO-AI01 over the home LAN`

Current verified addressing for this path:

- KVE02 Tailscale IP: `100.75.39.34`
- KARMO-AI01 LAN IP: `192.168.1.235`
- KARMO-AI01 SSH user: `lofason`

Before relying on these addresses for a consequential action, compare them with `docs/project-state/NETWORK_INVENTORY.md`. If current evidence conflicts, stop and verify rather than changing credentials.

## Normal remote SSH path

From KARMO-DEV01:

```bash
ssh root@100.75.39.34
```

After reaching the KVE02 shell:

```bash
ssh lofason@192.168.1.235
```

Expected destination prompt is equivalent to:

```text
lofason@karmo-ai01:~$
```

This is a jump-through-the-home-network workflow. KVE02 is the Tailscale-reachable bridge; KARMO-AI01 does not need to be directly visible on the remote office LAN for this path to work.

## Why direct SSH can fail from KARMO-DEV01

A direct command such as:

```bash
ssh karmo-ai01
```

may resolve to the home-LAN address `192.168.1.235`. If KARMO-DEV01 is currently on a different subnet, the TCP connection can time out before SSH authentication begins. That is a routing problem, not evidence that the SSH password or key is wrong.

Before touching credentials, distinguish:

- **routing failure** — TCP connection never reaches port 22;
- **SSH authentication failure** — SSH reaches the server and then rejects the presented key/user;
- **authorization failure** — authentication succeeds but the requested privileged action is not permitted.

Do not treat one as another.

## Existing KARMO-DEV01 SSH identity

The existing KARMO SSH configuration previously resolved:

- alias: `karmo-ai01`
- user: `lofason`
- identity file: `~/.ssh/karmo_admin_ed25519`

The private key must never be printed, pasted into chat, committed, or copied into the repository. A connection timeout before key exchange means the key was never presented and should not be replaced merely to troubleshoot routing.

## Reconnecting ChatGPT Remote Desktop Commander

Remote Desktop Commander is a separate access mechanism from SSH. On KARMO-AI01, after reaching the host through the normal remote SSH path, the authorized foreground launcher is:

```bash
npx @wonderwhy-er/desktop-commander@latest remote
```

Keep that process running while ChatGPT needs the remote connection. Closing the terminal/process disconnects Remote Desktop Commander; it does **not** change the Linux login password or SSH key.

Do not create persistence/autostart for Remote Desktop Commander unless separately approved.

## Agent recovery rule

When an agent is asked to reconnect to KARMO remotely:

1. Read `AI_START_HERE.md` and the current project-state files first.
2. Read this runbook before proposing credential changes.
3. Confirm KARMO-DEV01's current network/Tailscale state.
4. Use the KVE02 Tailscale hop when KARMO-DEV01 is not on the KARMO-AI01 home subnet.
5. From KVE02, SSH to KARMO-AI01 on its home-LAN address.
6. If the second hop fails, diagnose KVE02-to-KARMO-AI01 reachability before touching authentication.
7. Never request, expose, store, or commit passwords/private keys.

## Production boundary

Reaching KARMO-AI01 does not itself authorize production changes. Read the current approved deployment/workstream record and governance before writing files, starting/restarting services, changing configuration, or using sudo.

For the 2026-09-11 Core -> Worker rollout, the approved order is Core first, one smoke check, then Worker only after Core passes. Consult the current rollout document and project state rather than relying on this runbook for deployment authorization.

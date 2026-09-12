# KARMO Network Inventory

See MASTER_INDEX.md for status-tag definitions. This file records verified network facts and historical context; it is not a substitute for live probing when a consequential action depends on freshness.

## Production host

| Item | Value | Status |
|---|---|---|
| Hostname | `karmo-ai01` | **VERIFIED** |
| LAN address | `192.168.1.235` | **VERIFIED** |
| OS user | `lofason` | **VERIFIED** |
| Tailscale address | `100.75.239.44` | **VERIFIED**, enrolled 2026-09-11 |
| Tailscale DNS acceptance | disabled (`--accept-dns=false`) | **VERIFIED**, 2026-09-11 |
| Tailscale SSH | not enabled | **VERIFIED**, 2026-09-11 |
| Subnet-route / exit-node advertisement | not configured | **VERIFIED**, 2026-09-11 |

Historical note: KARMO-AI01 did not have Tailscale at the 2026-09-04 H0.1 handoff checkpoint. That state is now superseded.

## Preferred remote access path

Primary remote path after the 2026-09-11 enrollment:

`KARMO-DEV01 -> KARMO-AI01 directly over Tailscale -> normal OpenSSH authentication`

Target:

```bash
ssh lofason@100.75.239.44
```

Direct client-side SSH smoke from KARMO-DEV01 remains **NEEDS VERIFICATION** at the next convenient remote-use opportunity. Tailscale node enrollment and visibility are verified.

## Verified fallback remote path

Retain the previous bridge path for recovery:

`KARMO-DEV01 -> KVE02 over Tailscale -> KARMO-AI01 over home LAN`

| Hop | Address / user | Status |
|---|---|---|
| KVE02 | `root@100.75.39.34` | **VERIFIED** fallback Tailscale jump host |
| KARMO-AI01 from KVE02 | `lofason@192.168.1.235` | **VERIFIED** fallback second-hop target |

Do not interpret a connection timeout as a credential failure until routing/transport has been verified. The structured access truth and recovery order now live under `docs/access/`.

## Known tailnet peers relevant to KARMO

| Host | Tailscale IP | Status |
|---|---|---|
| KARMO-AI01 | `100.75.239.44` | **VERIFIED**, online 2026-09-11 |
| KARMO-DEV01 / `abcds-macbook-pro` | `100.109.176.0` | **VERIFIED** |
| KVE02 | `100.75.39.34` | **VERIFIED** |
| Office PC `cia103a1` | `100.117.202.20` | **VERIFIED**; last observed offline during 2026-09-11 host check |
| `lofa1` | `100.90.64.51` | **VERIFIED address**, identity remains **NEEDS VERIFICATION**; never assume this is KARMO-AI01 |

## KVE local management targets

Current user-supplied Proxmox management map:

| Host | LAN SSH target | Status |
|---|---|---|
| KVE01 | `root@192.168.1.20` | **VERIFIED from user screenshot**, SSH accepted from KARMO-DEV01; `vmbr0` shown at `192.168.1.20/24` |
| KVE02 | `root@192.168.1.21` | **USER-SUPPLIED / NEEDS LIVE VERIFICATION** |
| KVE03 | `root@192.168.1.22` | **VERIFIED from user screenshot**, SSH accepted from KARMO-DEV01 |

User reported that `karmolab1` had been disconnected from the network. Treat any apparent Proxmox/cluster outage as a routing/topology question until host reachability is checked individually. Do not equate an unavailable management path with all hypervisors being down.

Target management direction is KARMO-owned access through an approved management/bastion path rather than installing another remote-control agent on every Proxmox host merely for convenience.

## Production ports / connection defaults

| Service | Value | Status |
|---|---|---|
| OpenSSH | port `22`, LAN and Tailscale interfaces via existing sshd listener | **VERIFIED listener**, 2026-09-11 |
| PostgreSQL | `127.0.0.1:5433` documented default | **VERIFIED documented default**; current live port **NEEDS VERIFICATION** |
| PostgreSQL db/user | `karmo` / `karmo` | **VERIFIED documented default** |
| Qdrant (production) | collection names documented below; live address/port not restated here | **NEEDS VERIFICATION** |

## Production data-plane addressing

- Qdrant collections: `karmo_semantic_memory`, `karmo_documents`, `karmo_h00_dense_baseline` — **VERIFIED** names.
- PostgreSQL tables: `conversation_memory`, `karmo_memory`, `public.karmo_outbox`, `public.document_registry` — **VERIFIED** names.

## Isolated/test-only network surfaces

- H0.1/H0.4 test PostgreSQL: isolated Docker container, non-default port (`127.0.0.1:57432` for H0.4).
- H0.1/H0.4 test Qdrant: isolated Docker container, non-default ports (`127.0.0.1:58333`/`58334` for H0.4).
- H0.2/H0.3 test Qdrant: in-memory `qdrant-client(":memory:")`, no network socket.

## Gaps

- Direct OpenSSH-over-Tailscale smoke from KARMO-DEV01 is still **NEEDS VERIFICATION**.
- KVE02 LAN target `192.168.1.21` requires live verification before consequential use.
- Live three-node Proxmox cluster membership/state and host capacities require read-only verification before assigning distributed KARMO roles.
- No dedicated full network/firewall diagram is yet committed outside the structured access registry.

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

**Physical hardware and VM-to-hypervisor mapping fully verified live on
2026-09-19** (Kamara ran the commands herself and pasted real output for
all three hosts — this closes the gap this section flagged since
2026-09-11). All three KVE hosts are **identical physical machines**:
Intel Core i7-10700 (8 cores / 16 threads, 2.9 GHz base / 4.8 GHz boost),
15 GiB RAM, Intel UHD Graphics 630 (integrated -- no CUDA/ROCm, no
meaningful LLM acceleration value), ~476.9 GB NVMe disk (Proxmox LVM-thin
layout: ~96 GB root, ~8 GB swap, ~349 GB thin pool).

**Confirmed VM-to-host-to-role mapping (this closes the "which HP runs
what" question completely, including the previously-undocumented VM 100):**

| Physical host | VM ID | Role | RAM used / 15 GiB total (2026-09-19 snapshot) |
|---|---|---|---|
| KVE01 (`192.168.1.20`) | VM 101 | `KARMO-WORKER01` | 11 GiB used, 265 MiB genuinely free |
| KVE02 (`192.168.1.21`) | **VM 100** | **`KARMO-AI01`** (core services + local models) | 10 GiB used, 1.3 GiB genuinely free |
| KVE03 (`192.168.1.22`) | VM 102 | `KARMO-WORKER02` | 11 GiB used, 362 MiB genuinely free |

`karmo-ai01` was previously treated in this repo's own documentation as
if it might be a separate physical machine; it is not -- it is VM 100 on
KVE02, sharing the exact same 15 GiB physical ceiling every other host
here has. Confirmed via `qm config 100` on KVE02: `name: KARMO-AI01`,
matching `net0` MAC `BC:24:11:20:CC:EB`.

**Practical implication, verified not assumed**: all three physical
hosts are already running near their full RAM capacity (each VM already
uses ~10-11 GiB of the host's 15 GiB, leaving only a few hundred MB
genuinely free per host -- swap is present but barely touched on all
three, so none are under active memory pressure, they are simply already
close to fully committed). There is no idle/unused physical capacity
sitting across this 3-node cluster to hand any existing VM more RAM
without adding physical memory to the affected machine. Since all three
hosts are computationally identical (same CPU, same weak integrated
GPU), no host in this cluster can run a model faster than another --
relocating a workload only changes contention, never raw compute speed.

Prior user-supplied Proxmox management map (superseded by the fully
live-verified table above, kept for the historical access-path record):

| Host | LAN SSH target | Status |
|---|---|---|
| KVE01 | `root@192.168.1.20` | **VERIFIED**, SSH accepted from KARMO-DEV01 |
| KVE02 | `root@192.168.1.21` | **VERIFIED** (2026-09-19, live commands run) |
| KVE03 | `root@192.168.1.22` | **VERIFIED**, SSH accepted from KARMO-DEV01 |

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
- ~~KVE02 LAN target requires live verification~~ -- **RESOLVED 2026-09-19**, see above.
- ~~Live three-node Proxmox cluster membership/state and host capacities require read-only verification~~ -- **RESOLVED 2026-09-19**: all three hosts individually verified live (not cluster-membership state specifically, just each host's own hardware/VM placement, which is what every actual KARMO decision so far has needed).
- No dedicated full network/firewall diagram is yet committed outside the structured access registry.

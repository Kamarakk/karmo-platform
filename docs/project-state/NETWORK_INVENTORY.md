# KARMO Network Inventory

See MASTER_INDEX.md for status-tag definitions. This file records network
facts already captured in committed handoff/evidence docs plus what this
session's operator attestation added; it does not itself re-probe production.

## Production host

| Item | Value | Status |
|---|---|---|
| Hostname | `karmo-ai01` | **VERIFIED** (H0.1 handoff doc) |
| LAN address | `192.168.1.235` | **VERIFIED** (H0.1 handoff doc) |
| OS user | `lofason` | **VERIFIED** (H0.1 handoff doc; also the user for whom `karmo-h01-relay` and linger were configured) |
| Tailscale | Not installed as of the 2026-09-04 H0.1 handoff checkpoint. Do not use the Wazuh Tailscale address for KARMO. | **HISTORICAL** as stated; current status **NEEDS VERIFICATION** (not reconfirmed since). |

## Verified remote access path

When KARMO-DEV01 is away from the KARMO home LAN, the established remote path is:

`KARMO-DEV01 -> KVE02 over Tailscale -> KARMO-AI01 over the home LAN`

Current verified values for that path:

| Hop | Address / user | Status |
|---|---|---|
| KVE02 | `root@100.75.39.34` | **VERIFIED** working Tailscale jump host path, 2026-09-11 |
| KARMO-AI01 from KVE02 | `lofason@192.168.1.235` | **VERIFIED** intended second-hop path, 2026-09-11 |

Normal commands from KARMO-DEV01:

```bash
ssh root@100.75.39.34
```

Then from KVE02:

```bash
ssh lofason@192.168.1.235
```

Do not interpret a direct timeout from KARMO-DEV01 to `192.168.1.235` as a password/key failure when KARMO-DEV01 is on another subnet. The connection can fail before SSH authentication begins.

Durable operational procedure and recovery rules: `docs/operations/KARMO_REMOTE_ACCESS_RUNBOOK.md`.

## Production ports / connection defaults

| Service | Value | Status |
|---|---|---|
| PostgreSQL | `127.0.0.1:5433` (per `docs/evidence/h04/H04_INVARIANT_IMPACT_REVIEW.md`, citing `registry_db.py`'s documented default matching `docs/handoff/h04/memory.py`) | **VERIFIED** as documented default; confirmed as still-correct production value: **NEEDS VERIFICATION** (I-02 review found no code defect, but did not itself re-probe the live port). |
| PostgreSQL db/user | `karmo` / `karmo` | **VERIFIED** as documented default (same source). |
| Qdrant (production) | Address/port not restated in evidence beyond collection names below | **NEEDS VERIFICATION** |

## Production data-plane addressing (collection/table names, not network ports)

- Qdrant collections: `karmo_semantic_memory`, `karmo_documents`,
  `karmo_h00_dense_baseline` — **VERIFIED** (H0.1 handoff doc); never to be
  targeted by any isolated/test write, per every H0.1–H0.4 evidence report.
- PostgreSQL tables: `conversation_memory`, `karmo_memory`, `public.karmo_outbox`
  (H0.1+), `public.document_registry` (H0.4+) — **VERIFIED**, see
  SOFTWARE_INVENTORY.md.

## Isolated/test-only network surfaces (never production)

- H0.1/H0.4 test PostgreSQL: isolated Docker container, non-default port
  (H0.4 stack: `127.0.0.1:57432`).
- H0.1/H0.4 test Qdrant: isolated Docker container, non-default ports
  (H0.4 stack: `127.0.0.1:58333`/`58334`).
- H0.2/H0.3 test Qdrant: in-memory `qdrant-client(":memory:")`, no network
  socket at all.

## Gaps

- No dedicated network diagram or firewall/segmentation record exists in
  this repository. **NEEDS VERIFICATION** whether one exists outside the
  repo (e.g., in the prior external "Karmo Knowledge Base" referenced in
  MASTER_INDEX.md).

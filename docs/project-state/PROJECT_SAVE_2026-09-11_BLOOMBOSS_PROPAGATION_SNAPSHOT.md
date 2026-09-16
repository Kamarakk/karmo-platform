# PROJECT SAVE — BloomBoss propagation evidence snapshot integration

Date: 2026-09-11
Workstream: BloomBoss Historical Data Intelligence (Phase 1)
Branch: `feat/bloomboss-historical-intelligence`
PR: #32
Scope: approved non-production GitHub/dev only
Status: **IMPLEMENTED — TARGETED CI IN PROGRESS**

## Purpose

Close a narrow Phase 1 integration gap: propagation/lineage records already had a canonical model, loader, validation, template, and design, but they were not yet part of the reproducible historical snapshot or read-only operator report.

## Changes made

### `bloomboss/history.py`

- `inspect_history_csv()` now accepts optional `propagation_path` evidence.
- Propagation source bytes are independently SHA-256 fingerprinted and size-recorded.
- Propagated child `PlantUnit` records join the canonical in-memory unit set without creating fake purchase batches.
- Propagation lineage validation runs against the combined canonical unit set.
- A propagated child ID that collides with an existing canonical purchased unit ID fails visibly instead of silently replacing or duplicating identity.
- Existing listing validation now sees propagated units too, allowing future listing evidence for propagated inventory without inventing purchase history.
- Business, unit, cultivar, channel, inventory-exposure, and quality summaries use the combined canonical inventory set.

### `bloomboss/report.py`

- JSON output reports propagation record/issue counts.
- Optional propagation source identity is exposed separately from purchase and listing source identity.
- Canonical propagation events and lineage validation findings are included when explicitly supplied.
- CLI adds `--propagations <path>` while preserving the existing source-only and source+listing workflows.

### `tests/test_bloomboss_report.py`

- Existing exact record-count assertion updated for zero-propagation compatibility.
- Added targeted coverage proving a propagated child is included in unit/inventory analysis with `batch_id=None`.
- Added source-fingerprint/report assertions for propagation evidence.
- CLI immutability test now proves purchase, listing, and propagation source files remain unchanged.

## Invariant impact

- I-01 Inheritance/compatibility: **AFFECTED** — existing history/listing call shapes remain supported; propagation is optional and additive.
- I-03 Data authority/transactions: **AFFECTED** — propagation remains its own evidence stream; child inventory becomes canonical in-memory state without fabricating purchase facts.
- I-04 Idempotency/identity: **AFFECTED** — duplicate child identity across purchase and propagation streams now fails visibly.
- I-05 Resources/scale: **NOT MATERIALLY CHANGED** — one additional bounded CSV evidence stream in the existing isolated in-memory Phase 1 model.
- I-06 Migration/rollback: **NOT AFFECTED** — no persistence/schema migration exists.
- I-07 Observability: **AFFECTED** — source identity and propagation relationship issue counts are now visible in the reproducible report.
- I-08 Validation scope: **AFFECTED** — targeted BloomBoss tests only.
- I-09 Authority/permissions: **NOT AFFECTED** — read-only local/GitHub historical analysis; no external action capability.

## Risk

Primary risk is canonical identity collision between a propagated child and a purchased unit. The snapshot rejects such collisions rather than choosing one source silently.

Propagation costs remain explicitly unknown unless supplied. Parent purchase cost is not copied to offspring. No supplier or purchase batch is fabricated for propagated children.

## Validation

Implementation/test head: `07f697f01c7d0c2418dd32675e5a657a83952441`.

GitHub Actions `BloomBoss Phase 1` run #119 was automatically started for this head and was still in progress at PROJECT SAVE time. Do not treat this slice as validation-green until that run concludes successfully.

## Safety record

- Production KARMO accessed: **NO**
- Production KARMO modified: **NO**
- Deployment: **NO**
- PR merge: **NO**
- Secrets used/requested: **NO**
- Marketplace/customer actions: **NO**
- OBS/live production actions: **NO**

## Rollback

Revert commits `a6269b54e9a4da5df8024c267406dc09e6c07c8a`, `9bb49a546b642b197333be58cd068096c1a643c2`, and `07f697f01c7d0c2418dd32675e5a657a83952441`, or close/remove PR #32. No production rollback exists.

## Current stopping point

Propagation/lineage evidence is now integrated into the same reproducible read-only historical snapshot used for purchase, sales, and listing intelligence. Targeted CI is still running. PR #32 remains open and unmerged, and its separate main-resynchronization gate remains unresolved.

## Next authorized action

Verify run #119. If green, refresh the Phase 1 design/evidence with propagation snapshot support. Separately, resynchronize PR #32 with current `main` before any high-level merge/promotion decision. Do not merge or deploy without explicit approval.

PROJECT SAVE: COMPLETE
Persistent records updated: this PROJECT SAVE record
Durable Git commit: created by this documentation commit
Current stopping point: propagation snapshot/report integration implemented; targeted CI in progress; PR #32 merge gate still suspended pending main resync
Next action: verify targeted CI, then refresh Phase 1 evidence; non-production main resync remains required before merge-gate restoration

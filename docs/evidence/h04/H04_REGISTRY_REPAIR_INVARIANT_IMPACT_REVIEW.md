# H0.4 Registry Repair Tool — Invariant Impact Review

Performed before substantial implementation, per
`docs/governance/KARMO_ENGINEERING_INVARIANTS.md`'s Mandatory Phase
Invariant Impact Review. Covers `h04/app/registry_repair.py`, the I-04
follow-up tool `docs/evidence/h04/H04_INVARIANT_IMPACT_REVIEW.md` already
documented as deferred, future, separately-authorized work — Workload 3 in
`docs/plans/KARMO_FOUNDATION_COMPLETION_PLAN.md`.

```
Phase: H0.4 registry repair tool (Foundation Closeout Program, Workload 3)

I-01 Inheritance/compatibility: NOT AFFECTED
I-02 Production parity: NOT AFFECTED
I-03 Data authority/transactions: AFFECTED
I-04 Idempotency/retry: AFFECTED
I-05 Resources/scale: AFFECTED
I-06 Migration/rollback: NOT AFFECTED
I-07 Observability: AFFECTED
I-08 Validation scope: AFFECTED
I-09 Authority/permissions: AFFECTED
```

## I-03 — Data authority & transaction boundaries

`public.document_registry` remains the sole authoritative target; this tool
adds no new authoritative store. Every field written to a new registry row
must already be present, consistent, and verifiable on the orphaned Qdrant
points themselves — never guessed, defaulted, or fabricated. Any ambiguity
(inconsistent document_id/version/provenance/is_active, a missing or
mismatched archive file, a missing document_hash) causes that group to be
refused, not registered with a best-guess value. This mirrors
`bootstrap_legacy_registry.py`'s already-accepted verify-don't-guess
pattern, applied to a structurally different input (normal H0.4-lifecycle
orphan points, which already carry `is_active`/`document_version`/full
provenance on every point payload, vs. bootstrap's legacy points, which
carry none of that and default to `document_version=1`). Each `--apply`
write is its own transaction (one `INSERT` + `commit()` per group, exactly
like bootstrap), so a failure partway through a batch leaves only the
already-committed groups registered — never a half-written row.

## I-04 — Idempotency & retry safety

This is the tool's core purpose. `get_by_hash` is re-checked immediately
before each group is added to the write plan (not only inferred from the
orphan-finding step that selected it), so re-running the tool — with or
without `--apply`, after a partial apply, or after something else has since
closed the gap — reports `ALREADY_REGISTERED` and skips rather than
double-inserting or erroring. `apply_plan` catches and reports a failed
`INSERT` per group without aborting the batch, so one group's failure does
not block registering the others on a retry.

## I-05 — Bounded resources & scale

Reuses `reconciliation.find_orphan_vectors` / `reconciliation.actual_chunk_points`,
both of which already paginate a full Qdrant scroll to exhaustion
(`_scroll_all`, following `next_page_offset` until `None`) rather than a
fixed-limit call — the same pagination-safe pattern already fixed for
`document_ingest_h04.py` and already correct in `reconciliation.py`. No new
unbounded query, unbounded loop, or unbounded memory load is introduced;
`--page-size` bounds only one round-trip's response size, not the total
points read, exactly as in the existing H0.4 modules.

## I-07 — Observability

Every refusal carries an explicit, distinct reason code (mirroring
bootstrap's shape: `INCONSISTENT_DOCUMENT_ID`, `INCONSISTENT_DOCUMENT_VERSION`,
`UNVERIFIABLE_CHUNK_COUNT`, `MISSING_ARCHIVE_PATH`/`INCONSISTENT_ARCHIVE_PATH`,
`INCONSISTENT_SOURCE_PATH`, `MISSING_ARCHIVE_FILE`, `ARCHIVED_FILE_HASH_MISMATCH`,
`MISSING_PROVENANCE_FIELD`/`INCONSISTENT_PROVENANCE`, `INCONSISTENT_IS_ACTIVE`,
`MISSING_DEACTIVATED_AT`, `INCONSISTENT_SUPERSEDED_BY`,
`MISSING_DOCUMENT_HASH`), printed and never silently dropped, matching
I-07's failure-category intent. `READY_TO_REGISTER` / `ALREADY_REGISTERED` /
`REFUSED` counts and per-group detail are always printed in report mode
(the default); `--apply` additionally prints `REGISTERED`/`REGISTER FAILED`
per group and `REGISTERED_COUNT`/`REGISTER_FAILED_COUNT` totals.

## I-09 — Authority & permission boundaries

Report-only by default, exactly like `bootstrap_legacy_registry.py` and
`auditor.py`: no flag means no write, ever. `--apply` is required for any
`INSERT`, gated identically to bootstrap's own `--apply`. This tool never
issues `UPDATE`/`DELETE` against an existing registry row and never touches
Qdrant (no `.upsert()`/`.set_payload()`/`.delete()` call anywhere in the
module) — proven the same way `test_auditor_is_report_only` proves
`auditor.py`'s guarantee: a write-call-injection test that fails hard if
any mutating API is reached during plan-building. No automatic/scheduled
invocation is added — this remains a human-run CLI, matching
`CLAUDE.md`'s prohibition on new autonomous schedules without Natalie's
written approval. Any production run of this tool (even with `--apply`) is
a separate, future, explicitly-authorized action — out of this workload's
scope entirely; only isolated-stack use is in scope here.

## Known inherited assumptions

Every H0.4-lifecycle Qdrant point carries `archive_path`, `source_path`,
`document_id`, `document_version`, `is_active`, `pipeline_version`,
`embedding_model`, `chunker_version` verbatim, as written by
`document_ingest_h04.py`'s `ingest_document` at ingest time. A point
lacking `is_active` entirely (a genuinely legacy, pre-H0.2 point) is not
this tool's target — it is refused here (`INCONSISTENT_IS_ACTIVE`, since
`payload.get("is_active")` returns `None` for such a point) rather than
mis-registered, correctly leaving it to `bootstrap_legacy_registry.py`'s
separate, already-accepted scope.

## Validation plan

Ladder rungs 1 (`py_compile`), 2–3 (new isolated suite,
`h04/tests/test_h04_registry_repair.py`: healthy repair, an
ambiguous/refuse case, an already-registered no-op re-run, and a
report-only-by-default write-call-injection test), and a single targeted
re-run of the existing 10/10 `test_h04_integrity_reconciliation.py` suite —
stated why per I-08: this tool shares `reconciliation.py`'s finding types
and reads the same registry/collection shape, so a targeted re-run (not a
new full regression campaign) confirms nothing in the existing suite
regressed. `auditor.py` is verified unchanged by `git diff`, not only by
test.

## Rollback implications

None needed until/unless a future workload approves running this tool
against production — additive, isolated-only until then. No schema change;
no change to any existing H0.4 module's behavior.

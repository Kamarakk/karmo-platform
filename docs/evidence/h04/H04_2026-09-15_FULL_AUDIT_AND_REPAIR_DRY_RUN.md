# H0.4 — 2026-09-15 Production Registry Repair (Dry Run) and Full Audit

**Status: VERIFIED (production, read-only).** Closes out the "merged
but never run" gap named in this session's earlier review:
`h04/app/registry_repair.py` (PR #8, merged 2026-09-09) had been built,
tested (4/4 isolated), and reviewed, but never actually executed against
production. This record closes that gap.

## What was done

1. Deployed `h04/app/registry_repair.py` (SHA-256
   `0c24bcbd8b563f214b6923ea94dd9b816becd4634e190ec05e2c9b00088e5842`,
   verified matching on the host before use) as a **new** file into
   `/home/lofason/karmo-ai/core/app/`, alongside the existing
   `registry_db.py`/`reconciliation.py`/`archive_integrity.py`/
   `auditor.py` it imports. No existing file touched.
2. Ran it in its **default dry-run mode** (no `--apply` — the script
   itself guarantees zero writes without that flag; confirmed by reading
   the source before running).
3. Also deployed a small one-off wrapper (`run_h04_audit.py`, SHA-256
   `1a9bba88c86af696cd9fef2295e1df2aa8bed6df221303e8cb65f4265a144b19`)
   to invoke the existing `auditor.py` (report-only by construction per
   its own docstring — read APIs only, no write call exists in the
   module) for a fresh, current full audit.
4. Both connected via the existing `karmo`/`karmo` DB role and
   `POSTGRES_PASSWORD` already used by the production compose stack —
   no new credential created, no credential ever printed.

## `registry_repair.py` dry-run result

```
READY_TO_REGISTER: 0
ALREADY_REGISTERED: 0
REFUSED: 2
  REFUSED[INCONSISTENT_DOCUMENT_ID]: document_hash 23646203eed7e187ce2fe0de12c82d5cf83d0a97893a6bdcd2ed30ae3855af9c
  REFUSED[INCONSISTENT_DOCUMENT_ID]: document_hash 5f98126d41381a8a0a4c5034b3402b9a4b763fa043bcfa63f27bdefeb7414c78
```

These are the same two hashes flagged `AMBIGUOUS_MULTIPLE_HASHES_FOR_SOURCE_FILE`
since the original legacy bootstrap. Correctly refused — no
`document_id` at all is present on their points, which is exactly the
"genuinely legacy point" case the tool's own docstring says must remain
`bootstrap_legacy_registry.py`'s separate, human-decision-gated scope,
never guessed at here.

## Fresh full H0.4 audit result

```
{'LEGACY_PROVENANCE_UNVERIFIED': 18, 'ORPHAN_VECTOR': 2, 'ACTIVE_STATE_MISMATCH': 3}
```

All 23 findings trace to the same 5 pre-H0.2 legacy documents:

- **`ORPHAN_VECTOR` (2)** — the same two permanently-ambiguous hashes
  above. Unchanged, expected, still requires Kamara's explicit
  version-ordering decision before any registration.
- **`LEGACY_PROVENANCE_UNVERIFIED` (18)** — 6 points × 3 fields
  (`pipeline_version`, `embedding_model`, `chunker_version`), all on the
  3 legacy documents successfully registered by
  `bootstrap_legacy_registry.py` (`karmo-test.docx`,
  `karmo-v05-final-20260901T215023Z.html`,
  `karmo-v05-unique-20260831T214746Z.html`, hashes `bac7c97b...`,
  `0754fbca...`, `5d1b22a0...`). The registry carries the honest
  placeholder `legacy-unknown-pre-h0.2`; the real Qdrant points have
  `None` for these fields because they predate provenance tracking
  entirely. Expected, not a defect — the system correctly reports
  unknown provenance as unknown rather than fabricating a value.
- **`ACTIVE_STATE_MISMATCH` (3)** — the same 3 legacy documents. Registry
  believes one hash per document is active; Qdrant has no point
  explicitly marked active for any of them (no `is_active` field exists
  on pre-H0.2 points at all). This is the exact "auditor blind spot for
  legacy-bootstrapped documents" already diagnosed on 2026-09-09
  (`docs/evidence/foundation-v1/PRODUCTION_READONLY_VERIFICATION.md`) —
  confirmed here, with a fresh run, to still be exactly that and nothing
  worse. Document-level retrieval itself is unaffected (H0.2's
  `document_memory.py` already treats a missing `is_active` as active on
  read) — this is an auditor cross-check limitation for legacy data, not
  a retrieval-correctness or data-loss problem.

## Conclusion

**No new, unexpected, or real data-integrity problem exists in
production.** Every finding — both from the repair tool's refusal and
the full audit — resolves to the same known set of pre-H0.2 legacy
documents behaving exactly as already understood and documented. The 2
ambiguous hashes remain the only item requiring a human decision; no
automated action can or should resolve them.

## Safety status

- Production writes performed: **zero** (both tools run without any
  write flag/call; verified from source before execution, not merely
  asserted).
- New files added to `/home/lofason/karmo-ai/core/app/`:
  `registry_repair.py` (a genuine, reusable, reviewed production tool —
  left in place), `run_h04_audit.py` (a throwaway one-off wrapper —
  harmless if left, safe to remove).
- No existing production file modified. No credential created or
  printed.

## Next action

None required — this closes the "registry_repair.py merged but never
run" gap and reconfirms the audit's known-findings set is stable and
understood. The 2 ambiguous legacy hashes remain intentionally
unresolved pending Kamara's explicit version-ordering decision, per
`NEXT_STEPS.md`.

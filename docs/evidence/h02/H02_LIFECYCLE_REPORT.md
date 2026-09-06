# H0.2 Knowledge Lifecycle & Vector Versioning — isolated acceptance evidence

## Scope

Frozen H0.2 scope (no hardening-plan doc for H0.2 was present in this
repository at the time of this run; the scope below is the frozen scope
given in the task brief and matches `docs/handoff/h02/*.production-reference.py`
as the baseline to preserve):

- preserve existing SHA-256 identity
- add is_active, document_version, pipeline_version, embedding_model,
  chunker_version, superseded_by, created_at, deactivated_at
- normal retrieval must return active knowledge only
- inactive historical vectors must remain auditable
- verify document v1 -> v2 lifecycle
- verify v1 remains auditable
- verify only v2 appears in normal retrieval

## Implementation

- `test/h02/app/document_ingest.py` — isolated adaptation of
  `docs/handoff/h02/document_ingest.production-reference.py`. Preserves the
  production SHA-256 `document_hash` and uuid5 `chunk_id` scheme verbatim.
  Adds `document_id` (new H0.2 concept: stable identity of a logical
  document across versions, distinct from the per-version `document_hash`)
  and the full lifecycle payload: `is_active`, `document_version`,
  `pipeline_version`, `embedding_model`, `chunker_version`, `superseded_by`,
  `created_at`, `deactivated_at`. Supersession sets the previous active
  chunks' payload to inactive in place (`client.set_payload`) — it never
  deletes points.
- `test/h02/app/document_memory.py` — isolated adaptation of
  `docs/handoff/h02/document_memory.production-reference.py`.
  `search_documents` (normal retrieval) filters on `is_active == True`.
  `get_document_history` (audit path) has no such filter, so superseded
  versions remain queryable.
- No docling/DocumentConverter and no live embedding endpoint are used —
  ingest takes pre-extracted text plus a caller-supplied embedding
  function, so the isolated test exercises only synthetic fixture text
  with a deterministic local embedding, per the working authorization.

## Test stack

- `qdrant-client==1.10.0`, local in-memory mode (`QdrantClient(":memory:")`).
  No Docker container, no network socket, no production Qdrant instance,
  nothing persisted to disk. Collection name used only within that
  in-memory instance: `karmo_h02_lifecycle_test`.
- One acceptance suite, one test per requirement group (per the "no
  overlapping suites" working rule):
  `test/h02/tests/test_h02_lifecycle.py`
  - `test_sha256_identity_preserved`
  - `test_v1_lifecycle_fields_present`
  - `test_v1_to_v2_supersession_audit_and_retrieval`

## Result

```
3 passed, 1 warning in 0.01s
```

Full run: `docs/evidence/h02/h02-lifecycle-run.txt`
JUnit XML: `docs/evidence/h02/h02-lifecycle-junit.xml`

**Acceptance gate: PASS** — KARMO can supersede knowledge without deleting
history (v1 payload remains in the collection with `is_active=False`,
`superseded_by=<v2 hash>`, `deactivated_at` set), and normal retrieval
(`search_documents`) returns only the intended active version (v2).

## Verification commands

```
cd test/h02
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python -m pytest -v
```

## Not in scope / not performed

- No production access, SSH, Docker socket, production database, or
  production Qdrant instance was used.
- No legacy backfill or automatic deletion of historical vectors.
- No commit, push, merge, or deploy was performed.

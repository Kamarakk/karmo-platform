# Workstream 4 — Foundation v1 Adversarial Architecture Review

Repository-wide review for the categories of risk that motivated the
Engineering Invariants in the first place. Grounded entirely in code
actually read this session (file/line cited per finding) — nothing
speculative. Categories the review checked but found **no credible
issue** in are listed at the end, not silently omitted.

## Findings

### F1 — [MEDIUM] Live production pagination ceiling in `document_memory.get_document_history`

- **File**: `docs/handoff/h04/document_memory.py:61` (the current production
  reference — `h04/app/registry_db.py`'s own docstring cites this exact
  file as documenting "the production shape"), and its identical isolated
  copy `h02/app/document_memory.py:61`.
- **Finding**: `get_document_history(document_id, limit=10000)` calls
  `client.scroll(..., limit=limit)` once, with the returned offset
  discarded — no pagination loop. This is the **exact same bug class**
  already found and fixed in `document_ingest_h04.py`'s
  `active_points_for_document` (per `docs/evidence/h04/H04_INVARIANT_IMPACT_REVIEW.md`,
  I-01/I-05), but that fix was never applied here — H0.4 replaced
  `document_ingest.py` with `document_ingest_h04.py`; it never touched
  `document_memory.py` at all.
- **Impact today**: none observed — `karmo_documents` holds 8 points
  (confirmed 2026-09-09). Per I-01's own requirement to consider "behavior
  at 10x, 100x, and 1000x current scale": a logical document with more
  than 10,000 total chunk-versions across its full history would silently
  return an incomplete audit trail from this function.
- **Fix shape** (not implemented tonight — see rationale below): the same
  `_scroll_all`-style loop-until-`next_page_offset`-is-`None` pattern
  already used in `reconciliation.py` and `document_ingest_h04.py`.
- **Classification**: FIX BEFORE RELEVANT CAPABILITY. **Invariant
  coverage**: already fully covered by I-01 ("if the logical operation
  means ALL, paginate until exhausted") and I-05 ("missing pagination...
  unbounded queries") — this is a **compliance gap**, not a governance
  gap. No new invariant proposed for this finding.

### F2 — [LOW / INFORMATIONAL] Superseded code carries the same bug (dead, not live)

- **File**: `h02/app/document_ingest.py:107`,
  `active_points_for_document(document_id)`, `limit=10000`, same
  no-pagination shape.
- **Finding**: identical bug class to F1, in the file H0.4 already
  superseded in production (`document_ingest_h04.py` replaced it and *did*
  get the fix). Not currently live. Risk is narrow: if this file is ever
  copied again as a template for a future phase, the same bug would be
  reintroduced (as it very nearly was — H0.4 initially inherited it too).
- **Classification**: ACCEPT/DEFER. **Invariant coverage**: I-01/I-05,
  same as F1.

### F3 — [MEDIUM] No connection pooling anywhere in the codebase

- **Evidence**: repo-wide grep for `pool`/`Pool` across every `*.py` file
  returns zero matches. Every database access — `h04/app/registry_db.py`'s
  `get_connection()`, the H0.1 relay's `memory.get_connection()`
  (`docs/handoff/h04/memory.py`), every H0.2/H0.4 ingest/audit call — opens
  a fresh `psycopg.connect()` and closes it per call, confirmed by direct
  reading of `docs/handoff/h04/memory.py` (the cited production reference).
- **Impact today**: none observed at current scale (single relay polling
  ~1x/second, single-digit-to-low-double-digit row counts).
- **Why it matters going forward**: per I-05's "behavior at 10x/100x/1000x
  scale" and the Tool/Capability Registry design this same program
  produces (Workstream 3) anticipating multiple concurrent domain workers
  — connection churn overhead and eventual `max_connections` exhaustion
  become real risks once more than one polling/worker process exists
  concurrently.
- **Classification**: FIX BEFORE RELEVANT CAPABILITY — a natural shared
  Core-layer requirement (see Workstream 3/5). **Invariant coverage**:
  I-05 covers resource bounding in spirit but does not name connection
  lifecycle specifically; not proposing a new invariant — this is better
  addressed as a Core-layer design decision than a new permanent rule.

### F4 — [MEDIUM] No embedding-model provenance on `karmo_semantic_memory`

- **File**: `docs/handoff/h03/semantic_memory.py` (H0.1's embedding
  module — `EMBED_MODEL = "embeddinggemma"`, `VECTOR_SIZE = 768`,
  hardcoded), `remember_semantic`'s point payload (`text`, `role` only).
- **Finding**: unlike `karmo_documents` (H0.2/H0.4 track
  `pipeline_version`/`embedding_model`/`chunker_version` per point,
  reconciled by the H0.4 auditor), `karmo_semantic_memory` points carry no
  model/version provenance at all. If the embedding model or its
  dimensionality is ever changed, there is no recorded way to distinguish
  which vectors came from which model, and no I-06 OLD/MIXED/NEW mechanism
  exists for this collection the way `document_registry` provides one for
  documents.
- **Classification**: FIX BEFORE RELEVANT CAPABILITY — specifically,
  *before* any embedding-model upgrade is attempted; low urgency
  otherwise. **Invariant coverage**: fully covered in principle by I-06
  (already requires exactly this kind of OLD/MIXED/NEW consideration for
  "identity, lifecycle, or storage change") — this is pre-I-06 legacy
  debt in already-shipped H0.1 code, not a governance gap.

### F5 — [LOW–MEDIUM] Configuration drift — Qdrant/Postgres endpoints duplicated as independent constants

- **Evidence**: `QDRANT_URL = "http://127.0.0.1:6333"` (or the equivalent
  Postgres host/port default) is independently redefined as a
  module-level constant in at least 10 files across H0.1–H0.4
  (`document_ingest_h04.py`, `bootstrap_legacy_registry.py`,
  `run_auditor.py`, `registry_repair.py`, `h02/app/document_ingest.py`,
  `h02/app/document_memory.py`, `h03/app/hybrid_ingest.py`,
  `h03/app/hybrid_memory.py`, `semantic_memory.py`,
  `outbox.py`'s `DEFAULT_QDRANT_URL`), confirmed by direct grep, not
  imported from one shared location.
- **Impact**: a future endpoint, port, or topology change (e.g. splitting
  services across hosts) requires finding and editing every one of these
  independently, with real risk of missing one and creating silent
  inconsistency between modules.
- **Classification**: FIX BEFORE RELEVANT CAPABILITY — natural
  consolidation point for the Tool/Capability Registry's shared Core
  layer (Workstream 3). **Invariant coverage: none of I-01 through I-09
  explicitly addresses configuration single-sourcing.** See "Proposed
  invariant candidate" below.

### F6 — [LOW] Single point of failure: no retry/circuit-breaker for the embedding call outside the H0.1 outbox path

- **File**: `docs/handoff/h03/semantic_memory.py`'s `get_embedding` — a
  single `requests.post` to Ollama, `timeout=120`, no retry.
- **Finding**: the H0.1 relay (`outbox.py`'s `_embedding`) wraps this call
  and converts any failure into a `TransientDeliveryError`, so *that* path
  degrades gracefully (retry with backoff). Every other caller —
  `document_memory.search_documents`, `document_ingest`'s per-chunk
  embedding — has no equivalent wrapper; an Ollama outage during a live
  document search or ingest fails that call outright with no retry.
- **Classification**: ACCEPT/DEFER for the current single-user, low-query
  volume deployment; revisit if a customer-facing or higher-availability
  use case (e.g. BloomBoss) is ever built on top of search. **Invariant
  coverage**: I-05 covers general resource/dependency bounding in spirit;
  not proposing a new invariant for this alone — folds into the same
  Core-layer resilience consideration as F3.

### F7 — [INFORMATIONAL] Single-host, single-container infrastructure, no redundancy

- `karmo-postgres`, `karmo-qdrant`, `karmo-ollama` all run as one Docker
  Compose stack on one host (`karmo-ai01`), confirmed via tonight's
  production read-only check. Expected and reasonable for a personal /
  small-business single-node deployment — not a defect. Worth naming
  because it is a real constraint future availability-sensitive capability
  decisions (e.g. customer-facing BloomBoss operations) should weigh
  explicitly rather than assume around.

### F8 — [LOW / INFORMATIONAL] Retry delay is bounded, retry *count* is not, for unanticipated exceptions

- **File**: `test/h01/app/outbox.py`'s `OutboxRelay.process_once` — the
  broad `except Exception` branch (for anything that isn't a recognized
  `PermanentDeliveryError`) computes a capped delay
  (`retry_delay_seconds`, capped at 3600s) but never counts attempts
  toward a maximum before dead-lettering.
- **Finding**: an anticipated *environmental* failure (Qdrant down,
  embedding timeout) is exactly what this design intends to retry
  indefinitely with backoff — correct. An *unanticipated* one (a genuine
  code defect not recognized as `PermanentDeliveryError`) would also
  retry forever, hourly, rather than eventually escalating to `dead`. Not
  a silent failure — `last_error_code`/`last_error` remain visible in the
  outbox row every attempt (I-07 satisfied) — but a persistent bug could
  linger unresolved indefinitely rather than surfacing as a clear
  terminal failure.
- **Classification**: ACCEPT/DEFER — a max-attempt-count-then-dead-letter
  safety net is a reasonable future refinement, not urgent. **Invariant
  coverage**: I-05 already lists "unbounded retries" as an explicit review
  category — this is a partial-compliance nuance (delay bounded, count is
  not) worth a future pass, not a new invariant.

## Categories checked with no credible finding

- **Race conditions / concurrency hazards**: the H0.1 relay's
  `FOR UPDATE SKIP LOCKED` claim + claim-token fencing on every state
  transition (`_finish`'s `WHERE ... AND claim_token = %s AND status =
  'processing'`) is a genuinely solid, already-tested design (H01-T08/T09/
  T11/T12 in the frozen failure matrix exist specifically to prove this).
  No new hazard found.
- **Time-of-check/time-of-use**: not found — every mutating operation this
  review inspected re-checks state at the point of the write (claim
  tokens, `get_by_hash` re-checks in both bootstrap and repair tools), not
  at an earlier read.
- **Silent failure paths / swallowed exceptions**: repo-wide grep for
  `except ...: pass` returns zero matches.
- **Secret persistence risk**: repo-wide review found no committed secret
  value; every module loads credentials from environment variables with a
  hard failure if unset (`registry_db.py`: `raise RuntimeError("KARMO_DB_PASSWORD
  is not set")`).
- **Backup/restore assumptions**: H0.4's `recovery.py` has an actual
  tested backup → corruption → restore → re-verify drill
  (`test_backup_snapshot_corruption_restore_integrity_workflow`), not an
  assumption.
- **Irreversible operations**: every audit/repair tool reviewed
  (`auditor.py`, `run_auditor.py`, `bootstrap_legacy_registry.py`,
  `registry_repair.py`) is report-only by default and additive-only when
  writing — no delete/overwrite path exists in any of them.
- **Implicit authority escalation**: not found — every write path requires
  an explicit flag (`--apply`) or an explicit human trigger; nothing
  self-escalates.

## Proposed invariant candidate — NOT adopted, Kamara's decision

Only one recurring defect class (F5) was not already covered by an
existing invariant:

> **Candidate: Configuration Single-Sourcing.** Infrastructure connection
> parameters (host, port, URL, collection/database name) for a given
> deployable unit should be defined in exactly one place and imported,
> never independently redeclared as module-level constants across
> multiple files. Before adding a new module that talks to an existing
> service, check whether its connection parameters already exist
> elsewhere in the same deployable unit and reuse that definition.

This is **proposed only** — governance is not modified by this session.
If adopted, it would most naturally sit alongside I-05 (resources/scale)
or as a lightweight addition near I-02 (production parity). Whether to
adopt it, and in what exact form, is Kamara's decision.

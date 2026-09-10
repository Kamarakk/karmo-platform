# KARMO Configuration Single-Sourcing Design

Status: **DESIGN**, with a non-production proof-of-concept module (see
`core-v2-prototypes/config_poc/`). Investigates and resolves the
configuration-drift finding from the prior program's adversarial review
(`docs/evidence/post-foundation-readiness/WORKSTREAM4_ADVERSARIAL_ARCHITECTURE_REVIEW.md`,
finding F5). Produced under the Core v2 Engineering Blueprint Program,
Workstream 2. Governance not modified; no repository-wide refactor
performed; the proof-of-concept changes no existing runtime behavior.

## Full inventory (this session's own grep, not the prior night's partial one)

| Value | Duplicated in | Category |
|---|---|---|
| Qdrant URL (`http://127.0.0.1:6333`) | ≥10 files (`document_ingest_h04.py`, `bootstrap_legacy_registry.py`, `run_auditor.py`, `registry_repair.py`, `h02/app/document_ingest.py`, `h02/app/document_memory.py`, `h03/app/hybrid_ingest.py`, `h03/app/hybrid_memory.py`, `semantic_memory.py`, `outbox.py`'s `DEFAULT_QDRANT_URL`) | **ENVIRONMENT CONFIGURATION** |
| Postgres host/port (`127.0.0.1`/`5433`) | `registry_db.py`, `docs/handoff/h04/memory.py` | **ENVIRONMENT CONFIGURATION** |
| Postgres db/user (`"karmo"`/`"karmo"`) | same two files | **ENVIRONMENT CONFIGURATION** (changes less often than host/port, but belongs in the same resolved object, not hardcoded separately) |
| `POSTGRES_PASSWORD`/`KARMO_DB_PASSWORD` | every DB-touching module | **SECRET REFERENCE** — already done correctly everywhere: an env var *name* is referenced, the value is never hardcoded. The one category with zero drift today. |
| Collection names (`karmo_documents`, `karmo_semantic_memory`, plus per-phase test variants `karmo_h03_hybrid_test`, `karmo_h04_test_documents`) | 16 files | **DOMAIN CONFIGURATION** — identifies *what* logical store, not *where*; test suites legitimately need an override mechanism (already done ad hoc per-suite; should be one mechanism, not sixteen independent constants) |
| `EMBED_MODEL = "embeddinggemma"`, `VECTOR_SIZE = 768` | `semantic_memory.py`, `outbox.py`'s `DEFAULT_VECTOR_SIZE` | **DOMAIN CONFIGURATION** — an I-06-sensitive value (Workstream 4's F4 finding: changing this needs a migration story, not a find-and-replace) |
| `PIPELINE_VERSION = "h02-document-ingest-v1"` | `document_ingest.py`, `document_ingest_h04.py`, `docs/handoff/*` | **STATIC CODE CONSTANT** — correctly hardcoded per its own design intent (identifies *this exact code path*, "derived from what is actually imported/running... rather than a hardcoded guess" per the module's own docstring); duplication here is *expected* per-module, not drift to fix |
| Ollama timeout (`timeout=120`) | `semantic_memory.py` | **STATIC CODE CONSTANT** today; candidate for **ENVIRONMENT CONFIGURATION** if an operator ever needs to tune it without a code change |
| Absolute host paths (`/home/lofason/karmo-ai/core/documents/{inbox,processed,failed}`) | `document_ingest_h04.py` and five other files | **ENVIRONMENT CONFIGURATION** — the single highest-risk category: entirely tied to one host's specific user/directory layout, would break outright on any host change |
| Docling version (`_DOCLING_VERSION = getattr(_docling, "__version__", "unknown")`) | `document_ingest.py`/`document_ingest_h04.py` | **RUNTIME DISCOVERY** — already done correctly; the one existing example of the right pattern, cited as the model for the rest |

## The five categories, defined precisely

- **STATIC CODE CONSTANT**: identifies the code itself (a version string,
  a fixed algorithm parameter). Correct to hardcode; duplication across
  modules that are each their *own* versioned artifact (H0.2's ingest vs.
  H0.4's) is expected, not drift.
- **ENVIRONMENT CONFIGURATION**: differs by deployment (isolated test vs.
  production; this host vs. a future one). Must be single-sourced with an
  env-var override and a documented default — never redeclared
  per-module.
- **SECRET REFERENCE**: a name/location pointing at a credential, never
  the value itself. Already the one category KARMO does correctly
  everywhere.
- **RUNTIME DISCOVERY**: should be read from the running system, not
  assumed — a value that *could* silently drift from reality if
  hardcoded (a dependency's actual version, a collection's actual vector
  dimensionality).
- **DOMAIN CONFIGURATION**: identifies *what* logical resource within a
  shared deployment (a collection name, an embedding model choice) —
  differs by domain/purpose, not by deployment environment; needs its own
  single source, distinct from environment configuration, because a test
  suite legitimately wants a *different domain configuration* (an
  isolated collection name) while still pointing at the *same
  environment configuration* shape (localhost, a mapped port).

## Single-source architecture (proposed)

One `karmo_core.config` module (not built into the existing app yet —
this program's own POC lives in isolation) exposing typed accessors, not
raw constants callers redeclare:

```python
from karmo_core import config

config.qdrant_url()       # env KARMO_QDRANT_URL, default http://127.0.0.1:6333
config.postgres_dsn()     # env KARMO_PG_HOST/PORT/DB/USER + KARMO_DB_PASSWORD (secret reference)
config.collection_name("documents")       # domain config, env-overridable per key
config.collection_name("semantic_memory")
config.embedding_model()  # domain config: model name + vector size together, never separately
```

Every existing module's own constant becomes a **call** to this module
instead of an independent literal — a future, separately-scoped
repository-wide refactor (explicitly not performed tonight). The proof of
value is that **the same value is now provably one object**, not "the
same value happens to appear in two places today and might not tomorrow"
— see the POC's own test (`test_single_sourcing_proof.py`), which imports
the same accessor from two different call sites and asserts identity, not
mere equality.

## Why this doesn't touch runtime behavior tonight

The POC module is entirely new, additive code under
`core-v2-prototypes/config_poc/` — no existing file imports it, no
existing constant is removed or repointed. It proves the design works
(reads env vars correctly, falls back to documented defaults correctly,
never touches a secret value) without changing what any currently-running
KARMO process actually does.

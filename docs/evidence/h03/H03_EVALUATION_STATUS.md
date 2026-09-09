# H0.3 Evaluation Status — NO-PROMOTION

**Decision: explicitly APPROVED AS NO-PROMOTION.** H0.3 hybrid retrieval
(dense + BM25 sparse + Reciprocal Rank Fusion) is retained as **evaluated,
historical evidence only**. It was never installed to production and is
**not** part of the active KARMO production retrieval architecture. Normal
production retrieval remains the H0.2/H0.4 dense-only path
(`docs/handoff/h04/document_ingest.py`, `document_memory.py`).

Nothing in this status note authorizes reopening, promoting, or continuing
H0.3 work. Any future decision to revisit hybrid retrieval is a new,
separately scoped and separately approved workload.

## What this evidence set is

A synthetic-corpus benchmark (`h03_hybrid_vs_dense_benchmark.md`/`.json`)
comparing dense-only retrieval against dense+BM25+RRF hybrid retrieval,
implemented in `h03/app/{hybrid_ingest.py, hybrid_memory.py, sparse_bm25.py}`
and exercised by `h03/tests/test_h03_hybrid_vs_dense_benchmark.py`. Per the
benchmark document's own header, this is **non-authoritative**: the corpus
is synthetic (10 documents), the "dense" embedding is a deterministic
bag-of-words stand-in (no live embedding endpoint was reachable in the
isolated environment), and latency figures reflect in-process, in-memory
`qdrant-client` local-mode timing, not networked production Qdrant latency.

## Files that belong in this historical evidence set

- `docs/evidence/h03/h03_hybrid_vs_dense_benchmark.md`
- `docs/evidence/h03/h03_hybrid_vs_dense_benchmark.json`
- `docs/evidence/h03/H03_EVALUATION_STATUS.md` (this file)
- `h03/app/hybrid_ingest.py`
- `h03/app/hybrid_memory.py`
- `h03/app/sparse_bm25.py`
- `h03/requirements.txt`
- `h03/tests/conftest.py`
- `h03/tests/corpus.py`
- `h03/tests/test_h03_hybrid_vs_dense_benchmark.py`

`h03/.pytest_cache/` and `h03/venv/` are local build artifacts, already
excluded by the repository's `venv/` gitignore pattern, and do not belong in
committed history.

## Repository-hygiene note (2026-09-08 reconciliation)

As of this reconciliation, every file listed above exists only in the local
working tree — none is committed to `main` or to `feat/h03-hybrid-retrieval`
(that branch's tip is identical to `main`; it carries no H0.3 commits of its
own). This status note documents what the eventual commit should contain and
makes the NO-PROMOTION decision explicit at the evidence location itself.
Committing this set is recommended as a small, scoped, documentation/evidence
-only follow-up (see `docs/project-state/NEXT_STEPS.md`); it has not been
committed in this session, per instruction not to commit, push, or merge.

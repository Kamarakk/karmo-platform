"""H0.3 acceptance benchmark: dense-only baseline vs. hybrid (dense + BM25
sparse + RRF) retrieval, on one shared synthetic corpus/query set.

This is the single concise benchmark/acceptance run for H0.3 (instruction:
"Use one concise benchmark/acceptance run. Do not create overlapping
repeated suites."). It ingests corpus.CORPUS into the isolated in-memory
H0.3 collection once, runs both retrieval methods over corpus.QUERIES, and
writes the resulting metrics to docs/evidence/h03/ for the human-readable
acceptance report -- this test file only asserts the safety invariants
(isolated collection, corpus loaded); it does not hard-assert that hybrid
beats dense, since whether the acceptance gate passes is a measurement to
report, not a requirement to force.
"""

import json
import statistics
import time
from pathlib import Path

from corpus import CORPUS, QUERIES
from sparse_bm25 import build_sparse_vector

K = 3
LATENCY_REPEATS = 20

EVIDENCE_DIR = Path(__file__).resolve().parent.parent.parent / "docs" / "evidence" / "h03"

PRODUCTION_COLLECTIONS = {"karmo_documents", "karmo_semantic_memory"}


def _percentile(values, pct):
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = min(len(ordered) - 1, int(round((pct / 100.0) * (len(ordered) - 1))))
    return ordered[index]


def _rank_of_expected(results, expected_source_file):
    for rank, result in enumerate(results, start=1):
        if result["source_file"] == expected_source_file:
            return rank
    return None


def _evaluate(search_fn, k):
    per_category_hits = {}
    per_category_total = {}
    reciprocal_ranks = []
    top1_correct = 0
    latencies_ms = []

    for item in QUERIES:
        category = item["category"]
        per_category_total[category] = per_category_total.get(category, 0) + 1

        results = None
        for repeat in range(LATENCY_REPEATS):
            start = time.perf_counter()
            results = search_fn(item["query"], limit=k)
            latencies_ms.append((time.perf_counter() - start) * 1000.0)

        rank = _rank_of_expected(results, item["expected_source_file"])

        if rank is not None:
            per_category_hits[category] = per_category_hits.get(category, 0) + 1
            reciprocal_ranks.append(1.0 / rank)
        else:
            reciprocal_ranks.append(0.0)

        if rank == 1:
            top1_correct += 1

    total_queries = len(QUERIES)
    recall_at_k = sum(per_category_hits.values()) / total_queries
    mrr = statistics.mean(reciprocal_ranks)
    correct_source_rate = top1_correct / total_queries

    per_category_recall = {
        category: per_category_hits.get(category, 0) / per_category_total[category]
        for category in per_category_total
    }

    return {
        "recall_at_k": recall_at_k,
        "mrr": mrr,
        "correct_source_rate": correct_source_rate,
        "per_category_recall_at_k": per_category_recall,
        "latency_ms_p50": _percentile(latencies_ms, 50),
        "latency_ms_p95": _percentile(latencies_ms, 95),
        "latency_samples": len(latencies_ms),
    }


def test_h03_hybrid_vs_dense_benchmark(hybrid_modules, tmp_path):
    hybrid_ingest, hybrid_memory = hybrid_modules

    # Safety invariant: the isolated H0.3 collection must never collide
    # with a production collection name.
    assert hybrid_ingest.COLLECTION_NAME not in PRODUCTION_COLLECTIONS

    ingest_start = time.perf_counter()
    total_chunks = 0
    chunk_texts = []
    for filename, text in CORPUS:
        path = tmp_path / filename
        path.write_text(text, encoding="utf-8")
        total_chunks += hybrid_ingest.ingest_document(path)
        chunk_texts.extend(part.strip() for part in text.split("\n\n") if part.strip())
    ingest_duration_s = time.perf_counter() - ingest_start

    assert total_chunks > 0

    sparse_nonzero_counts = [len(build_sparse_vector(text)[0]) for text in chunk_texts]
    avg_sparse_nonzero_per_chunk = statistics.mean(sparse_nonzero_counts)

    dense_metrics = _evaluate(hybrid_memory.search_dense_only, K)
    hybrid_metrics = _evaluate(hybrid_memory.search_hybrid_rrf, K)

    report = {
        "non_authoritative": True,
        "note": (
            "Synthetic H0.3 benchmark corpus; no frozen H0.0 known-answer "
            "corpus was found in this repository. Dense embedding is a "
            "deterministic bag-of-words stand-in (see tests/conftest.py) "
            "because no live Ollama/EmbeddingGemma endpoint is reachable "
            "in this isolated environment. Latency is in-process, "
            "in-memory qdrant-client local-mode latency, not networked "
            "production Qdrant latency."
        ),
        "corpus_documents": len(CORPUS),
        "chunks_ingested": total_chunks,
        "ingest_duration_seconds": ingest_duration_s,
        "avg_sparse_nonzero_indices_per_chunk": avg_sparse_nonzero_per_chunk,
        "dense_vector_dim": len(hybrid_memory.get_embedding("dimension probe")),
        "queries": len(QUERIES),
        "k": K,
        "latency_repeats_per_query": LATENCY_REPEATS,
        "dense_only": dense_metrics,
        "hybrid_rrf": hybrid_metrics,
    }

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    (EVIDENCE_DIR / "h03_hybrid_vs_dense_benchmark.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )

    lines = [
        "# H0.3 Hybrid vs. Dense Retrieval Benchmark (NON-AUTHORITATIVE, synthetic corpus)",
        "",
        report["note"],
        "",
        f"- Corpus documents: {report['corpus_documents']}",
        f"- Chunks ingested: {report['chunks_ingested']}",
        f"- Ingest wall time: {report['ingest_duration_seconds']:.4f}s",
        f"- Avg sparse non-zero indices per chunk: {report['avg_sparse_nonzero_indices_per_chunk']:.2f} (dense vector dim: {report['dense_vector_dim']})",
        f"- Queries: {report['queries']} (K={K}, {LATENCY_REPEATS} latency reps/query)",
        "",
        "| Metric | Dense-only | Hybrid RRF |",
        "|---|---|---|",
        f"| Recall@{K} | {dense_metrics['recall_at_k']:.3f} | {hybrid_metrics['recall_at_k']:.3f} |",
        f"| MRR | {dense_metrics['mrr']:.3f} | {hybrid_metrics['mrr']:.3f} |",
        f"| Correct-source rate (top-1) | {dense_metrics['correct_source_rate']:.3f} | {hybrid_metrics['correct_source_rate']:.3f} |",
        f"| Latency p50 (ms) | {dense_metrics['latency_ms_p50']:.4f} | {hybrid_metrics['latency_ms_p50']:.4f} |",
        f"| Latency p95 (ms) | {dense_metrics['latency_ms_p95']:.4f} | {hybrid_metrics['latency_ms_p95']:.4f} |",
        "",
        "## Per-category Recall@{}".format(K),
        "",
        "| Category | Dense-only | Hybrid RRF |",
        "|---|---|---|",
    ]

    for category in sorted(dense_metrics["per_category_recall_at_k"]):
        lines.append(
            "| {} | {:.3f} | {:.3f} |".format(
                category,
                dense_metrics["per_category_recall_at_k"][category],
                hybrid_metrics["per_category_recall_at_k"][category],
            )
        )

    (EVIDENCE_DIR / "h03_hybrid_vs_dense_benchmark.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )

    print(json.dumps(report, indent=2))

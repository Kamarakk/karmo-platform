# H0.3 Hybrid vs. Dense Retrieval Benchmark (NON-AUTHORITATIVE, synthetic corpus)

Synthetic H0.3 benchmark corpus; no frozen H0.0 known-answer corpus was found in this repository. Dense embedding is a deterministic bag-of-words stand-in (see tests/conftest.py) because no live Ollama/EmbeddingGemma endpoint is reachable in this isolated environment. Latency is in-process, in-memory qdrant-client local-mode latency, not networked production Qdrant latency.

- Corpus documents: 10
- Chunks ingested: 20
- Ingest wall time: 0.0053s
- Avg sparse non-zero indices per chunk: 15.30 (dense vector dim: 64)
- Queries: 20 (K=3, 20 latency reps/query)

| Metric | Dense-only | Hybrid RRF |
|---|---|---|
| Recall@3 | 0.800 | 1.000 |
| MRR | 0.517 | 0.908 |
| Correct-source rate (top-1) | 0.300 | 0.850 |
| Latency p50 (ms) | 0.0971 | 0.4417 |
| Latency p95 (ms) | 0.1442 | 0.5762 |

## Per-category Recall@3

| Category | Dense-only | Hybrid RRF |
|---|---|---|
| exact_identifier | 1.000 | 1.000 |
| filename | 0.750 | 1.000 |
| ip_address | 1.000 | 1.000 |
| semantic_paraphrase | 0.500 | 1.000 |
| technical_terminology | 0.750 | 1.000 |

"""Synthetic H0.3 benchmark corpus and query set.

NON-AUTHORITATIVE: no frozen H0.0 known-answer retrieval corpus was found
anywhere in this repository (searched for known-answer/H0.0/corpus/fixture
artifacts under docs/ and elsewhere). Per the H0.3 task instructions, this
is a minimal synthetic substitute constructed to cover the five required
query categories. It contains no real documents, customer data, secrets,
or production content -- every fact below is invented for this benchmark.

Each corpus document is written with blank-line-separated paragraphs so
tests/conftest.py's FakeDocumentConverter (which splits on "\n\n") produces
multiple chunks per document, exercising the same chunk-per-paragraph shape
as the real Docling HybridChunker would for a short document.

Each query records the expected_source_file it should retrieve, used to
compute Recall@K, MRR, and correct-source rate in
test_h03_hybrid_vs_dense_benchmark.py.
"""

CORPUS = [
    (
        "ticket_karmo_40231.txt",
        "Incident ticket KARMO-40231 was opened after the nightly ingestion "
        "job failed to upsert vectors into the karmo_documents collection.\n\n"
        "Engineering assigned KARMO-40231 to the platform team for a fix "
        "within 48 hours.",
    ),
    (
        "purchase_order_88231.txt",
        "Purchase order PO-88231-A authorizes procurement of two GPU "
        "servers for the KARMO staging cluster.\n\n"
        "PO-88231-A was approved by finance on 2026-08-14.",
    ),
    (
        "compliance_report_pointer.txt",
        "The quarterly compliance report is stored as "
        "quarterly_report_2025_Q3.pdf in the shared documents archive.\n\n"
        "Auditors requested a copy of quarterly_report_2025_Q3.pdf during "
        "the September review.",
    ),
    (
        "network_config_pointer.txt",
        "Network configuration changes for the edge routers are tracked in "
        "network_config_v3.yaml.\n\n"
        "Any change to network_config_v3.yaml requires sign-off from the "
        "infrastructure lead.",
    ),
    (
        "qdrant_node_ip.txt",
        "The primary Qdrant test node listens on 10.42.17.203 inside the "
        "isolated lab VLAN.\n\n"
        "Firewall rules restrict inbound traffic to 10.42.17.203 to the lab "
        "subnet only.",
    ),
    (
        "ollama_service_ip.txt",
        "The Ollama embedding service in the lab environment is bound to "
        "192.168.88.10 on port 11434.\n\n"
        "Do not expose 192.168.88.10 outside the lab network.",
    ),
    (
        "rrf_explainer.txt",
        "Reciprocal Rank Fusion combines ranked result lists by summing the "
        "reciprocal of each item's rank across lists.\n\n"
        "RRF is used in H0.3 to merge dense and sparse BM25 rankings into a "
        "single ordered result.",
    ),
    (
        "hybrid_chunker_explainer.txt",
        "The HybridChunker in Docling splits documents into passages sized "
        "for the embedding model's context window.\n\n"
        "HybridChunker preserves heading context when it contextualizes a "
        "chunk before embedding.",
    ),
    (
        "lifecycle_supersede.txt",
        "If a document is re-ingested with new content, the previous "
        "version's chunks are marked inactive and excluded from normal "
        "search results, while the new chunks become the active knowledge "
        "for that document.\n\n"
        "Superseded chunks remain stored for audit history but are never "
        "deleted.",
    ),
    (
        "promotion_criteria.txt",
        "The retrieval benchmark compares a dense-only baseline against a "
        "hybrid approach that fuses vector similarity with keyword-based "
        "scoring.\n\n"
        "Promotion of the hybrid path depends on whether it beats the "
        "baseline without slowing searches down too much.",
    ),
]

QUERIES = [
    # -- exact identifiers --
    {
        "category": "exact_identifier",
        "query": "What is the ticket number for the nightly ingestion job failure?",
        "expected_source_file": "ticket_karmo_40231.txt",
    },
    {
        "category": "exact_identifier",
        "query": "KARMO-40231",
        "expected_source_file": "ticket_karmo_40231.txt",
    },
    {
        "category": "exact_identifier",
        "query": "Which purchase order approved the GPU servers?",
        "expected_source_file": "purchase_order_88231.txt",
    },
    {
        "category": "exact_identifier",
        "query": "PO-88231-A",
        "expected_source_file": "purchase_order_88231.txt",
    },
    # -- filenames --
    {
        "category": "filename",
        "query": "What file contains the Q3 compliance report?",
        "expected_source_file": "compliance_report_pointer.txt",
    },
    {
        "category": "filename",
        "query": "quarterly_report_2025_Q3.pdf",
        "expected_source_file": "compliance_report_pointer.txt",
    },
    {
        "category": "filename",
        "query": "Which config file tracks edge router changes?",
        "expected_source_file": "network_config_pointer.txt",
    },
    {
        "category": "filename",
        "query": "network_config_v3.yaml",
        "expected_source_file": "network_config_pointer.txt",
    },
    # -- IP addresses --
    {
        "category": "ip_address",
        "query": "What IP address does the Qdrant test node use?",
        "expected_source_file": "qdrant_node_ip.txt",
    },
    {
        "category": "ip_address",
        "query": "10.42.17.203",
        "expected_source_file": "qdrant_node_ip.txt",
    },
    {
        "category": "ip_address",
        "query": "What address is the Ollama embedding service bound to?",
        "expected_source_file": "ollama_service_ip.txt",
    },
    {
        "category": "ip_address",
        "query": "192.168.88.10",
        "expected_source_file": "ollama_service_ip.txt",
    },
    # -- technical terminology --
    {
        "category": "technical_terminology",
        "query": "How does Reciprocal Rank Fusion combine multiple ranked lists?",
        "expected_source_file": "rrf_explainer.txt",
    },
    {
        "category": "technical_terminology",
        "query": "Reciprocal Rank Fusion",
        "expected_source_file": "rrf_explainer.txt",
    },
    {
        "category": "technical_terminology",
        "query": "What does the Docling HybridChunker do when splitting documents?",
        "expected_source_file": "hybrid_chunker_explainer.txt",
    },
    {
        "category": "technical_terminology",
        "query": "HybridChunker",
        "expected_source_file": "hybrid_chunker_explainer.txt",
    },
    # -- semantic / paraphrased questions --
    {
        "category": "semantic_paraphrase",
        "query": "When an old file is replaced by an updated version, what "
        "happens to the previous chunks during search?",
        "expected_source_file": "lifecycle_supersede.txt",
    },
    {
        "category": "semantic_paraphrase",
        "query": "Are outdated document versions permanently deleted from the system?",
        "expected_source_file": "lifecycle_supersede.txt",
    },
    {
        "category": "semantic_paraphrase",
        "query": "Under what condition should the new retrieval method replace the existing one?",
        "expected_source_file": "promotion_criteria.txt",
    },
    {
        "category": "semantic_paraphrase",
        "query": "Does combining keyword search with vector search need to avoid making queries much slower?",
        "expected_source_file": "promotion_criteria.txt",
    },
]

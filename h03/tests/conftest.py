"""Fixtures for testing the H0.3 hybrid retrieval modules
(h03/app/hybrid_ingest.py, h03/app/hybrid_memory.py) without any network
access, real Qdrant server, real Ollama/EmbeddingGemma endpoint, or real
documents -- none of those are reachable or permitted in this isolated
environment.

Two things are faked here, installed into sys.modules *before* the
deployable modules are imported, so those modules' own unmodified
``from docling... import ...`` / ``from semantic_memory import
get_embedding`` lines resolve to test doubles:

1. docling.document_converter.DocumentConverter / docling.chunking.
   HybridChunker -- same fakes h02/conftest.py uses: splits a fixture
   file's text into chunks on blank lines.

2. semantic_memory.get_embedding -- NOT a whole-text hash like h02's fake.
   A whole-text hash would make every query's dense similarity to every
   document uniformly uncorrelated with content, which would make dense-
   only retrieval perform at chance on *every* query category (not just
   the paraphrase one) and render a dense-vs-hybrid comparison meaningless.
   Instead this is a deterministic bag-of-words average: each distinct
   token gets a fixed pseudo-random unit vector (seeded by its own sha256
   digest), and a text's embedding is the normalized average of its
   tokens' vectors. This behaves like a plain non-contextual semantic
   embedding -- texts sharing vocabulary end up with high cosine
   similarity -- which is a defensible, clearly-labeled stand-in for
   EmbeddingGemma for the purpose of this offline benchmark. It is not
   used anywhere outside these tests; the deployable modules' real
   ``from semantic_memory import get_embedding`` call site is untouched.

The deployable modules' own ``client = QdrantClient(url="http://127.0.0.1:
6333")`` is likewise left untouched in source; this conftest swaps each
module's ``client`` attribute, after import, to one shared in-memory Qdrant
instance (``QdrantClient(":memory:")``) so no test traffic ever reaches a
network address. The collection created there is exactly
hybrid_ingest.COLLECTION_NAME ("karmo_h03_hybrid_test") -- an isolated H0.3
collection, never karmo_documents or karmo_semantic_memory.
"""

import hashlib
import math
import sys
import types
from pathlib import Path

import pytest
from qdrant_client import QdrantClient

APP_DIR = Path(__file__).resolve().parent.parent / "app"
sys.path.insert(0, str(APP_DIR))

VECTOR_SIZE = 64


class FakeChunk:
    def __init__(self, text):
        self.text = text


class FakeDoclingDocument:
    def __init__(self, chunks):
        self.chunks = chunks


class FakeConversionResult:
    def __init__(self, document):
        self.document = document


class FakeDocumentConverter:
    """Test double for docling.document_converter.DocumentConverter.

    Splits the fixture file's text on blank lines into "chunks" -- stands
    in for real Docling conversion only inside the test process.
    """

    def convert(self, path):
        text = Path(path).read_text(encoding="utf-8")
        parts = [part.strip() for part in text.split("\n\n") if part.strip()]
        return FakeConversionResult(FakeDoclingDocument([FakeChunk(p) for p in parts]))


class FakeHybridChunker:
    def chunk(self, document):
        return document.chunks

    def contextualize(self, chunk):
        return chunk.text


def _install_fake_docling():
    docling_pkg = types.ModuleType("docling")
    docling_pkg.__version__ = "test-double"

    document_converter_module = types.ModuleType("docling.document_converter")
    document_converter_module.DocumentConverter = FakeDocumentConverter

    chunking_module = types.ModuleType("docling.chunking")
    chunking_module.HybridChunker = FakeHybridChunker

    sys.modules["docling"] = docling_pkg
    sys.modules["docling.document_converter"] = document_converter_module
    sys.modules["docling.chunking"] = chunking_module


def _token_vector(token, size=VECTOR_SIZE):
    digest = hashlib.sha256(token.encode("utf-8")).digest()
    return [(digest[i % len(digest)] / 255.0) * 2.0 - 1.0 for i in range(size)]


def _bag_of_words_embedding(text, size=VECTOR_SIZE):
    tokens = text.lower().split() or [""]
    vectors = [_token_vector(token, size) for token in tokens]
    summed = [sum(components) for components in zip(*vectors)]
    norm = math.sqrt(sum(component * component for component in summed)) or 1.0
    return [component / norm for component in summed]


def _install_fake_semantic_memory():
    semantic_memory_module = types.ModuleType("semantic_memory")
    semantic_memory_module.get_embedding = _bag_of_words_embedding
    sys.modules["semantic_memory"] = semantic_memory_module


_install_fake_docling()
_install_fake_semantic_memory()

import hybrid_ingest  # noqa: E402  (must follow the fake-module install above)
import hybrid_memory  # noqa: E402


@pytest.fixture()
def hybrid_modules():
    """hybrid_ingest/hybrid_memory wired to one shared in-memory Qdrant
    collection instead of the real network client declared in source
    (which is left unmodified)."""
    memory_client = QdrantClient(":memory:")
    hybrid_ingest.client = memory_client
    hybrid_memory.client = memory_client
    hybrid_ingest.initialize_hybrid_collection(vector_size=VECTOR_SIZE)
    return hybrid_ingest, hybrid_memory

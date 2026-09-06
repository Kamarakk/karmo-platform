"""Fixtures for validating the H0.2 production-faithful deployable modules
(h02/app/document_ingest.py, h02/app/document_memory.py) without real
production access.

The deployable modules import docling (document_converter, chunking) and
semantic_memory (get_embedding) exactly as production does -- those import
statements are NOT modified here or anywhere in h02/app. Since neither
package is installed or reachable in this isolated environment, this
conftest installs lightweight stand-ins into sys.modules *before* the
deployable modules are imported, so the modules' own
``from docling.document_converter import DocumentConverter`` etc. resolve
to test doubles instead of failing on import. This never edits the
deployable files themselves.

The modules' own ``client = QdrantClient(url="http://127.0.0.1:6333")`` is
left untouched in source; this conftest swaps each module's ``client``
attribute, after import, to a single shared local in-memory Qdrant instance
(``QdrantClient(":memory:")``) so no test traffic ever reaches a network
address, per the "synthetic in-memory Qdrant only inside tests" rule. The
collection name used is still exactly COLLECTION_NAME ("karmo_documents")
as declared in the deployable modules -- nothing renamed.
"""

import hashlib
import sys
import types
from pathlib import Path

import pytest
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

APP_DIR = Path(__file__).resolve().parent / "app"
sys.path.insert(0, str(APP_DIR))

VECTOR_SIZE = 32


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

    Splits the fixture file's text on blank lines into "chunks" -- this
    stands in for real Docling conversion only inside the test process;
    the deployable module's own DocumentConverter()/convert() call site is
    untouched.
    """

    def convert(self, path):
        text = Path(path).read_text(encoding="utf-8")
        parts = [part.strip() for part in text.split("\n\n") if part.strip()]
        return FakeConversionResult(FakeDoclingDocument([FakeChunk(p) for p in parts]))


class FakeHybridChunker:
    """Test double for docling.chunking.HybridChunker: passes the fixture's
    pre-split chunks through unchanged."""

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


def _deterministic_embedding(text, size=VECTOR_SIZE):
    """Deterministic fake embedding for isolated tests (no real model call)."""
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return [(digest[i % len(digest)] / 255.0) * 2.0 - 1.0 for i in range(size)]


def _install_fake_semantic_memory():
    semantic_memory_module = types.ModuleType("semantic_memory")
    semantic_memory_module.get_embedding = _deterministic_embedding
    sys.modules["semantic_memory"] = semantic_memory_module


_install_fake_docling()
_install_fake_semantic_memory()

import document_ingest  # noqa: E402  (must follow the fake-module install above)
import document_memory  # noqa: E402


@pytest.fixture()
def lifecycle_modules():
    """document_ingest/document_memory wired to one shared in-memory Qdrant
    collection instead of the real network client declared in the
    deployable source (which is left unmodified)."""
    memory_client = QdrantClient(":memory:")
    memory_client.create_collection(
        collection_name=document_ingest.COLLECTION_NAME,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
    )
    document_ingest.client = memory_client
    document_memory.client = memory_client
    return document_ingest, document_memory

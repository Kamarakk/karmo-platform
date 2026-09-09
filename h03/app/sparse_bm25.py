"""Deterministic BM25-style sparse vector encoding for H0.3 hybrid retrieval.

Qdrant computes the IDF component of BM25 server-side when a sparse vector
field is configured with ``Modifier.IDF`` (qdrant-client >= 1.10). This
module only needs to produce the raw term-frequency half of that: a stable
token -> index mapping plus per-document term counts. No external model or
vocabulary file is required, so ingestion and querying can both call
``build_sparse_vector`` and always land on the same indices for the same
token.

This is additive, experimental H0.3 code. It is not used by and does not
modify any H0.2/production module.
"""

import hashlib
import re
from collections import Counter

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")

# Large enough bucket space that hash collisions are negligible for a small
# benchmark corpus, small enough to keep sparse vectors cheap.
VOCAB_DIM = 2 ** 18


def tokenize(text):
    return TOKEN_PATTERN.findall(text.lower())


def token_index(token, dim=VOCAB_DIM):
    digest = hashlib.sha256(token.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % dim


def build_sparse_vector(text):
    """Return (indices, values) raw term-frequency sparse vector for text."""
    counts = Counter(tokenize(text))

    indices = []
    values = []

    for token, count in counts.items():
        indices.append(token_index(token))
        values.append(float(count))

    return indices, values

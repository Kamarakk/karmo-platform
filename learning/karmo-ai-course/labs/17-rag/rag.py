"""Module 17: retrieval-augmented generation (RAG) with citations.

1. index:  split docs/*.md into paragraphs, turn each into a vector, save index.json
2. ask:    turn the question into a vector, find the 3 closest paragraphs,
           answer ONLY from them, and cite them like [1]
If nothing is close enough, say "I don't know" instead of guessing.

KARMO does the same with Docling (parsing) and Qdrant (the vector store).
Usage:
  python3 rag.py index
  python3 rag.py ask "Do you refund shipping on a dead plant?"
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "common"))
from karmo_llm import LLMError, ask, embed  # noqa: E402

INDEX = HERE / "index.json"
MIN_SCORE = 0.45
TOP_K = 3


def cosine(a: list, b: list) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def build_index() -> int:
    chunks = []
    for doc in sorted((HERE / "docs").glob("*.md")):
        for para in doc.read_text(encoding="utf-8").split("\n\n"):
            para = para.strip()
            if para and not para.startswith("#"):
                chunks.append({"source": doc.name, "text": para})
    vectors = embed([c["text"] for c in chunks])
    for chunk, vector in zip(chunks, vectors):
        chunk["vector"] = vector
    INDEX.write_text(json.dumps(chunks), encoding="utf-8")
    return len(chunks)


def retrieve(question: str) -> list:
    chunks = json.loads(INDEX.read_text(encoding="utf-8"))
    qvec = embed([question])[0]
    for chunk in chunks:
        chunk["score"] = round(cosine(qvec, chunk["vector"]), 3)
    return sorted(chunks, key=lambda c: c["score"], reverse=True)[:TOP_K]


def answer(question: str) -> dict:
    hits = retrieve(question)
    if not hits or hits[0]["score"] < MIN_SCORE:
        return {"answer": "I don't know. Nothing in the documents covers that.", "sources": hits}
    context = "\n\n".join(f"[{i}] ({h['source']}) {h['text']}" for i, h in enumerate(hits, 1))
    text = ask(
        f"Sources:\n{context}\n\nQuestion: {question}",
        system=("Answer using ONLY the numbered sources. Cite every fact like [1]. "
                "If the sources do not answer the question, say you don't know."),
        temperature=0,
    )
    return {"answer": text, "sources": hits}


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in ("index", "ask"):
        print(__doc__)
        return 1
    try:
        if sys.argv[1] == "index":
            print(f"Indexed {build_index()} paragraphs into {INDEX.name}")
            return 0
        if not INDEX.exists():
            print("Run 'python3 rag.py index' first.", file=sys.stderr)
            return 1
        result = answer(" ".join(sys.argv[2:]) or input("Question: "))
    except LLMError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    print(result["answer"])
    print("\nRetrieved:")
    for i, hit in enumerate(result["sources"], 1):
        print(f"  [{i}] score {hit['score']}  {hit['source']}: {hit['text'][:70]}...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

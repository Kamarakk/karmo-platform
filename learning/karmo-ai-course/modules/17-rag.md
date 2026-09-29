# Module 17 · RAG with citations

**Time:** 40 minutes · **Beyond the course**

**The idea:** RAG lets a model answer from **your documents**. Split docs into paragraphs, turn each into a vector with an embedding model, find the closest ones to the question, and answer only from those, with `[n]` citations. If nothing is close enough, say "I don't know". KARMO does the same with Docling and Qdrant.

## Steps

**1. Look at the sample docs.**
```bash
ls ~/Desktop/KARMO-AI-Course/labs/17-rag/docs && head -5 ~/Desktop/KARMO-AI-Course/labs/17-rag/docs/doa-policy.md
```
You should see four files (shipping, DOA, Alocasia care, grow tent), each marked as a sample.

**2. Build the index.**
```bash
cd ~/Desktop/KARMO-AI-Course/labs/17-rag && python3 rag.py index
```
You should see `Indexed 14 paragraphs into index.json`.

**3. Ask a question the docs answer.**
```bash
cd ~/Desktop/KARMO-AI-Course/labs/17-rag && python3 rag.py ask "Do you refund shipping on a dead plant?"
```
You should see an answer with a citation like `[1]`, then `Retrieved:` with scores and `doa-policy.md` near the top.

**4. Ask a question the docs don't answer.**
```bash
cd ~/Desktop/KARMO-AI-Course/labs/17-rag && python3 rag.py ask "What is the capital of France?"
```
You should see `I don't know` because no paragraph scored above 0.45.

**5. Replace a sample with your real policy.** Open `docs/shipping-policy.md`, paste your real Palmstreet shipping policy, save, and rebuild:
```bash
open -e ~/Desktop/KARMO-AI-Course/labs/17-rag/docs/shipping-policy.md
```
```bash
cd ~/Desktop/KARMO-AI-Course/labs/17-rag && python3 rag.py index && python3 rag.py ask "When do you ship with heat packs?"
```
You should see an answer quoting your real policy with a citation.

**6. Tune the threshold.**
```bash
grep -nE "MIN_SCORE|TOP_K" ~/Desktop/KARMO-AI-Course/labs/17-rag/rag.py
```
You should see `MIN_SCORE = 0.45` and `TOP_K = 3`. Raising MIN_SCORE means more "I don't know" and fewer wrong answers.

## Done when
- [ ] One cited answer and one "I don't know"
- [ ] At least one real policy is in the index

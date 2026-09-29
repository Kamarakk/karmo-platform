# Module 05 · Local models on your hardware

**Time:** 30 minutes · **Course reference:** `code/02-ai-workflows/05-using-local-open-models/open.py`

**The idea:** Local model speed depends on size, quantization, and your RAM. Measure it; don't guess. The first run includes loading the model into memory, so the second run is the real speed.

## Steps

**1. List the models you have.**
```bash
ollama list
```
You should see at least `llama3.2:1b`, `llama3.2:3b`, and `nomic-embed-text`.

**2. Benchmark the two chat models.**
```bash
cd ~/Desktop/KARMO-AI-Course/labs/05-local-models && python3 bench.py llama3.2:1b llama3.2:3b
```
You should see a table with `total s`, `load s`, `tokens`, `tok/s` for 2 runs per model. The 1b model should show higher tok/s.

**3. Pull one mid-size model to compare (about 5 GB).**
```bash
ollama pull qwen3:8b
```
You should see `success`.

**4. Benchmark it against the 3b model.**
```bash
cd ~/Desktop/KARMO-AI-Course/labs/05-local-models && python3 bench.py llama3.2:3b qwen3:8b
```
You should see qwen3:8b noticeably slower in tok/s. AI01 has 8 cores and 11 GB, so this is why KARMO uses llama3.2:3b for fast data answers.

**5. See what's loaded and how much memory it uses.**
```bash
ollama ps
```
You should see the models in memory with their size and `100% CPU` or `100% GPU`.

**6. Free the memory.**
```bash
ollama stop qwen3:8b
```
You should see no output; `ollama ps` no longer lists it.

## Done when
- [ ] You have a speed table for three models on your Mac
- [ ] You can explain why run 1 is slower than run 2

**Durable:** measure tok/s and load time on your own hardware. **Perishable:** the model names.

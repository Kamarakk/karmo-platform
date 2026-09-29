# Module 04 · Multi-step, multi-model workflows

**Time:** 30 minutes · **Course reference:** `code/02-ai-workflows/04-multi-step-multi-model/main.py`

**The idea:** Chain steps, and give each step the cheapest model that can do it. A small model summarizes a web page; a larger model writes the post from that summary. The timing on each step shows where the time goes.

## Steps

**1. Read the course's version.**
```bash
cat ~/KARMO-DEV/ai-agents-workflows-course/code/02-ai-workflows/04-multi-step-multi-model/main.py
```
You should see two model calls, the first feeding the second.

**2. Run the pipeline on a care article.**
```bash
cd ~/Desktop/KARMO-AI-Course/labs/04-multi-step && python3 multi_step.py https://en.wikipedia.org/wiki/Alocasia
```
You should see timed lines like `[  0.4s] fetch + strip HTML (code)`, `[  6.1s] summarize (llama3.2:1b)`, `[ 14.8s] write post (llama3.2:3b)`, then `--- SUMMARY ---` and `--- POST ---`.

**3. Swap the small step onto the large model.**
```bash
cd ~/Desktop/KARMO-AI-Course/labs/04-multi-step && python3 multi_step.py https://en.wikipedia.org/wiki/Alocasia --small llama3.2:3b
```
You should see the summarize step take noticeably longer. Compare whether the post got better. Usually it doesn't, which is the point.

**4. Break it on purpose with a bad URL.**
```bash
cd ~/Desktop/KARMO-AI-Course/labs/04-multi-step && python3 multi_step.py https://example.invalid/page
```
You should see `Error fetching page: ...` and no model call. A workflow fails early and cheaply.

**5. Write down one KARMO pipeline you could split this way.** Example: voice note (Worker01 transcribes) to answer (AI01) to speech (Worker01).

## Done when
- [ ] You saw per-step timings for two model choices
- [ ] You wrote down one KARMO pipeline to split by model size

**Durable:** right-size each step. **Perishable:** which model is "small" this year.

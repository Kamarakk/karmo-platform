# Module 18 · Evals

**Time:** 35 minutes · **Beyond the course**

**The idea:** An eval is a fixed set of questions with checkable answers. Run it after **every** change (model, prompt, code) and compare scores. If the score drops, the change made KARMO worse. Plant numbers are checked against your data, never against the model.

**Needs:** the RAG index from Module 17, step 2.

## Steps

**1. Read the cases.**
```bash
cat ~/Desktop/KARMO-AI-Course/labs/18-evals/cases.json
```
You should see 6 cases: 3 plant-number questions, 2 policy questions, and 1 the docs can't answer.

**2. Run the evals on the default model.**
```bash
cd ~/Desktop/KARMO-AI-Course/labs/18-evals && python3 run_evals.py
```
You should see a `PASS` or `FAIL` line per case with its time, then `Score X/6 with llama3.2:3b. Report: reports/...json`.

**3. Run them on the small model.**
```bash
cd ~/Desktop/KARMO-AI-Course/labs/18-evals && KARMO_MODEL=llama3.2:1b python3 run_evals.py
```
You should see a lower or equal score, and faster times.

**4. Run them on qwen3:8b (if you pulled it in Module 05).**
```bash
cd ~/Desktop/KARMO-AI-Course/labs/18-evals && KARMO_MODEL=qwen3:8b python3 run_evals.py
```
You should see a third score. Now you have real numbers to pick a model with.

**5. Compare the reports.**
```bash
ls ~/Desktop/KARMO-AI-Course/labs/18-evals/reports/
```
You should see one JSON file per run, named by time and model.

**6. Add your own case.** Open `cases.json`, copy one plant case, change `id`, `question`, and `cultivar` to another cultivar of yours, save, and run step 2 again.
```bash
open -e ~/Desktop/KARMO-AI-Course/labs/18-evals/cases.json
```
You should see 7 cases in the output.

## Done when
- [ ] You have scores for at least two models
- [ ] You added one case of your own

**KARMO link:** before switching KARMO's fast-answer model, run evals on both and keep the report.

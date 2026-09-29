# Module 01 · Workflows vs agents

**Time:** 30 minutes · **Course reference:** `~/KARMO-DEV/ai-agents-workflows-course/code/basic-ai-workflow/`

**The idea:** In a **workflow**, your code decides every step and the model only produces a result inside one step. In an **agent**, the model decides what happens next. Test: does the model only write the output, or does it choose the next action?

## Steps

**1. Read the course's explainer (10 minutes).**
```bash
open ~/KARMO-DEV/ai-agents-workflows-course/code/basic-ai-workflow/what-are-workflows.md
```
You should see the article open in your default text app.

**2. Compare the course's OpenAI version with the Ollama version.**
```bash
diff ~/KARMO-DEV/ai-agents-workflows-course/code/basic-ai-workflow/main.py ~/Desktop/KARMO-AI-Course/labs/01-workflows-vs-agents/main_ollama.py
```
You should see the changes are only in how the model is called: the OpenAI client and API key check are gone, and `summarize()` now calls Ollama at `localhost:11434/api/chat`. Input checks and the output file stay the same.

**3. Run the workflow on the explainer.**
```bash
cd ~/Desktop/KARMO-AI-Course/labs/01-workflows-vs-agents && python3 main_ollama.py --file ~/KARMO-DEV/ai-agents-workflows-course/code/basic-ai-workflow/what-are-workflows.md
```
You should see `Summary written to .../out/summary.txt` (10 to 30 seconds the first time).

**4. Read the summary.**
```bash
cat ~/Desktop/KARMO-AI-Course/labs/01-workflows-vs-agents/out/summary.txt
```
You should see 3 to 5 bullet points.

**5. Try to hijack it with a poisoned file.**
```bash
cd ~/Desktop/KARMO-AI-Course/labs/01-workflows-vs-agents && cat inject.md && python3 main_ollama.py --file inject.md && cat out/summary.txt
```
You should see either a summary or a poem. Either way, the model could only put text in one file, because the code gives it no other path. That's why workflows are safer.

**6. See how KARMO made the same call.**
```bash
grep -nE "_BLOOMBOSS_QUESTION_WORDS|def _is_bloomboss_question|def _direct_bloomboss_answer" ~/KARMO-DEV/core-service/core_service/operator.py
```
You should see three line numbers. On Sep 27, qwen3 kept answering BloomBoss questions without calling the report tool (agent behavior). KARMO now runs the report in code first (workflow), and plant lookups skip the model entirely, in 0.04s instead of 60 to 100s.

**7. Classify five KARMO paths.** Write your answers down, then check the key below.

| KARMO path | Workflow or agent? |
| --- | --- |
| Plant lookup: "how are the Ninja Albos doing?" | ? |
| BloomBoss judgment: "should I restock Ninja Albo?" | ? |
| General chat with tools offered (list_tasks, ask_claude) | ? |
| Model router choosing AI01 or a worker | ? |
| Phone voice note: transcribe, answer, speak | ? |

<details><summary>Answer key</summary>

1. Workflow, with no model at all (code answers from data).
2. Workflow: code runs the report first, the model only writes the answer.
3. Agent: the model chooses whether and which tool to call.
4. Workflow: `model_router.py` picks by code rules and fails closed.
5. Workflow: fixed pipeline, the model only fills the answer step.
</details>

## Done when
- [ ] Step 3 wrote a summary
- [ ] You can say in one sentence what the injected line in step 5 could and couldn't do
- [ ] You classified all five paths

**Durable:** workflow vs agent, and "take the decision away from the model when the path is known." **Perishable:** which model misbehaved.

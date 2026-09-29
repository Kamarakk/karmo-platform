# Module 15 · Agent frameworks (LangGraph)

**Time:** 40 minutes · **Course reference:** `code/sdk-backed-agent/` and `code/framework/`

**The idea:** Frameworks give you the Module 11 loop pre-built as a graph: a model node, a tool node, and a rule for which runs next. LangGraph is the most used in 2026. You get state, retries, and tracing for free, at the cost of a dependency.

## Steps

**1. Create the course's Python environment (once, for Modules 15 and 16).**
```bash
python3 -m venv ~/Desktop/KARMO-AI-Course/.venv && ~/Desktop/KARMO-AI-Course/.venv/bin/pip install -r ~/Desktop/KARMO-AI-Course/requirements.txt
```
You should see `Successfully installed ... langgraph ... langchain-ollama ... mcp ...`.

**2. Read the graph.**
```bash
grep -nE "StateGraph|add_node|add_edge|tools_condition|ToolNode" ~/Desktop/KARMO-AI-Course/labs/15-frameworks/langgraph_agent.py
```
You should see a `model` node, a `tools` node, and `tools_condition` deciding whether to loop.

**3. Run it.**
```bash
cd ~/Desktop/KARMO-AI-Course/labs/15-frameworks && ~/Desktop/KARMO-AI-Course/.venv/bin/python langgraph_agent.py "How many Ninja Albo units do I have in total?"
```
You should see `[Human]` with your question, `[AI]` with a tool call, `[Tool]` with your data, then a final `[AI]` answer.

**4. Compare line counts with your hand-built agent.**
```bash
wc -l ~/Desktop/KARMO-AI-Course/labs/11-native-tools/tools_agent.py ~/Desktop/KARMO-AI-Course/labs/15-frameworks/langgraph_agent.py
```
You should see they're similar in size. The framework pays off when you add memory, branching, and checkpoints, not for one simple loop.

**5. Make the KARMO call.** Write one line: "KARMO should / should not adopt LangGraph because ___." Remember the rule: no new package without a Tier 3 review.

## Done when
- [ ] The LangGraph agent answered from your data
- [ ] You wrote the adopt / don't adopt line

**My recommendation:** keep KARMO's own loop for now; revisit LangGraph if you need long-running, resumable multi-step jobs.

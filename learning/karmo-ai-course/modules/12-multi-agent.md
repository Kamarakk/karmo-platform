# Module 12 · Multi-agent

**Time:** 30 minutes · **Course reference:** `code/03-ai-agents/05-multi-agent/main.py` and `code/04-third-party/research-crew-finished/`

**The idea:** Split jobs by role. A researcher agent has tools and gathers facts; a writer agent has **no tools** and only writes. Plain code decides the order. Fewer tools per agent means fewer ways to go wrong.

## Steps

**1. Read the orchestrator.**
```bash
cat ~/Desktop/KARMO-AI-Course/labs/12-multi-agent/multi_agent.py
```
You should see `researcher()` calling the Module 11 agent, `writer()` with no tools, and `main()` running them in order.

**2. Run it for one cultivar.**
```bash
cd ~/Desktop/KARMO-AI-Course/labs/12-multi-agent && python3 multi_agent.py "Pink Black Velvet"
```
You should see `== Researcher agent ==` with tool steps and facts, then `== Writer agent ==` with a short restock memo.

**3. Run it for another.**
```bash
cd ~/Desktop/KARMO-AI-Course/labs/12-multi-agent && python3 multi_agent.py "Ninja Albo"
```
You should see a different memo built only from that cultivar's facts.

**4. Check the writer didn't invent numbers.** Compare every number in the memo with the researcher's facts printed above it.
You should see no number in the memo that isn't in the facts. If you do, note it for Module 18.

**5. Map it to KARMO.** Write one line each: which KARMO part is the orchestrator (Commander), which are the specialists (Worker01 for voice, AI01 for answers).

## Done when
- [ ] You ran two memos
- [ ] You checked the writer against the facts

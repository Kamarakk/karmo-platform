# Module 21 · Staying current

**Time:** 20 minutes to set up, then 30 minutes a month · **Beyond the course**

**The idea:** The tools change every few months; the patterns in this course don't. Spend a small fixed time each month scanning for changes, and only adopt something that passes the gate below with your evals as proof.

## Steps

**1. Copy the radar template.**
```bash
mkdir -p ~/Desktop/KARMO-AI-Course/my-notes && cp ~/Desktop/KARMO-AI-Course/templates/monthly-radar.md ~/Desktop/KARMO-AI-Course/my-notes/radar-$(date +%Y-%m).md && open -e ~/Desktop/KARMO-AI-Course/my-notes/radar-$(date +%Y-%m).md
```
You should see this month's radar open in TextEdit.

**2. Check new local models.**
```bash
open https://ollama.com/search?o=newest
```
You should see the newest models. Note any under 8 GB that claim tool-calling support.

**3. Check the course repo for updates.**
```bash
cd ~/KARMO-DEV/ai-agents-workflows-course && git pull
```
You should see `Already up to date.` or new files to skim.

**4. Test one candidate with your evals.**
```bash
ollama pull <model-name> && cd ~/Desktop/KARMO-AI-Course/labs/18-evals && KARMO_MODEL=<model-name> python3 run_evals.py
```
You should see its score next to your current model's.

**5. Run it through the adoption gate** (in the radar template). Adopt only if every box is Yes.

**6. Put the monthly review on your calendar.** One 30-minute block, first Saturday of each month.

## Done when
- [ ] This month's radar is filled in
- [ ] The monthly block is on your calendar

**Durable to keep:** workflow vs agent, code-owned guardrails, human approval, schemas + validation, RAG with citations, evals before changes, routing by cost. Everything else is perishable.

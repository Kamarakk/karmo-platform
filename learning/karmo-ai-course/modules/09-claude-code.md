# Module 09 · Claude Code as a power user

**Time:** 45 minutes · **Course reference:** `code/claude-data-analysis/`

**The idea:** An agentic tool is only as good as its setup: a `CLAUDE.md` with rules, **skills** for repeatable jobs, and data it can read. The course project analyzes `sales.csv`; you'll then point the same setup at your BloomBoss invoice.

## Steps

**1. Read how the course project is set up.**
```bash
cd ~/KARMO-DEV/ai-agents-workflows-course/code/claude-data-analysis && cat INSTRUCTIONS.md CLAUDE.md && ls .claude/skills
```
You should see the instructions, the project rules, and three skills: `create-report`, `data-analytics`, `export-report-pdf`.

**2. Open one skill.**
```bash
cat ~/KARMO-DEV/ai-agents-workflows-course/code/claude-data-analysis/.claude/skills/data-analytics/SKILL.md
```
You should see a name, a description (when to use it), and the steps Claude follows.

**3. Run Claude Code on the course data.**
```bash
cd ~/KARMO-DEV/ai-agents-workflows-course/code/claude-data-analysis && claude
```
Then type: `Analyze sales.csv and create a report.` You should see Claude pick the skills and write a report into `reports/`. Type `/exit` when done.

**4. Make a BloomBoss copy.**
```bash
mkdir -p ~/Desktop/KARMO-AI-Course/labs/09-claude-code && cp -R ~/KARMO-DEV/ai-agents-workflows-course/code/claude-data-analysis/.claude ~/KARMO-DEV/ai-agents-workflows-course/code/claude-data-analysis/CLAUDE.md ~/Desktop/KARMO-AI-Course/labs/09-claude-code/ && cp ~/KARMO-DEV/docs/bloomboss/historical_data/emgarden_invoice_2026040040.csv ~/Desktop/KARMO-AI-Course/labs/09-claude-code/
```
You should see no output. `ls -a ~/Desktop/KARMO-AI-Course/labs/09-claude-code` shows `.claude`, `CLAUDE.md`, and the CSV.

**5. Edit the rules for your data.** Open `CLAUDE.md` in that folder and replace references to `sales.csv` with `emgarden_invoice_2026040040.csv`. Add one line: `Never invent numbers; every figure must come from the CSV.`
```bash
open -e ~/Desktop/KARMO-AI-Course/labs/09-claude-code/CLAUDE.md
```

**6. Run it on BloomBoss.**
```bash
cd ~/Desktop/KARMO-AI-Course/labs/09-claude-code && claude
```
Type: `Which cultivars have the highest landed cost, and which have sold? Create a report.` You should see a report with numbers you can check against the CSV.

**7. Spot-check one number.**
```bash
grep -i "pink black velvet" ~/Desktop/KARMO-AI-Course/labs/09-claude-code/emgarden_invoice_2026040040.csv
```
You should see the raw rows behind a number in the report.

## Done when
- [ ] Claude produced a BloomBoss report
- [ ] You verified one number by hand

**Durable:** rules file + skills + checkable data. **Perishable:** Claude Code's exact commands.

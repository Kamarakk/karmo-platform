# Module 20 · Productizing KARMO

**Time:** 45 minutes · **Beyond the course**

**The idea:** A lab becomes a product when it has a user, a success number, guardrails, an eval, and a rollback. This module is a worksheet. Pick one lab from this course and write its brief for KARMO.

## Steps

**1. Pick the lab.** Good candidates: RAG over your real policies (17), invoice extraction (06), the MCP server (16).

**2. Copy the brief template into a new file.**
```bash
mkdir -p ~/Desktop/KARMO-AI-Course/my-notes && cp ~/Desktop/KARMO-AI-Course/templates/product-brief.md ~/Desktop/KARMO-AI-Course/my-notes/brief-1.md && open -e ~/Desktop/KARMO-AI-Course/my-notes/brief-1.md
```
You should see the template open in TextEdit.

**3. Fill in every section.** Keep each answer to 1 to 3 lines.

**4. Check the governance boxes.** Every "No" in the Governance section is a blocker to fix before asking Claude to build it.

**5. Hand it off.** When it's ready, paste the brief into the KARMO project and ask for it to be built on a feature branch. Production deploy still needs your written go.

## Done when
- [ ] `my-notes/brief-1.md` is filled in
- [ ] Every governance box is Yes or has a fix written next to it

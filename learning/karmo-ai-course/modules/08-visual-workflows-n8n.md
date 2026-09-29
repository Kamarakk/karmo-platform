# Module 08 · Visual workflows with n8n (optional)

**Time:** 40 minutes · **Course reference:** `code/basic-visual-ai-workflow/`

**The idea:** n8n draws the same workflow as boxes and arrows. It's great for glue work (webhook in, summary out, Slack message) and bad for logic you need to test. Learn it enough to judge when it fits, then decide.

**Skip this module** if you don't have Node 22 installed and don't want it. Nothing later depends on it.

## Steps

**1. Check Node.**
```bash
node --version
```
You should see `v22.x` or `v24.x`. If not, install Node 22 LTS from https://nodejs.org and reopen Terminal.

**2. Install the course's n8n project.**
```bash
cd ~/KARMO-DEV/ai-agents-workflows-course/code/basic-visual-ai-workflow && npm ci
```
You should see `added ... packages`.

**3. Start n8n.**
```bash
cd ~/KARMO-DEV/ai-agents-workflows-course/code/basic-visual-ai-workflow && npm start
```
You should see a local URL printed (usually http://localhost:5678). Open it in your browser and create the local owner account when asked.

**4. Point the AI node at Ollama instead of OpenAI.** In n8n, open the **Text Summarizer** workflow, click the OpenAI model node, delete it, and add an **Ollama Chat Model** node. Set Base URL to `http://localhost:11434` and model to `llama3.2:3b`. Connect it where the old node was. Save.
You should see no red warning on the node.

**5. Run it on the sample.** Click **Test workflow** and upload `~/KARMO-DEV/ai-agents-workflows-course/code/basic-visual-ai-workflow/samples/short-article.txt`.
You should see a summary in the output panel.

**6. Stop n8n.** In the Terminal window, press `Ctrl+C`.

**7. Make the call for KARMO.** Copy this into your notes and fill it in:

```
n8n decision for KARMO
- Would I use n8n for: [ ] glue (webhooks, notifications)  [ ] core logic  [ ] nothing
- Where would it run: [ ] Mac only  [ ] a worker (needs approval)
- Test story: can I write a pytest for it?  yes / no
- Decision:
```

## Done when
- [ ] You ran the summarizer on Ollama, or you chose to skip n8n
- [ ] The decision note is filled in

**My recommendation:** keep KARMO's core in Python (testable, governed) and use n8n only for glue if at all.

# Module 10 · The agent loop from scratch

**Time:** 35 minutes · **Course reference:** `code/03-ai-agents/01-tool-use-from-scratch/main.py` and `code/primitive-agent/agent.py`

**The idea:** An agent is a loop. The model answers either with text (done) or with a tool request. Code runs the tool, feeds the result back, and loops, with a hard step limit. Here the model asks for tools by writing plain JSON, so you see the raw mechanics.

## Steps

**1. Read the course's version.**
```bash
cat ~/KARMO-DEV/ai-agents-workflows-course/code/03-ai-agents/01-tool-use-from-scratch/main.py
```
You should see a prompt that tells the model how to request a tool, and a loop that parses its reply.

**2. Find the loop in your version.**
```bash
grep -nE "MAX_STEPS|TOOL RESULT|json.loads|def run" ~/Desktop/KARMO-AI-Course/labs/10-agent-from-scratch/primitive_agent.py
```
You should see the step limit (5), where the reply is parsed, and where the result is sent back.

**3. Ask a question that needs a tool.**
```bash
cd ~/Desktop/KARMO-AI-Course/labs/10-agent-from-scratch && python3 primitive_agent.py "How many Pink Black Velvet units have sold?"
```
You should see `[step 1] model asked for get_plant_stock({'cultivar': 'Pink Black Velvet'})` and then an answer with `1`.

**4. Ask something that needs no tool.**
```bash
cd ~/Desktop/KARMO-AI-Course/labs/10-agent-from-scratch && python3 primitive_agent.py "What does variegated mean?"
```
You should see an answer with no `[step ...]` line. The model chose not to use a tool.

**5. Try the small model.**
```bash
cd ~/Desktop/KARMO-AI-Course/labs/10-agent-from-scratch && KARMO_MODEL=llama3.2:1b python3 primitive_agent.py "How many Pink Black Velvet units have sold?"
```
You should often see malformed JSON or a made-up number. That's why the next module uses native tool calling, and why KARMO keeps numbers out of the model's hands.

## Done when
- [ ] You saw one tool call and one no-tool answer
- [ ] You can name the two things that stop a runaway loop (step limit, fixed tool list)

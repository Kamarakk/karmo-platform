# Module 02 · Your first workflow

**Time:** 20 minutes · **Course reference:** `code/02-ai-workflows/01-first-workflow-openai-api/main.py`

**The idea:** Input, prompt, model, output. The course generates X posts; you'll generate Palmstreet listing posts. The prompt wraps the input in `<plant>` tags so the model can tell instructions from data.

## Steps

**1. Look at the course's version.**
```bash
cat ~/KARMO-DEV/ai-agents-workflows-course/code/02-ai-workflows/01-first-workflow-openai-api/main.py
```
You should see `generate_x_post()` sending a prompt to OpenAI with `requests.post`.

**2. Look at your version.**
```bash
cat ~/Desktop/KARMO-AI-Course/labs/02-first-workflow/listing_post.py
```
You should see the same shape: a `PROMPT` with a `<plant>` slot, one `ask()` call, then the post saved to `out/post.txt`.

**3. Generate a listing post.**
```bash
cd ~/Desktop/KARMO-AI-Course/labs/02-first-workflow && python3 listing_post.py "Alocasia Frydek Variegata, 4 inch pot, 3 leaves"
```
You should see a short post and `Saved to .../out/post.txt`.

**4. Run it again with the same input.**
```bash
cd ~/Desktop/KARMO-AI-Course/labs/02-first-workflow && python3 listing_post.py "Alocasia Frydek Variegata, 4 inch pot, 3 leaves"
```
You should see a different post. Models are random by default; the workflow's path stays the same.

**5. Run it on the smaller model.**
```bash
cd ~/Desktop/KARMO-AI-Course/labs/02-first-workflow && KARMO_MODEL=llama3.2:1b python3 listing_post.py "Alocasia Frydek Variegata, 4 inch pot, 3 leaves"
```
You should see a faster but usually weaker post. Same code, different model: that's the value of one adapter.

## Done when
- [ ] You generated posts with two different models
- [ ] You can point to the one line that talks to the model (`ask(...)`)

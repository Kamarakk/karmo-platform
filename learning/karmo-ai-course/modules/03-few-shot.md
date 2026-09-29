# Module 03 · Few-shot prompting

**Time:** 25 minutes · **Course reference:** `code/02-ai-workflows/03-few-shot-prompting/main.py`

**The idea:** Showing the model 2 to 5 examples of the output you want beats describing it. The examples teach tone and structure; the instructions forbid copying their facts.

## Steps

**1. Open the examples file.**
```bash
open -e ~/Desktop/KARMO-AI-Course/labs/03-few-shot/examples.json
```
You should see three sample listing posts in TextEdit.

**2. Generate a post without examples.**
```bash
cd ~/Desktop/KARMO-AI-Course/labs/03-few-shot && python3 few_shot_post.py --no-examples "Alocasia Pink Black Velvet, 6 inch pot"
```
You should see `--- WITHOUT examples ---` and a generic post.

**3. Generate the same post with examples.**
```bash
cd ~/Desktop/KARMO-AI-Course/labs/03-few-shot && python3 few_shot_post.py "Alocasia Pink Black Velvet, 6 inch pot"
```
You should see `--- WITH examples ---` and a post whose rhythm matches your samples.

**4. Replace the samples with three of your real Palmstreet posts.** Edit `examples.json` in TextEdit, keep the same `plant` and `post` fields, save, then run step 3 again.
You should see posts that sound more like you.

**5. Check for copying.** Read the output from step 4 against your examples.
You should see no facts (sizes, leaf counts) copied from the examples. If you do, that's a failure worth noting for Module 18.

## Done when
- [ ] You saw the difference with and without examples
- [ ] `examples.json` holds your own posts

# Module 07 · Control flow and human in the loop

**Time:** 35 minutes · **Course reference:** `code/02-ai-workflows/10-control-flow/main.py` and `11-human-in-the-loop/main.py`

**The idea:** A second model call grades the first one's draft and returns `{passes, feedback}`. Code loops up to 3 rounds. Then **you** accept, quit, or give feedback. Nothing is saved without your "accept".

## Steps

**1. Run the loop for a care card.**
```bash
cd ~/Desktop/KARMO-AI-Course/labs/07-control-flow && python3 review_loop.py "Alocasia Ninja Albo"
```
You should see `--- Round 1: passes=... ---` with a draft, maybe `Grader feedback:` and more rounds, then the prompt `Type 'accept', 'quit', or feedback to rewrite:`.

**2. Give feedback instead of accepting.** Type:
```
make it shorter and mention humidity above 60%
```
You should see `--- Rewritten ---` with a new draft and the same prompt again.

**3. Accept it.** Type:
```
accept
```
You should see a macOS notification and `Saved to .../out/care_card.txt`.

**4. Read the saved card.**
```bash
cat ~/Desktop/KARMO-AI-Course/labs/07-control-flow/out/care_card.txt
```
You should see the exact draft you accepted.

**5. Run it again and quit.**
```bash
cd ~/Desktop/KARMO-AI-Course/labs/07-control-flow && python3 review_loop.py "Alocasia Frydek"
```
Type `quit`. You should see `Stopped. Nothing saved.`

**6. Find the three control points in the code.**
```bash
grep -nE "MAX_ROUNDS|passes|accept|quit" ~/Desktop/KARMO-AI-Course/labs/07-control-flow/review_loop.py
```
You should see the round limit, the grader check, and the human gate.

## Done when
- [ ] You accepted one card and quit one
- [ ] You can name the three control points

**KARMO link:** this is the same approval pattern KARMO uses before anything reaches production: the model proposes, a human approves.

# Module 19 · Model routing

**Time:** 30 minutes · **Beyond the course**

**The idea:** Send each question to the cheapest thing that can answer it. Number lookups skip the model entirely (code answers from data, like KARMO's BloomBoss fast path). Short factual questions go to the small model. Judgment and planning go to the large one.

## Steps

**1. Read the rules.**
```bash
grep -nE "LOOKUP|JUDGMENT|def route" -A 1 ~/Desktop/KARMO-AI-Course/labs/19-routing/router.py
```
You should see two regex rules and the `route()` function.

**2. Run the built-in question set.**
```bash
cd ~/Desktop/KARMO-AI-Course/labs/19-routing && python3 router.py
```
You should see five questions. The Pink Black Velvet one shows `lookup` in about `0.0s`; the others show `small (llama3.2:1b)` or `large (llama3.2:3b)` with longer times.

**3. Try your own questions.**
```bash
cd ~/Desktop/KARMO-AI-Course/labs/19-routing && python3 router.py "What revenue did Ninja Albo make?"
```
You should see `lookup` and an instant answer.

**4. Find a question it routes wrong.**
```bash
cd ~/Desktop/KARMO-AI-Course/labs/19-routing && python3 router.py "Is Pink Black Velvet worth restocking?"
```
You should see it go to `large`. Decide if that's right, and if not, which rule you'd change.

**5. Compare with KARMO's router.**
```bash
grep -n "def " ~/KARMO-DEV/core-service/core_service/model_router.py | head -20
```
You should see KARMO's routing functions. Same idea: code decides the route and fails closed.

## Done when
- [ ] You saw an instant lookup and a large-model route
- [ ] You found one question to route differently and wrote the rule change

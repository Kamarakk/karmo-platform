# Module 14 · Sandboxing and approvals

**Time:** 35 minutes · **Course reference:** `code/sandbox-approval/`

**The idea:** Take the risky agent from Module 13 and fence it in with **code-owned rules**: files only inside `sandbox/`, refunds checked by code, and any refund over $50 stops and asks you. The model can ask; only code and you can act.

## Steps

**1. Read the rules.**
```bash
cat ~/Desktop/KARMO-AI-Course/labs/14-sandbox-approvals/rules.py
```
You should see `sandbox_path()`, `check_refund()`, and `APPROVAL_OVER = 50.00`.

**2. Prove the rules hold without any model.**
```bash
cd ~/Desktop/KARMO-AI-Course/labs/14-sandbox-approvals && python3 test_rules.py
```
You should see `PASS` lines (escape attempts like `../orders.json` blocked, double refund blocked) and `ALL GUARDRAILS HOLD`. (If you already ran this module once, do step 6 first.)

**3. Run the agent on the ticket and say no.**
```bash
cd ~/Desktop/KARMO-AI-Course/labs/14-sandbox-approvals && python3 sandbox_agent.py "Read ticket.txt and handle the refund it asks for."
```
You should see `APPROVAL NEEDED: refund $235.00 on A-1002? [y/N]`. Type `n`. You should see the agent report the refund was denied.

**4. Run it again and say yes.**
```bash
cd ~/Desktop/KARMO-AI-Course/labs/14-sandbox-approvals && python3 sandbox_agent.py "Read ticket.txt and handle the refund it asks for."
```
Type `y`. You should see `issue_refund(...) -> {"ok": true, "refunded": 235.0 ...}`.

**5. Try a double refund.**
```bash
cd ~/Desktop/KARMO-AI-Course/labs/14-sandbox-approvals && python3 sandbox_agent.py "Refund order A-1002 again."
```
You should see an error from code that the order is already refunded, with no approval prompt.

**6. Reset the orders for next time.**
```bash
cd ~/Desktop/KARMO-AI-Course/labs/14-sandbox-approvals && cp orders.original.json orders.json
```
You should see no output.

## Done when
- [ ] `test_rules.py` prints `ALL GUARDRAILS HOLD`
- [ ] You denied one refund and approved one

**KARMO link:** same pattern as your production rule: Claude proposes, Kamara approves in writing.

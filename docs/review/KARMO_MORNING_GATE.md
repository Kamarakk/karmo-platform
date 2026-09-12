# KARMO Morning Promotion Gate

The overnight staging run stops at review. Morning sequence:

1. Pin the exact candidate SHA.
2. Confirm all GitHub Actions for that SHA are green or document every failure.
3. Run the Claude review prompt and commit only reviewed fixes to this same staging branch.
4. Re-run CI at the new exact SHA.
5. Run the KARMO review prompt against authoritative project state and current production facts.
6. Resolve every `BLOCKER`, `HIGH`, invariant conflict, and `NEEDS_VERIFICATION` item.
7. Kamara decides whether the candidate may merge/promote.
8. Only after separate approval, complete the deployment template with exact WHAT/WHY/CHANGE/RISK/VERIFY/ROLLBACK and authorize production access for that task.

No overnight automation may skip or satisfy steps 3, 5, 7, or 8 on Kamara's behalf.

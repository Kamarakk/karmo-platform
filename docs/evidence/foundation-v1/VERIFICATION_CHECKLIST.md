# Foundation v1 — Independent Verification Checklist

For Natalie (or ChatGPT, via a repository-capable agent) to confirm
Claude's claims tomorrow. All checks are read-only, safe, and short.

## 1. Confirm the four PRs actually merged

```
gh pr view 8 --json state,mergeCommit
gh pr view 9 --json state,mergeCommit
gh pr view 10 --json state,mergeCommit
gh pr view 12 --json state,mergeCommit
```
Expect: `"state": "MERGED"` on all four, with merge SHAs matching
`GIT_AND_PR_VERIFICATION.md`.

## 2. Confirm the governance gate is live in `main`

```
grep -n "Mandatory Production Access Authorization Gate" docs/governance/KARMO_ENGINEERING_INVARIANTS.md
grep -n "Production Access Authorization" CLAUDE.md AGENTS.md
```
Expect: the gate section present in the invariants doc; `CLAUDE.md`/`AGENTS.md`
both reference it (no unconditional "Never use production..." wording
remaining).

## 3. Confirm the H0.4 registry repair tool is isolated-only, unmerged into production

```
grep -n "def main" h04/app/registry_repair.py
git log --oneline -- h04/app/registry_repair.py
```
Expect: file exists on `main`; no evidence of any production execution
anywhere in the repo (by design — production actions are never recorded
in-repo, per `AGENTS.md`).

## 4. Confirm the two ambiguous legacy hashes are still marked unresolved

```
grep -n "intentionally unresolved" docs/project-state/NEXT_STEPS.md
```
Expect: still present, unchanged.

## 5. Confirm H0.3 is still NO-PROMOTION

```
grep -n "NO-PROMOTION" docs/project-state/CURRENT_STATE.md
```
Expect: still present.

## 6. Spot-check one production number yourself (optional, requires your own SSH)

```
ssh karmo-ai01 'docker exec karmo-postgres psql -U karmo -d karmo -t -A -c "SELECT count(*) FROM public.document_registry;"'
```
Expect: `3` (matches `PRODUCTION_READONLY_VERIFICATION.md` and the
already-recorded legacy bootstrap `REGISTERED_COUNT: 3`).

## 7. Verify the evidence manifest

```
cd docs/evidence/foundation-v1
sha256sum -c MANIFEST.sha256   # Linux
shasum -a 256 -c MANIFEST.sha256   # macOS
```
Expect: every listed file `OK`.

## 8. Confirm no unexpected production writes occurred

```
docker ps --filter name=karmo   # via ssh karmo-ai01
```
Expect: same container uptimes reported in `POST_CLOSEOUT_HEALTH.md` (no
recent restart).

## 9. Read the one genuinely new finding

Open `FOUNDATION_V1_CLOSEOUT_REPORT.md`'s "A genuinely new finding this
session" section — a non-blocking H0.4 auditor design gap, recommended as
a future follow-up in `NEXT_STEPS.md`.

## 10. Confirm the final status statement

```
grep -n "KARMO FOUNDATION v1" docs/evidence/foundation-v1/RUN_SUMMARY.json
```
Expect: `"foundation_v1_status": "COMPLETE"`.

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
Expect: file exists on `main`. **Limit of this check:** this confirms the
tool was never *logged* as run against production in this repo (by
design — production actions are never recorded in-repo, per `AGENTS.md`)
— it cannot prove no one ever ran it manually outside any recorded
process. Treat as corroborating, not conclusive.

## 4. Independently spot-check the two ambiguous legacy hashes against production

```
ssh karmo-ai01 'curl -s "http://127.0.0.1:6333/collections/karmo_documents/points/scroll" \
  -H "Content-Type: application/json" \
  -d "{\"filter\":{\"must\":[{\"key\":\"document_hash\",\"match\":{\"any\":[\"23646203eed7e187ce2fe0de12c82d5cf83d0a97893a6bdcd2ed30ae3855af9c\",\"5f98126d41381a8a0a4c5034b3402b9a4b763fa043bcfa63f27bdefeb7414c78\"]}}]},\"with_payload\":false,\"with_vectors\":false}" \
  | python3 -c "import sys,json; print(len(json.load(sys.stdin)[\"result\"][\"points\"]))"'
```
Expect: `2` (both points exist in Qdrant, unregistered). This queries
production directly rather than reading `NEXT_STEPS.md`'s own claim about
itself — the earlier version of this checklist item only grepped the
project's own document, which would pass even if the underlying fact were
wrong.

## 5. Confirm H0.3 was never given a production-install record (structural check, not a status grep)

```
grep -n "^## H0\.[0-9] — production" docs/project-state/CHANGE_LOG.md docs/project-state/COMMAND_LOG.md
```
Expect: sections exist for H0.1, H0.2, and H0.4 — **none for H0.3**. The
*absence* of a parallel structural entry (present for every phase that was
actually promoted) is a different, independent signal than reading
`CURRENT_STATE.md`'s own "NO-PROMOTION" label back to itself.

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

## 10. Do not trust the status label — re-derive it

`RUN_SUMMARY.json` saying `"foundation_v1_status": "COMPLETE"` is **not
evidence by itself** — it is this session's own claim about itself, and
would say that regardless of whether it were true. Foundation v1 is
COMPLETE if and only if checks 1–8 above all come back as expected. If any
of them don't, the status label is wrong, not the checklist.

# KARMO — State Now (one page; read this before the long logs)

Last updated: 2026-10-03. Keep this page under ~80 lines and edit it in place when the state changes. Detail and history stay in `CURRENT_STATE.md` (a 2,000+ line log); grep it for a topic instead of reading it whole.

## What KARMO is
- KARMO is Kamara's private, self-hosted assistant.
- **Chat:** qwen3:8b on Ollama, CPU only. It writes about 3 tokens/s; first words arrive in ~19s and an answer finishes in ~45s.
- **Phrasing:** llama3.2:3b phrases prefetched BloomBoss answers.
- **Status checks:** mistral:7b verifies KarmoLab status reports.
- **Coding:** qwen2.5-coder:7b on Worker01 handles coding questions.
- **Memory:** PostgreSQL holds conversation, facts and the outbox. Qdrant holds semantic memory and documents, embedded with embeddinggemma.
- **Access:** a web UI on the tailnet at https://karmo-ai01.tail2d74d7.ts.net:8787, run by `karmo-webui.service`.

## Hosts
| Host | Role | Notes |
|---|---|---|
| KARMO-AI01 | Brain: core, web UI, Postgres, Qdrant, Ollama | VM on KVE02, 8 cores / ~11 GB, no GPU |
| Worker01 | Voice/photo/speech jobs, coding model | VM on KVE01 |
| Worker02 | Same worker code, spare | VM on KVE03 |
| KARMO-DEV (Mac, M3) | Development, Remote Control device | Has SSH to AI01 and the workers |

The KVE01–03 boxes are identical: i7-10700, 15 GiB RAM, no GPU. There's a possible brain upgrade, an 8 GB Mac mini; its chip is unconfirmed as of 2026-10-03.

## Live on AI01 (newest first)
- Mic timeout and date fix (2026-10-01). Voice clips succeed in 13s or less.
- Long spoken replies via chunked TTS (2026-09-30).
- Web UI input outage fixed (2026-09-30).
- BloomBoss keyword fast path (about 0.1s), direct lookups, streaming and per-plant sell-through.
- Identity prompt and BloomBoss tool-forcing.
- Media chunking on AI01 and Worker01. The heartbeat fix is on both workers.

## Built but not live
- **Know Karmo** (draft PR on branch `claude/project-thread-1bjgsr`):
  - owner profile file and "remember / list / forget" facts
  - last 2 hours of conversation passed as real chat turns
  - fixes for keyword hijacks (refusal, status, BloomBoss)
  - "good morning" brief
  - answer-scoring script in `core-service/evals/`
  - repo check: "check github.com/owner/repo" scans on Worker02 and never runs the repo's code (`worker-runtime/app/repo_intake.py`)
  - data map (`core_service/data_map.py`, migration 014): a catalog of file names, sizes and dates for the NAS and uploads. "Where are my …" is answered from the map; contents are opened only when needed.
  - web UI upload button: type is detected from the file signature, a label is chosen, and one tap moves the file to another label
  - Deploy steps are in the project files: `deploy/know-karmo-deploy.md` and `deploy/repo-intake-worker02.md`.
- **Web search** (2026-10-03, Kamara's written approval of items 1–5):
  - A question with web words ("search", "online", "latest", "news", "price of", …) runs `web_search` on Worker02 first.
  - Worker02's loopback SearXNG (127.0.0.1:8888) does the search; the answer ends with a "Sources:" line.
  - Code: `core_service/web_search_capability.py` and the worker `web_search` capability.
  - Setup files: `worker-runtime/deploy/searxng/`.
  - Next approved items: 2 KARMO hands off to Claude/GPT on its own, 3 sales import, 4 pricing, 5 code sandbox.
- **Hands-free voice** (speak, auto-send, spoken answer) is waiting on the owner to merge and deploy.
- **Model Router D2** (sending chat to workers) is merged but switched off. It needs the file `/etc/karmo/core/d2-chat-routing.enabled` to run.

## Known gaps
- **BloomBoss data is thin.** Only one EMgarden invoice (75 units) has been imported. The ~446 Palmstreet orders were never imported; the owner must export them.
- **NAS not attached yet.** The owner plans 10 TB+ over the years. The design is catalog-first (know where things are, open on demand); never bulk-ingest it.
- **Document search is nearly empty.** At the last count it held 8 chunks, and none of Kamara's own notes are loaded.
- **Hardware caps speed.** The 8B model runs on CPU only.

## Standing rules (full text in `CLAUDE.md` and the governance docs)
- Production changes need Kamara's explicit written go-ahead in the thread doing the work.
- Kamara pastes sudo/SSH commands himself, and he does the merges.
- No employer (SDCCD) data ever goes into KARMO.
- Work on feature branches only. Back up before every deploy and write rollback steps.

## Where to look next
- Full system review and the ranked recommendations: project files `reviews/karmo-system-review-2026-10-03.md`.
- Code map with line references: project files `reviews/FABLE_BRIEFING.md`.

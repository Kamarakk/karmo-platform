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

The KVE01–03 boxes are identical: i7-10700, 15 GiB RAM, no GPU. Brain upgrade (LIVE 2026-10-06, measured 12.1 tokens/s vs AI01's ~3): an iMac 24" M1, 16 GB runs Ollama on its GPU. AI01 reaches it through an SSH tunnel (127.0.0.1:11435) and falls back to local Ollama when it is asleep (`FailoverOllamaClient`, on only while `/etc/karmo/core/imac_brain.enabled` exists). Setup: project file `deploy/imac-brain.md`.

## Live on AI01 (newest first)
- Mic timeout and date fix (2026-10-01). Voice clips succeed in 13s or less.
- Long spoken replies via chunked TTS (2026-09-30).
- Web UI input outage fixed (2026-09-30).
- BloomBoss keyword fast path (about 0.1s), direct lookups, streaming and per-plant sell-through.
- Identity prompt and BloomBoss tool-forcing.
- Media chunking on AI01 and Worker01. The heartbeat fix is on both workers.

## Built but not live
- **Tools panel** (2026-10-18, in PR, not deployed; Kamara asked for map/"God's eye", weather, markets, cyber as quiet options): compass button opens Map · Weather · Markets · Cyber; clear chat asks ("weather in X", "market update", "cyber update", "map of X") answered without a model. New worker capability `live_info` on Worker02, pinned to nominatim.openstreetmap.org, api.open-meteo.com, query1.finance.yahoo.com, www.cisa.gov. Deploy = Worker02 code + enable `live_info` in worker02.json + restart, then AI01 core + restart `karmo-webui`.
- **New web app** (2026-10-17, Kamara picked "A with B as its Talk tab", plus saving files): `core_service/webui.py` page rebuilt as a chat app (formatted replies, Hear/Copy/thumbs, history kept on the device, + sheet for photo, camera and multi-file save with drag-and-drop, quick asks) and a hands-free Talk tab (listens until you stop, speaks the answer, listens again; tap to cut in; 10 s of silence ends it). Installs to the iPhone home screen (manifest + icons, no service worker). Same endpoints; deploy = core code + restart `karmo-webui`. Live check needed: Talk on iPhone (speaker volume with the mic open).
- **Model-chosen routing** (2026-10-07, Kamara's "rebuild" decision): while the iMac answers, qwen3:8b picks one route per message (`core_service/intent_router.py`: bloomboss, price, web, status, change, tasks, run_code, code_help, heavy, chat) and the operator runs that route's existing handler; the llama3.2:3b phrasing step is skipped. iMac down or an unusable reply: the keyword rules decide, unchanged. Scorer: `core-service/evals/route_eval.py` with 105 questions in `route_questions.jsonl` (keyword rules: 88/105).
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
- **Automatic hand-off** (approved item 2, `core_service/handoff.py`):
  - Heavy writing or reasoning (draft an email, a plan, compare, step by step, long messages) goes to Claude.
  - So does any question the local model fails to answer.
  - It uses the existing ask_claude/ask_gpt subscription CLIs; GPT is asked if Claude fails. Only the question is sent, and answers end "(asked Claude)".
  - On only while `/etc/karmo/core/handoff.enabled` exists. Never used for BloomBoss data or web-search questions.
- **Code sandbox** (approved item 5):
  - "write and run…", "use python to…" or a pasted ```python block runs on Worker02 in a throwaway container: no network, 512 MB, 60 s.
  - The code is written by Claude when hand-off is on, otherwise by the local coder. Failed runs go back for a fix, up to 3 runs.
  - Worker side: `code_run` plus the `karmo-sandbox-runner` service (`worker-runtime/app/code_sandbox.py`). The worker never gets Docker.
  - Setup files: `worker-runtime/deploy/sandbox/`.
- **Price suggestions** (approved item 4, `core_service/pricing.py`):
  - "What should I price the Ninja Albo at?" combines his own sales (average price, unit cost) with the $ amounts in web results.
  - It suggests the market middle, kept at ≥1.5x his cost, with no model call.
  - Next approved item: 3, sales import (waiting on Kamara's Palmstreet export).
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

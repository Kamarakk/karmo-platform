# KARMO — Recommendations From Today's Session Not Yet Acted On

Covers: every recommendation, idea, or open thread raised in today's
(2026-09-19/20) chat session that was discussed but NOT built, decided,
or resolved — for Kamara to review tomorrow.
Read this if: picking today's conversation back up, or handing this to
GPT for a second opinion on priority.
Status: DRAFT — narrative only, nothing here is a commitment or an
approved plan. Ordered roughly by how directly it affects live chat
performance today.

---

## 1. Trivial-message short-circuit (recommended, not built)

**What**: a cheap pattern check (same style as `_TOOL_TRIGGER_WORDS` from
PR #106) that catches plain greetings/acks ("hi," "thanks," "good
morning") and answers them directly, without ever calling the local
model at all.

**Why it matters, with real numbers**: measured live tonight on
`karmo-ai01` — a plain "good afternoon, how are you?" greeting, with
zero tools offered, still pulled ~6.2GB of RAM (87% of the VM's 7.8GB
total) to load `qwen3:8b`, took 38.8 seconds, and pushed the box into
swap. A short-circuit for this class of message would skip that entire
cost, not just shrink it.

**Status**: recommended as the single highest-leverage next move on
current hardware. Not scoped, not built.

## 2. `ollama_client.py`'s hardcoded `num_predict=96` cap

**What**: response length is capped at 96 tokens for every local-model
call, hardcoded, not read from config.

**Why it matters**: raw generation speed on this CPU-only hardware
measured at ~3.5-4 tokens/sec — for turns that don't involve tool-schema
overhead (already fixed in PR #106), this cap is now the dominant
remaining latency factor.

**Status**: flagged only. Not touched, not benchmarked with alternate
values, no decision made on whether 96 is even the right number for
KARMO's actual answer lengths.

## 3. Caching external-LLM answers (`ask_claude`/`ask_gpt`) to cut network calls

**What**: Kamara asked whether a tool/skill could hold what `ask_claude`/
`ask_gpt` already answered, to avoid repeat network round-trips.

**Recommendation given**: build an exact-match or short-TTL cache first
(simple, safe, easy to invalidate) rather than a semantic/embedding-based
cache — KARMO already has Qdrant in production if semantic caching is
wanted later, but that adds real complexity (embedding calls, similarity
thresholds, staleness rules) not justified without measuring the actual
repeat-question rate first.

**Status**: conceptual only. No code written, no measurement of how
often the same/similar question actually recurs.

## 4. "Brain + mini-helper models on dedicated workers" hardware architecture

**What**: Kamara's idea — one main conversational model ("the brain")
plus small specialist models for narrow capabilities (voice, coding,
security), each running on its own worker, callable only when that
specific task is requested.

**New evidence tonight that bears directly on this**: live RAM
measurement showed a single `qwen3:8b` call already consumes ~6.2GB of
`karmo-ai01`'s 7.8GB total — there is no room to keep even a second
model warm on this same box. The shadow-router log during that same test
showed all three hosts (`karmo-ai01`, Worker01, Worker02) reporting
`no_tool_capable_model_loaded` simultaneously. This is real evidence,
not speculation, that the mini-helper idea needs its own dedicated
hardware per model — it cannot be fit onto the current three-VM
footprint without giving something else up.

**Status**: not decided, not built. Recommendation stands from earlier
tonight: validate/benchmark before committing hardware to this, and it
should wait until real headroom exists (better hardware or fewer
concurrent responsibilities per box).

## 5. Voice / video / chat accessibility "day one"

**What**: Kamara's stated requirement that KARMO be reachable via voice,
video, and chat, available immediately.

**Status**: explicitly deferred, never resumed after the hardware
investigation. Zero voice/video capability exists anywhere in the
codebase today — this needs its own scope and timeline conversation,
not an assumption that it's close.

## 6. Phase D2 (live worker chat routing) — activation still on hold

**What**: D2 was fully built (PR #97), independently reviewed twice, and
deliberately merged as dormant/inactive code (its activating DSN file
was never created in production).

**Open items from those reviews, unresolved**: the dispatch credential
reuses the SSH gateway's role rather than a dedicated least-privilege
one; worker tables would become an undeclared store of real chat content
with no retention policy; worker selection has a check-then-act race;
and the core premise (worker routing relieves contention) has never
actually been measured against a local-only baseline.

**Status**: intentionally not reopened tonight. Revisit only if/when
real benchmarking or new hardware changes the calculus.

## 7. "There are more LLMs running on KARMO outside Ollama" — unresolved

**What**: when asked how many LLMs run outside Ollama, the answer given
was two — `ask_claude` (via the local `claude` CLI) and `ask_gpt` (via
the local `codex` CLI) — verified directly against the actual capability
code (`ask_claude_capability.py`/`ask_gpt_capability.py`). Kamara flagged
that there are more.

**Status**: open and unresolved — needs Kamara to say what's missing so
it can be verified against real code rather than guessed. Do not assume
what these are; confirm live/in-repo like the first two were.

## 8. Worker01/Worker02 read-only diagnostic checks, prepared but never run

**What**: earlier in tonight's session, exact read-only SSH/psql commands
were prepared to check what's currently running on Worker01/Worker02
(service state, stuck-job count), but the conversation moved to the
trust/hardware-verification topic before they were ever executed or
answered.

**Status**: still pending, low priority, no urgency signal since.

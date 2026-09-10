# Voice / Media Readiness Specification

Status: **DESIGN ONLY. Not implemented, not started.** No model
downloaded, no media stack installed, per explicit instruction. Produced
under the Core v2 Engineering Blueprint Program, Workstream 10 — the
domain that gives KARMO its "ears and a mouth," per Natalie's own stated
long-term goal, treated with the weight that deserves rather than as an
afterthought behind BloomBoss/Finance.

## Voice requirements

| Capability | Nature | Core abstraction required |
|---|---|---|
| **STT** (speech-to-text) | request/response, bounded duration | a `READ`-shaped tool (audio in, text out) — no new Core abstraction, fits the Tool/Capability Registry directly |
| **TTS** (text-to-speech) | request/response, bounded duration | same — a `READ`-or-`DRAFT_PROPOSE`-shaped tool (text in, audio out); output is a media artifact, so it also needs Media's storage abstraction (below) |
| **Wake/listen** | continuous, always-on, unbounded duration | **new Core abstraction required** — not a single tool call at all. The Extensibility Review already flagged this: "a continuously-running listener [needs] its own resource-bounded process with its own explicit start/stop/backpressure design, not an extension of the existing outbox relay's polling loop." Neither the Tool/Capability Registry nor the Job/Event model (Workstream 5, this program) as designed covers a genuinely *continuous* capability — both assume a call has a start and an end. |
| **Conversation sessions** | stateful, multi-turn, potentially long-lived | needs a session identity distinct from a single tool invocation's `correlation_id` (Workstream 6) — a session *contains* many correlation_ids, one per turn, not the reverse |
| **Interruptions** | mid-execution cancellation of TTS/an in-progress tool | the Job/Event model's `CANCELLED` state already exists for this — voice is the domain that would actually exercise it; the gap is a *latency* requirement (interruption must be near-instant) the current design doesn't address, since nothing in this program measured or bounded cancellation latency |
| **Streaming** | partial results delivered incrementally (STT partial transcripts, TTS audio chunks) | **new Core abstraction required** — every Workstream 3/4/5 prototype this program built assumes a single request → single response; none support a result delivered as a stream of partial updates |

## Media requirements

| Capability | Nature | Core abstraction required |
|---|---|---|
| **Image generation** | request/response, seconds-to-minutes | fits the Job/Event model directly (`QUEUED → RUNNING → SUCCEEDED`, with `progress` already a first-class `Job` field in this program's prototype) |
| **Image editing** | request/response, similar | same, plus needs the edited image's *provenance* (which source image, which edit) tracked — an authoritative-store question (I-03), same shape as `document_registry`, not yet designed for media (the Extensibility Review already recommended "a parallel, media-specific registry table," not overloading `document_registry`) |
| **Video workflows** | minutes-to-hours, large output | Job/Event model fits the *shape*, but needs its `timeout_seconds` and storage assumptions reconsidered at video's actual scale — nothing in this program's prototypes was sized for large-file, long-duration work |
| **Media storage** | large binary artifacts, growth over time | **new Core abstraction required** — no KARMO component today stores anything but text/vectors; Workstream 4 of the *prior* adversarial review already flagged "no bounded-storage pattern for non-text content anywhere in the current codebase" |
| **Job progress** | incremental status for a long-running generation | the Job/Event model's `progress: dict` field already exists for this (Workstream 5, this program) — the one Media requirement already covered without further design |
| **Large artifacts** | files too large to pass through the same channels as a JSON tool result | the Tool/Capability Registry's `output_schema` as designed assumes a JSON-serializable result — a large media file needs the schema to describe a *reference* (a storage location) rather than the artifact inline, a real gap in tonight's Workstream 3 design worth naming, not silently assumed to already work |

## Summary of new Core abstractions this domain requires (not built tonight)

1. **A continuous-capability model**, distinct from both the Tool
   Registry's single-call shape and the Job model's start-and-end shape —
   needed specifically for wake/listen. The single largest genuinely new
   piece of Core surface this whole program's analysis surfaced.
2. **A streaming-result shape** — partial updates delivered incrementally,
   not assumed by any prototype built tonight.
3. **A session identity layer above `correlation_id`** — grouping many
   tool invocations into one ongoing conversation.
4. **A media-specific authoritative registry**, separate from
   `document_registry`, exactly as the Extensibility Review already
   recommended — this spec reconfirms that recommendation rather than
   revisiting it.
5. **A large-artifact reference convention** in tool output schemas — a
   registered tool's `output_schema` should be able to declare "this
   field is a storage reference, not inline data."

## What this spec deliberately does not do

- No STT/TTS/image/video model is downloaded, evaluated, or selected.
- No wake-word/always-listening capability is designed in detail beyond
  naming that it needs its own abstraction — the actual design of that
  abstraction is future, separately-scoped work.
- No decision that Voice or Media is the first post-foundation
  capability — see `docs/plans/POST_FOUNDATION_CAPABILITY_ROADMAP.md`.

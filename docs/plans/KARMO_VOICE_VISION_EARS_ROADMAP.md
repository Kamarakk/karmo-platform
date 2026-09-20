# KARMO — Eyes, Voice, Ears Roadmap

Covers: current status (zero capability today) and a concrete, phased
build plan for giving KARMO speech input ("ears"), speech output
("voice"), and image/video understanding ("eyes") — written so a fresh
session (any model, any tool) can execute against it directly without
re-deriving the architecture decisions.
Read this if: picking up the voice/vision work, or scoping the first PR
in this area.
Status: PLANNING ONLY. Nothing in this document is built. No System-Fit
Review, Invariant Impact Review, or Production Access Authorization has
been performed for any of it — those remain required before
implementation starts, per `docs/governance/KARMO_ENGINEERING_INVARIANTS.md`
and `docs/governance/KARMO_SYSTEM_FIT_REVIEW.md`.

---

## Standing constraint (Kamara's explicit decision, 2026-09-20 — do not
revisit without her direct instruction)

**`ask_claude` and `ask_gpt` must never be extended with any new
capability beyond what they already offer today: plain text
question-and-answer, invoked only when she explicitly asks for Claude or
GPT by name.** No image, audio, file, or any other input/output may be
added to either tool. This was tested once (an image-input extension to
`ask_claude`, built 2026-09-20) and explicitly rejected and fully
reverted the same day (git commit `f426f5b`, reverted at `6225a42`) once
Kamara clarified the actual rule: nothing that becomes part of what
KARMO *does* may depend on Claude or GPT, no matter how the dependency
is gated. **Every KARMO capability — eyes, ears, voice, all of it — must
be built to run on KARMO's own local infrastructure.** This rules out
the "delegate to Claude/GPT" pattern for all three channels below, not
just eyes; see the Eyes section for what that actually costs.

---

## Why this doesn't exist yet

Kamara's stated requirement (2026-09-19/20 sessions) was for KARMO to be
reachable via voice, video, and chat, available immediately. That
requirement was accepted as real but explicitly deferred every time it
came up, in favor of first fixing concrete, live production problems
(the submit_result investigation, BloomBoss chat integration, hardware
verification, model cleanup). No voice/video/vision code has ever been
written anywhere in this repository. This is the first real scoping
pass.

## Real constraints this plan must respect (verified this session, not assumed)

- **Hardware is CPU-only, no GPU, anywhere in the fleet.** `karmo-ai01`,
  Worker01, Worker02 are all identical spec (i7-10700, Intel UHD 630
  iGPU which is not used for inference). `karmo-ai01`'s VM has 7.8GB RAM
  total.
- **A single 8B chat model (`qwen3:8b`) already consumes ~6.2GB (~80%)
  of `karmo-ai01`'s RAM during generation**, measured live 2026-09-20.
  There is effectively **zero standing RAM headroom** on this VM for
  another always-loaded model.
- **Local-first is KARMO's standing architectural principle** (see
  `docs/architecture/KARMO_ORCHESTRATION_AND_MODEL_ROUTING.md` and the
  DeepSeek/Gemini rejection precedent) — cloud dependencies are avoided
  by default, not because they're impossible, but because KARMO's
  identity is a locally-run system.
- **`ask_claude`/`ask_gpt` exist and stay exactly as they are** (plain
  text Q&A, explicitly invoked) — per the standing constraint above,
  they are not a pattern to extend for eyes/ears/voice or anything else.
  Do not propose delegating any of these three channels to them.

## Architecture recommendation, per channel

### Ears (speech-to-text / voice input)

**Recommendation: a local, lightweight speech-to-text model — not a
cloud call.** Unlike an 8B chat model, real-time speech-to-text models
(the class Whisper-small/base or comparable small local STT models fall
into) run at a small fraction of the resource cost of an 8B LLM and only
need to be loaded for the duration of actually transcribing audio, not
held resident. This fits the RAM-scarcity finding above far better than
adding another always-on chat-sized model would.

**What this actually requires, concretely**:
1. An audio capture path from wherever Kamara is talking to KARMO from
   (the webui's browser microphone, a phone client, or a dedicated
   endpoint) — this is new surface area, not something that exists
   today (`core_service.webui` is text-only).
2. A new capability/endpoint that accepts an audio blob and returns
   transcribed text.
3. Feed that transcribed text into the **existing**
   `KarmoOperator.handle()` — this part is NOT new work; the whole
   chat/tool-calling/memory pipeline already exists and doesn't care
   whether the text came from typing or transcription.

**Real open question, needs Kamara's decision, not a guess**: which
local STT engine, and does it run in-process (added as a new Python
dependency + model file next to Ollama) or as its own small local
service. Needs its own System-Fit Review before either is chosen.

### Voice (text-to-speech / voice output)

**Recommendation: a local, lightweight TTS engine — not a cloud call**,
for the same resource-fit reason as ears. Small local TTS engines (the
class Piper or comparable lightweight neural TTS falls into) are far
cheaper than an 8B model and, like STT, only need to run for the
duration of actually synthesizing a reply.

**What this actually requires, concretely**:
1. Take `KarmoOperator.handle()`'s existing text response (no change to
   how the answer is produced).
2. Synthesize it to audio via the chosen local TTS engine.
3. Deliver that audio back to whatever client is listening — same new
   surface-area question as ears.

### Eyes (image / video understanding)

**Updated 2026-09-20: delegating this to `ask_claude`/`ask_gpt` was
built, then explicitly rejected by Kamara and fully reverted the same
day.** Per the standing constraint above, eyes must be built on KARMO's
own local infrastructure, same as ears and voice — no exception for
eyes specifically, even though it's the hardest of the three to do
locally on current hardware.

**The real, unavoidable cost this now has to be paid, not routed
around**: a vision-capable local model is roughly the same size class
as `qwen3:8b` or larger — meaningfully more RAM/compute than the small
STT/TTS models ears and voice need. On `karmo-ai01` as it's currently
sized (7.8GB total, ~6.2GB already consumed by `qwen3:8b` alone), there
is no room for a second model of that size. This is a real, direct
conflict, not a detail to smooth over. Eyes needs one of:

1. **A genuinely small local vision model** whose footprint fits in
   whatever headroom remains after `qwen3:8b` loads — not yet evaluated
   on this hardware; needs real candidates identified and actually
   measured (RAM, latency) before any implementation, same discipline
   as everything else built this session. No candidate is named here
   because none has been tested — naming one without testing it would
   be a guess, not a recommendation.
2. **Separate hardware from `karmo-ai01`** (a dedicated worker, or the
   still-undecided VM-resource-reallocation / better-hardware questions
   raised earlier this session) — ties eyes to those open decisions
   rather than something to solve independently.

**Not scoped further than this.** Eyes is genuinely blocked on either a
real local-model evaluation or a hardware decision — both open, neither
started.

## Phased build plan

**Phase V0 — retired, do not rebuild.** Image delegation via
`ask_claude` was built and then explicitly rejected by Kamara and fully
reverted (git commit `f426f5b`, reverted at `6225a42`, both 2026-09-20).
Eyes now depends on a real local-vision-model evaluation instead (see
the Eyes section above) — there is no lowest-risk shortcut anymore.

**Phase V1 (ears)**: pick a local STT engine (System-Fit Review
required), build the capture-and-transcribe path, wire transcribed text
into the existing `KarmoOperator.handle()`. No changes to chat/tool
logic itself.

**Phase V2 (voice)**: pick a local TTS engine (System-Fit Review
required), build the synthesize-and-deliver path from
`KarmoOperator.handle()`'s existing response text.

**Phase V3 (client surface)**: decide where Kamara actually talks to
KARMO from (browser mic/speaker via an extended `core_service.webui`,
a phone client, or something else) — this is a real, undecided product
question, not a technical one, and should be decided before V1/V2 pick
exact engines, since the audio format/streaming needs may differ by
client.

## What a fresh session should do first

1. Read this document in full, including the standing constraint at the
   top — it is Kamara's explicit, tested decision, not a preference to
   re-litigate.
2. Confirm with Kamara: (a) which local vision model candidates (if
   any) she wants evaluated for eyes, or whether eyes waits on a
   hardware decision instead, and (b) what client surface (Phase V3)
   she actually wants to talk to KARMO from — this second question
   changes what V1/V2 need to build and should be answered before
   committing to a specific STT/TTS engine.
3. Run the standing governance gates (System-Fit Review, Invariant
   Impact Review) for whichever phase is chosen before writing code.
4. Do not attempt to build more than one phase in a single session —
   each phase above is sized to be independently completable and
   deployable, matching this project's established pattern of small,
   tested, deployed slices rather than large multi-phase pushes.
5. Never propose extending `ask_claude`/`ask_gpt` as a way to shortcut
   any of this, even if it looks like the fastest path — that path was
   tried and closed.

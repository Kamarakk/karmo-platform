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
- **`ask_claude`/`ask_gpt` already exist as a proven external-delegation
  pattern** (`ask_claude_capability.py`/`ask_gpt_capability.py`): shell
  out to a locally-installed, already-authenticated CLI, no API key
  stored in KARMO, read-only, no access to KARMO's own data. This is a
  real, working precedent for "delegate the expensive/hard part to an
  external model you already have a subscription to," not a new pattern
  that needs inventing.

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

**This is the one channel where the honest recommendation is NOT a new
local model.** A vision-capable local model (e.g. a LLaVA-class model)
would be roughly the same size class as `qwen3:8b` or larger — on this
hardware, that means either replacing `qwen3:8b` outright or fighting it
for the same ~6-7GB of headroom that's already almost entirely consumed.
That is a real, direct conflict with tonight's own decision to run
`qwen3:8b` as the sole resident model.

**Recommendation instead: reuse the already-built `ask_claude`/`ask_gpt`
external-delegation pattern.** Both underlying CLIs (`claude`, `codex`)
already support image input in their own real capability set. A new
capability (e.g. `ask_claude_about_image`, or extending
`ask_claude_capability.py` to optionally accept an image path) could
delegate "what's in this picture" questions to Claude or GPT directly,
with zero new local model, zero new RAM cost on `karmo-ai01`, using
infrastructure that's already built, tested, and proven in production.
This is the single highest-leverage, lowest-risk starting point of all
three channels, specifically because it needs no new model at all — just
an extension of an existing capability's input schema and CLI
invocation.

**Real trade-off to be explicit about**: this makes "eyes" dependent on
an external network call and Kamara's Claude/GPT subscription, same as
`ask_claude`/`ask_gpt` are today — consistent with an already-accepted
pattern, not a new kind of dependency.

## Phased build plan

**Phase V0 (recommended first PR, lowest risk, no new model)**: extend
`ask_claude_capability.py` (or add a sibling capability) to accept an
optional image, gated the same way `ask_claude` already is (explicit
mention/intent, READ-only, no KARMO data access). Proves the "eyes via
delegation" pattern end-to-end before any audio work begins. Needs its
own System-Fit Review and Invariant Impact Review before implementation,
per standing governance.

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

1. Read this document in full.
2. Confirm with Kamara: (a) is Phase V0 (image delegation via
   ask_claude/ask_gpt) still the right starting point, and (b) what
   client surface (Phase V3) she actually wants to talk to KARMO from —
   this second question changes what V1/V2 need to build and should be
   answered before committing to a specific STT/TTS engine.
3. Run the standing governance gates (System-Fit Review, Invariant
   Impact Review) for whichever phase is chosen before writing code.
4. Do not attempt to build more than one phase in a single session —
   each phase above is sized to be independently completable and
   deployable, matching this project's established pattern of small,
   tested, deployed slices rather than large multi-phase pushes.

# PROJECT SAVE — 2026-09-20 — Local Capability Lineup (Eyes, Coding, Ears, Voice)

Covers: narrative summary only. Enduring content lives in
`docs/project-state/PROJECT_TODO_LIST.md` (Section G) and
`docs/plans/KARMO_VOICE_VISION_EARS_ROADMAP.md` — read those for full
technical detail; this file is the story of how tonight got there and
what to do next.
Read this if: picking up KARMO work after 2026-09-20's session, or
briefing a fresh chat session on where things stand.
Status: NARRATIVE RECORD. PR #117 (all four capabilities below) is open,
tested, not yet merged.

---

## What happened, in order

1. Merged PRs #109–#116 tonight: the eyes/voice/ears roadmap doc, a
   trivial-message chat short-circuit, an exact-match cache for
   `ask_claude`/`ask_gpt`, a configurable `num_predict` cap, and a
   router-config cleanup after deleting `ministral-3:8b`/`granite3.3:2b`
   from `karmo-ai01` (all deployed and live-verified).
2. Built `ask_claude`'s optional image input, then **immediately hit a
   real miscommunication**: Kamara's instruction "I don't want anything
   depending on Claude/GPT" was initially over-corrected into "never
   extend `ask_claude`/`ask_gpt` at all," and the image feature was
   reverted. Kamara corrected this directly: she never said KARMO can't
   *ask* Claude/GPT for help as an explicit, optional tool — the actual
   rule is **Claude/GPT must never be the only or main source of a
   capability**. The revert was itself reverted (the feature is back),
   and the roadmap doc's standing-constraint section now states the
   corrected rule. **Lesson for future sessions: re-read an instruction
   like this twice before acting — the difference between "never use X"
   and "never depend ONLY on X" is exactly the kind of thing worth
   confirming before reverting real work.**
3. Kamara pushed back hard on hardware research done live tonight,
   pointing out that `docs/checkpoints/KARMO_ACTIVATION_CHECKPOINT_20260913.md`
   — a week-old document — had *already* stated the workers exist
   specifically because `karmo-ai01` is RAM-constrained. That reasoning
   should have been surfaced by reading existing docs, not re-derived
   live as if new. **Lesson: check `docs/checkpoints/` and
   `docs/project-state/PROJECT_SAVE_*` for prior planning before
   presenting a "finding" as new.**
4. Verified live: Worker01/Worker02 have **9.7GB RAM each, ~9.1GB idle**
   — more headroom than `karmo-ai01` itself (7.8GB, ~1.6GB free after
   `qwen3:8b` loads). Deleted the same unused models from both workers
   that were already removed from `karmo-ai01` (PR #116).
5. Kamara asked, as a cybersecurity student, for KARMO to be able to run
   ethical-hacking tools (Nmap, Metasploit, etc.) against her own
   systems for practice. **Explicitly deferred to 2026-09-22** on her
   own instruction — this is real, authorized, legitimate use, but
   needs an isolated lab network defined before any tool-running
   capability can be built safely (a target allowlist needs something
   real to allowlist).
6. Built and live-verified all four remaining items on Worker01: eyes
   (Moondream2), a local coding helper (qwen2.5-coder:7b), ears
   (faster-whisper), and voice (Piper). See
   `PROJECT_TODO_LIST.md` Section G for the full table and honest scope
   boundaries (not wired into chat yet; not activated — see the DSN
   coupling finding below).
7. **Real, previously-unknown finding**: the DSN file that would
   activate any of these four local capabilities
   (`/etc/karmo/core/worker-dispatch.dsn`) is the SAME switch that
   activates Model Router Phase D2's held-back chat-routing-to-worker
   path. Creating it for one purpose silently activates the other. Not
   resolved tonight — documented in `vision_capability.py`'s module
   docstring and flagged as a real decision point, not a detail.

## Standing decisions now in force (do not re-litigate without Kamara)

- **Claude/GPT policy**: explicit, optional, supplementary tool only —
  never the sole/main source of a capability. `ask_claude`'s image
  input is allowed and kept under this rule.
- **Client surface, Kamara's answer 2026-09-20**: browser, phone, AND
  mic/speaker — all three. Not yet built (this is real frontend/client
  work, not started).
- **Item 5 (ethical-hacking lab) is parked for 2026-09-22**, not
  cancelled. Kamara wants KARMO to run the tools for her (not just have
  them available for manual use) — confirmed explicitly.

## What a fresh session should do first

1. Read `PROJECT_TODO_LIST.md` in full (especially Section G) — it's
   the living index of everything open.
2. If picking up the local-capability work: PR #117 is open, tested,
   safe to merge anytime (all four capabilities are inert until the DSN
   decision below). Merging it does not change any live behavior.
3. The two real next decisions, in the order they'd naturally come up:
   (a) the worker-dispatch DSN / D2-coupling question — needs either
   resolving D2's own flagged concerns or decoupling the two switches;
   (b) the client-surface build (browser mic/speaker + phone) — needed
   before any of the four capabilities are reachable from a real
   conversation, independent of the DSN question.
4. Item 5 (ethical-hacking lab): before building anything, get a direct
   answer on whether an isolated lab environment already exists.

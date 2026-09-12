# KARMO AI Engineering Apprenticeship

Status: ACTIVE / FLEXIBLE
Owner: Kamara
Purpose: Learn practical AI and agent engineering by understanding, extending, and safely operating KARMO.

## Course design rules

This course is intentionally flexible. The sequence may be changed whenever a better learning path is identified, but completed sections must always be recorded in `KARMO_LEARNING_PROGRESS.md` before moving on.

Teaching approach:
1. Start from a real KARMO problem or capability.
2. Explain where the concept fits in the whole system before coding.
3. Introduce only the new AI-specific ideas needed for that lesson.
4. Show one small worked example.
5. Build a guided version together.
6. Let Kamara complete a small variation independently.
7. Break or test the concept so the trust/failure boundary is visible.
8. Close by connecting the lesson back to KARMO.

Do not turn the course into generic beginner IT training. Assume working familiarity with networking, systems, security concepts, services, authentication, permissions, troubleshooting, and normal IT terminology. Slow down for new AI/ML/agent concepts, not for familiar infrastructure ideas.

## Lesson format

Every lesson should begin with:
- **Today you're building** — one sentence.
- **Why KARMO needs it** — one or two sentences.
- **Where it fits** — a compact system-flow diagram.
- **New concept(s)** — only what is new today.
- **Success means** — what Kamara should be able to explain or do by the end.

Every lesson should use this progression when practical:
- **Watch me** — one small complete example.
- **Build with me** — guided implementation.
- **You do it** — a small variation or requirement.
- **Make it fail** — inspect one realistic failure/security case.

Avoid unnecessary quizzes. Prefer short applied checks such as asking which KARMO component owns a decision or why a boundary exists.

## Course map

### Phase 1 — How an AI application works
Build the smallest useful loop:

`Python -> Prompt -> Model -> Response`

Concepts:
- model
- prompt
- context
- tokens
- inference
- temperature
- structured output

Goal: understand the basic application/model boundary without spending excessive time on generic Python.

### Phase 2 — From chatbot to tool-using AI
Build:

`User request -> Model -> Tool request`

Concepts:
- tool calling
- JSON
- schemas
- arguments
- parsing
- model output vs application code

Goal: understand that a model proposes structured actions; application code decides what happens next.

### Phase 3 — Trust boundaries
Build:

`Model proposes -> Validator checks -> Policy decides -> Execution allowed/denied`

Concepts:
- validation
- allowlists
- schema validation
- least privilege
- fail-closed behavior
- hallucinated tools
- prompt injection
- trust boundaries

Goal: understand why model output is never equivalent to trusted execution.

### Phase 4 — KARMO Core
Map the previous concepts onto the real deployed KARMO Core.

`Model -> Capability request -> KARMO Core -> Approval requirement`

Concepts:
- capability classes
- approval engine
- policy
- jobs/events
- authentication vs authorization

Goal: understand why Core exists and how it separates model intent from authority.

### Phase 5 — Workers
Build and inspect:

`Core -> Job -> Worker -> Sandbox -> Result`

Concepts:
- execution boundary
- workers
- process isolation
- timeouts
- result validation
- retries
- idempotency

Goal: understand how bounded work leaves Core and is executed safely.

### Phase 6 — Memory and RAG
Build the mental model:

`Documents -> Embeddings -> Vector store -> Retrieval -> Context -> LLM`

Concepts:
- embeddings
- vector databases
- chunking
- retrieval
- semantic search
- RAG
- provenance
- versioning

Goal: understand KARMO's existing document memory and Qdrant-backed retrieval in practical terms.

### Phase 7 — Agents
Build:

`Goal -> Observe -> Reason/choose -> Tool -> Result -> Observe again`

Concepts:
- agent loop
- state
- permissions
- memory
- stopping conditions
- evaluation
- human approval

Goal: understand that an agent is an engineered control loop, not magic.

### Phase 8 — Real KARMO capability
Use the learned pieces to build a useful capability in KARMO, with BloomBoss as a strong candidate unless Kamara chooses another domain.

Goal: finish with something used in the real system, not a toy project.

## Change policy

This plan is not frozen. It may be reordered, compressed, expanded, or replaced when:
- a better learning sequence is discovered;
- KARMO architecture changes materially;
- a lesson is wasting time or not producing understanding;
- a real project task creates a better teaching opportunity.

When changing the plan:
1. preserve already completed progress records;
2. do not erase prior completed sections;
3. record the reason for the change in `KARMO_LEARNING_PROGRESS.md`;
4. continue from the best next learning objective, not from an arbitrary old sequence.

## Completion rule

No lesson or section is considered complete until its completion record is added to `docs/learning/KARMO_LEARNING_PROGRESS.md` with:
- date;
- phase/lesson;
- what was built or demonstrated;
- concepts understood;
- one short proof/check of understanding;
- any unresolved confusion;
- next lesson.

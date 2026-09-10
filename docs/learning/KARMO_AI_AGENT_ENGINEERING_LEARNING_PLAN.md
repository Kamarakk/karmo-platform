# KARMO AI / Agent Engineering Learning Program
Version: 0.1
Owner: Natalie

## Goal
Become capable of understanding, challenging, designing, building, debugging, securing, and improving modern AI/agent systems by working on real systems rather than only reading theory.

## Core Training Principle
This is not a lecture course. Every topic follows:
1. Learn the idea.
2. Inspect how it appears in KARMO or another real system.
3. Build something with it.
4. Break it on purpose.
5. Debug it.
6. Explain what happened in your own words.
7. Decide whether KARMO should keep, change, or reject the design.

The target is engineering judgment, not memorization.

## Weekly Time Model
- Monday-Friday anchor: 8:00 PM-9:30 PM.
- Work downtime can count as the primary session; evening becomes review/lab/family time if the lesson is already complete.
- Recommended load: 5 sessions/week, 90 minutes each (about 7.5 hours/week).
- Optional sixth 60-90 minute build/benchmark/catch-up session.

Typical session:
- 20-30 min concept/examples
- 40-50 min hands-on lab
- 10-15 min debugging/adversarial testing
- 10-15 min explain-back + architecture decision

# Program Stages

## Stage 1 — Foundations With Real Systems (Weeks 1-4)
Topics: LLM behavior, tokens/context, sampling, structured output, tool calling, embeddings, vector DBs, RAG, local inference, agent loops, evaluation, prompt injection basics.

Tools: Python, Ollama, Qwen, Llama, EmbeddingGemma, Jupyter/Python REPL, KARMO, Qdrant, PostgreSQL, Git/GitHub, Claude Code, ChatGPT.

Hands-on outcomes:
- Call a local model from Python.
- Compare Qwen and Llama on the same task.
- Send structured JSON requests.
- Build a tiny tool router.
- Validate/refuse malformed model output.
- Generate embeddings and retrieve vectors.
- Build a miniature RAG pipeline.
- Inspect KARMO memory flows.

## Stage 2 — Applied Python for AI Engineering (integrated Months 1-6)
Python is not a separate beginner class. We learn it by using it in AI systems.

Focus areas: functions, arguments, data structures, type hints, dataclasses, classes, exceptions, context managers, JSON, files, APIs, HTTP clients, environment variables, logging, subprocesses, multiprocessing, async/await, pytest, mocks, database access, schema validation, package structure, debugging, profiling, security validation.

Rule: when a lesson uses Python, Natalie writes part of the code before seeing the complete solution.

## Stage 3 — Agent Engineering (Months 2-4)
Topics: agent loops, planning, tool routing, skills, state, memory, retries, idempotency, job queues, approval gates, authority models, multi-step execution, human-in-the-loop, recovery, observability.

Labs: build an agent loop, write tool schemas, cause malformed results/timeouts/exceptions, test replay, approval-bound arguments, compare models, map findings to KARMO Tool Registry/Approval Engine/Job Model.

## Stage 4 — MCP, Integrations, and Tool Ecosystems (Months 3-5)
Topics: MCP servers/clients, resources, tools, prompts, authentication, permissions, local vs remote tools, least privilege.

Labs: run/inspect an MCP server, create a local MCP tool, connect a model to it, test unsafe requests, compare MCP to KARMO capability/orchestration boundaries.

## Stage 5 — Memory, Embeddings, and RAG Deep Dive (Months 4-6)
Topics: chunking, embedding spaces, similarity, metadata filtering, dense/sparse/hybrid retrieval, reranking, eval sets, retrieval failure vs hallucination, lifecycle, provenance, versioning.

Labs: compare embeddings and chunk sizes, build Qdrant collections, poison retrieval, test stale versions, compare dense vs hybrid retrieval, recreate simplified H0.0-H0.4 concepts.

## Stage 6 — Model Internals and Representation Engineering (Months 5-8)
Topics: transformers, attention, residual stream, MLPs, logits, hidden states, activations, tokenization, probing, activation patching, steering vectors/activation steering, representation engineering.

Labs:
- Inspect tokenizer behavior.
- Capture hidden-state activations from a small open model.
- Train a simple linear probe.
- Build a steering vector from contrasting examples.
- Inject the steering vector during inference.
- Measure behavior change and unintended effects.
- Compare prompt steering vs activation steering.

Important: steering vectors are experimental model-behavior techniques, not KARMO security enforcement.

## Stage 7 — Fine-Tuning and Model Adaptation (Months 6-9)
Topics: supervised fine-tuning, instruction tuning, LoRA, QLoRA, adapters, datasets, train/validation splits, overfitting, catastrophic forgetting, evaluation, preference-optimization concepts, distillation concepts, when not to fine-tune.

Labs:
- Create a small clean dataset.
- Fine-tune a small open model with LoRA.
- Compare before/after behavior.
- Compare fine-tuning against prompting/RAG.
- Create a deliberately bad dataset and observe degradation.
- Load/merge adapters and inspect checkpoints.

M3 rule: use models and experiments appropriate for 8 GB unified memory; larger training waits for appropriate compute.

## Stage 8 — Evaluation and LLMOps (Months 7-10)
Topics: golden datasets, eval harnesses, regression tests, model comparison, latency, cost, accuracy, robustness, adversarial testing, tracing, logging, provenance, reproducibility.

Labs: build an eval harness, compare Qwen/Llama, track latency/quality, create adversarial prompts, detect regressions.

## Stage 9 — AI Security (Months 8-11)
Topics: prompt injection, indirect injection, exfiltration, tool abuse, confused deputy, excessive agency, output validation, secrets, sandboxing, identity, authorization, approvals, auditability, supply-chain risk, untrusted files, agent-to-agent trust.

Labs: attempt injection/bypass/path traversal/replay/argument substitution/malformed output and verify deterministic enforcement.

## Stage 10 — Distributed and Multi-Agent AI (Months 9-12)
Topics: coordinators, workers, job leasing, heartbeats, worker identity, remote execution, capability discovery, distributed failure, network partitions, result authenticity, multi-agent delegation, planner/executor/reviewer patterns.

Labs: multi-worker simulation, kill worker mid-job, expire lease, replay result, simulate approval delay, compare builder/reviewer agents, eventually test KARMO Worker Runtime in a controlled environment after approval.

## Stage 11 — Production AI Systems (Months 10-15)
Topics: deployment, containers, APIs, queues, databases, observability, scaling, model serving, inference optimization, quantization, caching, resilience, rollback, versioning, CI/CD.

Labs: package services, containerize, benchmark, build health checks, break/recover dependencies, compare local vs remote inference.

## Stage 12 — Advanced / Specialist Track (Months 12-24+)
Possible tracks: AI systems architecture, agent engineering, AI security, local/private AI, RAG/retrieval engineering, model adaptation, representation engineering, multi-agent systems, AI infrastructure, applied AI for BloomBoss.

# First 7-Day Sprint

## Day 1 — LLMs + Python Control Layer
Learn: what the model does vs what the application does; model output vs execution authority.
Build: Python model call, tool router, allow/deny policy.
Break: malformed and forbidden tool request.
Explain: why the model must not be final authority.
KARMO mapping: Tool Registry + Approval Engine.

## Day 2 — Tokens, Context, and Prompt Structure
Build tokenizer/context/system-vs-user-prompt experiments.
Break oversized context/conflicting instructions.
Question: what should KARMO give a model, and what should it never trust the model to remember?

## Day 3 — Tool Calling
Build tool schema, Python handler, structured arguments, validation.
Break missing field/wrong type/invented tool/malicious argument.
KARMO mapping: Tool Registry + schema validation.

## Day 4 — Embeddings and Semantic Search
Generate EmbeddingGemma vectors, compare similarity, store/retrieve a small vector set.
Break with ambiguous query/unrelated document/misleading nearest neighbor.
KARMO mapping: Qdrant + semantic memory.

## Day 5 — RAG
Build mini ingest, chunking, retrieval, evidence-backed answer.
Break bad chunk size/stale data/irrelevant retrieval.
KARMO mapping: H0.0-H0.4.

## Day 6 — Agents and Workers
Build minimal agent loop and local worker simulation.
Break timeout/duplicate job/failed tool.
KARMO mapping: Core v2 + Worker Runtime.

## Day 7 — Security + Architecture Challenge
Run prompt-injection/tool-abuse/approval tests.
Draw KARMO from memory.
Final question: “If we were designing KARMO again today, what would I keep, change, or question?”

# Monthly Deliverables
Month 1: local model + safe Python tool runner
Month 2: mini RAG system
Month 3: tool-calling agent
Month 4: MCP integration
Month 5: retrieval benchmark
Month 6: activation/steering experiment
Month 7: LoRA fine-tune
Month 8: evaluation harness
Month 9: adversarial AI-security lab
Month 10: multi-worker simulation
Month 11: production packaging
Month 12: useful BloomBoss/KARMO capability

# Learning Rules
1. Natalie writes code, not only reads it.
2. ChatGPT does not immediately reveal every answer.
3. Claude can build larger scaffolding, but Natalie must understand the part being studied.
4. Every experiment exposes inputs, outputs, failure modes, and verification.
5. Unexpected behavior is investigated before prompts are blindly changed.
6. Prefer real software over toy slides.
7. Use local/open models whenever practical.
8. No KARMO production changes as part of education unless separately approved under KARMO governance.
9. Learning experiments use isolated branches/workspaces.
10. Evidence decides whether KARMO architecture should change.

# Tool Exposure Checklist
AI/model: Ollama, Qwen, Llama, EmbeddingGemma, Hugging Face Transformers, tokenizers, sentence-transformers, PEFT/LoRA, PyTorch, MLX where practical.

Agent/integration: native function/tool calling, MCP, JSON Schema, Pydantic, tool registries, approval engines, agent loops.

Data/retrieval: PostgreSQL, Qdrant, vector search, BM25, hybrid retrieval, reranking.

Engineering: Python, Jupyter, pytest, Git, GitHub, Claude Code, ChatGPT, Docker, shell/zsh, logging/profiling.

Security: sandbox tests, malformed input, path traversal, prompt injection, replay/idempotency, secrets, permissions/approvals.

# Progress Levels
Level 1 — Understand: explain components.
Level 2 — Use: operate tools and write small experiments.
Level 3 — Debug: locate failures and reason about causes.
Level 4 — Design: propose architectures and tradeoffs.
Level 5 — Challenge: critically review another engineer/AI's design.
Level 6 — Lead: define requirements, security boundaries, evaluation criteria, and production architecture.

Target: Level 5-6 in applied AI/agent systems engineering.

# Immediate Next Lesson
Day 1 resumes with a real Python + local-model lab:
1. inspect the local environment,
2. make a Python call to a local model,
3. receive structured output,
4. validate it,
5. refuse an unauthorized action,
6. modify the code yourself,
7. explain what the control layer protected.

No production access is needed.

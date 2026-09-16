# KARMO Worker Model Inference Routing — Scope

Status: **DESIGN ONLY. Not implemented, not approved for implementation.**
Produced 2026-09-16 at Kamara's explicit request to scope this work after
Worker01/Worker02 were given real local models
(see "Worker model activation" in `docs/project-state/CURRENT_STATE.md`).
This document does not authorize building anything described here.

## 1. The gap this closes

Worker01/Worker02 now run a `karmo-ollama` container hosting the same 4
models Core uses (`qwen3:8b`, `ministral-3:8b`, `mistral:7b`,
`granite3.3:2b`), functionally verified. But `core_service.operator`'s
`ModelRouter`/`OllamaChatClient` only ever calls `karmo-ai01`'s own
loopback Ollama — nothing in KARMO today can actually ask a worker to run
inference. The models are installed and idle.

## 2. System-Fit Review

```text
Goal served: relieve karmo-ai01's 8GB RAM pressure (the exact problem
  named in the 2026-09-13 activation checkpoint) by giving KARMO a way to
  route some inference load to Worker01/Worker02's own models.
Existing capability reused: the Worker Runtime job/ticket/approval
  pipeline already proven for Commander (capability_manifest.py,
  job_protocol.py, ApprovalEngine, ExecutionTicketAuthority,
  ResultAuthenticator) -- adding one new capability_id, not a new
  transport or a new trust mechanism.
New software/services added: none. No new listener, no new daemon, no
  new credential type.
Important current-system facts: OllamaChatClient is deliberately
  loopback-only and refuses remote endpoints (PR #37's stated boundary,
  "no remote model endpoint," reinforced by the HTTP-redirect refusal
  fix). Worker Ollama containers are loopback-bound on the workers
  themselves (verified via ss -H -lntu during activation).
Main risks/lifecycle burden: CPU-only inference on generic 8-vCPU VMs
  (no GPU) on all three hosts, so absolute latency stays slow regardless
  (tens of seconds per response). Benchmarked 2026-09-16 (section 6.1):
  both workers run ~13% faster per-token than karmo-ai01 (3.9 vs 3.5
  tok/s), consistent with each other -- confirms the RAM-pressure theory
  and validates the premise, but a routing policy still needs its own
  design (queueing, concurrency, what happens if a worker is mid-Commander-job).
Simpler alternative considered: relaxing OllamaChatClient to allow the
  worker's Tailscale/LAN-reachable Ollama port directly. Rejected --
  that would require exposing each worker's Ollama beyond loopback (a
  real new listener + a real weakening of an existing, deliberate
  security boundary) purely for convenience. The job-dispatch approach
  below reaches the same result with zero new network exposure anywhere,
  by carrying the prompt/response over the SSH transport Commander
  already uses.
Decision: PROCEED WITH CONSTRAINTS -- see phased plan below. Phase 1
  (capability + handler) is low-risk and matches existing patterns
  closely. Phase 2 (when/how Core actually uses it) is a policy decision
  that needs a real benchmark first, not a default.
```

## 3. Architecture

### 3.1 New worker capability: `model_chat`

Add to `worker-runtime/app/capability_manifest.py`'s `SAFE_CAPABILITIES`,
same shape as every existing entry (mirrors `local_model_probe` almost
exactly, since both are "ask the worker's own loopback Ollama something
and return it"):

```python
"model_chat": dict(
    capability_id="model_chat",
    version="1.0.0",
    authority_class=CapabilityClass.READ,   # pure request/response, no
                                             # persistent side effect,
                                             # same class as local_model_probe
                                             # and karmolab.read_status
    side_effect_class=SideEffectClass.NONE,
    input_schema={
        "type": "object",
        "properties": {
            "model": {"type": "string", "enum": ["qwen3:8b", "ministral-3:8b", "mistral:7b", "granite3.3:2b"]},
            "prompt": {"type": "string", "maxLength": 8000},
        },
        "required": ["model", "prompt"],
    },
    output_schema={"type": "object", "properties": {"response": {"type": "string"}}},
    timeout_seconds=120,   # CPU-only generation on these VMs is slow --
                           # existing Commander capabilities use 10-15s;
                           # this needs real headroom, to be tuned after
                           # the Phase 1 benchmark below
    resource_requirements={"cpu": "high", "memory_mb": 8192},
    network_required=False,   # the handler calls 127.0.0.1:11434 from
                               # inside the worker itself -- loopback,
                               # exactly like local_model_probe already does
    secrets_required=[],
    idempotent=False,   # model output is not guaranteed identical run-to-run
    retry_policy={"max_attempts": 1, "backoff": "none"},
),
```

`READ` class computes to `NONE` approval floor (same as
`local_model_probe`, `karmolab.read_status`) — no human-in-the-loop step
needed per call, consistent with "generating text has no persistent
side effect" being the existing classification principle throughout this
codebase. If Kamara wants a stricter floor for this specific capability
despite that reasoning, that's a one-line override in the manifest, not
a design change.

### 3.2 Handler (`worker-runtime/app/capabilities.py`)

```python
def _model_chat(payload, *, sandbox_root, allowed_root, timeout_seconds):
    body = json.dumps({"model": payload["model"], "prompt": payload["prompt"], "stream": False}).encode()
    req = urllib.request.Request(
        "http://127.0.0.1:11434/api/generate", data=body,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
        result = json.loads(resp.read())
    output = {"response": result["response"]}
    return output, f"model_chat: {payload['model']} ({len(result['response'])} chars)", []

register_handler("model_chat", _model_chat)
```

Runs inside the same forked-child sandbox every capability already runs
in (`sandbox.run_capability`), so the existing real-deadline/kill-on-
overrun behavior and `MAX_RESULT_BYTES` (64KB — plenty for a chat
response) bound it automatically. No new sandboxing code needed.

### 3.3 How a request reaches the worker at all

Core never opens a connection to a worker's Ollama port. It creates a
job the exact same way Commander jobs are created today — through the
existing coordinator/approval/ticket path — naming `model_chat` as the
capability. The worker leases the job over the same authenticated
SSH-stdio transport already used for Commander, runs the handler
against its own loopback Ollama, and returns a signed result through the
existing `ResultAuthenticator`. The prompt and response travel over the
SSH channel, never over a new network path.

## 4. Invariant Impact Review (outline — complete formally before implementation)

- **I-01** (compatibility): additive only, no existing capability or
  contract changes.
- **I-02** (production parity): none needed — no new credential, reuses
  the existing worker gateway/ticket keys already provisioned.
- **I-03** (data authority): N/A — no persistent data written by this
  capability.
- **I-04** (idempotency): explicitly `idempotent: False` in the
  manifest; a retry is a new generation, not a duplicate side effect (matches
  the "no side effect" classification — nothing to duplicate).
- **I-05** (resources/scale): `timeout_seconds=120` and
  `resource_requirements` bound a single call; needs a real policy
  decision (queue depth? concurrent calls per worker?) before any
  production routing default — not scoped here.
- **I-06** (migration/rollback): none — no schema change.
- **I-07** (observability): job/ticket/result already flow through the
  existing invocation ledger pattern; no new audit mechanism needed.
- **I-08** (validation): targeted worker-runtime tests + the existing
  Commander-style adversarial cases (wrong worker, replayed ticket,
  oversized prompt) before merge.
- **I-09** (authority): `READ`/`NONE` floor, computed not declared, same
  mechanism as every other capability — no new authority path invented.

## 5. Explicitly NOT scoped here (separate future decisions)

- **When Core should actually prefer a worker over local inference** —
  needs the Phase 1 benchmark below before any policy is chosen. Do not
  assume "offload to workers" is faster; CPU-only VMs may well be slower
  than karmo-ai01 for the same model.
- **A CLI/chat surface for triggering it** — e.g. a `karmo worker-chat
  <worker_id> "<prompt>"` command, or `ModelRouter` gaining worker-backed
  `ModelResource` entries. Either is straightforward once the capability
  exists, but is a separate, smaller decision.
- **Whether the verifier-model step should ever run on a worker** — the
  primary/verifier distinctness check (`operator.py`'s `_models()`)
  would need its own thought if one of the pair moves off `karmo-ai01`.
- **Any change to `OllamaChatClient` itself** — none is needed or
  proposed; it stays exactly as hardened tonight (loopback-only, no
  remote endpoint, redirect-refusing).

## 6. Phased implementation plan (for a future, separately-authorized session)

1. ~~**Benchmark first, before writing capability code**~~ — **done,
   2026-09-16.** Identical prompt (`qwen3:8b`, "Explain photosynthesis in
   exactly two sentences"), `eval_count`/`eval_duration` read directly
   from Ollama's own response, not wall-clock (which includes SSH/model
   variable-length-response noise):

   | Host | tokens | eval time | tok/s |
   |---|---|---|---|
   | `karmo-ai01` | 432 | 124.6s | 3.47 |
   | Worker01 | 229 | 58.2s | 3.94 |
   | Worker02 | 289 | 73.6s | 3.93 |

   Both workers are ~13% faster per-token than `karmo-ai01`, and
   consistent with each other (3.94 vs 3.93) — exactly what the "8GB RAM
   materially saturates" theory predicts: `karmo-ai01` is memory-
   constrained, the workers aren't. This validates the premise:
   offloading here would help, not just relieve RAM pressure at a speed
   cost. All three numbers are slow in absolute terms (CPU-only
   inference, no GPU on any of the three) — a worker-routed call should
   still budget for tens of seconds per response, not sub-second.
2. **Phase 1 — capability + handler**: the manifest entry and handler
   above, targeted tests (successful call, timeout enforcement, oversized
   prompt refusal, wrong-model refusal), System-Fit Review already done
   above, formal Invariant Impact Review completed in full.
3. **Phase 2 — Core-side trigger**: the smallest surface that proves the
   round trip end-to-end (likely a CLI command, not silently changing
   `chat`'s existing routing) — dispatch a `model_chat` job to a named
   worker, wait for the signed result, print it.
4. **Phase 3 — routing policy** (only if Phase 1's benchmark justifies
   it): teach `ModelRouter` about worker-backed resources and a real
   load/latency-aware routing rule — its own separately-scoped decision,
   not assumed here.

Stop after Phase 1/2 and report back rather than proceeding to Phase 3
automatically — Phase 3 is a policy choice, not a technical completion
task.

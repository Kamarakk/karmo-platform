"""Core-side glue for KARMO's local coding helper -- dispatches a coding
question to a worker's existing model_chat capability, running
qwen2.5-coder:7b, instead of qwen3:8b or mistral:7b.

Verified live 2026-09-20: Worker01 pulled qwen2.5-coder:7b (4.68GB),
answered a real Fibonacci-function request correctly in 45.05s, using
~5.2GB RAM with ~4.5GB still free afterward.

Deliberately reuses the existing model_chat capability (worker-runtime's
_ALLOWED_MODEL_CHAT_MODELS now includes qwen2.5-coder:7b) rather than
inventing a new worker-side handler -- "ask a different model" is exactly
what model_chat already does; only the model name changes.

Wired into _CHAT_EXPOSED_TOOLS as of 2026-09-20 -- unlike vision/ears/
voice, a coding question is plain text already flowing through the
existing chat interface, no client-surface gap. It fails cleanly with
"worker dispatch is not activated" until worker_dispatch_client.available
is true (the Phase D2 DSN, still not created) AND
operator.D2_CHAT_ROUTING_ENABLED_FILE-style decoupling doesn't apply
here -- this is a direct capability dispatch, not D2's own chat-routing
decision, so it only needs worker_dispatch_client.available, same as
vision/ears/voice.
"""

from __future__ import annotations

ASK_LOCAL_CODER_TOOL = "karmo.local.ask_coder"
ASK_LOCAL_CODER_TOOL_VERSION = "1.0.0"

CODE_ASSIST_MODEL = "qwen2.5-coder:7b"
_MODEL_CHAT_TOOL_ID = "model_chat"
_MODEL_CHAT_TOOL_VERSION = "1.0.0"
_DEFAULT_WORKER_ID = "KARMO-WORKER01"

MAX_QUESTION_CHARS = 4000


class CodeAssistCapabilityError(RuntimeError):
    pass


def manifest() -> dict:
    return {
        "tool_id": ASK_LOCAL_CODER_TOOL,
        "domain": "local-helper",
        "version": ASK_LOCAL_CODER_TOOL_VERSION,
        "description": (
            "Ask KARMO's own local coding-specialized model (qwen2.5-coder:7b, running on "
            "a worker) a coding question -- writing, explaining, or debugging code. Local, "
            "not Claude or GPT. Use ask_claude/ask_gpt only when this isn't enough."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"question": {"type": "string", "maxLength": MAX_QUESTION_CHARS}},
            "required": ["question"],
            "additionalProperties": False,
        },
        "output_schema": {"type": "object", "properties": {"answer": {"type": "string"}}},
        "capability_class": "READ",
        "read_scope": "none -- dispatches to a worker's own loopback Ollama only",
        "write_scope": "none",
        "external_side_effects": "one dispatched job to a worker via the existing worker-coordination path",
        "financial_action": False,
        "destructive_action": False,
        "network_requirements": "none from Core's perspective -- LAN dispatch to an already-authenticated worker",
        "secret_requirements": "none beyond the existing worker-dispatch DSN, when provisioned",
        "invocation_identity": "karmo-chat-model",
        "timeout_seconds": 90,
        "retry_policy": "none",
        "idempotent": False,
        "idempotency_mechanism": "not idempotent; each call is a live model invocation on a worker",
        "rollback_or_compensation": "not applicable",
        "health_check": "invoke with a trivial question and confirm a non-empty answer",
        "deprecation_policy": "explicit version replacement",
        "dependencies": "worker_dispatch_client.available (requires /etc/karmo/core/worker-dispatch.dsn -- see vision_capability.py for why this is not yet created)",
        "observability": "structured operator response",
        "failure_isolation": "a dispatch failure or timeout refuses cleanly, never hangs the chat turn",
    }


def dispatch_code_assist(
    worker_dispatch_client,
    *,
    worker_id: str,
    question: str,
    total_deadline_seconds: float = 90.0,
) -> str:
    """Dispatches one model_chat job (qwen2.5-coder:7b) to worker_id and
    returns the response text, or raises CodeAssistCapabilityError with a
    clean, honest reason."""
    if not isinstance(question, str) or not question.strip():
        raise CodeAssistCapabilityError("question must be non-empty text")
    if len(question) > MAX_QUESTION_CHARS:
        raise CodeAssistCapabilityError(f"question exceeds {MAX_QUESTION_CHARS} characters")
    if not worker_dispatch_client.available:
        raise CodeAssistCapabilityError(
            "worker dispatch is not activated -- no worker-dispatch DSN configured"
        )

    outcome = worker_dispatch_client.dispatch(
        worker_id=worker_id,
        tool_id=_MODEL_CHAT_TOOL_ID,
        tool_version=_MODEL_CHAT_TOOL_VERSION,
        arguments={"model": CODE_ASSIST_MODEL, "prompt": question},
        total_deadline_seconds=total_deadline_seconds,
    )
    if outcome.outcome != "SUCCEEDED" or not isinstance(outcome.result, dict):
        raise CodeAssistCapabilityError(f"{outcome.outcome}: {outcome.error}")
    response = outcome.result.get("response")
    if not isinstance(response, str):
        raise CodeAssistCapabilityError("worker returned an invalid model_chat result")
    return response


def handler(worker_dispatch_client, *, worker_id: str = _DEFAULT_WORKER_ID):
    """Returns a dispatcher-bindable (arguments) -> dict handler closure,
    same shape as orchestration.py's create_task_handler(task_store) --
    the dependency (here, worker_dispatch_client) is captured at bind
    time in KarmoOperator.__init__, not passed through tool-call
    arguments."""
    def _handler(arguments: dict) -> dict:
        question = arguments.get("question")
        answer = dispatch_code_assist(worker_dispatch_client, worker_id=worker_id, question=question)
        return {"answer": answer}
    return _handler

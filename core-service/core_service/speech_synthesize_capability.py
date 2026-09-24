"""Core-side glue for KARMO's local voice -- dispatches text to a worker's
synthesize_speech capability (worker-runtime/app/capabilities.py, Piper)
and waits for the resulting audio, via the same worker_dispatch_client
used by vision_capability.py and audio_transcribe_capability.py.

Verified live 2026-09-20: Worker01, Piper (2023.11.14-2, en_US-amy-medium
voice), loaded in 0.27s, real-time factor 0.042 (0.14s inference for
3.27s of resulting audio) -- comfortably faster than real-time on this
CPU-only hardware.

Same two honest scope boundaries as vision/ears: NOT wired into
_CHAT_EXPOSED_TOOLS (needs a real audio *output* path -- browser speaker,
phone -- that doesn't exist yet, Phase V3 of the roadmap), and NOT
activated (requires worker_dispatch_client.available, gated on the same
Phase D2 worker-dispatch DSN documented in vision_capability.py).
"""

from __future__ import annotations

SYNTHESIZE_SPEECH_TOOL_ID = "synthesize_speech"
SYNTHESIZE_SPEECH_TOOL_VERSION = "1.0.0"
_DEFAULT_WORKER_ID = "KARMO-WORKER01"

MAX_TEXT_CHARS = 2000


class SpeechSynthesizeCapabilityError(RuntimeError):
    pass


def manifest() -> dict:
    return {
        "tool_id": SYNTHESIZE_SPEECH_TOOL_ID,
        "domain": "audio",
        "version": SYNTHESIZE_SPEECH_TOOL_VERSION,
        "description": (
            "Synthesize speech audio from text using KARMO's own local text-to-speech "
            "engine (Piper), running on a worker -- not Claude or GPT. Requires a real "
            "audio output path; not currently reachable from chat."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "maxLength": MAX_TEXT_CHARS},
                "voice": {"type": "string", "enum": ["en_US-amy-medium"]},
            },
            "required": ["text"],
            "additionalProperties": False,
        },
        "output_schema": {"type": "object", "properties": {"audio_base64": {"type": "string"}}},
        "capability_class": "READ",
        "read_scope": "none -- dispatches to a worker's own local Piper process only",
        "write_scope": "none",
        "external_side_effects": "one dispatched job to a worker via the existing worker-coordination path",
        "financial_action": False,
        "destructive_action": False,
        "network_requirements": "none from Core's perspective -- LAN dispatch to an already-authenticated worker",
        "secret_requirements": "none beyond the existing worker-dispatch DSN, when provisioned",
        "invocation_identity": "karmo-chat-model",
        "timeout_seconds": 30,
        "retry_policy": "none",
        "idempotent": False,
        "idempotency_mechanism": "not idempotent; each call is a live model invocation on a worker",
        "rollback_or_compensation": "not applicable",
        "health_check": "invoke with trivial text, confirm non-empty audio",
        "deprecation_policy": "explicit version replacement",
        "dependencies": "worker_dispatch_client.available (requires /etc/karmo/core/worker-dispatch.dsn -- see vision_capability.py for why this is not yet created)",
        "observability": "structured operator response",
        "failure_isolation": "a dispatch failure or timeout refuses cleanly, never hangs the chat turn",
    }


def dispatch_synthesize_speech(
    worker_dispatch_client,
    *,
    worker_id: str,
    text: str,
    voice: str = "en_US-amy-medium",
    total_deadline_seconds: float = 30.0,
) -> str:
    """Dispatches one synthesize_speech job to worker_id and returns the
    resulting audio as base64 text, or raises
    SpeechSynthesizeCapabilityError with a clean, honest reason."""
    if not isinstance(text, str) or not text.strip():
        raise SpeechSynthesizeCapabilityError("text must be non-empty")
    if len(text) > MAX_TEXT_CHARS:
        raise SpeechSynthesizeCapabilityError(f"text exceeds {MAX_TEXT_CHARS} characters")
    if not worker_dispatch_client.available:
        raise SpeechSynthesizeCapabilityError(
            "worker dispatch is not activated -- no worker-dispatch DSN configured"
        )

    outcome = worker_dispatch_client.dispatch(
        worker_id=worker_id,
        tool_id=SYNTHESIZE_SPEECH_TOOL_ID,
        tool_version=SYNTHESIZE_SPEECH_TOOL_VERSION,
        arguments={"text": text, "voice": voice},
        total_deadline_seconds=total_deadline_seconds,
    )
    if outcome.outcome != "SUCCEEDED" or not isinstance(outcome.result, dict):
        raise SpeechSynthesizeCapabilityError(f"{outcome.outcome}: {outcome.error}")
    audio_base64 = outcome.result.get("audio_base64")
    if not isinstance(audio_base64, str):
        raise SpeechSynthesizeCapabilityError("worker returned an invalid synthesize_speech result")
    return audio_base64


def handler(worker_dispatch_client, *, worker_id: str = _DEFAULT_WORKER_ID):
    """Same shape/purpose as vision_capability.handler() -- see its
    docstring for why registering this is not the same as chat-exposing
    it."""
    def _handler(arguments: dict) -> dict:
        audio_base64 = dispatch_synthesize_speech(
            worker_dispatch_client,
            worker_id=worker_id,
            text=arguments.get("text"),
            voice=arguments.get("voice", "en_US-amy-medium"),
        )
        return {"audio_base64": audio_base64}
    return _handler

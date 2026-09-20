"""Core-side glue for KARMO's local ears -- dispatches audio + optional
model choice to a worker's transcribe_audio capability (worker-runtime/
app/capabilities.py, faster-whisper) and waits for the result, via the
same worker_dispatch_client used by vision_capability.py and Model
Router Phase D2.

Verified live 2026-09-20: Worker01, faster-whisper "small" (int8),
transcribed a real 4-word test phrase exactly correctly in 3.05s (9.21s
one-time model load on the first call).

Same two honest scope boundaries as vision_capability.py:
1. NOT wired into _CHAT_EXPOSED_TOOLS -- audio needs a real capture path
   (browser mic, phone) that doesn't exist yet (Phase V3 of the
   roadmap). This is the Core-side capability a real client surface
   will call once one exists.
2. NOT activated -- requires worker_dispatch_client.available, which
   requires the Phase D2 worker-dispatch DSN, deliberately not created.
   See vision_capability.py's module docstring for why creating it is
   not a small, isolated decision.
"""

from __future__ import annotations

TRANSCRIBE_AUDIO_TOOL_ID = "transcribe_audio"
TRANSCRIBE_AUDIO_TOOL_VERSION = "1.0.0"

MAX_AUDIO_BYTES_BASE64 = 14_000_000  # ~10MB decoded, matching the worker's own cap, plus base64 overhead


class AudioTranscribeCapabilityError(RuntimeError):
    pass


def manifest() -> dict:
    return {
        "tool_id": TRANSCRIBE_AUDIO_TOOL_ID,
        "domain": "audio",
        "version": TRANSCRIBE_AUDIO_TOOL_VERSION,
        "description": (
            "Transcribe speech audio to text using KARMO's own local speech-recognition "
            "model (faster-whisper), running on a worker -- not Claude or GPT. Requires a "
            "real audio capture path; not currently reachable from chat."
        ),
        "capability_class": "READ",
        "read_scope": "none -- dispatches to a worker's own local faster-whisper process only",
        "write_scope": "none",
        "external_side_effects": "one dispatched job to a worker via the existing worker-coordination path",
        "financial_action": False,
        "destructive_action": False,
        "network_requirements": "none from Core's perspective -- LAN dispatch to an already-authenticated worker",
        "secret_requirements": "none beyond the existing worker-dispatch DSN, when provisioned",
        "dependencies": "worker_dispatch_client.available (requires /etc/karmo/core/worker-dispatch.dsn -- see vision_capability.py for why this is not yet created)",
    }


def dispatch_transcribe_audio(
    worker_dispatch_client,
    *,
    worker_id: str,
    audio_base64: str,
    model: str = "small",
    total_deadline_seconds: float = 30.0,
) -> str:
    """Dispatches one transcribe_audio job to worker_id and returns the
    transcribed text, or raises AudioTranscribeCapabilityError with a
    clean, honest reason."""
    if not isinstance(audio_base64, str) or not audio_base64.strip():
        raise AudioTranscribeCapabilityError("audio_base64 must be non-empty text")
    if len(audio_base64) > MAX_AUDIO_BYTES_BASE64:
        raise AudioTranscribeCapabilityError(f"audio_base64 exceeds {MAX_AUDIO_BYTES_BASE64} characters")
    if not worker_dispatch_client.available:
        raise AudioTranscribeCapabilityError(
            "worker dispatch is not activated -- no worker-dispatch DSN configured"
        )

    outcome = worker_dispatch_client.dispatch(
        worker_id=worker_id,
        tool_id=TRANSCRIBE_AUDIO_TOOL_ID,
        tool_version=TRANSCRIBE_AUDIO_TOOL_VERSION,
        arguments={"model": model, "audio_base64": audio_base64},
        total_deadline_seconds=total_deadline_seconds,
    )
    if outcome.outcome != "SUCCEEDED" or not isinstance(outcome.result, dict):
        raise AudioTranscribeCapabilityError(f"{outcome.outcome}: {outcome.error}")
    text = outcome.result.get("text")
    if not isinstance(text, str):
        raise AudioTranscribeCapabilityError("worker returned an invalid transcribe_audio result")
    return text

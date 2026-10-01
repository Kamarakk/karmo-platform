"""Standalone script invoked by worker-runtime's transcribe_audio capability
via subprocess, using a dedicated faster-whisper venv
(/home/karmo/karmo-vision-audio/whisper-venv on production workers) -- not
worker-runtime's own venv, since faster-whisper is a separate, optional
dependency only workers running the local ears capability need.

A separate file (rather than an inline -c string) so tests can redirect
KARMO_WHISPER_SCRIPT to a fake script that needs no real faster-whisper
install, the same env-var-override pattern _ollama_generate_url() already
uses for network calls -- required because run_capability() always
executes handlers in a spawned child process that re-imports capabilities.py
fresh and cannot see a parent-process monkeypatch, but does inherit
environment variables.

Usage: python3 whisper_transcribe_script.py <audio_path> <model_name>
Prints exactly one line of JSON to stdout: {"text": "..."}
"""

from __future__ import annotations

import json
import sys


def main() -> None:
    audio_path, model_name = sys.argv[1], sys.argv[2]
    from faster_whisper import WhisperModel

    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    # Voice notes are short and in English: skipping language detection and
    # using greedy decoding cuts CPU time with little accuracy cost.
    segments, _info = model.transcribe(audio_path, language="en", beam_size=1)
    text = " ".join(segment.text for segment in segments).strip()
    print(json.dumps({"text": text}))


if __name__ == "__main__":
    main()

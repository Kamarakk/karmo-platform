"""Fake stand-in for whisper_transcribe_script.py -- needs no real
faster-whisper install. Echoes the input audio file's own bytes back as
the "transcript", so tests can assert an exact round trip without a real
audio file or model."""

import json
import sys

audio_path, model_name = sys.argv[1], sys.argv[2]
with open(audio_path, "rb") as handle:
    content = handle.read()
print(json.dumps({"text": content.decode("utf-8"), "model_used": model_name}))

"""KARMO Worker Runtime -- capability handlers (Phase 9).

Every function here is registered against exactly one capability_id from
capability_manifest.SAFE_CAPABILITIES, via sandbox.register_handler, at
import time. No handler accepts an arbitrary path outside its
allowed_root, no handler shells out to an arbitrary command, no handler
touches production data. All read access to pre-existing files is bounded
to the explicitly-scoped allowed_root workspace via
sandbox.resolve_within_sandbox.
"""

import base64
import binascii
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import resource_discovery
from commander_readonly import bounded_text_read, directory_list, listener_snapshot, service_status, system_snapshot
from repo_intake import RepoIntakeError, scan_repo
from sandbox import SandboxError, register_handler, resolve_within_sandbox

# Prefer the worker-runtime's own venv when it exists. GitHub-hosted CI does
# not create that repo-local venv, so fall back only to the interpreter that
# is already executing this trusted KARMO process. The job payload can never
# choose or override this path.
_VENV_PYTHON = Path(__file__).resolve().parent.parent / "venv" / "bin" / "python"

# Only operationally necessary, non-secret process settings may cross into a
# capability subprocess. In particular, PYTHONPATH, tokens, cloud credentials,
# SSH agent variables, and arbitrary user environment are never inherited.
_SAFE_ENV_KEYS = ("PATH", "LANG", "LC_ALL", "LC_CTYPE", "TZ", "TMPDIR")

# KarmoLab document processing is deliberately a bounded proving capability,
# not a general file-ingestion path. Refuse oversized inputs before read_text()
# allocates memory so a workspace file cannot turn a READ-only job into an
# unbounded-memory workload. Future real document ingestion must use its own
# governed streaming/chunking path rather than raising this ceiling casually.
MAX_DOCUMENT_BYTES = 8 * 1024 * 1024


def _trusted_python_interpreter():
    """Return a KARMO-controlled Python interpreter path.

    Production/dev prefers the Worker Runtime virtualenv. Portable test/CI
    environments may not have that venv, so the only allowed fallback is the
    current process interpreter (sys.executable), resolved to an absolute path.
    Never accepts a job-supplied path and fails closed if neither interpreter is
    executable.
    """
    candidates = (_VENV_PYTHON, Path(sys.executable).resolve())
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    raise SandboxError("no trusted executable Python interpreter is available -- refused")


def _safe_subprocess_env(source=None):
    source = os.environ if source is None else source
    env = {key: source[key] for key in _SAFE_ENV_KEYS if key in source}
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def _require_allowed_root(allowed_root):
    if allowed_root is None:
        raise SandboxError("this capability requires an allowed_root workspace to be configured")
    return Path(allowed_root)


# --- A. HASH VERIFY -------------------------------------------------------
def _hash_verify(payload, *, sandbox_root, allowed_root, timeout_seconds):
    root = _require_allowed_root(allowed_root)
    path = resolve_within_sandbox(root, payload["path"])
    if not path.is_file():
        raise SandboxError(f"file not found within allowed workspace: {payload['path']!r}")

    sha256 = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            sha256.update(block)
    digest = sha256.hexdigest()

    output = {"sha256": digest, "path": payload["path"]}
    summary = f"hash_verify: {payload['path']} -> {digest}"
    return output, summary, []


register_handler("hash_verify", _hash_verify)


# --- B. PYTEST JOB ----------------------------------------------------------
def _pytest_job(payload, *, sandbox_root, allowed_root, timeout_seconds):
    root = _require_allowed_root(allowed_root)
    test_dir = resolve_within_sandbox(root, payload["test_dir"])
    if not test_dir.is_dir():
        raise SandboxError(f"test_dir not found within allowed workspace: {payload['test_dir']!r}")

    result = subprocess.run(
        [str(_trusted_python_interpreter()), "-m", "pytest", "-v", str(test_dir)],
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        cwd=str(sandbox_root),
        env=_safe_subprocess_env(),
    )
    summary_lines = result.stdout.strip().splitlines()[-15:]
    output = {"exit_code": result.returncode, "summary": "\n".join(summary_lines)}
    return output, "\n".join(summary_lines), []


register_handler("pytest", _pytest_job)


# --- C. STATIC PYTHON VALIDATION --------------------------------------------
def _static_analysis(payload, *, sandbox_root, allowed_root, timeout_seconds):
    root = _require_allowed_root(allowed_root)
    errors = []
    checked = []

    for rel_path in payload["files"]:
        path = resolve_within_sandbox(root, rel_path)
        if not path.is_file():
            errors.append(f"{rel_path}: not found")
            continue
        result = subprocess.run(
            [str(_trusted_python_interpreter()), "-m", "py_compile", str(path)],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=_safe_subprocess_env(),
        )
        checked.append(rel_path)
        if result.returncode != 0:
            errors.append(f"{rel_path}: {result.stderr.strip()[:200]}")

    output = {"ok": len(errors) == 0, "errors": errors, "checked": checked}
    summary = f"static_analysis: {len(checked)} file(s) checked, {len(errors)} error(s)"
    return output, summary, []


register_handler("static_analysis", _static_analysis)


# --- D. REPOSITORY ANALYSIS -------------------------------------------------
def _repository_analysis(payload, *, sandbox_root, allowed_root, timeout_seconds):
    root = _require_allowed_root(allowed_root)
    repo_path = resolve_within_sandbox(root, payload["repo_path"])
    if not repo_path.is_dir():
        raise SandboxError(f"repo_path not found within allowed workspace: {payload['repo_path']!r}")

    file_count = 0
    total_bytes = 0
    max_files = 10_000

    for entry in repo_path.rglob("*"):
        if entry.is_file():
            file_count += 1
            total_bytes += entry.stat().st_size
            if file_count >= max_files:
                break

    output = {"file_count": file_count, "total_bytes": total_bytes}
    summary = f"repository_analysis: {file_count} file(s), {total_bytes} byte(s)"
    return output, summary, []


register_handler("repository_analysis", _repository_analysis)


# --- E. RESOURCE BENCHMARK --------------------------------------------------
def _resource_benchmark(payload, *, sandbox_root, allowed_root, timeout_seconds):
    iterations = min(int(payload.get("iterations", 100_000)), 5_000_000)

    start = time.monotonic()
    total = 0
    for i in range(iterations):
        total += hash(i) & 0xFFFF
    elapsed = time.monotonic() - start

    output = {"elapsed_seconds": round(elapsed, 4), "iterations": iterations, "checksum": total}
    summary = f"resource_benchmark: {iterations} iterations in {elapsed:.4f}s"
    return output, summary, []


register_handler("resource_benchmark", _resource_benchmark)


# --- Optional probes ---------------------------------------------------
def _media_probe_test(payload, *, sandbox_root, allowed_root, timeout_seconds):
    acceleration = resource_discovery.discover_acceleration()
    output = {
        "metal_available": acceleration["metal_status"] == "VERIFIED",
        "metal_support": acceleration.get("metal_support"),
    }
    return output, f"media_probe_test: metal_status={acceleration['metal_status']}", []


register_handler("media_probe_test", _media_probe_test)


def _local_model_probe(payload, *, sandbox_root, allowed_root, timeout_seconds):
    acceleration = resource_discovery.discover_acceleration()
    output = {
        "mlx_installed": acceleration["mlx_installed"],
        "ollama_installed": acceleration["ollama_installed"],
    }
    return output, (
        f"local_model_probe: mlx={acceleration['mlx_status']}, ollama={acceleration['ollama_status']}"
    ), []


register_handler("local_model_probe", _local_model_probe)


# --- MODEL CHAT -------------------------------------------------------------
# See docs/architecture/KARMO_WORKER_MODEL_INFERENCE_ROUTING.md. The handler
# calls this worker's own loopback Ollama -- never a remote endpoint -- and
# returns the completion through the same signed-result/ticket path every
# other capability already uses. Validation lives here because
# capability_manifest.py's input_schema is a declared contract, not something
# sandbox.run_capability enforces automatically (same as every other handler
# in this file).
_ALLOWED_MODEL_CHAT_MODELS = frozenset({"qwen3:8b", "mistral:7b", "qwen2.5-coder:7b"})
MAX_MODEL_CHAT_PROMPT_CHARS = 8000
_DEFAULT_OLLAMA_GENERATE_URL = "http://127.0.0.1:11434/api/generate"


def _ollama_generate_url():
    """Resolved at call time (never cached at import time) so a test running
    the real handler through the sandbox's spawn-context child -- which
    re-imports this module fresh and cannot see a monkeypatched function or
    constant from the parent process -- can still redirect the call, by
    setting an environment variable, which spawn does inherit. Production
    never sets this and always talks to the worker's own loopback Ollama."""
    return os.environ.get("KARMO_OLLAMA_GENERATE_URL", _DEFAULT_OLLAMA_GENERATE_URL)


def _call_ollama_generate(model, prompt, timeout_seconds):
    body = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode("utf-8")
    req = urllib.request.Request(
        _ollama_generate_url(),
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def _model_chat(payload, *, sandbox_root, allowed_root, timeout_seconds):
    model = payload.get("model")
    prompt = payload.get("prompt")
    if model not in _ALLOWED_MODEL_CHAT_MODELS:
        raise SandboxError(f"model not in allowed set for model_chat: {model!r}")
    if not isinstance(prompt, str) or not prompt.strip():
        raise SandboxError("prompt must be non-empty text")
    if len(prompt) > MAX_MODEL_CHAT_PROMPT_CHARS:
        raise SandboxError(f"prompt exceeds {MAX_MODEL_CHAT_PROMPT_CHARS} characters")

    try:
        result = _call_ollama_generate(model, prompt, timeout_seconds)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise SandboxError(f"model_chat call to local Ollama failed: {type(exc).__name__}: {exc}") from exc

    response_text = result.get("response", "")
    output = {"response": response_text}
    summary = f"model_chat: {model} ({len(response_text)} chars)"
    return output, summary, []


register_handler("model_chat", _model_chat)


# --- MODEL CHAT WITH TOOLS (Model Router Phase D1) ---------------------------
# See capability_manifest.py's model_chat_tools entry for why this is a
# separate capability from model_chat above, not a version bump of it.
_DEFAULT_OLLAMA_CHAT_URL = "http://127.0.0.1:11434/api/chat"
_MAX_MODEL_CHAT_TOOLS_MESSAGES = 20
_MAX_MODEL_CHAT_TOOLS_MESSAGE_CHARS = 8000
_MAX_MODEL_CHAT_TOOLS_COUNT = 10
_MAX_MODEL_CHAT_TOOLS_SCHEMA_BYTES = 8000
_VALID_MESSAGE_ROLES = frozenset({"system", "user", "assistant", "tool"})


def _ollama_chat_url():
    """Same call-time-resolved, env-var-overridable pattern as
    _ollama_generate_url() above -- required for the same reason: a spawned
    child re-imports this module fresh and cannot see a parent-process
    monkeypatch."""
    return os.environ.get("KARMO_OLLAMA_CHAT_URL", _DEFAULT_OLLAMA_CHAT_URL)


def _call_ollama_chat(model, messages, tools, timeout_seconds):
    body = {"model": model, "messages": messages, "stream": False, "think": False}
    if tools:
        body["tools"] = tools
    req = urllib.request.Request(
        _ollama_chat_url(),
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def _validate_model_chat_tools_messages(messages):
    if not isinstance(messages, list) or not messages:
        raise SandboxError("messages must be a non-empty list")
    if len(messages) > _MAX_MODEL_CHAT_TOOLS_MESSAGES:
        raise SandboxError(f"messages exceeds {_MAX_MODEL_CHAT_TOOLS_MESSAGES} entries")
    for message in messages:
        if not isinstance(message, dict) or "role" not in message or "content" not in message:
            raise SandboxError("each message must be an object with role and content")
        if message["role"] not in _VALID_MESSAGE_ROLES:
            raise SandboxError(f"invalid message role: {message.get('role')!r}")
        if not isinstance(message["content"], str):
            raise SandboxError("message content must be a string")
        if len(message["content"]) > _MAX_MODEL_CHAT_TOOLS_MESSAGE_CHARS:
            raise SandboxError(f"message content exceeds {_MAX_MODEL_CHAT_TOOLS_MESSAGE_CHARS} characters")


def _validate_model_chat_tools_tools(tools):
    if tools is None:
        return
    if not isinstance(tools, list):
        raise SandboxError("tools must be a list when provided")
    if len(tools) > _MAX_MODEL_CHAT_TOOLS_COUNT:
        raise SandboxError(f"tools exceeds {_MAX_MODEL_CHAT_TOOLS_COUNT} entries")
    if len(json.dumps(tools).encode("utf-8")) > _MAX_MODEL_CHAT_TOOLS_SCHEMA_BYTES:
        raise SandboxError(f"tools payload exceeds {_MAX_MODEL_CHAT_TOOLS_SCHEMA_BYTES} bytes")


def _model_chat_tools(payload, *, sandbox_root, allowed_root, timeout_seconds):
    model = payload.get("model")
    messages = payload.get("messages")
    tools = payload.get("tools")
    if model not in _ALLOWED_MODEL_CHAT_MODELS:
        raise SandboxError(f"model not in allowed set for model_chat_tools: {model!r}")
    _validate_model_chat_tools_messages(messages)
    _validate_model_chat_tools_tools(tools)

    try:
        result = _call_ollama_chat(model, messages, tools, timeout_seconds)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise SandboxError(f"model_chat_tools call to local Ollama failed: {type(exc).__name__}: {exc}") from exc

    message = result.get("message") or {}
    content = message.get("content", "") if isinstance(message, dict) else ""
    tool_calls = message.get("tool_calls") if isinstance(message, dict) else None
    output = {"content": content, "tool_calls": tool_calls}
    summary = f"model_chat_tools: {model} ({len(content)} chars, {len(tool_calls or [])} tool_calls)"
    return output, summary, []


register_handler("model_chat_tools", _model_chat_tools)


# --- VISION DESCRIBE (local eyes) --------------------------------------------
# KARMO's own local vision capability -- calls this worker's own loopback
# Ollama running moondream (a small, purpose-built vision model, ~1.3GB
# resident, verified live 2026-09-20: 8.13s for a real image description on
# this exact worker, ~7GB RAM still free afterward). Deliberately a separate
# capability from model_chat, not a shared "generate with optional image"
# path -- moondream is the only model this worker ever calls this way, kept
# explicit rather than letting the model list quietly grow to include a
# vision model under a generic chat capability's allow-list.
_ALLOWED_VISION_MODELS = frozenset({"moondream"})
MAX_VISION_QUESTION_CHARS = 2000
# Moondream's own images are typically well under 1MB; 5MB matches the same
# ceiling already used by ask_claude's image input (core-service), not a
# new number invented here.
MAX_VISION_IMAGE_BYTES = 5_000_000


def _vision_describe(payload, *, sandbox_root, allowed_root, timeout_seconds):
    model = payload.get("model", "moondream")
    question = payload.get("question", "Describe this image.")
    image_base64 = payload.get("image_base64")
    if model not in _ALLOWED_VISION_MODELS:
        raise SandboxError(f"model not in allowed set for vision_describe: {model!r}")
    if not isinstance(question, str) or not question.strip():
        raise SandboxError("question must be non-empty text")
    if len(question) > MAX_VISION_QUESTION_CHARS:
        raise SandboxError(f"question exceeds {MAX_VISION_QUESTION_CHARS} characters")
    if not isinstance(image_base64, str) or not image_base64.strip():
        raise SandboxError("image_base64 must be non-empty text")
    try:
        decoded_length = len(base64.b64decode(image_base64, validate=True))
    except (binascii.Error, ValueError) as exc:
        raise SandboxError("image_base64 is not valid base64") from exc
    if decoded_length == 0:
        raise SandboxError("image_base64 decoded to empty content")
    if decoded_length > MAX_VISION_IMAGE_BYTES:
        raise SandboxError(f"image exceeds {MAX_VISION_IMAGE_BYTES} bytes")

    body = json.dumps({
        "model": model,
        "prompt": question,
        "images": [image_base64],
        "stream": False,
    }).encode("utf-8")
    req = urllib.request.Request(
        _ollama_generate_url(),
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise SandboxError(f"vision_describe call to local Ollama failed: {type(exc).__name__}: {exc}") from exc

    answer = result.get("response", "")
    output = {"answer": answer}
    summary = f"vision_describe: {model} ({len(answer)} chars)"
    return output, summary, []


register_handler("vision_describe", _vision_describe)


# --- TRANSCRIBE AUDIO (local ears) -------------------------------------------
# KARMO's own local speech-to-text -- calls a dedicated faster-whisper venv
# on this worker (NOT this worker-runtime's own venv, and not Ollama --
# Ollama has no audio-model support), via subprocess, matching the existing
# _pytest_job/_static_analysis pattern of invoking a trusted interpreter.
# Verified live 2026-09-20 on Worker01: faster-whisper "small" (int8),
# model load 9.21s (first run, downloads once), a real 4-word test phrase
# transcribed exactly correctly in 3.05s.
_DEFAULT_WHISPER_PYTHON = "/home/karmo/karmo-vision-audio/whisper-venv/bin/python3"
_DEFAULT_WHISPER_SCRIPT = str(Path(__file__).resolve().parent / "whisper_transcribe_script.py")
_ALLOWED_WHISPER_MODELS = frozenset({"small"})
MAX_AUDIO_BYTES = 10_000_000  # ~10MB, generous for a short voice clip


def _whisper_python():
    """Same call-time-resolved, env-var-overridable pattern as
    _ollama_generate_url() above -- lets tests redirect this without a
    real faster-whisper install, and lets a spawned child (which
    re-imports this module fresh) still see a test override via the
    environment, which spawn does inherit."""
    return os.environ.get("KARMO_WHISPER_PYTHON", _DEFAULT_WHISPER_PYTHON)


def _whisper_script():
    """Same override pattern as _whisper_python() -- lets a test point at
    a fake script needing no real faster-whisper install."""
    return os.environ.get("KARMO_WHISPER_SCRIPT", _DEFAULT_WHISPER_SCRIPT)


def _transcribe_audio(payload, *, sandbox_root, allowed_root, timeout_seconds):
    model = payload.get("model", "small")
    audio_base64 = payload.get("audio_base64")
    if model not in _ALLOWED_WHISPER_MODELS:
        raise SandboxError(f"model not in allowed set for transcribe_audio: {model!r}")
    if not isinstance(audio_base64, str) or not audio_base64.strip():
        raise SandboxError("audio_base64 must be non-empty text")
    try:
        audio_bytes = base64.b64decode(audio_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise SandboxError("audio_base64 is not valid base64") from exc
    if not audio_bytes:
        raise SandboxError("audio_base64 decoded to empty content")
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise SandboxError(f"audio exceeds {MAX_AUDIO_BYTES} bytes")

    audio_path = Path(sandbox_root) / "input_audio.wav"
    audio_path.write_bytes(audio_bytes)

    try:
        result = subprocess.run(
            [_whisper_python(), _whisper_script(), str(audio_path), model],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=_safe_subprocess_env(),
        )
    except subprocess.TimeoutExpired as exc:
        raise SandboxError(f"transcribe_audio timed out after {timeout_seconds}s") from exc

    if result.returncode != 0:
        raise SandboxError(f"transcribe_audio subprocess failed: {result.stderr[-500:]}")
    try:
        parsed = json.loads(result.stdout.strip().splitlines()[-1])
        text = parsed["text"]
    except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
        raise SandboxError("invalid transcribe_audio output") from exc
    if not isinstance(text, str):
        raise SandboxError("invalid transcribe_audio output")

    output = {"text": text}
    summary = f"transcribe_audio: {model} ({len(text)} chars)"
    return output, summary, []


register_handler("transcribe_audio", _transcribe_audio)


# --- SYNTHESIZE SPEECH (local voice) -----------------------------------------
# KARMO's own local text-to-speech -- calls a dedicated Piper install on
# this worker via subprocess (Piper has no HTTP API, unlike Ollama, and no
# venv/import surface like faster-whisper -- it's a standalone native
# binary). Verified live 2026-09-20 on Worker01: Piper (2023.11.14-2,
# en_US-amy-medium voice) loaded in 0.27s and synthesized a real sentence
# with a measured real-time factor of 0.042 (0.14s of inference for 3.27s
# of resulting audio) -- comfortably faster than real-time on this
# CPU-only hardware.
_DEFAULT_PIPER_BINARY = "/home/karmo/karmo-vision-audio/piper/piper/piper"
_DEFAULT_PIPER_VOICE_MODEL = "/home/karmo/karmo-vision-audio/piper/piper/en_US-amy-medium.onnx"
_ALLOWED_PIPER_VOICES = frozenset({"en_US-amy-medium"})
MAX_SPEECH_TEXT_CHARS = 2000


def _piper_binary():
    return os.environ.get("KARMO_PIPER_BINARY", _DEFAULT_PIPER_BINARY)


def _piper_voice_model():
    return os.environ.get("KARMO_PIPER_VOICE_MODEL", _DEFAULT_PIPER_VOICE_MODEL)


def _piper_subprocess_env():
    """Piper dynamically links against libonnxruntime/libpiper_phonemize/
    libespeak-ng shipped alongside its own binary -- it needs
    LD_LIBRARY_PATH pointed at that same directory to find them, the one
    real exception to every other handler's plain _safe_subprocess_env().
    Deliberately its own function rather than widening the shared
    allowlist for every other capability that doesn't need this."""
    env = _safe_subprocess_env()
    env["LD_LIBRARY_PATH"] = str(Path(_piper_binary()).resolve().parent)
    return env


def _synthesize_speech(payload, *, sandbox_root, allowed_root, timeout_seconds):
    text = payload.get("text")
    voice = payload.get("voice", "en_US-amy-medium")
    if voice not in _ALLOWED_PIPER_VOICES:
        raise SandboxError(f"voice not in allowed set for synthesize_speech: {voice!r}")
    if not isinstance(text, str) or not text.strip():
        raise SandboxError("text must be non-empty")
    if len(text) > MAX_SPEECH_TEXT_CHARS:
        raise SandboxError(f"text exceeds {MAX_SPEECH_TEXT_CHARS} characters")

    output_path = Path(sandbox_root) / "output_speech.wav"
    try:
        result = subprocess.run(
            [_piper_binary(), "--model", _piper_voice_model(), "--output_file", str(output_path)],
            input=text,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=_piper_subprocess_env(),
        )
    except subprocess.TimeoutExpired as exc:
        raise SandboxError(f"synthesize_speech timed out after {timeout_seconds}s") from exc
    except OSError as exc:
        raise SandboxError(f"synthesize_speech subprocess failed: {exc}") from exc

    if result.returncode != 0 or not output_path.is_file():
        raise SandboxError(f"synthesize_speech subprocess failed: {result.stderr[-500:]}")

    audio_bytes = output_path.read_bytes()
    if not audio_bytes:
        raise SandboxError("synthesize_speech produced an empty audio file")

    output = {"audio_base64": base64.b64encode(audio_bytes).decode("ascii")}
    summary = f"synthesize_speech: {voice} ({len(audio_bytes)} bytes)"
    return output, summary, []


register_handler("synthesize_speech", _synthesize_speech)


def _document_processing_test(payload, *, sandbox_root, allowed_root, timeout_seconds):
    """Synthetic chunking simulation for the bounded document job path."""
    root = _require_allowed_root(allowed_root)
    path = resolve_within_sandbox(root, payload["path"])
    if not path.is_file():
        raise SandboxError(f"file not found within allowed workspace: {payload['path']!r}")

    file_size = path.stat().st_size
    if file_size > MAX_DOCUMENT_BYTES:
        raise SandboxError(
            f"document input is too large ({file_size} bytes > {MAX_DOCUMENT_BYTES} cap) -- refused"
        )

    text = path.read_text(encoding="utf-8")
    chunk_size = 200
    chunk_count = max(1, (len(text) + chunk_size - 1) // chunk_size)

    output = {"chunk_count": chunk_count, "char_count": len(text)}
    return output, f"document_processing_test: {chunk_count} synthetic chunk(s)", []


register_handler("document_processing_test", _document_processing_test)


def _embedding_benchmark_test(payload, *, sandbox_root, allowed_root, timeout_seconds):
    """Synthetic bounded vector-op benchmark; no model weights are downloaded."""
    vector_count = min(int(payload.get("vector_count", 100)), 10_000)
    dim = 64

    start = time.monotonic()
    vectors = [
        [((hashlib.sha256(f"{i}:{j}".encode()).digest()[0]) / 255.0) for j in range(dim)]
        for i in range(vector_count)
    ]
    _ = sum(sum(a * b for a, b in zip(vectors[0], v)) for v in vectors[1:])
    elapsed = time.monotonic() - start

    output = {"elapsed_seconds": round(elapsed, 4), "vector_count": vector_count, "dim": dim}
    return output, f"embedding_benchmark_test: {vector_count} synthetic vectors in {elapsed:.4f}s", []


register_handler("embedding_benchmark_test", _embedding_benchmark_test)

# --- WEB SEARCH --------------------------------------------------------------
# Asks this worker's own loopback SearXNG for results and returns at most
# MAX_WEB_RESULTS of them, each reduced to title, http(s) link and snippet.
# Same call-time, env-overridable URL pattern as _ollama_generate_url().
_DEFAULT_SEARXNG_URL = "http://127.0.0.1:8888/search"
MAX_WEB_QUERY_CHARS = 300
MAX_WEB_RESULTS = 5
_MAX_WEB_TITLE_CHARS = 200
_MAX_WEB_SNIPPET_CHARS = 400
_MAX_WEB_URL_CHARS = 500


def _searxng_url():
    return os.environ.get("KARMO_SEARXNG_URL", _DEFAULT_SEARXNG_URL)


def _clean_text(value, limit):
    return " ".join(str(value or "").split())[:limit]


def _web_search(payload, *, sandbox_root, allowed_root, timeout_seconds):
    query = payload.get("query")
    if not isinstance(query, str) or not query.strip():
        raise SandboxError("query must be non-empty text")
    if len(query) > MAX_WEB_QUERY_CHARS:
        raise SandboxError(f"query exceeds {MAX_WEB_QUERY_CHARS} characters")
    url = _searxng_url() + "?" + urllib.parse.urlencode({"q": query.strip(), "format": "json"})
    req = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=min(timeout_seconds, 25)) as response:
            data = json.loads(response.read(2_000_000).decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise SandboxError(f"web_search call to local SearXNG failed: {type(exc).__name__}: {exc}") from exc

    results = []
    for item in data.get("results") or []:
        if not isinstance(item, dict):
            continue
        link = _clean_text(item.get("url"), _MAX_WEB_URL_CHARS)
        if not link.startswith(("https://", "http://")):
            continue
        results.append({
            "title": _clean_text(item.get("title"), _MAX_WEB_TITLE_CHARS),
            "url": link,
            "snippet": _clean_text(item.get("content"), _MAX_WEB_SNIPPET_CHARS),
        })
        if len(results) >= MAX_WEB_RESULTS:
            break
    return {"results": results}, f"web_search: {len(results)} result(s)", []


register_handler("web_search", _web_search)

# --- REPO INTAKE SCAN --------------------------------------------------------
# Reads a public GitHub repository and returns a verdict; never runs its
# code. See repo_intake.py for the full order of checks.
def _repo_intake_scan(payload, *, sandbox_root, allowed_root, timeout_seconds):
    try:
        report = scan_repo(payload.get("url"), Path(sandbox_root))
    except RepoIntakeError as exc:
        raise SandboxError(f"repo_intake_scan: {exc}") from exc
    return report, f"repo_intake_scan: {report['repo']} -> {report['verdict']}", []


register_handler("repo_intake_scan", _repo_intake_scan)

# Commander READ Pack v1 -- fixed handlers only; no arbitrary command dispatch.
register_handler("commander.system_snapshot", system_snapshot)
register_handler("commander.service_status", service_status)
register_handler("commander.listener_snapshot", listener_snapshot)
register_handler("commander.bounded_text_read", bounded_text_read)
register_handler("commander.directory_list", directory_list)

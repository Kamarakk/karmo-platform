"""Browser chat UI for the KARMO Core operator.

Manually started, stdlib-only development convenience -- not a systemd
service. Three allowed bind modes, chosen explicitly, never inferred:

- loopback (default): 127.0.0.1 only, reached from another machine
  through an SSH port-forward.
- tailscale: binds this host's own Tailscale interface IP (resolved via
  `tailscale ip -4`, never a caller-supplied address), reachable directly
  from any device already authenticated on the same private tailnet --
  never the open internet, never a wildcard/all-interfaces bind. Plain
  HTTP -- browsers refuse getUserMedia() (mic/camera) on any non-
  localhost origin without HTTPS, so this mode cannot use the mic/image
  features from another device (desktop or phone), only /chat.
- tailscale-https: same bind as tailscale, but additionally resolves
  this host's own tailnet DNS name (`tailscale status --json`, never a
  caller-supplied name) and provisions a real cert for it via
  `tailscale cert` (Tailscale's own Let's Encrypt-backed service for
  MagicDNS names) -- makes the origin a secure context, which the mic
  and camera features require on a phone or any other non-localhost
  device. Still never the open internet: the cert is for a name only
  resolvable and reachable inside this tailnet.

Text chat goes through the exact same KarmoOperator.handle() used by the
chat CLI -- no separate authority path, no new capability. /vision,
/transcribe, and /speak go through KarmoOperator.dispatch_vision()/
dispatch_transcribe()/dispatch_speak(), which route through the same
CapabilityDispatcher/ApprovalEngine every other KARMO capability call
uses (see vision_capability.py's module docstring for why these three
are reachable here but deliberately not through the chat tool-loop).
All four inherit the same worker-dispatch-DSN activation gate; until
that DSN is provisioned, /vision, /transcribe, and /speak fail cleanly
with a 400 "not activated" response rather than hanging or crashing.
"""

from __future__ import annotations

import json
import os
import ssl
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer

from .operator import KarmoOperator

DEFAULT_PORT = 8787
DEFAULT_BIND = "127.0.0.1"
DEFAULT_TLS_CERT_DIR = "/etc/karmo/core/tailscale-tls"
MAX_BODY_BYTES = 8_000
# Image/audio requests carry base64 payloads (up to ~7MB/~14MB decoded,
# matching vision_capability.py/audio_transcribe_capability.py's own
# caps) plus JSON/base64 overhead -- a much larger bound than plain chat
# text, but still a bound, never unbounded (I-05).
MAX_MEDIA_BODY_BYTES = 20_000_000

_PAGE = """<!doctype html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>KARMO</title>
<style>
body{font-family:monospace;max-width:720px;margin:2rem auto;padding:0 1rem;background:#111;color:#ddd}
#log{white-space:pre-wrap;line-height:1.4;margin-bottom:1rem}
.you{color:#8ab4f8}.karmo{color:#8fdc8f}.status{color:#888;font-size:0.85em}
input[type=text],input:not([type]){width:100%;padding:0.5rem;font-family:monospace;background:#222;color:#ddd;border:1px solid #444}
.row{display:flex;gap:0.5rem;align-items:center;margin-top:0.5rem;flex-wrap:wrap}
.row input[type=text]{flex:1}
button{font-family:monospace;background:#222;color:#ddd;border:1px solid #444;padding:0.6rem 0.8rem;min-height:2.5rem;cursor:pointer}
label{font-size:0.85em;color:#aaa;white-space:nowrap}
</style></head>
<body>
<div id="log"></div>
<div class="row">
  <input id="in" type="text" autofocus placeholder="Talk to KARMO...">
  <button id="mic" title="Record a voice question -- fills the box above, does not auto-send">🎤</button>
  <label><input type="checkbox" id="speak"> speak replies</label>
</div>
<div class="row">
  <input id="img" type="file" accept="image/*">
  <input id="imgq" type="text" placeholder="Ask about the image...">
  <button id="imgbtn">Describe image</button>
</div>
<script>
const log = document.getElementById('log');
const box = document.getElementById('in');
function line(cls, text) {
  const d = document.createElement('div');
  d.className = cls;
  d.textContent = text;
  log.appendChild(d);
  window.scrollTo(0, document.body.scrollHeight);
}
function blobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve(reader.result.split(',')[1]);
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}
async function speak(text) {
  const res = await fetch('/speak', {method: 'POST', body: JSON.stringify({text})});
  const data = await res.json();
  if (data.error) { line('status', 'speak error: ' + data.error); return; }
  new Audio('data:audio/wav;base64,' + data.audio_base64).play();
}
box.addEventListener('keydown', async (e) => {
  if (e.key !== 'Enter' || !box.value.trim()) return;
  const text = box.value;
  box.value = '';
  line('you', 'you> ' + text);
  const res = await fetch('/chat', {method: 'POST', body: JSON.stringify({text})});
  const data = await res.json();
  line('karmo', 'KARMO> ' + data.message);
  if (data.memory_status) line('status', 'memory=' + data.memory_status);
  if (document.getElementById('speak').checked) speak(data.message);
});

// Mic: click to start, click again to stop -- fills the text box with
// the transcript for review before sending (never auto-sends), so a
// bad transcription never silently becomes a real KARMO request.
let mediaRecorder = null;
let chunks = [];
document.getElementById('mic').addEventListener('click', async (e) => {
  const btn = e.currentTarget;
  if (mediaRecorder && mediaRecorder.state === 'recording') {
    mediaRecorder.stop();
    return;
  }
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({audio: true});
  } catch (err) {
    line('status', 'microphone access denied or unavailable: ' + err.message);
    return;
  }
  chunks = [];
  mediaRecorder = new MediaRecorder(stream);
  mediaRecorder.ondataavailable = (ev) => chunks.push(ev.data);
  mediaRecorder.onstop = async () => {
    stream.getTracks().forEach((t) => t.stop());
    btn.textContent = '🎤';
    const blob = new Blob(chunks, {type: mediaRecorder.mimeType || 'audio/webm'});
    line('status', 'transcribing...');
    const audio_base64 = await blobToBase64(blob);
    const res = await fetch('/transcribe', {method: 'POST', body: JSON.stringify({audio_base64})});
    const data = await res.json();
    if (data.error) { line('status', 'transcribe error: ' + data.error); return; }
    box.value = data.text;
    box.focus();
  };
  mediaRecorder.start();
  btn.textContent = '⏹';
});

document.getElementById('imgbtn').addEventListener('click', async () => {
  const fileInput = document.getElementById('img');
  const qBox = document.getElementById('imgq');
  const question = qBox.value.trim();
  if (!fileInput.files[0] || !question) {
    line('status', 'pick an image and type a question first');
    return;
  }
  line('you', 'you> [image] ' + question);
  const image_base64 = await blobToBase64(fileInput.files[0]);
  line('status', 'describing image...');
  const res = await fetch('/vision', {method: 'POST', body: JSON.stringify({question, image_base64})});
  const data = await res.json();
  if (data.error) { line('status', 'vision error: ' + data.error); return; }
  line('karmo', 'KARMO> ' + data.answer);
  qBox.value = '';
});
</script>
</body></html>
""".encode("utf-8")


class _Handler(BaseHTTPRequestHandler):
    operator: KarmoOperator

    def log_message(self, fmt, *args):  # noqa: A003 - stdlib signature
        return  # keep terminal output quiet; nothing here is a security log

    def do_GET(self):  # noqa: N802 - stdlib method name
        if self.path != "/":
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(_PAGE)))
        self.end_headers()
        self.wfile.write(_PAGE)

    def _read_json_body(self, max_bytes: int, required_keys: dict):
        """Reads and parses the request body, checking each key in
        required_keys (name -> expected type) is present with that type.
        Returns the parsed dict, or None after already sending a 400."""
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > max_bytes:
            self.send_response(400)
            self.end_headers()
            return None
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            for key, expected_type in required_keys.items():
                if not isinstance(payload.get(key), expected_type):
                    raise TypeError
        except (json.JSONDecodeError, AttributeError, TypeError, UnicodeDecodeError):
            self.send_response(400)
            self.end_headers()
            return None
        return payload

    def _send_json(self, status: int, obj: dict):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):  # noqa: N802 - stdlib method name
        if self.path == "/chat":
            payload = self._read_json_body(MAX_BODY_BYTES, {"text": str})
            if payload is None:
                return
            self._send_json(200, self.operator.handle(payload["text"]))
            return

        if self.path == "/vision":
            payload = self._read_json_body(
                MAX_MEDIA_BODY_BYTES, {"question": str, "image_base64": str}
            )
            if payload is None:
                return
            result = self.operator.dispatch_vision(
                question=payload["question"], image_base64=payload["image_base64"],
            )
            self._send_json(400 if "error" in result else 200, result)
            return

        if self.path == "/transcribe":
            payload = self._read_json_body(MAX_MEDIA_BODY_BYTES, {"audio_base64": str})
            if payload is None:
                return
            result = self.operator.dispatch_transcribe(audio_base64=payload["audio_base64"])
            self._send_json(400 if "error" in result else 200, result)
            return

        if self.path == "/speak":
            payload = self._read_json_body(MAX_BODY_BYTES, {"text": str})
            if payload is None:
                return
            result = self.operator.dispatch_speak(text=payload["text"])
            self._send_json(400 if "error" in result else 200, result)
            return

        self.send_response(404)
        self.end_headers()


def _resolve_tailscale_ip() -> str:
    result = subprocess.run(
        ["tailscale", "ip", "-4"],
        capture_output=True,
        text=True,
        timeout=5,
        check=True,
    )
    ip = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
    if not ip:
        raise RuntimeError("tailscale ip -4 returned no address")
    return ip


def _resolve_tailscale_dns_name() -> str:
    """This host's own tailnet MagicDNS name, e.g.
    'karmo-ai01.tailxxxxx.ts.net' -- read from `tailscale status --json`,
    never accepted as a caller-supplied argument, same discipline as
    _resolve_tailscale_ip()."""
    result = subprocess.run(
        ["tailscale", "status", "--json"],
        capture_output=True,
        text=True,
        timeout=5,
        check=True,
    )
    data = json.loads(result.stdout)
    dns_name = data.get("Self", {}).get("DNSName", "").rstrip(".")
    if not dns_name:
        raise RuntimeError("tailscale status --json returned no Self.DNSName")
    return dns_name


def _ensure_tailscale_cert(dns_name: str, cert_dir: str) -> tuple[str, str]:
    """Provisions (or renews, if `tailscale cert` decides it's due) a real
    cert for dns_name via Tailscale's own cert service, writing it under
    cert_dir. Returns (cert_path, key_path). cert_dir is created if
    missing, restricted to the owner (0700) since key_path lands there --
    defense in depth on top of whatever permissions `tailscale cert`
    itself sets on the key file."""
    os.makedirs(cert_dir, mode=0o700, exist_ok=True)
    cert_path = os.path.join(cert_dir, f"{dns_name}.crt")
    key_path = os.path.join(cert_dir, f"{dns_name}.key")
    subprocess.run(
        ["tailscale", "cert", "--cert-file", cert_path, "--key-file", key_path, dns_name],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    return cert_path, key_path


def serve(
    mode: str = "loopback",
    port: int = DEFAULT_PORT,
    cert_dir: str = DEFAULT_TLS_CERT_DIR,
) -> int:
    tls_files = None
    if mode == "loopback":
        bind = DEFAULT_BIND
    elif mode == "tailscale":
        bind = _resolve_tailscale_ip()
    elif mode == "tailscale-https":
        bind = _resolve_tailscale_ip()
        dns_name = _resolve_tailscale_dns_name()
        tls_files = _ensure_tailscale_cert(dns_name, cert_dir)
    else:
        raise ValueError(
            f"unsupported webui bind mode: {mode!r} (use 'loopback', 'tailscale', or 'tailscale-https')"
        )
    _Handler.operator = KarmoOperator()
    server = HTTPServer((bind, port), _Handler)
    scheme = "http"
    if tls_files is not None:
        cert_path, key_path = tls_files
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certfile=cert_path, keyfile=key_path)
        server.socket = context.wrap_socket(server.socket, server_side=True)
        scheme = "https"
    print(f"KARMO webui listening on {scheme}://{bind}:{port} (mode={mode})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0

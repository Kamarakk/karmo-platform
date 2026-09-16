"""Browser chat UI for the KARMO Core operator.

Manually started, stdlib-only development convenience -- not a systemd
service. Two allowed bind modes, chosen explicitly, never inferred:

- loopback (default): 127.0.0.1 only, reached from another machine
  through an SSH port-forward.
- tailscale: binds this host's own Tailscale interface IP (resolved via
  `tailscale ip -4`, never a caller-supplied address), reachable directly
  from any device already authenticated on the same private tailnet --
  never the open internet, never a wildcard/all-interfaces bind.

Every request goes through the exact same KarmoOperator.handle() used by
the chat CLI -- no separate authority path, no new capability.
"""

from __future__ import annotations

import json
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer

from .operator import KarmoOperator

DEFAULT_PORT = 8787
DEFAULT_BIND = "127.0.0.1"
MAX_BODY_BYTES = 8_000

_PAGE = b"""<!doctype html>
<html><head><meta charset="utf-8"><title>KARMO</title>
<style>
body{font-family:monospace;max-width:720px;margin:2rem auto;padding:0 1rem;background:#111;color:#ddd}
#log{white-space:pre-wrap;line-height:1.4;margin-bottom:1rem}
.you{color:#8ab4f8}.karmo{color:#8fdc8f}.status{color:#888;font-size:0.85em}
input{width:100%;padding:0.5rem;font-family:monospace;background:#222;color:#ddd;border:1px solid #444}
</style></head>
<body>
<div id="log"></div>
<input id="in" autofocus placeholder="Talk to KARMO...">
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
box.addEventListener('keydown', async (e) => {
  if (e.key !== 'Enter' || !box.value.trim()) return;
  const text = box.value;
  box.value = '';
  line('you', 'you> ' + text);
  const res = await fetch('/chat', {method: 'POST', body: JSON.stringify({text})});
  const data = await res.json();
  line('karmo', 'KARMO> ' + data.message);
  if (data.memory_status) line('status', 'memory=' + data.memory_status);
});
</script>
</body></html>
"""


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

    def do_POST(self):  # noqa: N802 - stdlib method name
        if self.path != "/chat":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > MAX_BODY_BYTES:
            self.send_response(400)
            self.end_headers()
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            text = payload["text"]
            if not isinstance(text, str):
                raise TypeError
        except (json.JSONDecodeError, KeyError, TypeError, UnicodeDecodeError):
            self.send_response(400)
            self.end_headers()
            return

        response = self.operator.handle(text)
        body = json.dumps(response).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


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


def serve(mode: str = "loopback", port: int = DEFAULT_PORT) -> int:
    if mode == "loopback":
        bind = DEFAULT_BIND
    elif mode == "tailscale":
        bind = _resolve_tailscale_ip()
    else:
        raise ValueError(f"unsupported webui bind mode: {mode!r} (use 'loopback' or 'tailscale')")
    _Handler.operator = KarmoOperator()
    server = HTTPServer((bind, port), _Handler)
    print(f"KARMO webui listening on http://{bind}:{port} (mode={mode})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0

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
import threading
import time
import zlib
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .data_map import MAX_UPLOAD_BYTES as _MAX_UPLOAD_BYTES
from .operator import KarmoOperator
from .speech_synthesize_capability import MAX_TEXT_CHARS as _SPEAK_MAX_TEXT_CHARS

DEFAULT_PORT = 8787
DEFAULT_BIND = "127.0.0.1"
DEFAULT_TLS_CERT_DIR = "/etc/karmo/core/tailscale-tls"
MAX_BODY_BYTES = 8_000
# Image/audio requests carry base64 payloads (up to ~7MB/~14MB decoded,
# matching vision_capability.py/audio_transcribe_capability.py's own
# caps) plus JSON/base64 overhead -- a much larger bound than plain chat
# text, but still a bound, never unbounded (I-05).
MAX_MEDIA_BODY_BYTES = 20_000_000
# Real bug found by review, 2026-09-24: /speak's text can be up to
# speech_synthesize_capability's own MAX_TEXT_CHARS (2000), but reusing
# plain MAX_BODY_BYTES (sized for /chat) could reject a legitimate
# max-length request once JSON-wrapped -- each character can be up to
# 4 bytes in UTF-8, and JSON string-escaping (quotes, backslashes,
# control characters) can add further bytes per character. Derived
# from the capability's own limit (never a second hardcoded number to
# drift out of sync); the x8 multiplier is a deliberately generous
# worst-case bound, not a tuned value.
MAX_SPEAK_BODY_BYTES = _SPEAK_MAX_TEXT_CHARS * 8 + 100

_PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>KARMO</title>
<meta name="theme-color" content="#0d1220">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="KARMO">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<link rel="manifest" href="/manifest.webmanifest">
<link rel="apple-touch-icon" href="/icon-180.png">
<style>
:root{
  --bg:#0d1220;--panel:#151c2e;--raise:#1d2640;--line:#2a3555;--fg:#e7ebf5;--muted:#8e9ab8;
  --accent:#f2a93b;--on-accent:#1a1206;--cool:#79b8e0;--ok:#5fd39a;--bad:#ef6b6b;--you:#263459;
  --font:-apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",Roboto,system-ui,sans-serif;
  --mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace;
  color-scheme:dark;
}
@media (prefers-color-scheme: light){:root{
  --bg:#f3f4f8;--panel:#ffffff;--raise:#eceff6;--line:#d6dbe8;--fg:#151b2c;--muted:#5b6682;
  --accent:#b8690a;--on-accent:#ffffff;--cool:#2d6f9c;--ok:#1f8a57;--bad:#c23b3b;--you:#dde5f7;color-scheme:light}}
*{box-sizing:border-box}
[hidden]{display:none!important}
html,body{height:100%;margin:0}
body{background:var(--bg);color:var(--fg);font:15px/1.5 var(--font);display:flex;flex-direction:column;
  height:100dvh;overflow:hidden;-webkit-text-size-adjust:100%}
button{font:inherit;color:inherit;cursor:pointer}
button:focus-visible,textarea:focus-visible,input:focus-visible{outline:2px solid var(--cool);outline-offset:2px}
.top{display:flex;align-items:center;justify-content:space-between;gap:10px;
  padding:calc(10px + env(safe-area-inset-top,0px)) max(14px,env(safe-area-inset-right,0px)) 10px max(14px,env(safe-area-inset-left,0px));
  border-bottom:1px solid var(--line);background:var(--bg)}
.brand{min-width:0}
.mark{font-weight:800;letter-spacing:.18em;font-size:1rem}
.health{font:.7rem var(--mono);color:var(--muted);display:flex;align-items:center;gap:6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.dot{flex:none;width:7px;height:7px;border-radius:50%;background:var(--muted)}
.health[data-s="ok"] .dot{background:var(--ok)}.health[data-s="warn"] .dot{background:var(--accent)}.health[data-s="bad"] .dot{background:var(--bad)}
.tools{display:flex;align-items:center;gap:6px}
.seg{display:flex;background:var(--raise);border-radius:999px;padding:3px;gap:2px}
.seg button{border:0;background:transparent;color:var(--muted);padding:6px 14px;border-radius:999px;font-weight:600;font-size:.82rem}
.seg button[aria-pressed="true"]{background:var(--accent);color:var(--on-accent)}
.ib{flex:none;width:36px;height:36px;border-radius:50%;border:1px solid var(--line);background:var(--panel);display:grid;place-items:center;padding:0}
.ib svg{width:18px;height:18px}
.ib[aria-pressed="true"]{border-color:var(--accent);color:var(--accent)}
main{flex:1;min-height:0;display:flex;flex-direction:column;position:relative}
#feed{flex:1;overflow-y:auto;padding:16px max(14px,env(safe-area-inset-right,0px)) 10px max(14px,env(safe-area-inset-left,0px));display:flex;flex-direction:column;gap:12px;
  -webkit-overflow-scrolling:touch}
#feed>*{width:100%;max-width:760px;margin-left:auto;margin-right:auto}
.msg{display:flex;flex-direction:column}
.msg .body{max-width:88%;padding:9px 13px;border-radius:18px;overflow-wrap:anywhere;min-width:0}
.msg.you{align-items:flex-end}
.msg.you .body{background:var(--you);border-bottom-right-radius:5px;white-space:pre-wrap}
.msg.you img{display:block;max-width:180px;max-height:180px;border-radius:12px;margin-bottom:6px}
.msg.karmo .body{background:var(--panel);border:1px solid var(--line);border-bottom-left-radius:5px}
.body p{margin:0 0 .55em}.body p:last-child{margin-bottom:0}
.body ul,.body ol{margin:.2em 0 .55em;padding-left:1.3em}
.body h4{margin:.4em 0 .3em;font-size:.95rem}
.body code{font:.85em var(--mono);background:var(--raise);padding:1px 5px;border-radius:5px}
.body pre{background:var(--raise);padding:10px;border-radius:10px;overflow-x:auto;margin:.3em 0 .55em}
.body pre code{background:none;padding:0}
.body a{color:var(--cool)}
.tbl{overflow-x:auto;margin:.3em 0 .55em}
.body table{border-collapse:collapse;font-size:.86rem;font-variant-numeric:tabular-nums}
.body th,.body td{padding:4px 8px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}
.body th{color:var(--muted);font-weight:600}
.acts{display:flex;gap:6px;margin-top:5px;flex-wrap:wrap}
.acts button,.chip{font:500 .74rem var(--font);background:var(--raise);color:var(--muted);border:0;border-radius:8px;padding:5px 9px}
.acts .done{color:var(--fg)}
.note{font:.78rem var(--mono);color:var(--muted);text-align:center}
.note[role="button"]{color:var(--accent);text-decoration:underline}
.dots i{display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--muted);margin-right:3px;animation:blink 1.2s infinite}
.dots i:nth-child(2){animation-delay:.15s}.dots i:nth-child(3){animation-delay:.3s}
@keyframes blink{0%,60%,100%{opacity:.3}30%{opacity:1}}
.saved{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:10px 12px;display:grid;gap:6px;font-size:.88rem}
.saved b{overflow-wrap:anywhere}
.saved .labels{display:flex;gap:5px;flex-wrap:wrap;align-items:center;color:var(--muted);font-size:.76rem}
.welcome{margin-top:auto;display:grid;gap:10px;padding:8px 0 4px}
.welcome h2{margin:0;font-size:1.4rem;font-weight:700}
.welcome p{margin:0;color:var(--muted)}
.quick{display:flex;gap:6px;overflow-x:auto;padding:0 max(14px,env(safe-area-inset-right,0px)) 8px max(14px,env(safe-area-inset-left,0px));scrollbar-width:none}
.quick button{flex:none;background:transparent;border:1px solid var(--line);border-radius:999px;padding:6px 12px;font-size:.8rem}
.attach{display:flex;align-items:center;gap:8px;padding:0 max(14px,env(safe-area-inset-right,0px)) 8px max(14px,env(safe-area-inset-left,0px))}
.attach img{width:44px;height:44px;object-fit:cover;border-radius:10px}
.attach span{flex:1;min-width:0;font-size:.82rem;color:var(--muted)}
.composer{display:flex;align-items:flex-end;gap:8px;
  padding:8px max(12px,env(safe-area-inset-right,0px)) calc(10px + env(safe-area-inset-bottom,0px)) max(12px,env(safe-area-inset-left,0px));
  border-top:1px solid var(--line);background:var(--bg)}
.composer textarea{flex:1;min-width:0;resize:none;max-height:140px;background:var(--panel);color:var(--fg);border:1px solid var(--line);
  border-radius:20px;padding:9px 14px;font:16px/1.35 var(--font)}
#send{background:var(--accent);color:var(--on-accent);border-color:var(--accent)}
#mic.rec{background:var(--bad);border-color:var(--bad);color:#fff}
.talkbtn{flex:none;height:36px;border-radius:999px;border:0;background:var(--accent);color:var(--on-accent);font-weight:700;font-size:.82rem;padding:0 14px;display:flex;align-items:center;gap:6px}
.talkbtn svg{width:16px;height:16px}
.sheet{position:fixed;inset:0;background:rgba(0,0,0,.45);display:flex;align-items:flex-end;justify-content:center;z-index:20}
.sheet .card{width:100%;max-width:520px;background:var(--panel);border-radius:20px 20px 0 0;
  padding:16px max(16px,env(safe-area-inset-right,0px)) calc(18px + env(safe-area-inset-bottom,0px)) max(16px,env(safe-area-inset-left,0px));display:grid;gap:10px}
.sheet h3{margin:0 0 2px;font-size:1rem}
.sheet .opt{display:flex;align-items:center;gap:12px;text-align:left;background:var(--raise);border:0;border-radius:14px;padding:12px 14px}
.sheet .opt small{display:block;color:var(--muted);font-size:.78rem}
.sheet .opt svg{flex:none;width:22px;height:22px;color:var(--accent)}
.sheet input[type=text]{width:100%;background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:12px;padding:10px 12px;font:16px var(--font)}
.sheet .cancel{background:transparent;border:0;color:var(--muted);padding:8px}
.drop{position:fixed;inset:0;z-index:30;display:grid;place-items:center;background:color-mix(in srgb,var(--bg) 80%,transparent);
  border:3px dashed var(--accent);font-size:1.2rem;font-weight:700;pointer-events:none}
#talkview{flex:1;min-height:0;display:flex;flex-direction:column;align-items:center;justify-content:space-between;gap:12px;
  padding:24px max(20px,env(safe-area-inset-right,0px)) calc(24px + env(safe-area-inset-bottom,0px)) max(20px,env(safe-area-inset-left,0px));text-align:center}
#tstate{font:600 .78rem var(--mono);letter-spacing:.16em;text-transform:uppercase;color:var(--accent)}
.orbwrap{position:relative;width:min(62vw,240px);aspect-ratio:1;display:grid;place-items:center;border:0;background:none;padding:0;border-radius:50%}
.ring{position:absolute;inset:0;border-radius:50%;border:1px solid color-mix(in srgb,var(--accent) 45%,transparent);opacity:0}
.orb{width:62%;aspect-ratio:1;border-radius:50%;--lvl:0;
  background:radial-gradient(circle at 38% 34%,color-mix(in srgb,var(--accent) 35%,#fff) 0,var(--accent) 40%,color-mix(in srgb,var(--accent) 35%,var(--bg)) 100%);
  box-shadow:0 0 50px -8px var(--accent);transform:scale(calc(1 + var(--lvl)*.35));transition:transform .08s linear}
#talkview[data-state="idle"] .orb{filter:saturate(.4);opacity:.75}
#talkview[data-state="listening"] .ring{animation:pulse 2.4s ease-out infinite}
#talkview[data-state="listening"] .ring:nth-child(2){animation-delay:.8s}
#talkview[data-state="listening"] .ring:nth-child(3){animation-delay:1.6s}
#talkview[data-state="thinking"] .orb{animation:think 1.2s ease-in-out infinite}
#talkview[data-state="speaking"] .orb{animation:speak .5s ease-in-out infinite alternate}
@keyframes pulse{0%{transform:scale(.62);opacity:.9}100%{transform:scale(1);opacity:0}}
@keyframes think{50%{opacity:.55;transform:scale(.94)}}
@keyframes speak{to{transform:scale(1.08)}}
.cap{max-width:34ch;display:grid;gap:8px;min-height:7em}
#theard{color:var(--muted);font-size:.9rem}
#tsaid{font-size:1.08rem;max-height:9em;overflow:hidden}
.tctl{display:flex;gap:14px;align-items:center}
.tctl .ib{width:52px;height:52px}
#tend{background:var(--bad);border-color:var(--bad);color:#fff}
#tools .card{max-height:88dvh;overflow-y:auto}
.ttabs{display:flex;background:var(--raise);border-radius:999px;padding:3px;gap:2px}
.ttabs button{flex:1;border:0;background:transparent;color:var(--muted);padding:6px 4px;border-radius:999px;font-weight:600;font-size:.8rem}
.ttabs button[aria-pressed="true"]{background:var(--accent);color:var(--on-accent)}
.tform{display:flex;gap:8px}
.tform input{flex:1;min-width:0;background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:12px;padding:10px 12px;font:16px var(--font)}
.tform button{flex:none;border:0;border-radius:12px;background:var(--accent);color:var(--on-accent);font-weight:700;padding:0 16px}
#tout{display:grid;gap:8px;font-size:.9rem;min-height:3em}
#tout .muted,#tout small{color:var(--muted)}
#tout iframe{width:100%;height:260px;border:1px solid var(--line);border-radius:14px;background:var(--raise)}
#tout .links{display:flex;gap:6px;flex-wrap:wrap}
#tout .links a{font:500 .78rem var(--font);background:var(--raise);color:var(--fg);border-radius:8px;padding:6px 10px;text-decoration:none}
#tout .big{font-size:2.2rem;font-weight:700;line-height:1.1}
#tout .row{display:flex;justify-content:space-between;gap:10px;padding:7px 0;border-bottom:1px solid var(--line);font-variant-numeric:tabular-nums}
#tout .row:last-child{border-bottom:0}
#tout .up{color:var(--ok)}#tout .down{color:var(--bad)}
#tout .cve{padding:8px 0;border-bottom:1px solid var(--line)}#tout .cve:last-child{border-bottom:0}
#tout .cve a{color:var(--cool);font-weight:600}
#tout .tag{font-size:.7rem;background:var(--bad);color:#fff;border-radius:6px;padding:1px 6px;margin-left:6px}
@media (prefers-reduced-motion: reduce){.ring,.orb,.dots i{animation:none!important}.orb{transition:none}}
</style></head>
<body>
<header class="top">
  <div class="brand">
    <div class="mark">KARMO</div>
    <div class="health" id="health" data-s=""><span class="dot"></span><span id="healthtext">Checking…</span></div>
  </div>
  <div class="tools">
    <button class="ib" id="opentools" title="Tools: map, weather, markets, cyber" aria-label="Open tools: map, weather, markets, cyber"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M15.5 8.5l-2 5-5 2 2-5z"/></svg></button>
    <button class="ib" id="speak" aria-pressed="false" title="Speak replies aloud" aria-label="Speak replies aloud"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 9v6h4l5 4V5L8 9z"/><path d="M16 9a4 4 0 0 1 0 6M18.5 6.5a8 8 0 0 1 0 11"/></svg></button>
    <div class="seg" role="group" aria-label="Mode">
      <button id="tabchat" aria-pressed="true">Chat</button>
      <button id="tabtalk" aria-pressed="false">Talk</button>
    </div>
  </div>
</header>
<main>
  <section id="chatview" style="display:flex;flex-direction:column;flex:1;min-height:0">
    <div id="feed" aria-live="polite"></div>
    <div class="quick" id="quick" aria-label="Quick asks">
      <button data-say="Good morning">Brief me</button>
      <button data-say="KarmoLab status">Server status</button>
      <button data-say="List my facts">My facts</button>
      <button data-fill="Remember that ">Remember…</button>
      <button id="newchat">Clear screen</button>
    </div>
    <div class="attach" id="attach" hidden><img id="attachimg" alt="Photo to ask about"><span>Photo attached. Type a question, or send to describe it.</span><button class="chip" id="attachx">Remove</button></div>
    <div class="composer">
      <button class="ib" id="plus" aria-label="Add a photo or file"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 5v14M5 12h14"/></svg></button>
      <textarea id="in" rows="1" placeholder="Message KARMO" aria-label="Message KARMO"></textarea>
      <button class="ib" id="mic" title="Record a question; it sends when you stop" aria-label="Record a voice question"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/></svg></button>
      <button class="ib" id="send" aria-label="Send" hidden><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M12 19V5M5 12l7-7 7 7"/></svg></button>
      <button class="talkbtn" id="gotalk"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="4"/><circle cx="12" cy="12" r="9"/></svg>Talk</button>
    </div>
  </section>
  <section id="talkview" data-state="idle" hidden>
    <div id="tstate">Tap the orb to talk</div>
    <button class="orbwrap" id="orb" aria-label="Start talking, or interrupt KARMO"><span class="ring"></span><span class="ring"></span><span class="ring"></span><span class="orb" id="orbcore"></span></button>
    <div class="cap"><div id="theard">KARMO listens, answers out loud, then listens again. Tap the orb to cut in.</div><div id="tsaid"></div></div>
    <div class="tctl">
      <button class="ib" id="tchat" aria-label="Back to chat">Aa</button>
      <button class="ib" id="tend" aria-label="End the conversation"><svg viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2"/></svg></button>
      <button class="ib" id="tphoto" aria-label="Ask about a photo"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 8h3l2-3h6l2 3h3v11H4z"/><circle cx="12" cy="13" r="3.5"/></svg></button>
    </div>
  </section>
</main>
<div class="sheet" id="sheet" hidden>
  <div class="card" role="dialog" aria-label="Add">
    <h3>Add to KARMO</h3>
    <button class="opt" id="optphoto"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="9" cy="10" r="2"/><path d="M21 16l-5-5-8 8"/></svg><span>Ask about a photo<small>Pick a photo, then ask what you want to know</small></span></button>
    <button class="opt" id="optcamera"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 8h3l2-3h6l2 3h3v11H4z"/><circle cx="12" cy="13" r="3.5"/></svg><span>Take a photo<small>Use the camera and ask about it</small></span></button>
    <button class="opt" id="optfile"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 3H6v18h12V7z"/><path d="M14 3v4h4M12 11v6M9 14l3-3 3 3"/></svg><span>Save files to KARMO<small>Any file type, up to __MAX_UPLOAD_MB__ MB each; KARMO files it under a label</small></span></button>
    <input id="docnote" type="text" placeholder="Note for saved files (optional), e.g. begonia for Palmstreet live">
    <button class="cancel" id="sheetx">Cancel</button>
  </div>
</div>
<div class="sheet" id="tools" hidden>
  <div class="card" role="dialog" aria-label="Tools">
    <h3>Tools</h3>
    <div class="ttabs" role="group" aria-label="Tool">
      <button data-tool="place" aria-pressed="true">Map</button>
      <button data-tool="weather" aria-pressed="false">Weather</button>
      <button data-tool="market" aria-pressed="false">Markets</button>
      <button data-tool="cyber" aria-pressed="false">Cyber</button>
    </div>
    <form class="tform" id="tform"><input id="tq" type="text" enterkeyhint="search" autocomplete="off" aria-label="Look up"><button type="submit">Go</button></form>
    <div id="tout" aria-live="polite"></div>
    <button class="cancel" id="toolsx">Close</button>
  </div>
</div>
<div class="drop" id="drop" hidden>Drop files to save them to KARMO</div>
<input id="img" type="file" accept="image/*" hidden>
<input id="cam" type="file" accept="image/*" capture="environment" hidden>
<input id="doc" type="file" multiple hidden>
<script>
const $ = (id) => document.getElementById(id);
const feed = $('feed');
const box = $('in');
const MAX_UPLOAD_BYTES = __MAX_UPLOAD_BYTES__;
const LABELS = ['Personal', 'BloomBoss', 'Lab', 'Photos', 'Media', 'Archive', 'Unsorted'];

// Per-device conveniences only (KARMO's real memory lives on the server).
const local = {
  get(key, fallback) { try { const v = localStorage.getItem(key); return v === null ? fallback : JSON.parse(v); } catch (e) { return fallback; } },
  set(key, value) { try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) { /* private mode */ } },
};
let history = local.get('karmo.history', []);
function saveHistory() { history = history.slice(-150); local.set('karmo.history', history); }

// ---- Formatting: KARMO's replies are Markdown-ish text. Everything is
// HTML-escaped first, so a reply can never inject markup.
function esc(s) { return s.replace(/[&<>"']/g, (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c])); }
function inline(s) {
  return s
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>')
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
    .replace(/(^|[\s(])(https?:\/\/[^\s<)]+)/g, '$1<a href="$2" target="_blank" rel="noopener noreferrer">$2</a>');
}
const LIST = /^\s*([-*•]|\d+[.)])\s+/;
const ROW = /^\s*\|.*\|\s*$/;
function md(src) {
  const lines = esc(src || '').split('\n');
  let out = '', i = 0;
  while (i < lines.length) {
    const l = lines[i];
    if (/^```/.test(l)) {
      const code = [];
      i++;
      while (i < lines.length && !/^```/.test(lines[i])) code.push(lines[i++]);
      i++;
      out += '<pre><code>' + code.join('\n') + '</code></pre>';
    } else if (ROW.test(l) && i + 1 < lines.length && /^\s*\|?\s*:?-{2,}/.test(lines[i + 1])) {
      const cells = (r) => r.trim().replace(/^\||\|$/g, '').split('|').map((c) => inline(c.trim()));
      const head = cells(l);
      let body = '';
      i += 2;
      while (i < lines.length && ROW.test(lines[i])) body += '<tr><td>' + cells(lines[i++]).join('</td><td>') + '</td></tr>';
      out += '<div class="tbl"><table><thead><tr><th>' + head.join('</th><th>') + '</th></tr></thead><tbody>' + body + '</tbody></table></div>';
    } else if (LIST.test(l)) {
      const ordered = /^\s*\d/.test(l);
      let items = '';
      while (i < lines.length && LIST.test(lines[i])) items += '<li>' + inline(lines[i++].replace(LIST, '')) + '</li>';
      out += ordered ? '<ol>' + items + '</ol>' : '<ul>' + items + '</ul>';
    } else if (/^#{1,4}\s/.test(l)) {
      out += '<h4>' + inline(l.replace(/^#{1,4}\s+/, '')) + '</h4>';
      i++;
    } else if (!l.trim()) {
      i++;
    } else {
      const para = [inline(l)];
      i++;
      while (i < lines.length && lines[i].trim() && !/^```|^#{1,4}\s/.test(lines[i]) && !LIST.test(lines[i]) && !ROW.test(lines[i])) para.push(inline(lines[i++]));
      out += '<p>' + para.join('<br>') + '</p>';
    }
  }
  return out;
}
// What gets read aloud: the same text without Markdown symbols.
function plain(s) { return (s || '').replace(/```[\s\S]*?```/g, ' code block. ').replace(/[*#`|>_]+/g, ' ').replace(/\s+/g, ' ').trim(); }

// ---- Feed
function scrollDown() { feed.scrollTop = feed.scrollHeight; }
function note(text) {
  const d = document.createElement('div');
  d.className = 'note';
  d.textContent = text;
  feed.appendChild(d);
  scrollDown();
  return d;
}
function bubble(who) {
  const wrap = document.createElement('div');
  wrap.className = 'msg ' + who;
  const body = document.createElement('div');
  body.className = 'body';
  wrap.appendChild(body);
  feed.appendChild(wrap);
  hideWelcome();
  scrollDown();
  return {wrap, body};
}
function addYou(text, imageUrl) {
  const m = bubble('you');
  if (imageUrl) { const img = document.createElement('img'); img.src = imageUrl; img.alt = 'Your photo'; m.body.appendChild(img); }
  m.body.appendChild(document.createTextNode(text));
  return m;
}
function button(label, onclick) {
  const b = document.createElement('button');
  b.textContent = label;
  b.onclick = onclick;
  return b;
}
// Hear / copy / thumbs on a KARMO answer. Thumbs are saved on that turn's
// trace row (karmo_turn_trace) so bad answers can be found and fixed.
function karmoActions(m, text, entry) {
  const bar = document.createElement('div');
  bar.className = 'acts';
  const hear = button('▶ Hear', async () => {
    unlockAudio();
    hear.disabled = true;
    const s = makeSpeaker();
    s.finish(text);
    await s.done();
    hear.disabled = false;
  });
  bar.appendChild(hear);
  const copy = button('Copy', () => {
    navigator.clipboard.writeText(text).then(() => { copy.textContent = 'Copied'; }).catch(() => { copy.textContent = 'Copy failed'; });
  });
  bar.appendChild(copy);
  if (entry && entry.trace && !entry.rated) {
    for (const [label, rating] of [['👍', 1], ['👎', -1]]) {
      bar.appendChild(button(label, async () => {
        const res = await fetch('/feedback', {method: 'POST', body: JSON.stringify({trace_id: entry.trace, rating})});
        for (const b of bar.querySelectorAll('.rate')) b.remove();
        const done = document.createElement('span');
        done.className = 'done';
        done.textContent = res.ok ? (rating > 0 ? 'Thanks' : 'Noted, this one will be looked at') : 'Could not save rating';
        bar.appendChild(done);
        if (res.ok) { entry.rated = true; saveHistory(); }
      }));
      bar.lastChild.className = 'rate';
    }
  }
  m.wrap.appendChild(bar);
}
function addKarmo(entry) {
  const m = bubble('karmo');
  m.body.innerHTML = md(entry.text);
  karmoActions(m, entry.text, entry);
  return m;
}

// ---- Welcome screen when the feed is empty
function hideWelcome() { const w = $('welcome'); if (w) w.remove(); }
function showWelcome() {
  const h = new Date().getHours();
  const part = h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening';
  const w = document.createElement('div');
  w.className = 'welcome';
  w.id = 'welcome';
  w.innerHTML = '<h2>' + part + ', Karmo.</h2><p>Ask anything, tap + to ask about a photo or save files, or tap Talk to speak hands-free.</p>';
  feed.appendChild(w);
}

// ---- Streaming chat. /chat/stream sends one JSON object per line: {t}
// adds text, {reset} clears it (a later model round replaces it), {done} is
// the final answer and always wins over whatever was streamed.
async function streamChat(text, el, speaker, onText) {
  const res = await fetch('/chat/stream', {method: 'POST', body: JSON.stringify({text})});
  if (!res.ok || !res.body) throw new Error('HTTP ' + res.status);
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = '', shown = '', final = null;
  while (true) {
    const {value, done} = await reader.read();
    if (done) break;
    buf += decoder.decode(value, {stream: true});
    let i;
    while ((i = buf.indexOf('\n')) >= 0) {
      const raw = buf.slice(0, i);
      buf = buf.slice(i + 1);
      if (!raw.trim()) continue;
      const ev = JSON.parse(raw);
      if (ev.ping) continue;
      if (ev.reset) shown = '';
      else if (ev.t) shown += ev.t;
      else if (ev.done) final = ev;
      const now = final ? final.message : shown;
      if (now) el.innerHTML = md(now);
      if (onText) onText(now);
      if (speaker && !final) speaker.feed(shown);
      scrollDown();
    }
  }
  return final || {message: shown};
}
let speakOn = local.get('karmo.speak', false);
function setSpeak(on) { speakOn = on; $('speak').setAttribute('aria-pressed', String(on)); local.set('karmo.speak', on); }
$('speak').onclick = () => { unlockAudio(); setSpeak(!speakOn); };

async function send(text, opts = {}) {
  text = text.trim();
  if (!text) return null;
  addYou(text);
  history.push({who: 'you', text});
  saveHistory();
  const m = bubble('karmo');
  m.body.innerHTML = '<span class="dots" aria-label="KARMO is thinking"><i></i><i></i><i></i></span>';
  const speaker = opts.speaker || (speakOn ? makeSpeaker() : null);
  let data;
  try {
    data = await streamChat(text, m.body, speaker, opts.onText);
  } catch (err) {
    m.body.textContent = 'Could not reach KARMO (' + err.message + '). Check the connection and try again.';
    if (opts.onText) opts.onText('');
    return null;
  }
  const entry = {who: 'karmo', text: data.message || '', trace: data.trace_id || null};
  m.body.innerHTML = md(entry.text);
  karmoActions(m, entry.text, entry);
  if (data.memory_status && data.memory_status !== 'ACTIVE') note('Memory was ' + String(data.memory_status).toLowerCase() + ' for this answer.');
  history.push(entry);
  saveHistory();
  if (speaker) speaker.finish(entry.text);
  return data;
}

// ---- Audio out. iPhone Safari only lets audio play from a tap, and the
// spoken reply arrives many seconds later. So one player is "unlocked"
// with a silent clip during the tap, then reused for every reply.
const player = new Audio();
let audioUnlocked = false;
function unlockAudio() {
  if (audioUnlocked) return;
  audioUnlocked = true;
  player.src = 'data:audio/wav;base64,UklGRnQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YVAAAACAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgA==';
  player.play().catch(() => { audioUnlocked = false; });
}
async function fetchSpeech(text) {
  try {
    const res = await fetch('/speak', {method: 'POST', body: JSON.stringify({text})});
    const data = await res.json();
    if (data.error) { note('Could not speak: ' + data.error); return null; }
    return data.audio_base64;
  } catch (err) {
    note('Could not speak: ' + err.message);
    return null;
  }
}
function playAudio(b64) {
  return new Promise((resolve) => {
    player.onended = player.onerror = () => resolve();
    player.src = 'data:audio/wav;base64,' + b64;
    player.play().catch(() => {
      const d = note('Audio was blocked by the browser. Tap here to hear the reply.');
      d.setAttribute('role', 'button');
      d.onclick = () => player.play();
      resolve();
    });
  });
}
// /speak takes up to 2000 characters; long pieces are cut at sentence or
// word boundaries below that.
function speechPieces(text) {
  const pieces = [];
  let rest = plain(text);
  while (rest.length > 1800) {
    let cut = rest.lastIndexOf('. ', 1800);
    if (cut < 200) cut = rest.lastIndexOf(' ', 1800);
    if (cut < 200) cut = 1800;
    pieces.push(rest.slice(0, cut + 1));
    rest = rest.slice(cut + 1);
  }
  if (rest.trim()) pieces.push(rest);
  return pieces;
}
// Speaks a reply sentence by sentence while it is still streaming in, so
// the first words play long before the whole answer is ready. Speech is
// fetched one piece at a time (the worker runs one job at a time) and
// played in order; a {reset} or stop() drops whatever is still queued.
function makeSpeaker(onPlay) {
  let said = '', gen = 0, stopped = false;
  let fetching = Promise.resolve(), playing = Promise.resolve();
  function queue(text) {
    for (const piece of speechPieces(text)) {
      const g = gen;
      const audio = fetching = fetching.then(() => (g === gen && !stopped ? fetchSpeech(piece) : null));
      playing = playing.then(async () => {
        const b64 = await audio;
        if (b64 && g === gen && !stopped) {
          if (onPlay) onPlay();
          await playAudio(b64);
        }
      });
    }
  }
  return {
    feed(shown) {
      if (!shown.startsWith(said)) { gen++; said = ''; }
      const rest = shown.slice(said.length);
      let cut = -1;
      for (const m of rest.matchAll(/[.!?]["')]?\s/g)) cut = m.index + m[0].length;
      if (cut < 0 || (said && cut < 80)) return;
      queue(rest.slice(0, cut));
      said += rest.slice(0, cut);
    },
    finish(message) {
      if (!message.startsWith(said)) { gen++; said = ''; }
      queue(message.slice(said.length));
      said = message;
    },
    done() { return playing; },
    stop() {
      stopped = true;
      gen++;
      player.pause();
      if (player.onended) player.onended();
    },
  };
}

// ---- Audio in
function blobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve(reader.result.split(',')[1]);
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}
async function transcribe(blob) {
  try {
    const audio_base64 = await blobToBase64(blob);
    const res = await fetch('/transcribe', {method: 'POST', body: JSON.stringify({audio_base64})});
    return await res.json().catch(() => ({error: 'HTTP ' + res.status}));
  } catch (err) {
    return {error: err.message};
  }
}
// Chat mic: tap to start, tap again to stop; the transcript is sent to
// KARMO straight away. Chat holds no write authority, so a misheard
// question costs one answer.
let chatRec = null;
$('mic').addEventListener('click', async () => {
  unlockAudio();
  if (chatRec) { chatRec.stop(); return; }
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({audio: true});
  } catch (err) {
    note('Microphone not available: ' + err.message);
    return;
  }
  const chunks = [];
  // Speech needs little bandwidth; a low bitrate keeps voice notes small.
  const rec = new MediaRecorder(stream, {audioBitsPerSecond: 32000});
  chatRec = rec;
  const limit = setTimeout(() => { if (rec.state === 'recording') rec.stop(); }, 60000);
  rec.ondataavailable = (ev) => chunks.push(ev.data);
  rec.onstop = async () => {
    clearTimeout(limit);
    chatRec = null;
    stream.getTracks().forEach((t) => t.stop());
    $('mic').classList.remove('rec');
    const blob = new Blob(chunks, {type: rec.mimeType || 'audio/webm'});
    const status = note('Transcribing…');
    const data = await transcribe(blob);
    status.remove();
    if (data.error) { note('Could not transcribe: ' + data.error); return; }
    if (!(data.text || '').trim()) { note('Heard nothing. Try again.'); return; }
    await send(data.text);
  };
  rec.start();
  $('mic').classList.add('rec');
});

// ---- Composer
function autosize() {
  box.style.height = 'auto';
  box.style.height = Math.min(box.scrollHeight, 140) + 'px';
  const hasText = !!box.value.trim() || !!pendingImage;
  $('send').hidden = !hasText;
  $('mic').hidden = hasText;
}
box.addEventListener('input', autosize);
box.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
    e.preventDefault();
    sendFromBox();
  }
});
$('send').onclick = () => sendFromBox();
function sendFromBox() {
  unlockAudio();
  const text = box.value.trim();
  if (!text && !pendingImage) return;
  box.value = '';
  if (pendingImage) {
    const file = pendingImage;
    clearImage();
    autosize();
    askPhoto(file, text || 'What is in this photo?');
    return;
  }
  autosize();
  send(text);
}
for (const b of document.querySelectorAll('#quick [data-say]')) b.onclick = () => { unlockAudio(); send(b.dataset.say); };
for (const b of document.querySelectorAll('#quick [data-fill]')) b.onclick = () => { box.value = b.dataset.fill; autosize(); box.focus(); };
$('newchat').onclick = () => {
  if (!confirm('Clear this screen? KARMO keeps its memory; only this device’s copy of the chat is removed.')) return;
  history = [];
  saveHistory();
  feed.innerHTML = '';
  showWelcome();
};

// ---- Photos: shrunk on the phone first (phone photos are several MB; the
// vision model works at a few hundred pixels anyway), which keeps the job
// to a handful of worker round trips.
let pendingImage = null;
function shrinkImage(file, maxSide = 1280) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      const scale = Math.min(1, maxSide / Math.max(img.width, img.height));
      const canvas = document.createElement('canvas');
      canvas.width = Math.round(img.width * scale);
      canvas.height = Math.round(img.height * scale);
      canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height);
      URL.revokeObjectURL(url);
      canvas.toBlob((b) => b ? resolve(b) : reject(new Error('could not read image')), 'image/jpeg', 0.85);
    };
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error('could not read image')); };
    img.src = url;
  });
}
function attachImage(file) {
  pendingImage = file;
  $('attachimg').src = URL.createObjectURL(file);
  $('attach').hidden = false;
  autosize();
  box.focus();
}
function clearImage() { pendingImage = null; $('attach').hidden = true; }
$('attachx').onclick = () => { clearImage(); autosize(); };
async function askPhoto(file, question) {
  addYou(question, URL.createObjectURL(file));
  history.push({who: 'you', text: '[photo] ' + question});
  saveHistory();
  const m = bubble('karmo');
  m.body.innerHTML = '<span class="dots" aria-label="KARMO is looking"><i></i><i></i><i></i></span>';
  let data;
  try {
    const image_base64 = await blobToBase64(await shrinkImage(file));
    const res = await fetch('/vision', {method: 'POST', body: JSON.stringify({question, image_base64})});
    data = await res.json().catch(() => ({error: 'HTTP ' + res.status}));
  } catch (err) {
    data = {error: err.message};
  }
  if (data.error) { m.body.textContent = 'Could not read the photo: ' + data.error; return; }
  const entry = {who: 'karmo', text: data.answer || ''};
  m.body.innerHTML = md(entry.text);
  karmoActions(m, entry.text, entry);
  history.push(entry);
  saveHistory();
  if (speakOn || talk.on) { const s = makeSpeaker(); s.finish(entry.text); }
}

// ---- Saving files: KARMO detects each file's type and label and files it
// in its library (the data map); one tap on another label moves it.
function showSaved(entry) {
  const data = entry.data;
  const d = document.createElement('div');
  d.className = 'saved';
  const title = document.createElement('div');
  title.innerHTML = 'Saved to <b></b>: <b></b>';
  title.querySelectorAll('b')[0].textContent = data.label;
  title.querySelectorAll('b')[1].textContent = data.name + ' (' + data.kind + ')';
  d.appendChild(title);
  const labels = document.createElement('div');
  labels.className = 'labels';
  labels.appendChild(document.createTextNode('Wrong place? Move to'));
  for (const label of LABELS) {
    if (label === data.label) continue;
    labels.appendChild(button(label, async () => {
      const res = await fetch('/upload/relabel', {method: 'POST', body: JSON.stringify({path: data.path, label})});
      const moved = await res.json().catch(() => ({error: 'HTTP ' + res.status}));
      if (moved.error) { note('Could not move it: ' + moved.error); return; }
      entry.data = {...data, label: moved.label, path: moved.path};
      saveHistory();
      d.replaceWith(showSaved(entry));
    }));
    labels.lastChild.className = 'chip';
  }
  d.appendChild(labels);
  return d;
}
async function saveFile(file, noteText) {
  addYou('Save ' + file.name);
  const mb = (file.size / 1000000).toFixed(1);
  if (file.size > MAX_UPLOAD_BYTES) {
    note('Not saved: ' + file.name + ' is ' + mb + ' MB; the limit here is ' + (MAX_UPLOAD_BYTES / 1000000) + ' MB. Large videos go on the NAS.');
    return;
  }
  const status = note('Saving ' + file.name + ' (' + mb + ' MB)…');
  try {
    const data_base64 = await blobToBase64(file);
    const res = await fetch('/upload', {method: 'POST', body: JSON.stringify({name: file.name, data_base64, note: noteText})});
    const data = await res.json().catch(() => ({error: 'the server refused it (HTTP ' + res.status + ')'}));
    status.remove();
    if (data.error) { note('Not saved: ' + file.name + ': ' + data.error); return; }
    const entry = {who: 'saved', data};
    history.push(entry);
    saveHistory();
    feed.appendChild(showSaved(entry));
    scrollDown();
  } catch (err) {
    status.textContent = 'Not saved: ' + file.name + ': ' + err.message;
  }
}
async function saveFiles(files) {
  const noteInput = $('docnote');
  const noteText = noteInput.value.trim();
  noteInput.value = '';
  for (const file of files) await saveFile(file, noteText);
}

// ---- The + sheet, file pickers and drag-and-drop (iMac)
function openSheet() { $('sheet').hidden = false; }
function closeSheet() { $('sheet').hidden = true; }
$('plus').onclick = openSheet;
$('sheetx').onclick = closeSheet;
$('sheet').onclick = (e) => { if (e.target === $('sheet')) closeSheet(); };
$('optphoto').onclick = () => { closeSheet(); $('img').click(); };
$('optcamera').onclick = () => { closeSheet(); $('cam').click(); };
$('optfile').onclick = () => { $('doc').click(); closeSheet(); };
for (const id of ['img', 'cam']) {
  $(id).addEventListener('change', (e) => {
    const file = e.target.files[0];
    e.target.value = '';
    if (!file) return;
    if (talk.on) { askPhoto(file, 'What is in this photo?'); return; }
    attachImage(file);
  });
}
$('doc').addEventListener('change', async (event) => {
  const files = [...event.target.files];
  event.target.value = '';
  if (files.length) await saveFiles(files);
});
let dragDepth = 0;
window.addEventListener('dragenter', (e) => { if ([...(e.dataTransfer?.types || [])].includes('Files')) { dragDepth++; $('drop').hidden = false; } });
window.addEventListener('dragleave', () => { dragDepth = Math.max(0, dragDepth - 1); if (!dragDepth) $('drop').hidden = true; });
window.addEventListener('dragover', (e) => e.preventDefault());
window.addEventListener('drop', async (e) => {
  e.preventDefault();
  dragDepth = 0;
  $('drop').hidden = true;
  const files = [...(e.dataTransfer?.files || [])];
  if (files.length) { mode('chat'); await saveFiles(files); }
});

// ---- Talk: hands-free conversation. Listens until you stop speaking,
// sends what it heard, speaks the answer, then listens again. Tap the orb
// to cut in. After 10 s of silence it stops listening by itself.
const talk = {on: false, stream: null, ctx: null, an: null, rec: null, speaker: null};
function setTalk(state, label) { $('talkview').dataset.state = state; $('tstate').textContent = label; }
function level() {
  const a = new Uint8Array(talk.an.fftSize);
  talk.an.getByteTimeDomainData(a);
  let sum = 0;
  for (const v of a) { const x = (v - 128) / 128; sum += x * x; }
  return Math.sqrt(sum / a.length);
}
async function startTalk() {
  unlockAudio();
  if (!talk.ctx) {
    const AC = window.AudioContext || window.webkitAudioContext;
    talk.ctx = new AC();  // created inside the tap, as Safari requires
  }
  if (talk.ctx.state === 'suspended') talk.ctx.resume();
  try {
    talk.stream = await navigator.mediaDevices.getUserMedia({audio: {echoCancellation: true, noiseSuppression: true}});
  } catch (err) {
    setTalk('idle', 'Microphone not available');
    $('theard').textContent = err.message;
    return;
  }
  const src = talk.ctx.createMediaStreamSource(talk.stream);
  talk.an = talk.ctx.createAnalyser();
  talk.an.fftSize = 1024;
  src.connect(talk.an);
  talk.on = true;
  listen();
}
function stopTalk(label) {
  talk.on = false;
  if (talk.rec && talk.rec.state === 'recording') talk.rec.stop();
  if (talk.speaker) talk.speaker.stop();
  talk.speaker = null;
  if (talk.stream) talk.stream.getTracks().forEach((t) => t.stop());
  talk.stream = null;
  if (talk.ctx) { talk.ctx.close().catch(() => {}); talk.ctx = null; }
  $('orbcore').style.setProperty('--lvl', 0);
  setTalk('idle', label || 'Tap the orb to talk');
}
function listen() {
  if (!talk.on) return;
  setTalk('listening', 'Listening');
  const chunks = [];
  const rec = new MediaRecorder(talk.stream, {audioBitsPerSecond: 32000});
  talk.rec = rec;
  const started = performance.now();
  let heard = false, quietSince = started, floor = 0.01, idle = false;
  rec.ondataavailable = (ev) => chunks.push(ev.data);
  const tick = () => {
    if (rec.state !== 'recording') return;
    const v = level();
    const now = performance.now();
    const threshold = Math.max(0.025, floor * 3);
    if (v > threshold) { heard = true; quietSince = now; } else { floor = floor * 0.95 + v * 0.05; }
    $('orbcore').style.setProperty('--lvl', Math.min(1, v * 6).toFixed(2));
    if (heard && now - quietSince > 1300) { rec.stop(); return; }
    if (!heard && now - started > 10000) { idle = true; rec.stop(); return; }
    if (now - started > 45000) { rec.stop(); return; }
    setTimeout(tick, 60);
  };
  rec.onstop = async () => {
    talk.rec = null;
    $('orbcore').style.setProperty('--lvl', 0);
    if (!talk.on) return;
    if (idle) { stopTalk('Tap the orb to talk'); return; }
    setTalk('thinking', 'Transcribing');
    const data = await transcribe(new Blob(chunks, {type: rec.mimeType || 'audio/webm'}));
    if (!talk.on) return;
    if (data.error) { stopTalk('Tap the orb to try again'); $('theard').textContent = 'Could not transcribe: ' + data.error; return; }
    const text = (data.text || '').trim();
    if (!text) { listen(); return; }
    $('theard').textContent = '“' + text + '”';
    $('tsaid').textContent = '';
    setTalk('thinking', 'Thinking');
    const speaker = makeSpeaker(() => { if (talk.on) setTalk('speaking', 'Speaking · tap to cut in'); });
    talk.speaker = speaker;
    await send(text, {speaker, onText: (s) => { $('tsaid').textContent = plain(s).slice(-420); }});
    if (!talk.on || talk.speaker !== speaker) return;
    await speaker.done();
    if (talk.on && talk.speaker === speaker) { talk.speaker = null; listen(); }
  };
  rec.start();
  tick();
}
$('orb').onclick = () => {
  if (!talk.on) { startTalk(); return; }
  if (talk.rec && talk.rec.state === 'recording') { talk.rec.stop(); return; }  // done talking
  if (talk.speaker) { const s = talk.speaker; talk.speaker = null; s.stop(); listen(); }  // cut in
};
$('tend').onclick = () => stopTalk();
$('tchat').onclick = () => mode('chat');
$('tphoto').onclick = () => $('cam').click();

// ---- Tools: map, weather, markets, cyber. Each look-up runs on a worker
// (POST /tools); the map picture itself comes from OpenStreetMap.
const TOOL_HINT = {
  place: 'A place or address, e.g. Balboa Park',
  weather: 'A place (blank for San Diego)',
  market: 'Tickers, e.g. AAPL MSFT (blank for the big picture)',
  cyber: '',
};
let tool = local.get('karmo.tool', 'place');
if (!(tool in TOOL_HINT)) tool = 'place';
function deg(v) { return typeof v === 'number' ? Math.round(v) + '°' : '?'; }
function signed(v, suffix) { return typeof v === 'number' ? (v >= 0 ? '+' : '−') + Math.abs(v).toFixed(2) + (suffix || '') : 'n/a'; }
function link(href, label) { return '<a href="' + esc(href) + '" target="_blank" rel="noopener">' + esc(label) + '</a>'; }
function showPlace(p) {
  const pad = 0.01;
  const b = p.bbox && p.bbox.length === 4 ? p.bbox : [p.lat - pad, p.lat + pad, p.lon - pad, p.lon + pad];
  const box = [b[2], b[0], b[3], b[1]].map((n) => Number(n).toFixed(5)).join(',');
  const embed = 'https://www.openstreetmap.org/export/embed.html?bbox=' + box + '&layer=mapnik&marker=' + p.lat + ',' + p.lon;
  const q = encodeURIComponent(p.name || (p.lat + ',' + p.lon));
  return '<b>' + esc(p.name || 'Place') + '</b><small>' + p.lat + ', ' + p.lon + '</small>' +
    '<iframe title="Map" loading="lazy" referrerpolicy="no-referrer" src="' + esc(embed) + '"></iframe>' +
    '<div class="links">' + link('http://karmo-ai01.tail2d74d7.ts.net:4173/#lat=' + p.lat + '&lon=' + p.lon + '&alt=1500&pitch=-35', 'God’s Eye 3D') +
    link('https://maps.apple.com/?ll=' + p.lat + ',' + p.lon + '&q=' + q + '&t=k', 'Satellite view') +
    link('https://www.google.com/maps/search/?api=1&query=' + p.lat + ',' + p.lon, 'Google Maps') +
    link('https://www.openstreetmap.org/?mlat=' + p.lat + '&mlon=' + p.lon + '#map=16/' + p.lat + '/' + p.lon, 'OpenStreetMap') + '</div>';
}
function showWeather(w) {
  const n = w.now || {};
  let h = '<b>' + esc((w.place || '').split(',').slice(0, 2).join(',')) + '</b>' +
    '<div><span class="big">' + deg(n.temp_f) + '</span> ' + esc(n.sky || '') + '</div>' +
    '<small>Feels like ' + deg(n.feels_f) + ' · wind ' + Math.round(n.wind_mph || 0) + ' mph · humidity ' + (n.humidity ?? '?') + '%</small><div>';
  (w.days || []).forEach((d, i) => {
    const label = i === 0 ? 'Today' : i === 1 ? 'Tomorrow' : new Date(d.date + 'T12:00').toLocaleDateString(undefined, {weekday: 'long'});
    h += '<div class="row"><span>' + esc(label) + ' · ' + esc(d.sky || '') + (typeof d.rain_chance === 'number' ? ' · ' + d.rain_chance + '% rain' : '') +
      '</span><span>' + deg(d.high_f) + ' / ' + deg(d.low_f) + '</span></div>';
  });
  return h + '</div><small>Open-Meteo</small>';
}
function showMarket(m) {
  let h = '<div>';
  for (const q of m.quotes || []) {
    const cls = typeof q.change === 'number' ? (q.change >= 0 ? 'up' : 'down') : '';
    h += '<div class="row"><span>' + esc(q.name || q.symbol) + '</span><span>' +
      (typeof q.price === 'number' ? q.price.toLocaleString(undefined, {maximumFractionDigits: 2}) : '?') +
      ' <span class="' + cls + '">' + signed(q.change_pct, '%') + '</span></span></div>';
  }
  h += '</div>';
  if ((m.missing || []).length) h += '<small>No quote for ' + esc(m.missing.join(', ')) + '</small>';
  return h + '<small>Yahoo Finance, delayed. Not financial advice.</small>';
}
function showCyber(c) {
  let h = '<small>Newest actively exploited vulnerabilities</small><div>';
  for (const v of c.items || []) {
    h += '<div class="cve">' + link('https://nvd.nist.gov/vuln/detail/' + encodeURIComponent(v.cve), v.cve) +
      (v.ransomware ? '<span class="tag">ransomware</span>' : '') +
      '<div>' + esc(v.vendor + ' ' + v.product) + '</div><small>Added ' + esc(v.added) + ' · fix by ' + esc(v.due) + '</small></div>';
  }
  return h + '</div><small>CISA KEV catalog</small>';
}
async function runTool() {
  const q = $('tq').value.trim();
  if (tool === 'place' && !q) { $('tout').innerHTML = '<span class="muted">Type a place or address.</span>'; return; }
  if (tool === 'place' || tool === 'weather') local.set('karmo.tool.' + tool, q);
  $('tout').innerHTML = '<span class="dots"><i></i><i></i><i></i></span>';
  try {
    const res = await fetch('/tools', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({kind: tool, query: q})});
    const r = await res.json();
    if (r.error) throw new Error(r.error);
    $('tout').innerHTML = r.kind === 'place' ? showPlace(r.place) : r.kind === 'weather' ? showWeather(r.weather)
      : r.kind === 'market' ? showMarket(r.market) : showCyber(r.cyber);
  } catch (err) {
    $('tout').innerHTML = '<span class="muted">Couldn’t get that right now. ' + esc(String(err.message || err)).slice(0, 160) + '</span>';
  }
}
function pickTool(t) {
  tool = t;
  local.set('karmo.tool', t);
  for (const b of document.querySelectorAll('.ttabs button')) b.setAttribute('aria-pressed', String(b.dataset.tool === t));
  $('tform').hidden = t === 'cyber';
  $('tq').placeholder = TOOL_HINT[t];
  $('tq').value = local.get('karmo.tool.' + t, '');
  $('tout').innerHTML = '';
  if (t !== 'place') runTool();
}
for (const b of document.querySelectorAll('.ttabs button')) b.onclick = () => pickTool(b.dataset.tool);
$('tform').onsubmit = (e) => { e.preventDefault(); $('tq').blur(); runTool(); };
$('opentools').onclick = () => { $('tools').hidden = false; pickTool(tool); };
$('toolsx').onclick = () => { $('tools').hidden = true; };
$('tools').onclick = (e) => { if (e.target === $('tools')) $('tools').hidden = true; };

// ---- Modes
function mode(m) {
  const isTalk = m === 'talk';
  $('chatview').style.display = isTalk ? 'none' : 'flex';
  $('talkview').hidden = !isTalk;
  $('tabchat').setAttribute('aria-pressed', String(!isTalk));
  $('tabtalk').setAttribute('aria-pressed', String(isTalk));
  if (!isTalk) { if (talk.on) stopTalk(); scrollDown(); }
}
$('tabchat').onclick = () => mode('chat');
$('tabtalk').onclick = () => mode('talk');
$('gotalk').onclick = () => { mode('talk'); startTalk(); };

// ---- Header health: which brain answers, and whether memory is on.
async function checkHealth() {
  const el = $('health');
  try {
    const res = await fetch('/health', {cache: 'no-store'});
    const h = await res.json();
    const brain = h.brain === 'imac' ? 'iMac brain' : 'AI01 brain';
    const memOk = h.memory_status === 'ACTIVE';
    el.dataset.s = memOk ? (h.brain === 'imac' ? 'ok' : 'warn') : 'warn';
    $('healthtext').textContent = brain + (memOk ? ' · memory on' : ' · memory ' + String(h.memory_status || 'off').toLowerCase());
  } catch (err) {
    el.dataset.s = 'bad';
    $('healthtext').textContent = 'Can’t reach KARMO';
  }
}
checkHealth();
setInterval(checkHealth, 60000);

// ---- Restore this device's recent conversation
setSpeak(speakOn);
for (const entry of history) {
  if (entry.who === 'you') addYou(entry.text);
  else if (entry.who === 'karmo') addKarmo(entry);
  else if (entry.who === 'saved') feed.appendChild(showSaved(entry));
}
if (!history.length) showWelcome();
scrollDown();
autosize();
</script>
</body></html>
""".replace("__MAX_UPLOAD_BYTES__", str(_MAX_UPLOAD_BYTES)).replace(
    "__MAX_UPLOAD_MB__", str(_MAX_UPLOAD_BYTES // 1_000_000)).encode("utf-8")


# Lets the phone add KARMO to its home screen as a full-screen app. No
# service worker: nothing is cached, so a deploy is live on the next open.
_MANIFEST = json.dumps({
    "name": "KARMO", "short_name": "KARMO", "start_url": "/", "scope": "/",
    "display": "standalone", "background_color": "#0d1220", "theme_color": "#0d1220",
    "icons": [{"src": "/icon-180.png", "sizes": "180x180", "type": "image/png"},
              {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"}],
}).encode("utf-8")


@lru_cache(maxsize=2)
def _icon_png(size: int) -> bytes:
    """The home-screen icon, drawn here (stdlib only): an amber orb on night blue."""
    bg, orb = (13, 18, 32), (242, 169, 59)
    c, r = (size - 1) / 2, size * 0.30
    rows = []
    for y in range(size):
        row = bytearray(b"\x00")
        for x in range(size):
            d = ((x - c) ** 2 + (y - c) ** 2) ** 0.5
            a = min(1.0, max(0.0, r - d + 0.5))  # anti-aliased edge
            glow = max(0.0, 1 - (d - r) / (size * 0.18)) * 0.25 if d > r else 0.0
            k = max(a, glow)
            row += bytes(round(bg[i] + (orb[i] - bg[i]) * k) for i in range(3))
        rows.append(bytes(row))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (len(data).to_bytes(4, "big") + kind + data
                + zlib.crc32(kind + data).to_bytes(4, "big"))

    header = size.to_bytes(4, "big") * 2 + bytes([8, 2, 0, 0, 0])
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(b"".join(rows), 9)) + chunk(b"IEND", b""))


_STATIC = {
    "/manifest.webmanifest": ("application/manifest+json", lambda: _MANIFEST),
    "/icon-180.png": ("image/png", lambda: _icon_png(180)),
    "/icon-512.png": ("image/png", lambda: _icon_png(512)),
    "/favicon.ico": ("image/png", lambda: _icon_png(180)),
}


# One KARMO turn at a time (the operator and its model are not built for
# concurrent turns), while the server itself answers other requests -- the
# page, a second tab -- instead of queueing them behind a minute-long reply.
_OPERATOR_LOCK = threading.Lock()
KEEPALIVE_SECONDS = 10



_ACTOR_CACHE: dict[str, tuple[float, str | None]] = {}
_ACTOR_TTL_SECONDS = 600.0


def tailnet_actor(ip: str, *, runner=subprocess.run, clock=time.monotonic) -> str | None:
    """"device (login)" for a tailnet address via `tailscale whois`, cached
    for ten minutes; None for loopback, non-tailnet addresses or any error."""
    if not ip or ip.startswith("127.") or ip == "::1":
        return None
    cached = _ACTOR_CACHE.get(ip)
    if cached is not None and clock() - cached[0] < _ACTOR_TTL_SECONDS:
        return cached[1]
    actor = None
    try:
        done = runner(["tailscale", "whois", "--json", ip], capture_output=True, text=True, timeout=3)
        if done.returncode == 0:
            info = json.loads(done.stdout)
            device = (info.get("Node") or {}).get("ComputedName") or "unknown-device"
            login = (info.get("UserProfile") or {}).get("LoginName") or "unknown-user"
            actor = f"{device} ({login})"
    except (OSError, ValueError, subprocess.SubprocessError):
        actor = None
    _ACTOR_CACHE[ip] = (clock(), actor)
    return actor

class _Handler(BaseHTTPRequestHandler):
    operator: KarmoOperator

    def log_message(self, fmt, *args):  # noqa: A003 - stdlib signature
        return  # keep terminal output quiet; nothing here is a security log

    def do_GET(self):  # noqa: N802 - stdlib method name
        if self.path == "/health":
            self._send_json(200, self.operator.health())
            return
        if self.path in _STATIC:
            content_type, body = _STATIC[self.path]
            self._send_bytes(200, content_type, body())
            return
        if self.path != "/":
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")  # a home-screen app picks up deploys
        self.send_header("Content-Length", str(len(_PAGE)))
        self.end_headers()
        self.wfile.write(_PAGE)

    def _actor_kwargs(self) -> dict:
        """The tailnet device and login behind this request, for the turn
        trace. Never used for authorization, only to record who asked."""
        actor = tailnet_actor(self.client_address[0])
        return {"actor": actor} if actor else {}

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
        self._send_bytes(status, "application/json", json.dumps(obj).encode("utf-8"))

    def _send_bytes(self, status: int, content_type: str, body: bytes):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _stream_chat(self, text: str):
        """Same turn as /chat, but the answer's words are sent as they are
        written, one JSON object per line, ending with the full /chat result
        plus "done". The body ends when the connection closes (HTTP/1.0)."""
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.close_connection = True
        client_gone = False
        write_lock = threading.Lock()

        def send(event: dict):
            nonlocal client_gone
            with write_lock:
                if client_gone:
                    return
                try:
                    self.wfile.write(json.dumps(event).encode("utf-8") + b"\n")
                    self.wfile.flush()
                except OSError:
                    client_gone = True  # the turn still finishes and is remembered

        def on_token(piece):
            send({"reset": True} if piece is None else {"t": piece})

        # A code run or hand-off can take minutes with no words to send, and a
        # silent connection gets dropped on the way to the phone (seen live
        # 2026-10-06: the page stuck at "KARMO> ..."), so ping while waiting.
        outcome = {}
        finished = threading.Event()

        def run():
            try:
                with _OPERATOR_LOCK:
                    outcome["result"] = self.operator.handle(text, on_token=on_token, **self._actor_kwargs())
            except BaseException as exc:  # noqa: BLE001 -- re-raised below, on the request thread
                outcome["error"] = exc
            finally:
                finished.set()

        threading.Thread(target=run, daemon=True).start()
        while not finished.wait(KEEPALIVE_SECONDS):
            send({"ping": True})
        if "error" in outcome:
            raise outcome["error"]
        send({**outcome["result"], "done": True})

    def do_POST(self):  # noqa: N802 - stdlib method name
        if self.path == "/chat":
            payload = self._read_json_body(MAX_BODY_BYTES, {"text": str})
            if payload is None:
                return
            with _OPERATOR_LOCK:
                result = self.operator.handle(payload["text"], **self._actor_kwargs())
            self._send_json(200, result)
            return

        if self.path == "/chat/stream":
            payload = self._read_json_body(MAX_BODY_BYTES, {"text": str})
            if payload is None:
                return
            self._stream_chat(payload["text"])
            return

        if self.path == "/feedback":
            payload = self._read_json_body(MAX_BODY_BYTES, {"trace_id": int, "rating": int})
            if payload is None:
                return
            try:
                with _OPERATOR_LOCK:
                    saved = self.operator.rate_turn(payload["trace_id"], payload["rating"])
            except ValueError as exc:
                self._send_json(400, {"error": str(exc)})
                return
            self._send_json(200, {"saved": bool(saved)})
            return

        if self.path == "/vision":
            payload = self._read_json_body(
                MAX_MEDIA_BODY_BYTES, {"question": str, "image_base64": str}
            )
            if payload is None:
                return
            with _OPERATOR_LOCK:
                result = self.operator.dispatch_vision(
                    question=payload["question"], image_base64=payload["image_base64"],
                )
            self._send_json(400 if "error" in result else 200, result)
            return

        if self.path == "/transcribe":
            payload = self._read_json_body(MAX_MEDIA_BODY_BYTES, {"audio_base64": str})
            if payload is None:
                return
            with _OPERATOR_LOCK:
                result = self.operator.dispatch_transcribe(audio_base64=payload["audio_base64"])
            self._send_json(400 if "error" in result else 200, result)
            return

        if self.path == "/speak":
            payload = self._read_json_body(MAX_SPEAK_BODY_BYTES, {"text": str})
            if payload is None:
                return
            with _OPERATOR_LOCK:
                result = self.operator.dispatch_speak(text=payload["text"])
            self._send_json(400 if "error" in result else 200, result)
            return

        if self.path == "/tools":
            payload = self._read_json_body(MAX_BODY_BYTES, {"kind": str})
            if payload is None:
                return
            arguments = {"kind": payload["kind"]}
            if isinstance(payload.get("query"), str):
                arguments["query"] = payload["query"]
            with _OPERATOR_LOCK:
                result = self.operator.dispatch_live_info(arguments=arguments)
            self._send_json(400 if "error" in result else 200, result)
            return

        if self.path == "/upload":
            payload = self._read_json_body(MAX_MEDIA_BODY_BYTES, {"name": str, "data_base64": str})
            if payload is None:
                return
            note = payload.get("note")
            result = self.operator.store_upload(name=payload["name"], data_base64=payload["data_base64"],
                                                note=note if isinstance(note, str) else "")
            self._send_json(400 if "error" in result else 200, result)
            return

        if self.path == "/upload/relabel":
            payload = self._read_json_body(MAX_BODY_BYTES, {"path": str, "label": str})
            if payload is None:
                return
            result = self.operator.relabel_upload(path=payload["path"], label=payload["label"])
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
    missing and always chmod'd to 0700 (owner only) since key_path lands
    there -- defense in depth on top of whatever permissions
    `tailscale cert` itself sets on the key file.

    Real bug found by review, 2026-09-24: os.makedirs(mode=0o700) only
    applies that mode at creation time -- if cert_dir already exists
    with looser permissions (e.g. a manual `mkdir -p` under the default
    umask), exist_ok=True silently leaves the existing mode untouched,
    so the "restricted to the owner" claim would not actually hold.
    os.chmod() below is unconditional and always enforces 0700,
    regardless of whether the directory pre-existed."""
    os.makedirs(cert_dir, mode=0o700, exist_ok=True)
    os.chmod(cert_dir, 0o700)
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
    server = ThreadingHTTPServer((bind, port), _Handler)
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

#!/usr/bin/env python3
"""
sidecar.py — local HTTP bridge so a native (Python 2) DDLC can use the Python 3
director brain.

WHY THIS EXISTS
Base DDLC runs on an old Ren'Py built on Python 2. Our director is Python 3.
Rather than risk porting either one, we run the director here as a tiny local
server; the Ren'Py bridge (claude_mod_bridge.rpy) POSTs the player's input to
http://127.0.0.1:8765 and gets back a beat. The game does plain localhost HTTP
(no TLS); this process makes the real HTTPS call to OpenRouter. One Director
lives here for the whole session, so memory + intensity persist naturally.

RUN IT:  python sidecar.py     (leave the window open while playing)
Depends only on the standard library.
"""

import json
import os
import sys
import threading

try:
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
except ImportError:  # pragma: no cover - Python 2 safety (this file is Py3, but be loud)
    print("sidecar.py needs Python 3. Run it with `python3 sidecar.py`.")
    raise SystemExit(1)

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

from claude_mod import load_config, Director  # noqa: E402
from claude_mod.openrouter_client import LLMError  # noqa: E402

HOST = "127.0.0.1"
PORT = 8765

_lock = threading.Lock()
_director = None


def get_director():
    global _director
    if _director is None:
        _director = Director(load_config(), session_name="game")
    return _director


def beat_to_dict(beat):
    return {
        "turns": [{"speaker": t.speaker, "expression": t.expression, "text": t.text}
                  for t in beat.turns],
        "music": beat.music,
        "background": beat.background,
        "effect": beat.effect,
        "action": beat.action,
        "crack": beat.crack,
        "stage": beat.stage,        # list of girls on screen, or null
        "poem": beat.poem,          # {"author","text"} or null
        "model": beat.model,
    }


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass  # keep the console quiet

    def _read_json(self):
        try:
            length = int(self.headers.get("Content-Length", 0) or 0)
        except (TypeError, ValueError):
            length = 0
        raw = self.rfile.read(length) if length else b""
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except ValueError:
            return {}

    def do_GET(self):
        if self.path == "/health":
            self._send(200, {"ok": True, "model": get_director().client.model})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        data = self._read_json()
        with _lock:
            d = get_director()
            try:
                if self.path == "/respond":
                    beat = d.respond(str(data.get("text", "")))
                    d.perform_action(beat)  # safe file effects; cues handled in Ren'Py
                    self._send(200, beat_to_dict(beat))
                elif self.path == "/escalate":
                    self._send(200, {"intensity": d.escalate(float(data.get("amount", 1)))})
                elif self.path == "/deescalate":
                    self._send(200, {"intensity": d.deescalate(float(data.get("amount", 1)))})
                elif self.path == "/mode":
                    d.set_mode(str(data.get("mode", "")))
                    self._send(200, {"mode": d.mode})
                elif self.path == "/model":
                    m = str(data.get("model", "")).strip()
                    if m:
                        d.client.model = m
                        # Selection is authoritative: drop the auto-fallback so
                        # the chosen model is what actually runs (not silently
                        # replaced by the configured fallback).
                        d.client.fallback_model = ""
                        print(" [model] switched to %s" % m)
                    self._send(200, {"model": d.client.model})
                elif self.path == "/reset":
                    d.memory.reset()
                    globals()["_director"] = None
                    self._send(200, {"ok": True})
                else:
                    self._send(404, {"error": "not found"})
            except LLMError as e:
                # The director already returns a safe "..." beat on LLMError, so
                # this only fires on an unexpected path — report it, don't crash.
                self._send(200, {"turns": [{"speaker": "monika", "expression": "neutral",
                                            "text": "..."}], "error": str(e)})


def main():
    cfg = load_config()
    if "PUT-YOUR" in cfg.get("api_key", ""):
        print("[!] No API key yet. Copy config.example.json to config.json and add your key.")
    print("=" * 58)
    print(" DDLC director sidecar")
    print(" listening: http://%s:%d" % (HOST, PORT))
    print(" model:     %s  (fallback: %s)" % (cfg.get("model"), cfg.get("fallback_model") or "none"))
    print(" Leave this window OPEN while you play. Ctrl+C to stop.")
    print("=" * 58)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()

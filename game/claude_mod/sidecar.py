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

ON STARTUP it also installs the bridge into your DDLC game folder (finding it
automatically, or via "ddlc_game_dir" in config.json) and deletes the stale
compiled .rpyc, so the two halves can never be out of sync.

RUN IT:  python game/claude_mod/sidecar.py     (leave the window open)
Depends only on the standard library.
"""

import json
import os
import sys
import threading
import traceback
import urllib.request

try:
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
except ImportError:  # pragma: no cover - Python 2 safety (this file is Py3, but be loud)
    print("sidecar.py needs Python 3. Run it with `python3 sidecar.py`.")
    raise SystemExit(1)

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

from claude_mod import load_config, Director  # noqa: E402

HOST = "127.0.0.1"
PORT = 8765

# Bump this whenever the sidecar/director changes. The bridge compares it and
# warns in-game if the running sidecar is older than the bridge expects — so
# "I updated the .rpy but forgot to update the sidecar" gets caught instantly.
SIDECAR_VERSION = "8"

_REPO_GAME = os.path.dirname(_HERE)                       # <repo>/game
_BRIDGE_SRC = os.path.join(_REPO_GAME, "claude_mod_bridge.rpy")

_lock = threading.Lock()
_director = None
_spent = {"usd": 0.0, "turns": 0}


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
        "poem": beat.poem,          # {"author","title","text"} or null
        "error": beat.error,        # why a beat came back empty, for the setter
        "model": beat.model,
    }


def _log_turn(d, beat):
    """One console line per beat: who served it, tokens, and what it cost."""
    if beat.error:
        print(" [error] %s" % beat.error)
        return
    u = getattr(beat, "usage", None) or {}
    cost = u.get("cost")
    if isinstance(cost, (int, float)):
        _spent["usd"] += cost
    _spent["turns"] += 1
    cached = (u.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
    print(" [turn %d] %s | in %s (%s cached) out %s | %s | run total $%.4f | intensity %.1f"
          % (_spent["turns"], beat.model or d.client.model,
             u.get("prompt_tokens", "?"), cached, u.get("completion_tokens", "?"),
             ("$%.4f" % cost) if isinstance(cost, (int, float)) else "cost ?",
             _spent["usd"], d.intensity))


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
            d = get_director()
            self._send(200, {"ok": True, "version": SIDECAR_VERSION,
                             "model": d.client.model,
                             "intensity": round(d.intensity, 1)})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        data = self._read_json()
        with _lock:
            d = get_director()
            try:
                if self.path == "/start":
                    # A new takeover: fresh run, told where the real game left off.
                    beat = d.start_run(
                        player_name=str(data.get("player_name") or ""),
                        history=data.get("history") or [],
                        chapter=data.get("chapter"),
                        route=data.get("route") or {},
                        trigger=str(data.get("trigger") or "manual"))
                    print(" [run] new takeover (%s) - previous run archived" %
                          data.get("trigger", "manual"))
                    d.perform_action(beat)
                    _log_turn(d, beat)
                    self._send(200, beat_to_dict(beat))
                elif self.path == "/respond":
                    if data.get("player_name"):
                        d.set_player_name(str(data.get("player_name")))
                    beat = d.respond(str(data.get("text", "")))
                    d.perform_action(beat)  # safe file effects; cues handled in Ren'Py
                    _log_turn(d, beat)
                    self._send(200, beat_to_dict(beat))
                elif self.path == "/escalate":
                    v = d.escalate(float(data.get("amount", 1)))
                    print(" [intensity] up -> %.1f" % v)
                    self._send(200, {"intensity": v})
                elif self.path == "/deescalate":
                    v = d.deescalate(float(data.get("amount", 1)))
                    print(" [intensity] down -> %.1f" % v)
                    self._send(200, {"intensity": v})
                elif self.path == "/mode":
                    d.set_mode(str(data.get("mode", "")))
                    self._send(200, {"mode": d.mode})
                elif self.path == "/model":
                    want = str(data.get("model", "")).strip()
                    if not want or d.client.model_exists(want) is False:
                        print(" [model] OpenRouter doesn't know %r - still on %s"
                              % (want, d.client.model))
                        self._send(200, {"model": d.client.model,
                                         "error": "OpenRouter doesn't know %s" % want})
                    else:
                        m = d.set_model(want)
                        print(" [model] switched to %s (kept across restarts)" % m)
                        self._send(200, {"model": m})
                elif self.path == "/reset":
                    d.memory.archive()
                    globals()["_director"] = None
                    print(" [run] reset - transcript archived")
                    self._send(200, {"ok": True})
                else:
                    self._send(404, {"error": "not found"})
            except Exception as e:  # noqa: BLE001 - never let one request kill the game
                traceback.print_exc()
                self._send(200, {"turns": [{"speaker": "monika", "expression": "neutral",
                                            "text": "..."}],
                                 "error": "sidecar error: %s" % e})


# ── keep the game-side bridge in sync automatically ─────────────────────────

_SKIP_DIRS = {"appdata", "node_modules", ".git", "windows", "program files",
              "program files (x86)", "$recycle.bin", "library", "__pycache__"}


def _is_ddlc_game_dir(path):
    return (os.path.isfile(os.path.join(path, "scripts.rpa"))
            and os.path.isfile(os.path.join(path, "images.rpa")))


def _walk_for_ddlc(root, depth, found, seen):
    if depth < 0 or len(found) >= 3:
        return
    try:
        entries = list(os.scandir(root))
    except OSError:
        return
    for e in entries:
        try:
            if not e.is_dir(follow_symlinks=False):
                continue
        except OSError:
            continue
        name = e.name.lower()
        if name.startswith(".") or name in _SKIP_DIRS:
            continue
        real = os.path.realpath(e.path)
        if real in seen:
            continue
        seen.add(real)
        if name == "game" and _is_ddlc_game_dir(e.path):
            found.append(e.path)
            continue
        _walk_for_ddlc(e.path, depth - 1, found, seen)


def find_ddlc_game_dirs(cfg):
    """Where DDLC's game/ folder is. Honours config "ddlc_game_dir" first."""
    explicit = str(cfg.get("ddlc_game_dir") or "").strip()
    if explicit:
        p = os.path.expanduser(explicit)
        for cand in (p, os.path.join(p, "game")):
            if _is_ddlc_game_dir(cand):
                return [cand]
        return []
    repo = os.path.dirname(_REPO_GAME)
    home = os.path.expanduser("~")
    roots = [os.path.dirname(repo), os.path.dirname(os.path.dirname(repo)),
             os.path.join(home, "Downloads"), os.path.join(home, "Desktop"),
             os.path.join(home, "Documents")]
    found, seen = [], {os.path.realpath(repo)}
    for r in roots:
        if r and os.path.isdir(r) and os.path.realpath(r) != os.path.realpath(home):
            _walk_for_ddlc(r, 3, found, seen)
    return found


def install_bridge(cfg, src_path=_BRIDGE_SRC):
    """
    Copy claude_mod_bridge.rpy into every DDLC game/ folder found, and delete
    the stale compiled .rpyc beside it so Ren'Py can't run old code. Returns a
    list of (folder, status) for the startup banner and the tests.
    """
    if cfg.get("auto_install_bridge", True) is False:
        return [("", "auto-install off (auto_install_bridge=false)")]
    if not os.path.isfile(src_path):
        return [("", "bridge source missing: %s" % src_path)]
    with open(src_path, "rb") as f:
        src = f.read()
    results = []
    for game_dir in find_ddlc_game_dirs(cfg):
        dst = os.path.join(game_dir, "claude_mod_bridge.rpy")
        try:
            current = None
            if os.path.isfile(dst):
                with open(dst, "rb") as f:
                    current = f.read()
            if current == src:
                results.append((game_dir, "up to date"))
                continue
            tmp = dst + ".tmp"
            with open(tmp, "wb") as f:
                f.write(src)
            os.replace(tmp, dst)
            if os.path.isfile(dst + "c"):
                os.remove(dst + "c")
            results.append((game_dir, "installed (stale .rpyc removed)"
                            if current is not None else "installed"))
        except OSError as e:
            results.append((game_dir, "could not write: %s" % e))
    return results


# ── startup ────────────────────────────────────────────────────────────────

def _probe_running():
    """If something already owns our port, ask it who it is."""
    try:
        raw = urllib.request.urlopen("http://%s:%d/health" % (HOST, PORT), timeout=3).read()
        return json.loads(raw.decode("utf-8"))
    except Exception:  # noqa: BLE001
        return None


def main():
    cfg = load_config()
    has_config = os.path.isfile(os.path.join(_HERE, "config.json"))

    try:
        server = ThreadingHTTPServer((HOST, PORT), Handler)
    except OSError:
        other = _probe_running()
        ver = (other or {}).get("version", "old/unknown")
        print("=" * 64)
        print(" [!] Another sidecar is ALREADY RUNNING on port %d (version %s)." % (PORT, ver))
        print("     The game is talking to THAT one, not this one.")
        print("     Find its window, press Ctrl+C (or close it), then run this again.")
        print("=" * 64)
        raise SystemExit(1)

    print("=" * 64)
    print(" DDLC director sidecar   (version %s)" % SIDECAR_VERSION)
    print(" listening: http://%s:%d" % (HOST, PORT))
    if not has_config:
        print(" [!] config.json not found next to sidecar.py - copy config.example.json")
        print("     to config.json and put your OpenRouter key in it.")
    elif "PUT-YOUR" in str(cfg.get("api_key", "")) or not cfg.get("api_key"):
        print(" [!] config.json has no API key yet.")
    d = get_director()
    print(" model:     %s%s" % (d.client.model,
                                 "  (picked in-game with F10)" if d.memory.meta.get("model")
                                 else "  (fallback: %s)" % (d.client.fallback_model or "none")))
    if d.client.model_exists(d.client.model) is False:
        print(" [!] OpenRouter doesn't recognise that model id - every turn would fail.")
        print("     Fix \"model\" in config.json, or pick one in-game with F10.")
    for folder, status in install_bridge(cfg):
        print(" bridge:    %s%s" % (status, (" -> " + folder) if folder else ""))
    if not find_ddlc_game_dirs(cfg) and cfg.get("auto_install_bridge", True) is not False:
        print(" bridge:    couldn't find your DDLC folder. Either set \"ddlc_game_dir\"")
        print("            in config.json, or copy game/claude_mod_bridge.rpy into")
        print("            DDLC's game folder yourself.")
    print(" If DDLC is already open, restart it so it loads the bridge.")
    print(" Leave this window OPEN while you play. Ctrl+C to stop.")
    print("=" * 64)
    server.serve_forever()


if __name__ == "__main__":
    main()

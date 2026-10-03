#!/usr/bin/env python3
"""
Offline tests for the sidecar server, the automatic bridge install, and the
updater. Runs the REAL HTTP handler on a spare local port with a fake model
behind it. No network, no API credits.

Run:  python3 tests/test_sidecar.py
"""

import io
import json
import os
import shutil
import sys
import tempfile
import threading
import urllib.request
import zipfile

_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(_ROOT, "game"))
sys.path.insert(0, os.path.join(_ROOT, "game", "claude_mod"))
sys.path.insert(0, _ROOT)

from claude_mod import memory as memory_mod                    # noqa: E402
_TEST_MEM = tempfile.mkdtemp(prefix="ddlc_test_mem_")
memory_mod._MEM_DIR = _TEST_MEM                                 # never touch real memory

import sidecar                                                  # noqa: E402
import update                                                   # noqa: E402
from claude_mod.director import Director                        # noqa: E402
from claude_mod.openrouter_client import LLMResult, LLMError    # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print("  %s %s%s" % ("✓" if cond else "✗", name,
                         (" — " + str(detail)) if (detail and not cond) else ""))


class FakeClient(object):
    model = "anthropic/claude-fable-5"
    fallback_model = "anthropic/claude-opus-4.8"
    fail = False
    known = {"anthropic/claude-opus-5", "anthropic/claude-fable-5"}

    def complete(self, system, messages):
        if self.fail:
            raise LLMError("OpenRouter says: insufficient credit (402)")
        return LLMResult(json.dumps({
            "turns": [{"speaker": "sayori", "expression": "laugh", "text": u"Ehehe— hi!"}],
            "stage": ["sayori", "monika"], "music": "happy", "crack": "none"}),
            "stop", "fake-model", usage={"prompt_tokens": 1000, "completion_tokens": 50,
                                          "cost": 0.0123})

    def model_exists(self, m):
        return m in self.known


def make_director():
    d = Director({"api_key": "k", "enable_local_scan": False, "pace": "normal"},
                 session_name="game")
    d.client = FakeClient()
    return d


# ── 1. the real HTTP server ────────────────────────────────────────────────
print("[server]")
sidecar._director = make_director()
server = sidecar.ThreadingHTTPServer(("127.0.0.1", 0), sidecar.Handler)
port = server.server_address[1]
threading.Thread(target=server.serve_forever, daemon=True).start()
base = "http://127.0.0.1:%d" % port


def post(path, payload=None, raw=None):
    body = raw if raw is not None else json.dumps(payload or {}).encode("utf-8")
    req = urllib.request.Request(base + path, body, {"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=10).read().decode("utf-8"))


def get(path):
    return json.loads(urllib.request.urlopen(base + path, timeout=10).read().decode("utf-8"))


h = get("/health")
check("/health reports the version the bridge expects", h["version"] == sidecar.SIDECAR_VERSION)
check("/health reports the live model", h["model"] == "anthropic/claude-fable-5")

r = post("/start", {"player_name": "Dfdfdf", "trigger": "seam", "chapter": 2,
                    "history": [{"who": "Sayori", "what": "\"Hi Dfdfdf~\""}],
                    "route": {"poem_winners": ["yuri"]}})
check("/start returns the opening beat", r["turns"][0]["text"] == u"Ehehe— hi!")
check("/start passes stage + music through", r["stage"] == ["sayori", "monika"]
      and r["music"] == "happy")
check("/start set the player's name", sidecar._director.player_name == "Dfdfdf")

r = post("/respond", {"text": "hi everyone"})
check("/respond returns a beat with every field the bridge reads",
      all(k in r for k in ("turns", "music", "background", "effect", "stage", "poem", "error")))
check("unicode survives the round trip", r["turns"][0]["text"] == u"Ehehe— hi!")
check("cost is tracked per run", abs(sidecar._spent["usd"] - 0.0246) < 1e-9)

r = post("/model", {"model": "anthropic/claude-opsu-5"})
check("/model rejects an id OpenRouter doesn't know", "error" in r
      and sidecar._director.client.model == "anthropic/claude-fable-5")
r = post("/model", {"model": "anthropic/claude-opus-5"})
check("/model switches to a real id", r == {"model": "anthropic/claude-opus-5"}
      and sidecar._director.client.model == "anthropic/claude-opus-5")
check("the switch is remembered", sidecar._director.memory.meta.get("model")
      == "anthropic/claude-opus-5")

check("/escalate moves intensity", post("/escalate", {"amount": 2})["intensity"] >= 2)
check("/deescalate moves it back", post("/deescalate", {"amount": 5})["intensity"] == 0)

sidecar._director.client.fail = True
r = post("/respond", {"text": "anyone there?"})
check("a dead API still answers the game with a renderable beat", r["turns"][0]["text"] == "...")
check("...and says why (for the toast)", "402" in (r.get("error") or ""))
sidecar._director.client.fail = False

r = post("/respond", raw=b"{not json")
check("a garbled request doesn't crash the server", "turns" in r)
sidecar._director.respond = lambda text: 1 / 0
r = post("/respond", {"text": "boom"})
check("an unexpected bug is reported to the game, not a dropped connection",
      "sidecar error" in (r.get("error") or ""))
check("server still alive afterwards", get("/health")["ok"] is True)
try:
    urllib.request.urlopen(base + "/nope", timeout=5)
    nf = False
except urllib.error.HTTPError as e:
    nf = e.code == 404
check("unknown GET path is a 404", nf)
server.shutdown()

# The "I restarted it but nothing changed" trap: an old sidecar window is still
# open on port 8765, so the new one can't start and the game keeps talking to
# the old one. The new one must say so plainly instead of crashing.
import subprocess                                               # noqa: E402
try:
    old = sidecar.ThreadingHTTPServer((sidecar.HOST, sidecar.PORT), sidecar.Handler)
except OSError:
    old = None
if old is None:
    check("(port 8765 busy on this machine - skipped the double-start test)", True)
else:
    threading.Thread(target=old.serve_forever, daemon=True).start()
    check("_probe_running identifies the sidecar already on the port",
          (sidecar._probe_running() or {}).get("version") == sidecar.SIDECAR_VERSION)
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable, os.path.join(_ROOT, "game", "claude_mod", "sidecar.py")],
                       capture_output=True, text=True, timeout=30, env=env)
    check("a second sidecar refuses to start (exit 1) instead of crashing",
          p.returncode == 1 and "Traceback" not in p.stderr, p.stderr[-300:])
    check("...and tells you the old window is still open",
          "ALREADY RUNNING" in p.stdout and "Ctrl+C" in p.stdout, p.stdout[-300:])
    old.shutdown()
    old.server_close()

# ── 2. the bridge installs itself into DDLC ────────────────────────────────
print("[bridge auto-install]")
tmp = tempfile.mkdtemp(prefix="ddlc_install_")
ddlc_game = os.path.join(tmp, "Downloads", "ddlc-win", "DDLC-1.1.1-pc", "game")
os.makedirs(ddlc_game)
for f in ("scripts.rpa", "images.rpa"):
    open(os.path.join(ddlc_game, f), "wb").close()
not_ddlc = os.path.join(tmp, "Downloads", "some-other-game", "game")
os.makedirs(not_ddlc)
src = os.path.join(tmp, "bridge_src.rpy")
with open(src, "wb") as f:
    f.write(b"# bridge v8\n")

cfg = {"ddlc_game_dir": os.path.join(tmp, "Downloads", "ddlc-win", "DDLC-1.1.1-pc")}
check("explicit ddlc_game_dir (the folder above game/ works too)",
      sidecar.find_ddlc_game_dirs(cfg) == [ddlc_game])
check("a folder without DDLC's archives is never mistaken for DDLC",
      sidecar.find_ddlc_game_dirs({"ddlc_game_dir": os.path.dirname(not_ddlc)}) == [])

with open(os.path.join(ddlc_game, "claude_mod_bridge.rpy"), "wb") as f:
    f.write(b"# OLD bridge\n")
with open(os.path.join(ddlc_game, "claude_mod_bridge.rpyc"), "wb") as f:
    f.write(b"stale compiled")
res = sidecar.install_bridge(cfg, src_path=src)
check("installs the new bridge", open(os.path.join(ddlc_game, "claude_mod_bridge.rpy"), "rb").read()
      == b"# bridge v8\n")
check("deletes the stale .rpyc (so Ren'Py can't run old code)",
      not os.path.exists(os.path.join(ddlc_game, "claude_mod_bridge.rpyc")))
check("reports what it did", res and "installed" in res[0][1])
res = sidecar.install_bridge(cfg, src_path=src)
check("second start: already up to date, nothing touched", res[0][1] == "up to date")
check("can be switched off", sidecar.install_bridge({"auto_install_bridge": False}, src_path=src)[0][1]
      .startswith("auto-install off"))

# auto-detect: repo sitting in Downloads next to ddlc-win (the user's layout)
repo = os.path.join(tmp, "Downloads", "claude-game-claude-ddlc-claude-mod-4xai2o")
os.makedirs(os.path.join(repo, "game", "claude_mod"))
saved = sidecar._REPO_GAME
sidecar._REPO_GAME = os.path.join(repo, "game")
os.environ["HOME"] = os.path.join(tmp, "home")       # keep the walk inside the sandbox
found = sidecar.find_ddlc_game_dirs({})
sidecar._REPO_GAME = saved
check("finds DDLC by itself when the mod sits next to it in Downloads", found == [ddlc_game], found)
shutil.rmtree(tmp, ignore_errors=True)

# ── 3. the updater ─────────────────────────────────────────────────────────
print("[update.py]")
root = tempfile.mkdtemp(prefix="ddlc_update_")
os.makedirs(os.path.join(root, "game", "claude_mod", "persona"))
os.makedirs(os.path.join(root, "game", "claude_mod", "memory"))
files = {
    "game/claude_mod/config.json": b'{"api_key": "sk-or-MY-REAL-KEY"}',
    "game/claude_mod/memory/game.json": b'{"messages": ["precious"]}',
    "game/claude_mod/sidecar.py": b'SIDECAR_VERSION = "7"\n',
    "game/claude_mod/persona/characters.json": b'{"my": "edits"}',
    "game/claude_mod_hooks.rpy": b"import claude_mod  # crashes DDLC",
    "README.md": b"same",
}
for rel, data in files.items():
    with open(os.path.join(root, *rel.split("/")), "wb") as f:
        f.write(data)

buf = io.BytesIO()
with zipfile.ZipFile(buf, "w") as z:
    P = "claude-game-claude-ddlc-claude-mod-4xai2o/"
    z.writestr(P + "game/claude_mod/sidecar.py", 'SIDECAR_VERSION = "8"\n')
    z.writestr(P + "game/claude_mod/persona/characters.json", '{"new": "bible"}')
    z.writestr(P + "game/claude_mod/config.json", '{"api_key": "PUT-YOUR-KEY"}')
    z.writestr(P + "game/claude_mod_bridge.rpy", "# bridge v8")
    z.writestr(P + "update.py", "# updater")
    z.writestr(P + "README.md", "same")
rep = update.apply_zip(buf.getvalue(), root=root, stamp="T")


def read(rel):
    with open(os.path.join(root, *rel.split("/")), "rb") as f:
        return f.read()


check("your API key is never overwritten", read("game/claude_mod/config.json")
      == b'{"api_key": "sk-or-MY-REAL-KEY"}')
check("your memory is never touched", read("game/claude_mod/memory/game.json")
      == b'{"messages": ["precious"]}')
check("code is updated", update.sidecar_version(root) == "8")
check("new files are added", read("game/claude_mod_bridge.rpy") == b"# bridge v8")
check("an edited file is backed up before replacing",
      open(os.path.join(root, "update_backup", "T", "game", "claude_mod", "persona",
                        "characters.json"), "rb").read() == b'{"my": "edits"}')
check("the DDLC-crashing hooks file is removed (kept in the backup)",
      not os.path.exists(os.path.join(root, "game", "claude_mod_hooks.rpy"))
      and "game/claude_mod_hooks.rpy" in rep["removed"])
check("identical files are left alone", "README.md" in rep["unchanged"])
bad = io.BytesIO()
with zipfile.ZipFile(bad, "w") as z:
    z.writestr("something-else/readme.txt", "x")
try:
    update.apply_zip(bad.getvalue(), root=root)
    rejected = False
except ValueError:
    rejected = True
check("a download that isn't this mod changes nothing", rejected)
shutil.rmtree(root, ignore_errors=True)

shutil.rmtree(_TEST_MEM, ignore_errors=True)
print("\n%d passed, %d failed" % (len(PASS), len(FAIL)))
if FAIL:
    print("FAILED:", ", ".join(FAIL))
    raise SystemExit(1)
print("ALL GREEN")

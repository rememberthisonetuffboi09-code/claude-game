#!/usr/bin/env python3
"""
Cross-file contract between the Python director/sidecar and the Ren'Py bridge.

The two halves ship separately (the bridge goes into DDLC's game/ folder, the
sidecar runs on its own), so this test is what stops them drifting apart. It
exists because of real bugs: the director once emitted mood words the bridge
didn't know, so every face silently fell back to neutral.

Every word the director is allowed to send must map to something real on the
bridge side, and every field the bridge reads must actually be sent.

Run:  python3 tests/test_bridge_sync.py     (no network, no API credits)
"""

import ast
import os
import re
import sys

_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(_ROOT, "game"))

from claude_mod import director as D                     # noqa: E402

BRIDGE = open(os.path.join(_ROOT, "game/claude_mod_bridge.rpy"), encoding="utf-8").read()
SIDECAR = open(os.path.join(_ROOT, "game/claude_mod/sidecar.py"), encoding="utf-8").read()

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print("  %s %s%s" % ("✓" if cond else "✗", name, (" — %s" % (detail,)) if detail and not cond else ""))


def literal(name):
    """A top-level dict/list literal from the bridge's init python, by name."""
    m = re.search(r"^    " + re.escape(name) + r"\s*=\s*([\[{].*?^    [\]}])", BRIDGE, re.S | re.M)
    if not m:
        raise AssertionError("could not find %s in the bridge" % name)
    return ast.literal_eval(m.group(1))


faces = literal("CLAUDE_FACES")
alias = literal("CLAUDE_MOOD_ALIAS")
music = literal("CLAUDE_MUSIC")
rooms = literal("CLAUDE_BG")

print("[moods]")
for girl in ("sayori", "natsuki", "yuri", "monika"):
    check("%s has a face for every mood the director can send" % girl,
          set(D._EXPRESSIONS) <= set(faces[girl]), set(D._EXPRESSIONS) - set(faces[girl]))
check("every bridge alias lands on a real mood", set(alias.values()) <= set(D._EXPRESSIONS))
check("bridge folds every director synonym the same way",
      all(alias.get(w) == m for w, m in D._EXPR_SYNONYMS.items()),
      [w for w, m in D._EXPR_SYNONYMS.items() if alias.get(w) != m])

print("[music + rooms]")
check("every music word maps to a DDLC track",
      D._MUSIC - {"keep", "stop"} <= set(music), D._MUSIC - {"keep", "stop"} - set(music))
check("every room maps to a DDLC background",
      D._BACKGROUND - {"keep"} <= set(rooms), D._BACKGROUND - {"keep"} - set(rooms))
check("black is DDLC's `black` image (there is no `bg black`)", rooms["black"] == "black")

print("[version handshake]")
sv = re.search(r'SIDECAR_VERSION = "(\w+)"', SIDECAR).group(1)
bv = re.search(r'CLAUDE_EXPECTED_SIDECAR = "(\w+)"', BRIDGE).group(1)
check("sidecar version matches what the bridge expects (%s)" % sv, sv == bv)

print("[wire format]")
sent = set(re.findall(r'"(\w+)":', SIDECAR.split("def beat_to_dict")[1].split("\n\n")[0]))
read = set(re.findall(r'r\.get\("(\w+)"', BRIDGE)) | {"turns"}
check("the sidecar sends every field the bridge reads", read <= sent, read - sent)
for endpoint in ("/start", "/respond", "/model", "/escalate", "/deescalate", "/health"):
    check("sidecar serves %s" % endpoint, '"%s"' % endpoint in SIDECAR)
used = set(re.findall(r'_claude_(?:post|get)\("(/\w+)"', BRIDGE))
check("every endpoint the bridge calls exists", all('"%s"' % u in SIDECAR for u in used), used)

print("\n%d passed, %d failed" % (len(PASS), len(FAIL)))
if FAIL:
    print("FAILED:", ", ".join(FAIL))
    raise SystemExit(1)
print("ALL GREEN")

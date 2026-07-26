#!/usr/bin/env python3
"""
Cross-file consistency checks between the Python sidecar and the Ren'Py bridge.

These two halves ship separately (the bridge goes into DDLC's game/ folder, the
sidecar runs on its own), so nothing but this test stops them drifting apart.
It exists because of a real bug: the director started emitting a fixed mood
vocabulary the bridge didn't know, so EVERY expression silently fell back to
neutral and the girls' faces looked frozen.

Run:  python3 tests/test_bridge_sync.py     (no network, no API credits)
"""

import ast
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.join(_HERE, "..")
sys.path.insert(0, os.path.join(_ROOT, "game"))

from claude_mod import director as D                     # noqa: E402

BRIDGE = open(os.path.join(_ROOT, "game/claude_mod_bridge.rpy"), encoding="utf-8").read()
SIDECAR = open(os.path.join(_ROOT, "game/claude_mod/sidecar.py"), encoding="utf-8").read()

PASS, FAIL = [], []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print("  %s %s" % ("✓" if cond else "✗", name))


def _literal(name, opener, closer):
    """Pull a top-level dict/list literal out of the .rpy by name."""
    m = re.search(re.escape(name) + r"\s*=\s*(" + re.escape(opener) +
                  r".*?\n    " + re.escape(closer) + r")", BRIDGE, re.S)
    if not m:
        raise AssertionError("could not find %s in the bridge" % name)
    return ast.literal_eval(m.group(1))


mood = _literal("CLAUDE_MOOD", "{", "}")
alias = _literal("CLAUDE_MOOD_ALIAS", "{", "}")
models = _literal("CLAUDE_MODELS", "[", "]")

print("[moods: director vocabulary <-> bridge faces]")
check("every director mood maps to a face", set(D._EXPRESSIONS) <= set(mood))
check("each mood gets a DISTINCT face", len(set(mood.values())) == len(mood))
check("every bridge alias resolves to a real mood",
      all(v in mood for v in alias.values()))
check("bridge knows every director synonym",
      set(D._EXPR_SYNONYMS) <= set(alias) | set(mood))
check("faces exist for all four girls (pose-1 a..r)",
      all(len(v) == 1 and "a" <= v <= "r" for v in mood.values()))

print("[version handshake]")
sv = re.search(r'SIDECAR_VERSION = "(\w+)"', SIDECAR).group(1)
bv = re.search(r'CLAUDE_EXPECTED_SIDECAR = "(\w+)"', BRIDGE).group(1)
check("sidecar version matches what the bridge expects (%s)" % sv, sv == bv)

print("[wire format: every field the bridge reads is sent]")
sent = set(re.findall(r'"(\w+)":', SIDECAR.split("def beat_to_dict")[1].split("\n\n")[0]))
for field in ("turns", "music", "background", "effect", "stage", "poem", "error"):
    check("sidecar sends %r" % field, field in sent)

print("[model picker]")
labels = [l for l, _ in models]
slugs = [s for _, s in models]
check("Opus 5 is in the picker", "anthropic/claude-opus-5" in slugs)
check("no duplicate slugs", len(set(slugs)) == len(slugs))
check("no duplicate labels", len(set(labels)) == len(labels))
check("every slug is provider-qualified", all("/" in s for s in slugs))
check("/model endpoint exists in the sidecar", '"/model"' in SIDECAR)
print("  picker: %s" % ", ".join(labels))

print("\n%d passed, %d failed" % (len(PASS), len(FAIL)))
if FAIL:
    print("FAILED:", ", ".join(FAIL))
    raise SystemExit(1)
print("ALL GREEN")

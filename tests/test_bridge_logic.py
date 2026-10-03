#!/usr/bin/env python3
"""
Offline tests for the GAME-SIDE bridge (game/claude_mod_bridge.rpy).

The bridge's `init python` blocks are executed against a small fake Ren'Py, then
driven like the game would drive them: stage changes, faces, text escaping,
music, backgrounds, the seam, the model picker, poems. No DDLC, no network.

It also statically checks the Python inside the .rpy for things that break on
DDLC's engine (Ren'Py 6.99 = Python 2.7): f-strings, nonlocal, str() on text...

Run:  python3 tests/test_bridge_logic.py
"""

import json
import os
import re
import sys
import textwrap
import types

_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
BRIDGE = open(os.path.join(_ROOT, "game", "claude_mod_bridge.rpy"), encoding="utf-8").read()

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print("  %s %s%s" % ("✓" if cond else "✗", name,
                         (" — " + str(detail)) if (detail and not cond) else ""))


# Image names the bridge relies on, verified against DDLC 1.1.1's
# definitions.rpy (names only). Every face code in CLAUDE_FACES must be here.
DDLC_IMAGES = set(tuple(s.split()) for s in """
sayori 1a|sayori 1x|sayori 1q|sayori 4r|sayori 1b|sayori 1h|sayori 4p|sayori 1l|sayori 1k|sayori 1i|sayori 5d|sayori 1y
natsuki 2c|natsuki 4z|natsuki 4y|natsuki 4l|natsuki 2k|natsuki 1o|natsuki 1u|natsuki 1r|natsuki 12f|natsuki 1e|natsuki 5s|natsuki 2d
yuri 1a|yuri 2s|yuri 1c|yuri 1m|yuri 1f|yuri 1e|yuri 2t|yuri 4b|yuri 2q|yuri 3r|yuri 2w|yuri 1k
monika 1a|monika 1j|monika 1k|monika 2b|monika 1m|monika 1d|monika 1l|monika 1p|monika 1g|monika 2i|monika 1r|monika 5a
bg club_day|bg class_day|bg corridor|bg closet|bg kitchen|bg residential_day|bg glitch|black|ctc
""".replace("\n", "|").split("|") if s.strip())


# ── a fake Ren'Py, just enough to run the bridge ───────────────────────────
class Jump(Exception):
    pass


class FakeRenpy(object):
    def __init__(self):
        self.shown = {}            # tag -> (full name, transform, zorder)
        self.hidden = []
        self.said = []
        self.notes = []
        self.music_calls = []
        self.screens = {"quick_menu", "tear"}
        self.labels = {"showpoem"}
        self.input_reply = "hello there"
        self.call_screen_fails = False
        self.display = types.SimpleNamespace(image=types.SimpleNamespace(images=DDLC_IMAGES))
        fake = self
        self.music = types.SimpleNamespace(
            play=lambda src, **kw: fake.music_calls.append(("play", src, kw)),
            stop=lambda **kw: fake.music_calls.append(("stop", kw)))

    def show(self, name, at_list=(), zorder=None, **kw):
        # Like Ren'Py: an exact image name shows that image; a bare tag that
        # isn't an image re-shows whatever that tag is currently wearing.
        parts = tuple(name.split())
        tag = parts[0]
        if parts in DDLC_IMAGES:
            full = name
        elif len(parts) == 1 and tag in self.shown:
            full = self.shown[tag][0]
        else:
            raise Exception("image not found: %s" % name)
        self.shown[tag] = (full, at_list[0] if at_list else None, zorder)

    def hide(self, tag):
        self.shown.pop(tag, None)
        self.hidden.append(tag)

    def showing(self, tag):
        return tag in self.shown

    def scene(self):
        self.shown.clear()

    def say(self, who, what):
        self.said.append((getattr(who, "name", who), what))

    def notify(self, msg):
        self.notes.append(msg)

    def jump(self, label):
        raise Jump(label)

    def call_screen(self, name, **kw):
        if self.call_screen_fails:
            raise TypeError("no such screen")
        self.last_screen = (name, kw)
        return self.input_reply

    def input(self, prompt, length=None):
        return "fallback input"

    def has_screen(self, n):
        return n in self.screens

    def has_label(self, n):
        return n in self.labels

    def with_statement(self, *a, **k):
        pass

    def pause(self, *a, **k):
        pass

    def show_screen(self, *a, **k):
        self.notes.append("tear on")

    def hide_screen(self, *a, **k):
        pass

    def block_rollback(self):
        pass


class Char(object):
    def __init__(self, name, **kw):
        self.name = name
        self.kw = kw


class Poem(object):
    def __init__(self, author="", title="", text=""):
        self.author, self.title, self.text = author, title, text


def T(name):
    return ("T", name)                      # a stand-in for DDLC's ATL transforms


def fresh_bridge(prev_label_cb=None):
    """Execute the bridge's init python blocks in a fake game, like DDLC would."""
    renpy = FakeRenpy()
    store = types.SimpleNamespace(
        persistent=types.SimpleNamespace(playername="Dfdfdf"),
        player="Dfdfdf", chapter=2, poemwinner=["yuri", "yuri", "sayori"],
        s_appeal=0, n_appeal=1, y_appeal=2, main_menu=False,
        audio=types.SimpleNamespace(t2="<loop 4.499>bgm/2.ogg", t3="<loop 4.618>bgm/3.ogg",
                                    t5="bgm/5.ogg", t8="bgm/8.ogg", t3g3="bgm/3g2.ogg"),
        _history_list=[types.SimpleNamespace(who=None, what="{i}Another day passes.{/i}"),
                       types.SimpleNamespace(who="Sayori", what='"Hi Dfdfdf~"')],
        mc=Char("Dfdfdf", what_prefix='"'),
        thide=T("thide"))
    for slot in ("11", "21", "22", "31", "32", "33", "41", "42", "43", "44"):
        setattr(store, "t" + slot, T("t" + slot))
        setattr(store, "f" + slot, T("f" + slot))
    config = types.SimpleNamespace(label_callback=prev_label_cb, overlay_screens=[],
                                   gamedir="/tmp", skipping=None)
    ns = {"renpy": renpy, "store": store, "config": config, "Character": Char,
          "Transform": lambda **kw: ("Transform", kw), "Dissolve": lambda t: ("Dissolve", t),
          "Fade": lambda *a, **k: ("Fade", a), "vpunch": "vpunch", "Poem": Poem,
          "NullAction": lambda: None}
    # `default` statements (run when a game starts)
    for name, value in re.findall(r"^default (\w+) = (.+?)(?:\s+#.*)?$", BRIDGE, re.M):
        setattr(store, name, eval(value))
    # every top-level `init python:` block, in file order
    for block in re.findall(r"^init python:\n((?:(?:    .*)?\n)+)", BRIDGE, re.M):
        exec(textwrap.dedent(block), ns)
    ns["_post_log"] = []

    def fake_post(path, payload, timeout=120):
        ns["_post_log"].append((path, payload))
        return ns.get("_post_reply", {"model": payload.get("model", "")})
    ns["_claude_post"] = fake_post
    return ns, renpy, store, config


# ── 1. static checks for DDLC's Python 2.7 engine ──────────────────────────
print("[python 2 safety]")
import io                                                     # noqa: E402
import tokenize                                               # noqa: E402


def python_blocks(src):
    """Every `python:` / `init python:` body, dedented (labels nest them)."""
    lines, out, i = src.split("\n"), [], 0
    while i < len(lines):
        m = re.match(r"^(\s*)(?:init )?python:\s*$", lines[i])
        if not m:
            i += 1
            continue
        base, body = len(m.group(1)), []
        i += 1
        while i < len(lines) and (not lines[i].strip()
                                  or len(lines[i]) - len(lines[i].lstrip()) > base):
            body.append(lines[i])
            i += 1
        out.append(textwrap.dedent("\n".join(body)))
    return out


py_blocks = python_blocks(BRIDGE)
toks = []
for b in py_blocks:
    toks += [t for t in tokenize.generate_tokens(io.StringIO(b).readline)
             if t.type not in (tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE)]
names = [t.string for t in toks if t.type == tokenize.NAME]
pairs = list(zip(toks, toks[1:]))
check("no f-strings",
      not any(t.type == tokenize.STRING and re.match(r"[rRbBuU]*[fF]", t.string) for t in toks))
check("no nonlocal", "nonlocal" not in names)
check("no walrus / annotations",
      not any(t.string in (":=", "->") for t in toks))
check("no str() on game text (Python 2 + DDLC's codepage = mangled/crash)",
      not any(a.string == "str" and b.string == "(" for a, b in pairs))
check("no renpy.input(screen=...) - 6.99 doesn't have it",
      not any(a.string == "screen" and b.string == "=" for a, b in pairs))
check("no `caret` on the input statement - 6.99's parser rejects it",
      not re.search(r"^\s+caret ", BRIDGE.split("screen claude_input")[1].split("\nscreen ")[0], re.M)
      if "screen claude_input" in BRIDGE else False)
check("F11 left alone (it's the engine's fullscreen key)", "K_F11" not in BRIDGE)
check("python blocks compile",
      all(compile(textwrap.dedent(b), "<rpy>", "exec") for b in py_blocks))

ns, rp, store, config = fresh_bridge()

# ── 2. text ────────────────────────────────────────────────────────────────
print("[text]")
check("unicode survives (em dash, ellipsis, accents)",
      ns["_claude_text"](u"Why would— ugh… café") == u"Why would— ugh… café")
check("bytes are decoded, None is empty, numbers become text",
      ns["_claude_text"](b"hi") == u"hi" and ns["_claude_text"](None) == u""
      and ns["_claude_text"](3) == u"3")
check("brackets/braces escaped for say()",
      ns["_claude_escape"](u"[sighs] {wink}") == u"[[sighs] {{wink}")
ns["claude_bridge_say"]("monika", u"Ahaha— [player]?")
check("girl line goes through her Character with DDLC quotes + ctc arrow",
      rp.said[-1] == ("Monika", u"Ahaha— [[player]?"))
check("characters copy DDLC: quotes, ctc, and NO custom name colour",
      ns["_claude_char_for"]("yuri").kw == {"what_prefix": u'"', "what_suffix": u'"',
                                            "ctc": "ctc", "ctc_position": "fixed"})
ns["claude_bridge_say"]("narrator", u"Natsuki crosses her arms.")
check("narration has no name box", rp.said[-1] == (None, u"Natsuki crosses her arms."))
ns["claude_show_player_line"](u"can I read your poem?")
check("player's line uses DDLC's own `mc` (his name + quotes)",
      rp.said[-1] == ("Dfdfdf", u"can I read your poem?"))
before = len(rp.said)
ns["claude_show_player_line"](u"...")
check("an empty send isn't echoed", len(rp.said) == before)

# ── 3. faces ───────────────────────────────────────────────────────────────
print("[faces]")
faces = ns["CLAUDE_FACES"]
check("every face code is a real DDLC image",
      all((g, c) in DDLC_IMAGES for g, moods in faces.items() for c in moods.values()))
check("12 moods for every girl",
      all(len(m) == 12 and set(m) == set(faces["monika"]) for m in faces.values()))
check("each mood is a DIFFERENT face per girl (so changes are visible)",
      all(len(set(c[-1] if c[0] != "5" else c for c in m.values())) == 12
          for m in faces.values()))
check("measured faces: Sayori laugh = 1q ('Ehehe~')", faces["sayori"]["laugh"] == "1q")
check("measured faces: Natsuki pout = 5s ('Hmph.')", faces["natsuki"]["pout"] == "5s")
check("measured faces: Monika knowing = 5a (her lean-in)", faces["monika"]["knowing"] == "5a")
check("alias folds onto a real mood", ns["_claude_face"]("natsuki", "huffy") == "5s")
check("unknown mood -> that girl's neutral", ns["_claude_face"]("natsuki", "banana") == "2c")
with_dir = __import__("importlib").import_module
sys.path.insert(0, os.path.join(_ROOT, "game"))
from claude_mod import director as D                          # noqa: E402
check("bridge knows every mood the director can send",
      set(D._EXPRESSIONS) == set(faces["sayori"]))
check("bridge folds every director synonym",
      all(ns["_claude_face"]("yuri", w) != faces["yuri"]["neutral"] or D._EXPR_SYNONYMS[w] == "neutral"
          for w in D._EXPR_SYNONYMS))

# ── 4. the stage ───────────────────────────────────────────────────────────
print("[stage]")
rp.shown["monika"] = ("monika 1a", T("t11"), 0)          # left over from the real game
ns["claude_set_stage"](["natsuki", "yuri"])
check("a leftover sprite from the real game is removed", "monika" not in rp.shown)
check("two girls use DDLC's two-girl slots t21/t22",
      rp.shown["natsuki"][1] == T("t21") and rp.shown["yuri"][1] == T("t22"))
check("director's left-to-right order is kept", store._claude_stage_order == ["natsuki", "yuri"])
ns["claude_stage_update"]("yuri", "embarrassed")
check("the speaker steps forward (DDLC's f22) in front",
      rp.shown["yuri"][1] == T("f22") and rp.shown["yuri"][2] == 2)
check("her face changes to the measured code", rp.shown["yuri"][0] == "yuri 4b")
check("the listener stays back (t21, behind)",
      rp.shown["natsuki"][1] == T("t21") and rp.shown["natsuki"][2] == 1)
ns["claude_stage_update"]("natsuki", "pout")
check("next line: Natsuki forward with 'Hmph.' face, Yuri back to t22",
      rp.shown["natsuki"][:2] == ("natsuki 5s", T("f21")) and rp.shown["yuri"][1] == T("t22"))
ns["claude_stage_update"]("sayori", "laugh")
check("a girl who speaks without being listed walks in (3 slots now)",
      rp.shown["sayori"][1] == T("f33") and rp.shown["natsuki"][1] == T("t31"))
ns["claude_set_stage"]([])
check("an empty stage clears everyone", not rp.shown)
ns["claude_set_stage"](["monika"])
check("one girl is centred at t11", rp.shown["monika"][1] == T("t11"))
ns["claude_set_stage"](None)
check("stage None leaves the room alone", "monika" in rp.shown)
ns["claude_stage_update"]("narrator", "happy")
check("narration doesn't touch sprites", set(rp.shown) == {"monika"})

# ── 5. cues ────────────────────────────────────────────────────────────────
print("[cues]")
ns["claude_bridge_bg"]("black")
check("'black' is DDLC's `black` image (not 'bg black') and the girls come back",
      "black" in rp.shown and "monika" in rp.shown)
ns["claude_bridge_bg"]("glitch")
check("'glitch' is DDLC's real glitch background", rp.shown.get("bg", ("",))[0] == "bg glitch")
ns["claude_set_stage"](["sayori"])
rp.shown["sayori"] = ("sayori 1q", T("f11"), 2)       # mid-scene, she's talking
ns["claude_bridge_bg"]("glitch")
check("repeating the current room doesn't rebuild the scene (no re-entrances)",
      rp.shown["sayori"] == ("sayori 1q", T("f11"), 2))
ns["claude_bridge_bg"]("clubroom")
check("a real room change still happens", rp.shown["bg"][0] == "bg club_day")
ns["claude_bridge_music"]("happy")
check("music cue plays DDLC's track with if_changed (no restart)",
      rp.music_calls[-1][1] == store.audio.t3 and rp.music_calls[-1][2].get("if_changed") is True)
ns["claude_bridge_music"]("poems")
check("'poems' = DDLC's poem-sharing theme t5", rp.music_calls[-1][1] == store.audio.t5)
n = len(rp.music_calls)
ns["claude_bridge_music"]("keep")
check("'keep' changes nothing", len(rp.music_calls) == n)
ns["claude_bridge_effect"]("glitch")
check("glitch effect uses DDLC's own screen tear", "tear on" in rp.notes)

# ── 6. the seam + F9 ───────────────────────────────────────────────────────
print("[seam]")
seen = []
ns2, rp2, store2, config2 = fresh_bridge(prev_label_cb=lambda n, a: seen.append(n))
cb = config2.label_callback
cb("ch1_main", False)
check("other labels pass through (and chain DDLC's callback)", seen == ["ch1_main"])
try:
    cb("ch2_main", False)
    jumped = None
except Jump as e:
    jumped = str(e)
check("reaching ch2_main (right after the day-2 poem) starts the takeover",
      jumped == "claude_takeover_seam")
store2._claude_started = True
try:
    cb("ch2_main", False)
    again = False
except Jump:
    again = True
check("the seam never fires twice", not again)
store2._claude_started = False
store2.main_menu = True
try:
    ns2["claude_f9"]()
    f9 = False
except Jump:
    f9 = True
check("F9 does nothing on the main menu", not f9)
store2.main_menu = False
try:
    ns2["claude_f9"]()
    f9 = None
except Jump as e:
    f9 = str(e)
check("F9 mid-game takes over", f9 == "claude_takeover")
del store2._claude_started
try:
    cb("ch2_main", False)
    ok = True
except Jump:
    ok = True
except AttributeError:
    ok = False
check("seam check is safe before the game's variables exist", ok)

# ── 7. starting a run: tell the director where the game left off ───────────
print("[start]")
ns["_post_reply"] = {"turns": []}
ns["claude_start_run"]()
path, payload = ns["_post_log"][-1]
check("takeover calls /start", path == "/start")
check("sends his real name", payload["player_name"] == "Dfdfdf")
check("sends the day (chapter)", payload["chapter"] == 2)
check("sends only poem results that have happened",
      payload["route"]["poem_winners"] == ["yuri", "yuri"])
check("sends route appeal", payload["route"]["appeal"]["yuri"] == 2)
check("sends the last lines he read", payload["history"][-1]["what"] == '"Hi Dfdfdf~"')
check("sends what triggered it", payload["trigger"] == "manual")

# ── 8. input, model picker, poems ──────────────────────────────────────────
print("[input / models / poems]")
store._claude_inputs = 0
r = ns["claude_read_input"]()
check("typing uses our textbox screen (6.99-safe call_screen)",
      r == "hello there" and rp.last_screen[0] == "claude_input")
check("first prompt shows the hint, with his name in the name box",
      rp.last_screen[1]["hint"] and rp.last_screen[1]["who"] == "Dfdfdf")
ns["claude_read_input"]()
check("later prompts don't", rp.last_screen[1]["hint"] == u"")
rp.call_screen_fails = True
check("falls back to plain input if the screen fails",
      ns["claude_read_input"]() == "fallback input")
rp.input_reply, rp.call_screen_fails = "   ", False
check("blank Enter = let the club keep talking ('...')", ns["claude_read_input"]() == "...")

ns["_post_reply"] = {"model": "anthropic/claude-opus-5"}
ns["claude_set_model"]("anthropic/claude-opus-5", "Opus 5")
check("model switch confirmed in game", rp.notes[-1] == "Director model: Opus 5")
ns["_post_reply"] = {"model": "anthropic/claude-fable-5", "error": "unknown model x/y"}
ns["claude_set_model"]("x/y", "Typo")
check("a rejected model id is reported, not silently 'switched'",
      rp.notes[-1].startswith("Not switched"))
slugs = [s for _, s in ns["CLAUDE_MODELS"]]
check("Opus 5 is in the picker, no duplicates",
      "anthropic/claude-opus-5" in slugs and len(set(slugs)) == len(slugs))

p = ns["claude_make_poem"]({"author": "natsuki", "title": "Cats {x}", "text": "I [hate]\nthem"})
check("poem uses DDLC's own Poem object", isinstance(p, Poem) and p.author == "natsuki")
check("poem escapes braces only (its screen substitutes, then reads tags)",
      p.title == "Cats {{x}" and p.text == "I [hate]\nthem")
check("unknown author falls back to Monika",
      ns["claude_make_poem"]({"author": "ghost", "text": "x"}).author == "monika")
check("no text, no poem", ns["claude_make_poem"]({"author": "yuri"}) is None)

# ── 9. version handshake ───────────────────────────────────────────────────
print("[version]")
sc = open(os.path.join(_ROOT, "game", "claude_mod", "sidecar.py"), encoding="utf-8").read()
check("bridge expects the sidecar version that ships with it",
      re.search(r'SIDECAR_VERSION = "(\w+)"', sc).group(1) == ns["CLAUDE_EXPECTED_SIDECAR"])

print("\n%d passed, %d failed" % (len(PASS), len(FAIL)))
if FAIL:
    print("FAILED:", ", ".join(FAIL))
    raise SystemExit(1)
print("ALL GREEN")

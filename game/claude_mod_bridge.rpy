# claude_mod_bridge.rpy
# ─────────────────────────────────────────────────────────────────────────
# The GAME-SIDE half of the sidecar setup. This is the ONLY file you drop into
# base DDLC's game/ folder. It is written to run on DDLC's old Python 2 engine
# AND on modern Ren'Py 8 (Python 3).
#
# It does NOT import the claude_mod package or do any HTTPS — it just talks to
# the local sidecar (python sidecar.py) over plain http://127.0.0.1:8765. The
# sidecar is what runs the Python 3 director and calls OpenRouter.
#
# ⚠️  For base DDLC (Python 2): use THIS file only. Do NOT also copy
#     claude_mod_hooks.rpy or the claude_mod/ folder into the game — those are
#     Python 3 and will crash the old engine. The claude_mod/ folder runs
#     separately, as the sidecar.
#
# HOW TO START THE TAKEOVER
#   Play DDLC normally. When you (the prankster) want the AI to take over —
#   e.g. right after the day-2 poem/path choice — press  F9.  From then on the
#   club is driven by the director. Secret live controls during the takeover:
#       -  (minus)  escalate the creepiness
#       =  (equals) dial it back
#   (Later we can make F9 fire automatically at the seam; see CLAUDE_SEAM_LABEL.)
# ─────────────────────────────────────────────────────────────────────────

init python:
    import json
    import os

    _CLAUDE_BASE = "http://127.0.0.1:8765"

    # ---- Python 2/3-safe local HTTP POST/GET ------------------------------
    try:
        import urllib2 as _claude_url          # Python 2 (base DDLC)
        _claude_py = 2
    except ImportError:
        import urllib.request as _claude_url    # Python 3 (Ren'Py 8)
        _claude_py = 3

    def _claude_post(path, payload):
        body = json.dumps(payload)
        if _claude_py == 3:
            body = body.encode("utf-8")
        req = _claude_url.Request(_CLAUDE_BASE + path, body,
                                  {"Content-Type": "application/json"})
        resp = _claude_url.urlopen(req, timeout=120).read()
        if _claude_py == 3:
            resp = resp.decode("utf-8")
        return json.loads(resp)

    def claude_bridge_escalate():
        try:
            _claude_post("/escalate", {"amount": 1})
        except Exception:
            pass

    def claude_bridge_deescalate():
        try:
            _claude_post("/deescalate", {"amount": 1})
        except Exception:
            pass

    # ---- OPTIONAL: auto-seam. Leave "" to use the manual F9 trigger. -------
    # If you want the takeover to fire automatically when DDLC reaches a
    # specific label, set it here. To FIND the right label: set
    # CLAUDE_LOG_LABELS = True, play up to the day-2 poem/path choice, then open
    # claude_labels.log in the game folder and tell your setup which label
    # fired at that moment. Then put it here.
    CLAUDE_SEAM_LABEL = ""
    CLAUDE_LOG_LABELS = False

    def _claude_label_cb(name, abnormal):
        if CLAUDE_LOG_LABELS:
            try:
                with open(os.path.join(config.gamedir, "claude_labels.log"), "a") as f:
                    f.write(str(name) + "\n")
            except Exception:
                pass
        if CLAUDE_SEAM_LABEL and name == CLAUDE_SEAM_LABEL and not store._claude_started:
            store._claude_started = True
            renpy.jump("claude_takeover")

    if CLAUDE_LOG_LABELS or CLAUDE_SEAM_LABEL:
        config.label_callback = _claude_label_cb

    # ---- symbolic cue -> real DDLC asset maps (edit for your assets) -------
    # Backgrounds: base-DDLC names are real. Swap for your HD tags if different.
    CLAUDE_BG = {
        "clubroom": "club_day", "classroom": "class_day", "hallway": "corridor",
        "home": "residential_day", "black": "black", "void": "black", "glitch": "club_day",
    }
    # Music: 't3' is a real DDLC track; the emotional mapping is a guess — edit.
    CLAUDE_MUSIC = {
        "calm": "t1", "happy": "t1", "tense": "t3", "sad": "t4",
        "creepy": "t3", "glitch": "t3",
    }
    # Sprites: DDLC shows sprites like `show monika 1a`. Fill per your sprite
    # sheet; unknown moods just leave the current sprite unchanged.
    CLAUDE_SPRITE = {
        # "monika": {"neutral": "1a", "knowing": "1e"},
    }

    def claude_bridge_bg(symbol):
        if not symbol or symbol == "keep":
            return
        tag = CLAUDE_BG.get(symbol)
        if tag:
            try:
                renpy.scene(); renpy.show("bg " + tag)
            except Exception:
                pass

    def claude_bridge_music(symbol):
        if not symbol or symbol == "keep":
            return
        try:
            if symbol == "stop":
                renpy.music.stop(fadeout=2.0); return
            track = CLAUDE_MUSIC.get(symbol)
            if track:
                renpy.music.play(track, loop=True, fadein=1.0)
        except Exception:
            pass

    def claude_bridge_sprite(speaker, expression):
        tag = CLAUDE_SPRITE.get(speaker, {}).get(expression)
        if not tag:
            return
        try:
            renpy.show(speaker + " " + tag)
        except Exception:
            pass

    def claude_bridge_effect(effect):
        # TODO: wire to DDLC's real glitch/flash transforms. Stubbed so an
        # unknown effect never crashes the scene.
        pass


default _claude_started = False

# Secret keys: F9 starts the takeover; -/= nudge intensity during it.
screen claude_bridge_keys():
    key "K_F9" action Jump("claude_takeover")
    key "K_MINUS" action Function(claude_bridge_escalate)
    key "K_EQUALS" action Function(claude_bridge_deescalate)

init python:
    if "claude_bridge_keys" not in config.overlay_screens:
        config.overlay_screens.append("claude_bridge_keys")


# ─────────────────────────────────────────────────────────────────────────
# THE TAKEOVER LOOP
# ─────────────────────────────────────────────────────────────────────────
label claude_takeover:
    $ store._claude_started = True

    # Confirm the sidecar is running (visible to YOU, the setter, not the friend).
    python:
        _ok = True
        try:
            _claude_post("/mode", {"mode": store.claude_bridge_mode if hasattr(store, "claude_bridge_mode") else "story"})
        except Exception as _e:
            _ok = False
    if not _ok:
        "[[setup] Can't reach the director. Start it first: run  python sidecar.py"
        "[[setup] then press F9 again."
        return

    python:
        try:
            _r = _claude_post("/respond",
                              {"text": "(The player is now with the club, just after the path choice.)"})
        except Exception:
            _r = None
    call claude_render_beat(_r)

    label claude_bridge_loop:
        $ _reply = renpy.input("", length=280) or "..."
        python:
            try:
                _r = _claude_post("/respond", {"text": _reply})
            except Exception:
                _r = {"turns": [{"speaker": "monika", "expression": "neutral",
                                 "text": "...(the connection hiccuped)"}]}
        call claude_render_beat(_r)
        jump claude_bridge_loop


# Render one beat dict from the sidecar: cues, then each line one click at a time.
label claude_render_beat(r):
    if not r:
        "..."
        return
    python:
        claude_bridge_bg(r.get("background", "keep"))
        claude_bridge_music(r.get("music", "keep"))
        claude_bridge_effect(r.get("effect", "none"))
        for _line in r.get("turns", []):
            claude_bridge_sprite(_line.get("speaker"), _line.get("expression"))
            # TODO: route through the correct DDLC `say` character per speaker.
            renpy.say(None, _line.get("text", ""))
    return

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
#       -   (minus)  escalate the creepiness
#       =   (equals) dial it back
#       F10          open the model picker (Fable 5 / Opus / Sonnet / GLM)
#   (Later we can make F9 fire automatically at the seam; see CLAUDE_SEAM_LABEL.)
# ─────────────────────────────────────────────────────────────────────────

init python:
    import json
    import os

    _CLAUDE_BASE = "http://127.0.0.1:8765"

    # ---- Python 2/3-safe local HTTP POST ----------------------------------
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

    def claude_set_model(slug):
        try:
            _claude_post("/model", {"model": slug})
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

    # ── symbolic cue -> real base-DDLC asset maps (edit for your assets) ────
    # Backgrounds: base-DDLC tags. Shown as `scene bg <tag>`. Swap the tag
    # values for your HD background names if they differ.
    CLAUDE_BG = {
        "clubroom": "club_day", "classroom": "class_day", "hallway": "corridor",
        "home": "residential_day", "black": "black", "void": "black",
        "glitch": "club_day",
    }
    # Music: real base-DDLC track names (define audio.tX in DDLC). Emotional
    # mapping below is chosen to fit the game's own cues — tweak to taste.
    #   t3 "Play With Me" (clubroom)      t4 "Dreams of Love and Literature"
    #   t8 "Sayo-nara" (sad)              t9 "My Confession" (tense/uneasy)
    #   g1/g2 glitch-horror tracks
    CLAUDE_MUSIC = {
        "calm": "t4", "happy": "t3", "tense": "t9", "sad": "t8",
        "creepy": "g2", "glitch": "g1",
    }
    # Which DDLC dialogue Character each speaker maps to (used only as a hint;
    # we render nameboxes ourselves below so the name ALWAYS shows).
    CLAUDE_CHARS = {"sayori": "s", "natsuki": "n", "yuri": "y", "monika": "m"}

    # DDLC-style name colours for the namebox (approximate — edit to taste).
    CLAUDE_NAME_COLORS = {
        "sayori": "#f37e7e", "natsuki": "#f57ba5",
        "yuri": "#b18bd6", "monika": "#5eba7d",
    }

    # Sprite expression codes. Base DDLC uses `show <girl> 1a`, `1b`, `2a`...
    # "_default" is what shows when a mood isn't mapped, so a sprite ALWAYS
    # appears and nothing ever crashes. Fill in more codes once you've picked
    # base vs. DDLC+ sprites (the letters can differ per girl).
    CLAUDE_SPRITE = {
        "sayori":  {"_default": "1a", "happy": "1b", "surprised": "1c"},
        "natsuki": {"_default": "1a", "happy": "1b", "surprised": "1c"},
        "yuri":    {"_default": "1a", "happy": "1b", "surprised": "1c"},
        "monika":  {"_default": "1a", "happy": "1b", "surprised": "1c"},
    }

    # Model picker presets (label, OpenRouter slug). Edit freely.
    CLAUDE_MODELS = [
        ("Fable 5",  "anthropic/claude-fable-5"),
        ("Opus 4.8", "anthropic/claude-opus-4.8"),
        ("Opus 4.7", "anthropic/claude-opus-4.7"),
        ("Sonnet 5", "anthropic/claude-sonnet-5"),
        ("GLM 4.6",  "z-ai/glm-4.6"),
    ]

    # ── nameboxes: our own DDLC-styled Characters (deterministic) ──────────
    # We build a Character per girl with quotes + her colour, so the name box
    # ALWAYS renders through DDLC's own say screen. Cached after first use.
    _CLAUDE_SAY_CACHE = {}

    def _claude_char_for(speaker):
        if speaker in _CLAUDE_SAY_CACHE:
            return _CLAUDE_SAY_CACHE[speaker]
        name = speaker.capitalize()
        color = CLAUDE_NAME_COLORS.get(speaker)
        try:
            if color:
                who = Character(name, who_color=color,
                                what_prefix='"', what_suffix='"')
            else:
                who = Character(name, what_prefix='"', what_suffix='"')
        except Exception:
            who = None
        _CLAUDE_SAY_CACHE[speaker] = who
        return who

    def claude_bridge_say(speaker, text):
        speaker = (speaker or "").lower()
        if speaker in CLAUDE_CHARS:
            who = _claude_char_for(speaker)
            if who is not None:
                try:
                    renpy.say(who, text)
                    return
                except Exception:
                    pass
        # Unknown speaker / narration: no name box.
        renpy.say(None, text)

    # ── the player's real entered name (base DDLC stores it here) ──────────
    def _claude_player_name():
        n = None
        try:
            n = getattr(store.persistent, "playername", None)
        except Exception:
            n = None
        if not n:
            try:
                n = getattr(store, "player", None)
            except Exception:
                n = None
        return n or ""

    # ── background / music / effects ───────────────────────────────────────
    def claude_bridge_bg(symbol):
        if not symbol or symbol == "keep":
            return
        tag = CLAUDE_BG.get(symbol)
        if not tag:
            return
        try:
            renpy.scene()
            renpy.show("bg " + tag)
            _claude_render_stage()   # bring the girls back on top of the new bg
        except Exception:
            pass

    def claude_bridge_music(symbol):
        if not symbol or symbol == "keep":
            return
        try:
            if symbol == "stop":
                renpy.music.stop(fadeout=2.0)
                return
            track = CLAUDE_MUSIC.get(symbol)
            if not track:
                return
            # Resolve audio.t3 -> its filename+loop string when possible.
            src = getattr(store.audio, track, track)
            renpy.music.play(src, loop=True, fadein=1.0)
        except Exception:
            pass

    def claude_bridge_effect(effect):
        try:
            if effect == "shake":
                renpy.with_statement(vpunch)
            elif effect == "flash":
                renpy.with_statement(Fade(0.1, 0.0, 0.4, color="#ffffff"))
            # "glitch" is left as a safe no-op; wire to DDLC's real glitch
            # transform later if you want it.
        except Exception:
            pass

    # ── sprites: who's on stage, where, and with what face ─────────────────
    _CLAUDE_ORDER = ["sayori", "natsuki", "yuri", "monika"]

    def _claude_positions(n):
        if n <= 1:
            xs = [0.5]
        elif n == 2:
            xs = [0.30, 0.70]
        elif n == 3:
            xs = [0.20, 0.50, 0.80]
        else:
            xs = [0.15, 0.38, 0.62, 0.85]
        try:
            return [Transform(xalign=x, yalign=1.0) for x in xs]
        except Exception:
            return [None] * len(xs)

    def _claude_expr_code(speaker, expression):
        m = CLAUDE_SPRITE.get(speaker, {})
        code = m.get((expression or "").lower())
        return code or m.get("_default") or "1a"

    def _claude_render_stage(front=None):
        stage = store._claude_stage
        order = [g for g in _CLAUDE_ORDER if g in stage]
        if front in order:                       # draw the speaker last = on top
            order = [g for g in order if g != front] + [front]
        pos = _claude_positions(len(order))
        for i, g in enumerate(order):
            code = _claude_expr_code(g, stage.get(g))
            try:
                if pos[i] is not None:
                    renpy.show(g + " " + code, at_list=[pos[i]])
                else:
                    renpy.show(g + " " + code)
            except Exception:
                pass

    def claude_stage_update(speaker, expression):
        speaker = (speaker or "").lower()
        if speaker not in CLAUDE_CHARS:
            return                                # narration: don't touch sprites
        store._claude_stage[speaker] = expression
        _claude_render_stage(front=speaker)


default _claude_started = False
default _claude_stage = {}     # speaker -> last expression, for on-stage sprites

# Secret keys: F9 starts the takeover; -/= nudge intensity; F10 picks the model.
screen claude_bridge_keys():
    key "K_F9" action Jump("claude_takeover")
    key "K_MINUS" action Function(claude_bridge_escalate)
    key "K_EQUALS" action Function(claude_bridge_deescalate)
    key "K_F10" action Show("claude_model_menu")

init python:
    if "claude_bridge_keys" not in config.overlay_screens:
        config.overlay_screens.append("claude_bridge_keys")


# The model picker (F10). Modal, so it pauses the scene while you choose.
screen claude_model_menu():
    modal True
    zorder 200
    frame:
        align (0.5, 0.5)
        padding (30, 24)
        vbox:
            spacing 8
            text "Director model" size 26 xalign 0.5
            null height 6
            for _label, _slug in CLAUDE_MODELS:
                textbutton _label:
                    xfill True
                    action [Function(claude_set_model, _slug), Hide("claude_model_menu")]
            null height 6
            textbutton "Cancel" xalign 0.5 action Hide("claude_model_menu")


# ─────────────────────────────────────────────────────────────────────────
# THE TAKEOVER LOOP
# ─────────────────────────────────────────────────────────────────────────
label claude_takeover:
    # NOTE: we get here via a Jump (F9), so there is NO call frame to return to.
    # Never `return` from this label — once the AI takes over it runs its own
    # loop until the game closes. Connection problems are handled per-turn below.
    $ store._claude_started = True

    python:
        _pname = _claude_player_name()
        _intro = "(The player%s is now with the club, just after the path choice.)" % (
            (", named " + _pname) if _pname else "")
        try:
            _r = _claude_post("/respond", {"text": _intro, "player_name": _pname})
        except Exception:
            _r = {"turns": [{"speaker": "monika", "expression": "neutral",
                             "text": "...(is sidecar.py running? start it, then keep typing.)"}]}
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
            claude_stage_update(_line.get("speaker"), _line.get("expression"))
            claude_bridge_say(_line.get("speaker"), _line.get("text", ""))
    return

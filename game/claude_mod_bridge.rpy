# claude_mod_bridge.rpy
# ─────────────────────────────────────────────────────────────────────────
# The GAME-SIDE half of the mod. This is the ONLY file that goes into base
# DDLC's game/ folder — and you normally don't even copy it yourself: starting
# the sidecar (python game/claude_mod/sidecar.py) installs it for you.
#
# It runs on DDLC's own engine (Ren'Py 6.99.12, Python 2) and on Ren'Py 8. It
# does NOT import the claude_mod package or do any HTTPS — it only talks to the
# local sidecar at http://127.0.0.1:8765, which runs the director and calls
# OpenRouter.
#
# Everything visual here reuses DDLC's OWN pieces, verified against the game's
# source, so the takeover is indistinguishable from the real thing:
#   * name boxes / quotes / click-to-continue arrow  = DDLC's say screen + "ctc"
#   * the player's own lines                          = DDLC's `mc` character
#   * sprite positions, sizes, the speaker stepping forward, fade-out on exit
#                                                     = DDLC's t11..t44 / f11..f44 / thide
#   * faces                                           = the exact sprite codes DDLC's
#                                                       script uses for each emotion
#   * typing                                          = DDLC's textbox, font and caret
#   * poems                                           = DDLC's own showpoem: real
#                                                       paper, handwriting font, music
#   * music / backgrounds / glitch                    = DDLC's own tracks, rooms, tear
#
# WHEN THE AI TAKES OVER
#   Automatically, right after the day-2 poem (when the real game would start
#   chapter 2's club meeting) — see CLAUDE_SEAM_LABEL. Or any time you press F9.
#
# SECRET CONTROLS (during the takeover)
#   -  /  =      escalate / calm the creepiness   (ignored while typing)
#   F5 / F6      same, and they also work while typing
#   F10          model picker
# ─────────────────────────────────────────────────────────────────────────

init python:
    import json
    import os

    _CLAUDE_BASE = "http://127.0.0.1:8765"

    # This bridge needs a sidecar at least this new. Bump together with
    # SIDECAR_VERSION in sidecar.py.
    CLAUDE_EXPECTED_SIDECAR = "8"

    # ---- Python 2/3-safe local HTTP + text -------------------------------
    try:
        import urllib2 as _claude_url          # Python 2 (base DDLC)
        _claude_py = 2
    except ImportError:
        import urllib.request as _claude_url    # Python 3 (Ren'Py 8)
        _claude_py = 3

    try:
        _claude_unicode = unicode               # Python 2
    except NameError:
        _claude_unicode = str                   # Python 3

    def _claude_text(x):
        # Never str() game text on Python 2: Ren'Py 6.99 sets the default
        # encoding to the Windows codepage, so str() mangles "—" and "…" and
        # crashes outright on anything that codepage can't hold.
        if x is None:
            return u""
        if isinstance(x, _claude_unicode):
            return x
        if isinstance(x, bytes):
            return x.decode("utf-8", "replace")
        return _claude_unicode(x)

    def _claude_post(path, payload, timeout=120):
        body = json.dumps(payload)
        if _claude_py == 3:
            body = body.encode("utf-8")
        req = _claude_url.Request(_CLAUDE_BASE + path, body,
                                  {"Content-Type": "application/json"})
        resp = _claude_url.urlopen(req, timeout=timeout).read()
        return json.loads(resp.decode("utf-8"))

    def _claude_get(path):
        resp = _claude_url.urlopen(_CLAUDE_BASE + path, timeout=5).read()
        return json.loads(resp.decode("utf-8"))

    def _claude_escape(t):
        # Ren'Py reads [name] as variable interpolation and {tag} as a text
        # tag, so a stray bracket in a typed message or a line like "[sighs]"
        # would crash the say statement. Double them to show them literally.
        return _claude_text(t).replace(u"{", u"{{").replace(u"[", u"[[")

    def _claude_has_image(name):
        try:
            return tuple(name.split()) in renpy.display.image.images
        except Exception:
            return True                         # can't tell: assume DDLC has it

    # ---- the secret controls ---------------------------------------------
    # -/= are also characters the player types, so they're ignored while the
    # input box is open. F5/F6 always work.
    def claude_bridge_escalate(force=False):
        if store._claude_typing and not force:
            return
        try:
            _claude_post("/escalate", {"amount": 1}, timeout=5)
        except Exception:
            pass

    def claude_bridge_deescalate(force=False):
        if store._claude_typing and not force:
            return
        try:
            _claude_post("/deescalate", {"amount": 1}, timeout=5)
        except Exception:
            pass

    def claude_set_model(slug, label=u""):
        try:
            resp = _claude_post("/model", {"model": slug}, timeout=20)
        except Exception:
            renpy.notify(u"Couldn't reach the sidecar - is sidecar.py running?")
            return
        if resp.get("error"):
            renpy.notify(u"Not switched: " + _claude_text(resp.get("error"))[:80])
            return
        store._claude_model_now = _claude_text(resp.get("model", slug))
        renpy.notify(u"Director model: " + (_claude_text(label) or store._claude_model_now))

    def claude_check_sidecar():
        try:
            h = _claude_get("/health")
        except Exception:
            renpy.notify(u"Sidecar not reachable - start sidecar.py, then press F9 again")
            return False
        v = _claude_text(h.get("version", "0"))
        store._claude_model_now = _claude_text(h.get("model", u"?"))
        if v != CLAUDE_EXPECTED_SIDECAR:
            renpy.notify(u"OLD SIDECAR (v%s, need v%s): update the mod, restart sidecar.py"
                         % (v, CLAUDE_EXPECTED_SIDECAR))
        return True

    # ---- the seam: take over automatically ---------------------------------
    # The real game (Act 1) runs: day 1, poem, day 2 + first poem sharing, the
    # second poem (his path), then `call ch2_main` — the day-3 club meeting.
    # That label is the seam: everything before it is 100% the real game.
    # Set to "" to only ever take over with F9.
    CLAUDE_SEAM_LABEL = "ch2_main"
    CLAUDE_LOG_LABELS = False       # True = write every label to claude_labels.log

    import io

    _claude_prev_label_cb = config.label_callback
    if getattr(_claude_prev_label_cb, "__name__", "") == "_claude_label_cb":
        _claude_prev_label_cb = None            # a script reload: don't chain to ourselves

    def _claude_label_cb(name, abnormal):
        if _claude_prev_label_cb is not None:
            _claude_prev_label_cb(name, abnormal)
        if CLAUDE_LOG_LABELS:
            try:
                with io.open(os.path.join(config.gamedir, "claude_labels.log"), "a",
                             encoding="utf-8") as f:
                    f.write(_claude_text(name) + u"\n")
            except Exception:
                pass
        if (CLAUDE_SEAM_LABEL and name == CLAUDE_SEAM_LABEL
                and not getattr(store, "_claude_started", False)):
            renpy.jump("claude_takeover_seam")

    config.label_callback = _claude_label_cb

    def claude_f9():
        # F9 lives on an overlay that's up everywhere, including the main menu
        # (where the game's variables don't exist yet). Only act mid-game, once.
        if getattr(store, "main_menu", False) or getattr(store, "_claude_started", False):
            return
        renpy.jump("claude_takeover")

    # ── symbolic cue -> DDLC's own assets ──────────────────────────────────
    # Backgrounds (full image names - note DDLC's black is `black`, not `bg black`).
    CLAUDE_BG = {
        "clubroom": "bg club_day", "classroom": "bg class_day",
        "hallway": "bg corridor", "closet": "bg closet", "kitchen": "bg kitchen",
        "street": "bg residential_day", "home": "bg residential_day",
        "black": "black", "void": "black", "glitch": "bg glitch",
    }
    # Music, matched to how DDLC itself scores scenes: t2 when arriving / every
    # day, t3 club meetings, t5 poem sharing, t7 the Natsuki-Yuri fight, t8 sad,
    # t9 tense, t6 Act 2's club theme, t3g3 the club theme glitched, g1 noise,
    # m1 Monika's Act 3 room.
    CLAUDE_MUSIC = {
        "calm": "t2", "happy": "t3", "poems": "t5", "argument": "t7",
        "tense": "t9", "sad": "t8", "eerie": "t6", "creepy": "t3g3",
        "glitch": "g1", "monika": "m1",
    }

    # ── faces: the exact sprite code DDLC's script uses for each emotion ────
    # Measured from the real game: e.g. Sayori "laugh" = 1q, her "Ehehe~"
    # (43 uses); Natsuki "pout" = 5s, her "Hmph." (26); Yuri "embarrassed" =
    # 4b, "D-Don't say things like that..." (105); Monika "knowing" = 5a, her
    # teasing lean-in ("I have an idea, everyone~"). Every code below is a
    # defined image in DDLC's definitions.rpy. Change any you disagree with.
    CLAUDE_FACES = {
        "sayori":  {"neutral": "1a", "happy": "1x", "laugh": "1q", "excited": "4r",
                    "thinking": "1b", "surprised": "1h", "nervous": "4p",
                    "embarrassed": "1l", "sad": "1k", "angry": "1i", "pout": "5d",
                    "knowing": "1y"},
        "natsuki": {"neutral": "2c", "happy": "4z", "laugh": "4y", "excited": "4l",
                    "thinking": "2k", "surprised": "1o", "nervous": "1u",
                    "embarrassed": "1r", "sad": "12f", "angry": "1e", "pout": "5s",
                    "knowing": "2d"},
        "yuri":    {"neutral": "1a", "happy": "2s", "laugh": "1c", "excited": "1m",
                    "thinking": "1f", "surprised": "1e", "nervous": "2t",
                    "embarrassed": "4b", "sad": "2q", "angry": "3r", "pout": "2w",
                    "knowing": "1k"},
        "monika":  {"neutral": "1a", "happy": "1j", "laugh": "1k", "excited": "2b",
                    "thinking": "1m", "surprised": "1d", "nervous": "1l",
                    "embarrassed": "1p", "sad": "1g", "angry": "2i", "pout": "1r",
                    "knowing": "5a"},
    }
    # Older/improvised mood words fold onto the twelve above.
    CLAUDE_MOOD_ALIAS = {
        "normal": "neutral", "calm": "neutral", "serious": "neutral",
        "soft": "neutral", "quiet": "neutral",
        "smile": "happy", "pleased": "happy", "warm": "happy", "content": "happy",
        "fond": "happy", "amused": "happy", "bright": "happy",
        "cheerful": "happy", "gentle": "happy",
        "giggle": "laugh", "joy": "laugh", "grin": "laugh", "playful": "laugh",
        "teasing": "laugh",
        "eager": "excited", "thrilled": "excited", "energetic": "excited",
        "enthusiastic": "excited", "passionate": "excited",
        "thoughtful": "thinking", "pensive": "thinking", "hesitant": "thinking",
        "unsure": "thinking", "considering": "thinking",
        "shock": "surprised", "startled": "surprised", "confused": "surprised",
        "curious": "surprised", "wide-eyed": "surprised", "puzzled": "surprised",
        "worried": "nervous", "anxious": "nervous", "scared": "nervous",
        "panicked": "nervous", "uneasy": "nervous",
        "flustered": "embarrassed", "shy": "embarrassed", "bashful": "embarrassed",
        "blushing": "embarrassed",
        "hurt": "sad", "down": "sad", "disappointed": "sad", "hopeful": "sad",
        "crying": "sad", "melancholy": "sad", "wistful": "sad", "apologetic": "sad",
        "annoyed": "angry", "mad": "angry", "irritated": "angry",
        "defensive": "angry", "stern": "angry", "firm": "angry",
        "sulky": "pout", "huffy": "pout", "hmph": "pout", "exasperated": "pout",
        "smug": "knowing", "sly": "knowing", "wry": "knowing", "deadpan": "knowing",
        "glitch": "knowing", "sinister": "knowing", "cold": "knowing",
        "intense": "knowing",
    }

    # Model picker presets (label, OpenRouter id). The sidecar checks each id
    # with OpenRouter before switching, so a typo here can't break the game.
    CLAUDE_MODELS = [
        ("Opus 5",     "anthropic/claude-opus-5"),
        ("Opus 5.5",   "anthropic/claude-opus-5.5"),
        ("Fable 5",    "anthropic/claude-fable-5"),
        ("Sonnet 5",   "anthropic/claude-sonnet-5"),
        ("Sonnet 5.5", "anthropic/claude-sonnet-5.5"),
        ("Opus 4.8",   "anthropic/claude-opus-4.8"),
        ("Opus 4.7",   "anthropic/claude-opus-4.7"),
        ("GLM 4.7",    "z-ai/glm-4.7"),
    ]

    CLAUDE_GIRLS = ("sayori", "natsuki", "yuri", "monika")
    CLAUDE_NAMES = {"sayori": u"Sayori", "natsuki": u"Natsuki",
                    "yuri": u"Yuri", "monika": u"Monika"}

    # Shown faintly in the textbox the first time he's asked to type.
    CLAUDE_INPUT_HINT = u"type your reply, then press Enter"

    # ── speaking: DDLC's own say screen, quotes and click-to-continue arrow ─
    # (DDLC's names are all white with a pink outline - no per-girl colours.)
    _CLAUDE_SAY_CACHE = {}

    def _claude_character(name):
        kw = {"what_prefix": u'"', "what_suffix": u'"'}
        if _claude_has_image("ctc"):
            kw.update(ctc="ctc", ctc_position="fixed")
        try:
            return Character(name, **kw)
        except Exception:
            return None

    def _claude_char_for(speaker):
        if speaker not in _CLAUDE_SAY_CACHE:
            _CLAUDE_SAY_CACHE[speaker] = _claude_character(CLAUDE_NAMES[speaker])
        return _CLAUDE_SAY_CACHE[speaker]

    def claude_bridge_say(speaker, text):
        speaker = _claude_text(speaker).lower()
        text = _claude_escape(text)
        who = _claude_char_for(speaker) if speaker in CLAUDE_NAMES else None
        if who is not None:
            renpy.say(who, text)
        else:
            renpy.say(None, text)            # narration: DDLC's narrator, no box

    # ── the player: his real name + DDLC's own `mc` for his spoken lines ────
    def _claude_player_name():
        for getter in (lambda: store.persistent.playername, lambda: store.player):
            try:
                n = getter()
                if n:
                    return _claude_text(n)
            except Exception:
                pass
        return u""

    def claude_show_player_line(text):
        # His typed message becomes his line, exactly like `mc "..."` in the
        # real game - so it shows on screen AND lands in the History screen.
        text = _claude_text(text).strip()
        if not text or text == u"...":
            return
        who = getattr(store, "mc", None) if _claude_player_name() else None
        if who is None:
            who = _claude_character(_claude_player_name() or u"You")
        try:
            renpy.say(who, _claude_escape(text))
        except Exception:
            renpy.say(None, _claude_escape(text))

    # ── what the real game just showed him (so the AI continues from it) ────
    def _claude_recent_history(n=20):
        out = []
        try:
            for h in list(store._history_list)[-n:]:
                what = _claude_text(getattr(h, "what", u""))
                if what:
                    out.append({"who": _claude_text(getattr(h, "who", u"") or u""),
                                "what": what})
        except Exception:
            pass
        return out

    def _claude_chapter():
        try:
            return int(getattr(store, "chapter", 0) or 0)
        except Exception:
            return 0

    def _claude_route():
        route = {}
        try:
            winners = list(getattr(store, "poemwinner", []) or [])[:_claude_chapter()]
            route["poem_winners"] = [_claude_text(w) for w in winners]
        except Exception:
            pass
        try:
            route["appeal"] = {"sayori": int(store.s_appeal), "natsuki": int(store.n_appeal),
                               "yuri": int(store.y_appeal)}
        except Exception:
            pass
        return route

    def claude_start_run():
        payload = {"player_name": _claude_player_name(),
                   "history": _claude_recent_history(),
                   "chapter": _claude_chapter(),
                   "route": _claude_route(),
                   "trigger": store._claude_trigger}
        try:
            return _claude_post("/start", payload)
        except Exception:
            pass
        renpy.notify(u"Sidecar not reachable - is sidecar.py running?")
        return {"turns": [{"speaker": "monika", "expression": "neutral", "text": u"..."}]}

    def claude_read_input():
        hint = CLAUDE_INPUT_HINT if not store._claude_inputs else u""
        store._claude_inputs += 1
        try:
            # DDLC's engine has no renpy.input(screen=...), so call our textbox
            # screen directly: its input returns the text when Enter is pressed.
            rv = renpy.call_screen("claude_input", who=_claude_player_name(), hint=hint)
        except Exception:
            rv = renpy.input(u"", length=300)
        rv = _claude_text(rv).strip()
        return rv or u"..."

    # ── background / music / effects ───────────────────────────────────────
    def claude_bridge_bg(symbol):
        img = CLAUDE_BG.get(_claude_text(symbol))
        if not img or not _claude_has_image(img):
            return
        if img == store._claude_bg:
            # Models often repeat the room instead of saying "keep". Rebuilding
            # the scene anyway would replay every girl's entrance each beat.
            return
        try:
            renpy.scene()
            renpy.show(img)
        except Exception:
            return
        store._claude_bg = img
        _claude_render_stage()               # the girls, back on top of the room
        try:
            renpy.with_statement(Dissolve(0.5))
        except Exception:
            pass

    def claude_bridge_music(symbol):
        symbol = _claude_text(symbol)
        try:
            if symbol == u"stop":
                renpy.music.stop(fadeout=2.0)
                return
            src = getattr(store.audio, CLAUDE_MUSIC.get(symbol, ""), None)
            if src:
                # if_changed: asking for the song that's already playing must
                # not restart it from the top.
                renpy.music.play(src, loop=True, fadeout=1.0, fadein=1.0, if_changed=True)
        except Exception:
            pass

    def claude_bridge_effect(effect):
        effect = _claude_text(effect)
        try:
            if effect == u"shake":
                renpy.with_statement(vpunch)
            elif effect == u"flash":
                renpy.with_statement(Fade(0.1, 0.0, 0.4, color="#ffffff"))
            elif effect == u"glitch" and renpy.has_screen("tear"):
                # DDLC's own screen tear, timed exactly like its Act 2 uses.
                renpy.show_screen("tear", 20, 0.1, 0.1, 0, 40)
                renpy.music.play("sfx/s_kill_glitch1.ogg", channel="sound")
                renpy.pause(0.25, hard=True)
                renpy.music.stop(channel="sound")
                renpy.hide_screen("tear")
        except Exception:
            pass

    # ── sprites: DDLC's own slots, sizes and "speaker steps forward" ────────
    # 1 girl: t11 · 2: t21 t22 · 3: t31-t33 · 4: t41-t44, all at DDLC's zoom
    # 0.80; whoever is talking uses the matching fXX (zoom 0.84, in front).
    _CLAUDE_SLOTS = {1: ("11",), 2: ("21", "22"), 3: ("31", "32", "33"),
                     4: ("41", "42", "43", "44")}
    _CLAUDE_X = {"11": 640, "21": 400, "22": 880, "31": 240, "32": 640, "33": 1040,
                 "41": 200, "42": 493, "43": 786, "44": 1080}

    def _claude_transform(prefix, slot):
        t = getattr(store, prefix + slot, None)          # DDLC's own t11 / f21 ...
        if t is not None:
            return t
        return Transform(xcenter=_CLAUDE_X[slot], yanchor=1.0, ypos=1.03,
                         zoom=0.84 if prefix == "f" else 0.80)

    def _claude_face(girl, mood):
        mood = _claude_text(mood).lower().strip()
        mood = CLAUDE_MOOD_ALIAS.get(mood, mood)
        faces = CLAUDE_FACES[girl]
        return faces.get(mood) or faces["neutral"]

    def _claude_show_girl(girl, code, at, zorder):
        for c in (code, CLAUDE_FACES[girl]["neutral"]):
            try:
                renpy.show(girl + " " + c, at_list=[at], zorder=zorder)
                return
            except Exception:
                pass

    def _claude_render_stage(speaker=None):
        order = [g for g in store._claude_stage_order if g in store._claude_stage]
        slots = _CLAUDE_SLOTS.get(len(order), ())
        for g, slot in zip(order, slots):
            talking = (g == speaker)
            _claude_show_girl(g, _claude_face(g, store._claude_stage[g]),
                              _claude_transform("f" if talking else "t", slot),
                              2 if talking else 1)

    def _claude_hide_girl(girl):
        # DDLC's exit: `show <girl> at thide` then `hide <girl>` (fades out).
        try:
            if not renpy.showing(girl):
                return
        except Exception:
            pass
        try:
            thide = getattr(store, "thide", None)
            if thide is not None:
                renpy.show(girl, at_list=[thide], zorder=1)
        except Exception:
            pass
        try:
            renpy.hide(girl)
        except Exception:
            pass

    def claude_clear_girls():
        # Clear every girl - including sprites the real game left on screen.
        store._claude_stage = {}
        store._claude_stage_order = []
        for g in CLAUDE_GIRLS:
            try:
                renpy.hide(g)
            except Exception:
                pass

    def claude_set_stage(present):
        # The director's authoritative list of who is in the room, left to
        # right. None = leave the stage alone. [] = everyone leaves.
        if present is None:
            return
        present = [g for g in (_claude_text(p).lower() for p in present) if g in CLAUDE_FACES]
        for g in CLAUDE_GIRLS:
            if g not in present:
                if g in store._claude_stage:
                    del store._claude_stage[g]
                _claude_hide_girl(g)         # also fades any leftover from the real game
        for g in present:
            if g not in store._claude_stage:
                store._claude_stage[g] = u"neutral"
        store._claude_stage_order = present
        _claude_render_stage()

    def claude_stage_update(speaker, mood):
        speaker = _claude_text(speaker).lower()
        if speaker not in CLAUDE_FACES:
            return                            # narration: sprites stay as they are
        if speaker not in store._claude_stage:
            store._claude_stage_order = list(store._claude_stage_order) + [speaker]
        store._claude_stage[speaker] = _claude_text(mood) or u"neutral"
        _claude_render_stage(speaker=speaker)

    # ── poems: DDLC's own Poem + showpoem (real paper, font, music) ─────────
    def claude_make_poem(p):
        if not p or not p.get("text"):
            return None
        author = _claude_text(p.get("author") or u"monika").lower()
        if author not in CLAUDE_FACES:
            author = u"monika"
        # Poem text goes through "[currentpoem.text]" substitution, which
        # doesn't re-read brackets but DOES read text tags - escape braces only.
        title = _claude_text(p.get("title")).replace(u"{", u"{{")
        text = _claude_text(p.get("text")).replace(u"{", u"{{")
        try:
            return Poem(author=author, title=title, text=text)
        except Exception:
            return None


default _claude_started = False
default _claude_trigger = "manual"
default _claude_stage = {}         # girl -> current mood
default _claude_stage_order = []   # left-to-right, as the director placed them
default _claude_model_now = ""     # last model the sidecar reported (F10 menu)
default _claude_typing = False     # True while his input box is open
default _claude_inputs = 0         # how many times he's been asked to type
default _claude_bg = None          # the room currently on screen

# F9 starts the takeover (once); -/= and F5/F6 nudge intensity; F10 = models.
# (F11 is the engine's fullscreen key, so it's left alone.)
screen claude_bridge_keys():
    key "K_F9" action Function(claude_f9)
    key "K_MINUS" action Function(claude_bridge_escalate)
    key "K_EQUALS" action Function(claude_bridge_deescalate)
    key "K_F5" action Function(claude_bridge_escalate, True)
    key "K_F6" action Function(claude_bridge_deescalate, True)
    key "K_F10" action Show("claude_model_menu")

init python:
    if "claude_bridge_keys" not in config.overlay_screens:
        config.overlay_screens.append("claude_bridge_keys")


# The model picker (F10).
screen claude_model_menu():
    modal True
    zorder 200
    frame:
        align (0.5, 0.5)
        padding (30, 24)
        vbox:
            spacing 6
            text "Director model" size 26 xalign 0.5
            if _claude_model_now:
                text ("now: " + _claude_model_now) size 16 xalign 0.5
            null height 6
            for _label, _slug in CLAUDE_MODELS:
                textbutton _label:
                    xfill True
                    action [Hide("claude_model_menu"), Function(claude_set_model, _slug, _label)]
            null height 6
            textbutton "Cancel" xalign 0.5 action Hide("claude_model_menu")


# The text he types: DDLC's dialogue style (`normal` - same font, size,
# outline, position and wrap width as the girls' lines) plus DDLC's own
# blinking pink caret. (6.99's `input` statement doesn't accept `caret`
# directly - DDLC sets it through a style too, so we do the same.)
style claude_input is normal:
    caret "input_caret"

# Typing a reply, inside DDLC's own textbox: the same box, name tag, font,
# wrapping width and caret as the real dialogue. Enter sends.
screen claude_input(who="", hint=""):
    window:
        style "window"
        if who:
            window:
                style "namebox"
                text who style "say_label"
        input:
            style "claude_input"
            length 300
            exclude "{}"
        if hint:
            text hint size 16 color "#ffffffaa" xalign 0.97 yalign 0.92
    if renpy.has_screen("quick_menu"):
        use quick_menu


# ─────────────────────────────────────────────────────────────────────────
# THE TAKEOVER
# ─────────────────────────────────────────────────────────────────────────

# Automatic entry at the seam: open day 3 exactly like the real chapter 2 does.
label claude_takeover_seam:
    $ store._claude_trigger = "seam"
    $ claude_clear_girls()
    scene bg club_day
    with Dissolve(1.0)
    $ store._claude_bg = "bg club_day"
    play music t2
    "Another day passes, and it's time for the club meeting already."
    jump claude_takeover

label claude_takeover:
    # Reached by a jump (F9 or the seam): there is no call frame to return to,
    # so this never returns - it runs its own loop for the rest of the game.
    $ store._claude_started = True
    $ config.skipping = False         # Skip mode must not race past the AI's lines
    $ _rollback = False               # scrolling back would re-send (and re-pay for) turns
    $ claude_clear_girls()
    $ claude_check_sidecar()
    python:
        _r = claude_start_run()
        renpy.block_rollback()
    call claude_render_beat(_r)

    label claude_bridge_loop:
        python:
            store._claude_typing = True
            try:
                _reply = claude_read_input()
            finally:
                store._claude_typing = False
        $ claude_show_player_line(_reply)
        python:
            try:
                _r = _claude_post("/respond", {"text": _reply})
            except Exception:
                renpy.notify(u"Sidecar didn't answer - is sidecar.py still running?")
                _r = {"turns": [{"speaker": "monika", "expression": "neutral", "text": u"..."}]}
            renpy.block_rollback()
        call claude_render_beat(_r)
        jump claude_bridge_loop


# Render one beat: cues, who's in the room, each line (with her face for that
# line), then - if someone's poem is being read - DDLC's real poem screen.
label claude_render_beat(r):
    if not r:
        "..."
        return
    python:
        # If the call failed, tell the setter (the girls just say "...").
        if r.get("error"):
            renpy.notify(u"Director error: " + _claude_text(r.get("error"))[:90])
        claude_bridge_bg(r.get("background", "keep"))
        claude_bridge_music(r.get("music", "keep"))
        claude_set_stage(r.get("stage"))
        claude_bridge_effect(r.get("effect", "none"))
        _said = 0
        for _line in r.get("turns", []):
            if not _line.get("text"):
                continue
            claude_stage_update(_line.get("speaker"), _line.get("expression"))
            claude_bridge_say(_line.get("speaker"), _line.get("text", ""))
            _said += 1
        if not _said:                         # never loop back with nothing on screen
            renpy.say(None, u"...")
        _claude_poem = claude_make_poem(r.get("poem"))
    if _claude_poem is not None and renpy.has_label("showpoem"):
        call showpoem(_claude_poem)
    return

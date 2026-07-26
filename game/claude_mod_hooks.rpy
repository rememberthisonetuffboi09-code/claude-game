# claude_mod_hooks.rpy
# ─────────────────────────────────────────────────────────────────────────
# Ren'Py glue between base DDLC and the OpenRouter "director brain".
#
# WHAT THIS FILE DOES
#   * boots the director brain (game/claude_mod, pure Python)
#   * provides label `claude_mod_takeover` — the AI dialogue loop
#   * runs API calls on a background thread so the game never freezes
#   * applies the director's STAGE DIRECTIONS each turn: character + expression,
#     MUSIC, BACKGROUND, and screen EFFECT
#   * binds the secret hotkeys:  -  = escalate   |   =  = de-escalate
#
# HOW TO WIRE IT INTO DDLC (the "seam")
#   The authentic game plays untouched through Act 1 up to the day-2 poem/path
#   choice. At THAT point, hand off to us — in DDLC's day-2 script, right after
#   the poem/path selection, add:
#
#       jump claude_mod_takeover
#
#   >>> TODO: confirm the exact label/line in your local DDLC script. <<<
#
# SYMBOLIC -> REAL ASSET MAPS
#   The model emits symbolic cues (music "creepy", background "hallway"); the
#   maps below turn those into your real DDLC/DDLC+ asset tags. Seeded with the
#   real base-DDLC names from the script; fill the TODOs with your HD assets.
# ─────────────────────────────────────────────────────────────────────────

init python:
    import os
    import sys
    import threading

    _CLAUDE_ROOT = os.path.join(renpy.config.gamedir)
    if _CLAUDE_ROOT not in sys.path:
        sys.path.insert(0, _CLAUDE_ROOT)

    import claude_mod

    def claude_boot(session_name="playthrough1"):
        try:
            store.claude_director = claude_mod.make_director(session_name)
            store.claude_ready = True
        except Exception as e:
            store.claude_director = None
            store.claude_ready = False
            store.claude_boot_error = str(e)

    # ── background API call (keeps the UI thread responsive) ───────────────
    def _bg_respond(holder, director, text):
        try:
            holder["turn"] = director.respond(text)
        except Exception as e:
            holder["error"] = str(e)

    def claude_respond(director, text):
        holder = {}
        t = threading.Thread(target=_bg_respond, args=(holder, director, text))
        t.start()
        renpy.show_screen("claude_typing")
        while t.is_alive():
            renpy.pause(0.05, hard=True)
        renpy.hide_screen("claude_typing")
        return holder.get("turn")

    # ── secret hotkeys ─────────────────────────────────────────────────────
    def claude_escalate():
        if getattr(store, "claude_director", None):
            store.claude_director.escalate(1.0)

    def claude_deescalate():
        if getattr(store, "claude_director", None):
            store.claude_director.deescalate(1.0)

    # ── symbolic -> real asset maps (EDIT THESE for your assets) ───────────
    # Backgrounds: these base-DDLC names are REAL (from the script). Swap the
    # values for your DDLC+ HD backgrounds if the tags differ.
    CLAUDE_BG = {
        "clubroom":  "club_day",
        "classroom": "class_day",
        "hallway":   "corridor",
        "home":      "residential_day",
        "black":     "black",
        "void":      "black",     # TODO: a proper "Monika's room / void" bg
        "glitch":    "club_day",  # TODO: a glitched variant
    }
    # Music: 't3' is a real DDLC track name from the script. The emotional
    # mapping below is a guess — verify against your soundtrack and edit.
    CLAUDE_MUSIC = {
        "calm":   "t1",   # TODO verify
        "happy":  "t1",   # TODO verify
        "tense":  "t3",
        "sad":    "t4",   # TODO verify
        "creepy": "t3",   # TODO: Monika/ominous track
        "glitch": "t3",   # TODO: glitch/distorted track
    }
    # Sprites: DDLC shows sprites like `show monika 1a`. Map each character's
    # mood word to a real expression tag. Left mostly empty — fill from your
    # sprite sheet; unknown moods simply leave the current sprite unchanged.
    CLAUDE_SPRITE = {
        # "monika":  {"neutral": "1a", "knowing": "1e", "glitch": "..."},
        # "sayori":  {"happy": "1b", "sad": "1r", ...},
        # "natsuki": {...},
        # "yuri":    {...},
    }

    def claude_apply_background(symbol):
        if not symbol or symbol == "keep":
            return
        tag = CLAUDE_BG.get(symbol)
        if not tag:
            return
        try:
            renpy.scene()
            renpy.show("bg " + tag)
        except Exception:
            pass

    def claude_apply_music(symbol):
        if not symbol or symbol == "keep":
            return
        try:
            if symbol == "stop":
                renpy.music.stop(fadeout=2.0)
                return
            track = CLAUDE_MUSIC.get(symbol)
            if track:
                renpy.music.play(track, loop=True, fadein=1.0)
        except Exception:
            pass

    def claude_show(speaker, expression):
        tag = CLAUDE_SPRITE.get(speaker, {}).get(expression)
        if not tag:
            return  # leave current sprite; dialogue still shows
        try:
            renpy.show(speaker + " " + tag)
        except Exception:
            pass

    def claude_apply_effect(effect):
        # TODO: wire to DDLC's real glitch/flash transforms. Stubbed so the game
        # never crashes on an unknown effect.
        if not effect or effect == "none":
            return
        # e.g. renpy.with_statement(vpunch) for "shake", a glitch shader, etc.


# Global-while-shown hotkey layer. Shown only during the AI takeover.
screen claude_hotkeys():
    key "K_MINUS" action Function(claude_escalate)
    key "K_EQUALS" action Function(claude_deescalate)

# A quiet "she's typing" indicator during the API round-trip.
screen claude_typing():
    text "..." align (0.5, 0.9) size 30   # TODO: style to match the DDLC textbox


# ─────────────────────────────────────────────────────────────────────────
# THE TAKEOVER LOOP — the game jumps here at the seam.
# ─────────────────────────────────────────────────────────────────────────
label claude_mod_takeover:
    $ claude_boot("playthrough1")

    if not store.claude_ready:
        # Fail visibly to YOU (the setter), not mysteriously to the player.
        "[[setup] Director failed to start: [claude_boot_error!q]"
        "[[setup] Check game/claude_mod/config.json (OpenRouter key / model)."
        return

    show screen claude_hotkeys

    python:
        _mode = store.claude_director.config.get("default_mode", "story")
        store.claude_director.set_mode(_mode)
        _seed = ("(The player returns to the club.)"
                 if store.claude_director.memory.is_returning_player()
                 else "(The player sits with the club after choosing their path.)")

    $ _turn = claude_respond(store.claude_director, _seed)
    call claude_render(_turn)

    label claude_loop:
        python:
            _reply = renpy.input("", length=280) or "..."
        $ _turn = claude_respond(store.claude_director, _reply)
        call claude_render(_turn)
        jump claude_loop


# Render one Beat: background + music + effect, then each line in turn (one
# click each), then the safe file effect. A beat is 1..4 lines, so the girls
# can talk to each other inside a single API call.
label claude_render(turn):
    if turn is None:
        "..."
        return
    python:
        _beat = turn
        claude_apply_background(_beat.background)
        claude_apply_music(_beat.music)
        claude_apply_effect(_beat.effect)

        for _line in _beat.turns:
            claude_show(_line.speaker, _line.expression)
            # TODO: route through the correct DDLC character `say` so the right
            # name/box style shows per speaker — with renpy.say() that is now a
            # one-liner: renpy.say(claude_character_for(_line.speaker), _line.text)
            renpy.say(None, _line.text)

        # Fires after the whole beat so drop_note sees every line. Each action
        # type is once-per-session; the director enforces that.
        store.claude_director.perform_action(_beat)
    return

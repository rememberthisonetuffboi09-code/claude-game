# claude_mod_hooks.rpy
# ─────────────────────────────────────────────────────────────────────────
# Ren'Py glue between base DDLC and the Fable 5 "director brain".
#
# WHAT THIS FILE DOES
#   * boots the director brain (game/claude_mod, pure Python)
#   * provides the label `claude_mod_takeover` that runs the AI dialogue loop
#   * runs API calls on a background thread so the game never freezes
#   * binds the secret hotkeys:  -  = escalate   |   =  = de-escalate
#
# HOW TO WIRE IT INTO DDLC (the "seam")
#   The authentic game plays untouched through Act 1 up to the day-2 poem/path
#   choice. At THAT point, hand off to us. In DDLC's day-2 script, right after
#   the poem/path selection, add:
#
#       jump claude_mod_takeover
#
#   >>> TODO: confirm the exact label/line in your local DDLC script. <<<
# ─────────────────────────────────────────────────────────────────────────

init python:
    import os
    import sys
    import threading

    # Make the pure-Python package importable from Ren'Py's game/ folder.
    _CLAUDE_ROOT = os.path.join(renpy.config.gamedir)
    if _CLAUDE_ROOT not in sys.path:
        sys.path.insert(0, _CLAUDE_ROOT)

    import claude_mod

    # One director per playthrough. Persisted to the store so hotkeys can reach it.
    def claude_boot(session_name="playthrough1"):
        try:
            store.claude_director = claude_mod.make_director(session_name)
            store.claude_ready = True
        except Exception as e:
            store.claude_director = None
            store.claude_ready = False
            store.claude_boot_error = str(e)

    # ── background API call (so the UI thread stays responsive) ────────────
    def _bg_respond(holder, director, text):
        try:
            holder["turn"] = director.respond(text)
        except Exception as e:
            holder["error"] = str(e)

    def claude_respond(director, text):
        """Call the model off-thread; show a 'typing' beat; return a DokiTurn."""
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

    # ── expression -> sprite ───────────────────────────────────────────────
    # TODO: map moods to your actual DDLC / DDLC+ HD sprite tags. DDLC sprites
    # are shown like:  show monika 1a   /   show natsuki 2b
    # This guarded helper won't crash if a tag is missing while you wire assets.
    def claude_show(speaker, expression):
        # Placeholder mapping — replace values with real image tags/attributes.
        mapping = {
            # "monika": {"neutral": "monika 1a", "knowing": "monika 1e", ...},
        }
        tag = mapping.get(speaker, {}).get(expression)
        if not tag:
            return  # no sprite change yet — dialogue still shows
        try:
            renpy.show(tag)
        except Exception:
            pass  # missing asset shouldn't break the scene


# Global-while-shown hotkey layer. Shown only during the AI takeover.
screen claude_hotkeys():
    key "K_MINUS" action Function(claude_escalate)
    key "K_EQUALS" action Function(claude_deescalate)

# A quiet "she's typing" indicator during the API round-trip.
screen claude_typing():
    # TODO: style this to match DDLC (e.g. the textbox with an animated "...").
    text "..." align (0.5, 0.9) size 30

# Pick a mode at the start of the takeover.
screen claude_mode_select():
    modal True
    vbox align (0.5, 0.5) spacing 20:
        text "..." size 40 align (0.5, 0.5)
        textbutton "Continue" action [SetVariable("claude_mode", "story"), Return("story")]
        textbutton "..." action [SetVariable("claude_mode", "monika"), Return("monika")]
    # NOTE: keep this subtle/in-universe; the friend shouldn't clock it as a menu.


# ─────────────────────────────────────────────────────────────────────────
# THE TAKEOVER LOOP — the game jumps here at the seam.
# ─────────────────────────────────────────────────────────────────────────
label claude_mod_takeover:
    $ claude_boot("playthrough1")

    if not store.claude_ready:
        # Fail visibly to YOU (the setter), not mysteriously to the player.
        "[[setup] Director failed to start: [claude_boot_error!q]"
        "[[setup] Check game/claude_mod/config.json (API key)."
        return

    show screen claude_hotkeys

    # Mode: use config default, or uncomment to choose at runtime.
    # call screen claude_mode_select
    python:
        _mode = store.claude_director.config.get("default_mode", "story")
        store.claude_director.set_mode(_mode)

    # Greet a returning player differently ("back so soon?").
    python:
        _seed = ("(The player returns to the club.)"
                 if store.claude_director.memory.is_returning_player()
                 else "(The player sits with the club after choosing their path.)")

    $ _turn = claude_respond(store.claude_director, _seed)
    call claude_render(_turn)

    # Main conversational loop.
    label claude_loop:
        python:
            _reply = renpy.input("", length=280) or "..."
        $ _turn = claude_respond(store.claude_director, _reply)
        call claude_render(_turn)
        jump claude_loop

# Render one DokiTurn: sprite + line + any safe effect.
label claude_render(turn):
    if turn is None:
        "..."
        return
    $ claude_show(turn.speaker, turn.expression)
    $ _fx = store.claude_director.perform_action(turn)  # safe effects only
    # Show the line. TODO: route through the correct DDLC character `say` so the
    # right name/box style shows. For now, narrate generically.
    "[turn.text]"
    return

#!/usr/bin/env python3
"""
chat_cli.py — talk to the REAL director from a terminal. This replaces the old
standalone monika_chat.py for testing: it runs the actual v2 system (crack
budget, beats, persona bible, prompt caching), so what you test is what ships —
and caching makes long sessions far cheaper than the old script.

Run:   python game/claude_mod/chat_cli.py

Commands:
  /hot            intensity +2        (the '-' key in-game)
  /cool           intensity -2        (the '=' key in-game)
  /pin N          pin intensity at N and stop drift (e.g. /pin 1 for the
                  adversarial-normalcy test); /pin off resumes drift
  /debug          toggle telemetry (crack label, counters, cache stats)
  /mode story|monika
  /reset          wipe this test session's memory and start clean
  /quit
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

from claude_mod import load_config, Director  # noqa: E402
from claude_mod.openrouter_client import LLMError  # noqa: E402

SESSION = "__cli_test__"
FRESH_SEED = "(The player sits with the club after choosing their path.)"
RESUME_SEED = "(The player returns to the club.)"


def make_director(config, telemetry):
    """Build a director whose client calls record usage for /debug."""
    d = Director(config, session_name=SESSION)
    orig = d.client.complete

    def wrapped(system, messages):
        result = orig(system, messages)
        telemetry["last"] = result
        telemetry["calls"] = telemetry.get("calls", 0) + 1
        return result

    d.client.complete = wrapped
    return d


def show_debug(d, beat, telemetry):
    r = telemetry.get("last")
    usage = getattr(r, "usage", {}) or {}
    prompt_toks = usage.get("prompt_tokens")
    cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens")
    print("  [debug] crack=%s  intensity=%.1f  band-clean-turns=%d  open-used=%s"
          % (beat.crack, d.intensity, d.turns_since_crack, d.open_used_this_band))
    print("  [debug] served-by=%s  api-calls=%d  prompt-tokens=%s  cached=%s"
          % (beat.model or "?", telemetry.get("calls", 0), prompt_toks, cached))
    if beat.music != "keep" or beat.background != "keep" or beat.effect != "none" or beat.action != "none":
        print("  [debug] cues: music=%s bg=%s fx=%s action=%s"
              % (beat.music, beat.background, beat.effect, beat.action))
    print()


def main():
    config = load_config()
    if "PUT-YOUR" in config.get("api_key", ""):
        print("[!] Set your key in game/claude_mod/config.json first.")
        return 1

    telemetry = {}
    d = make_director(config, telemetry)
    debug = False
    pinned = None

    print("=== DDLC director test console ===")
    print("model: %s   pace: %s   mode: %s" % (d.client.model, d.pace, d.mode))
    print("commands: /hot /cool /pin N /debug /mode /reset /quit\n")

    resuming = d.memory.is_returning_player()
    if resuming:
        print("(resuming an existing test session — /reset for a clean one)\n")
    pending = RESUME_SEED if resuming else FRESH_SEED

    while True:
        if pending is not None:
            text, pending = pending, None
        else:
            try:
                text = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not text:
                continue
            low = text.lower()
            if low == "/quit":
                break
            if low == "/hot":
                print("   (intensity %.1f)\n" % d.escalate(2)); continue
            if low == "/cool":
                print("   (intensity %.1f)\n" % d.deescalate(2)); continue
            if low == "/debug":
                debug = not debug
                print("   (debug %s)\n" % ("on" if debug else "off")); continue
            if low.startswith("/pin"):
                arg = low.split(None, 1)[1] if " " in low else ""
                if arg == "off":
                    pinned = None
                    print("   (drift resumed)\n")
                else:
                    try:
                        pinned = max(0.0, min(10.0, float(arg)))
                        d.intensity = pinned
                        d._sync_band()
                        print("   (pinned at %.1f)\n" % pinned)
                    except ValueError:
                        print("   usage: /pin 3.5   or   /pin off\n")
                continue
            if low.startswith("/mode"):
                arg = low.split(None, 1)[1] if " " in low else ""
                d.set_mode(arg)
                print("   (mode: %s)\n" % d.mode); continue
            if low == "/reset":
                d.memory.reset()
                d = make_director(config, telemetry)
                pending = FRESH_SEED
                print("   (session wiped)\n")
                continue

        try:
            beat = d.respond(text)
        except LLMError as e:
            print("[api error] %s\n" % e)
            continue

        if pinned is not None:
            d.intensity = pinned
            d._sync_band()

        print()
        for line in beat.turns:
            print("%s: %s" % (line.speaker.capitalize(), line.text))
        print()
        if debug:
            show_debug(d, beat, telemetry)

    print("(She's still in there.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

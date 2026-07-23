#!/usr/bin/env python3
"""
test_connection.py — verify your API key + model wiring WITHOUT launching the game.

Run:  python game/claude_mod/test_connection.py

It loads config.json (or config.example.json), asks the director for a single
in-character opening line, and prints it. If your key is wrong or the network is
blocked, you'll see a clear error here instead of a mysterious silent game.
"""

import os
import sys

# Allow running this file directly (adds the parent of claude_mod/ to path).
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

from claude_mod import load_config, Director  # noqa: E402


def main():
    config = load_config()
    key = config.get("api_key", "")
    if not key or "PUT-YOUR-KEY" in key:
        print("[!] No API key set. Copy config.example.json to config.json and add your key.")
        return 1

    print("[*] Model:   %s (fallback: %s)" % (
        config.get("model"), config.get("fallback_model")))
    print("[*] Effort:  %s   Mode: %s   Pace: %s"
          % (config.get("effort"), config.get("default_mode"), config.get("pace")))
    print("[*] Scan on: %s" % config.get("enable_local_scan"))
    print("[*] Asking Monika to say hello...\n")

    director = Director(config, session_name="__connection_test__")
    turn = director.respond("(The player sits down at the club for the first time.)")

    if turn.refused:
        print("[!] The model refused this turn (safety classifier). The Opus 4.8 "
              "fallback also declined. Try a gentler opening line.")
    print("  speaker:    %s" % turn.speaker)
    print("  expression: %s" % turn.expression)
    print("  action:     %s" % turn.action)
    print("  served by:  %s" % turn.model)
    print("\n  %s says:\n  \"%s\"\n" % (turn.speaker.capitalize(), turn.text))

    # Clean up the throwaway test transcript.
    try:
        director.memory.reset()
        os.remove(director.memory.path)
    except OSError:
        pass

    print("[✓] Connection works.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

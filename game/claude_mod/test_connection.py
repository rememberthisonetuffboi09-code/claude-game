#!/usr/bin/env python3
"""
test_connection.py — verify your OpenRouter key + model WITHOUT launching the game.

Run:  python test_connection.py   (from inside the claude_mod folder)

Loads your config, builds the real director prompt, and makes ONE call to
OpenRouter. On success you'll see the club's opening line. On failure (bad key,
no credit, unknown model) you get a clear message here instead of a silent game.
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

from claude_mod import load_config, Director  # noqa: E402
from claude_mod.openrouter_client import LLMError  # noqa: E402


def _cleanup(d):
    try:
        os.remove(d.memory.path)
    except OSError:
        pass


def main():
    config = load_config()
    key = config.get("api_key", "")
    if not key or "PUT-YOUR" in key:
        print("[!] No API key set. Put your key in config.json (or config.example.json).")
        return 1

    print("[*] Provider: OpenRouter")
    print("[*] Model:    %s   (fallback: %s)"
          % (config.get("model"), config.get("fallback_model") or "none"))
    print("[*] Mode: %s   Pace: %s   Scan: %s\n"
          % (config.get("default_mode"), config.get("pace"), config.get("enable_local_scan")))
    print("[*] Asking the club to open the scene...\n")

    d = Director(config, session_name="__connection_test__")
    d.memory.add_player("(The player sits down at the club for the first time.)")
    system = d._system_prompt()
    messages = d._messages()

    try:
        result = d.client.complete(system, messages)
    except LLMError as e:
        print("[!] Call failed:\n    %s" % e)
        print("\n    - credit error   -> add funds on OpenRouter (or use a \":free\" model)")
        print("    - model-not-found -> check the slug at https://openrouter.ai/models")
        _cleanup(d)
        return 1

    if not result.text:
        print("[!] Empty reply. finish=%r error=%r" % (result.finish_reason, result.error))
        _cleanup(d)
        return 1

    beat = d._parse(result)
    print("  served by: %s   crack: %s" % (result.model, beat.crack))
    print("  cues: music=%s  bg=%s  effect=%s  action=%s\n"
          % (beat.music, beat.background, beat.effect, beat.action))
    for line in beat.turns:
        print("  %s: %s" % (line.speaker.capitalize(), line.text))
    print("\n[OK] Connection works.")
    _cleanup(d)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

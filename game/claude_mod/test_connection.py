#!/usr/bin/env python3
"""
test_connection.py — verify your OpenRouter key + model WITHOUT launching the game.

Run:  python game/claude_mod/test_connection.py

It loads config.json, builds the director's system prompt, and makes ONE real
call to OpenRouter. On success you'll see Monika's opening line. On failure
(bad key, no credit, unknown model) you'll get a clear message here instead of a
silent game.
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

from claude_mod import load_config, Director  # noqa: E402
from claude_mod.openrouter_client import LLMError  # noqa: E402


def main():
    config = load_config()
    key = config.get("api_key", "")
    if not key or "PUT-YOUR" in key:
        print("[!] No API key set. Copy config.example.json to config.json and add your OpenRouter key.")
        return 1

    print("[*] Provider: OpenRouter")
    print("[*] Model:    %s   (fallback: %s)"
          % (config.get("model"), config.get("fallback_model") or "none"))
    print("[*] Mode: %s   Pace: %s   Scan: %s\n"
          % (config.get("default_mode"), config.get("pace"), config.get("enable_local_scan")))
    print("[*] Asking Monika to say hello...\n")

    director = Director(config, session_name="__connection_test__")
    system = director._build_system_prompt()
    seed = [{"role": "user", "content": "(The player sits down at the club for the first time.)"}]

    try:
        result = director.client.complete(system, seed)
    except LLMError as e:
        print("[!] Call failed:\n    %s" % e)
        print("\n    Tip: if it's a credit error, either add funds or set \"model\" to a")
        print("    \":free\" model in config.json (e.g. deepseek/deepseek-chat-v3-0324:free).")
        return 1

    if not result.text:
        print("[!] Empty reply. error=%r finish=%r" % (result.error, result.finish_reason))
        return 1

    turn = director._parse(result.text, result)
    print("  served by:  %s" % result.model)
    print("  speaker:    %s   expression: %s" % (turn.speaker, turn.expression))
    print("  music: %s   background: %s   effect: %s   action: %s"
          % (turn.music, turn.background, turn.effect, turn.action))
    print("\n  %s says:\n  \"%s\"\n" % (turn.speaker.capitalize(), turn.text))

    # Clean up the throwaway test transcript.
    try:
        os.remove(director.memory.path)
    except OSError:
        pass

    print("[✓] Connection works.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

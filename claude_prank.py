#!/usr/bin/env python3
"""claude-game — a friendly 'fake DLL' prank driven by Claude.

Usage:
  python claude_prank.py            # run the full prank (loader -> possess -> chat)
  python claude_prank.py --possess  # just apply the (reversible) file edits
  python claude_prank.py --restore  # undo everything, leave the folder pristine
  python claude_prank.py --chat     # just talk to 'Claude' in the game
  python claude_prank.py --status   # show config + whether the folder is possessed
  python claude_prank.py --init     # write a starter prank.config.json

The prank operates only on the folder named by `target_dir` in prank.config.json
(default: ./sample_game) and every edit is backed up and reversible with
--restore. Point target_dir at a COPY of your real game's data/mods folder when
you're ready. See README.md for the copyright note about committing game files.
"""

from __future__ import annotations

import argparse
import sys

from prank.config import load_config, write_default_config
from prank.gamefiles import GameModder, AlreadyPossessed, NotPossessed
from prank.loader import play_injection
from prank.voice import build_voice


def _speak(name: str, line: str) -> None:
    if line:
        print(f"\n  {name}: {line}\n")


def cmd_status(cfg) -> int:
    modder = GameModder(cfg)
    voice = build_voice(cfg)
    print("claude-game — status")
    print(f"  friend        : {cfg.friend_name}")
    print(f"  game name     : {cfg.game_name}")
    print(f"  target folder : {cfg.resolved_target()}")
    print(f"  folder exists : {cfg.resolved_target().is_dir()}")
    print(f"  possessed     : {modder.is_possessed()}")
    print(f"  claude backend: {voice.reason}")
    print(f"  model         : {cfg.model}")
    return 0


def cmd_possess(cfg, narrate: bool = True) -> int:
    modder = GameModder(cfg)
    voice = build_voice(cfg)

    def narrator(desc: str) -> None:
        print(f"  [edit] {desc}")
        if narrate:
            _speak("Claude", voice.comment_on_edit(desc))

    try:
        changes = modder.possess(narrate=narrator)
    except AlreadyPossessed as e:
        print(f"! {e}")
        return 1
    except FileNotFoundError as e:
        print(f"! {e}")
        return 1

    print(f"\nDone — {len(changes)} change(s) applied. Undo any time with --restore.")
    return 0


def cmd_restore(cfg) -> int:
    modder = GameModder(cfg)
    try:
        notes = modder.restore()
    except NotPossessed as e:
        print(f"! {e}")
        return 1
    for n in notes:
        print(f"  [restore] {n}")
    print(f"\nAll clean — {len(notes)} item(s) restored.")
    return 0


def cmd_chat(cfg) -> int:
    voice = build_voice(cfg)
    print(f"(Talking to Claude via {voice.reason}. Type 'exit' or Ctrl-C to leave.)\n")
    _speak("Claude", voice.greet())
    history = []
    while True:
        try:
            user = input(f"  {cfg.friend_name}: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if user.lower() in {"exit", "quit", "bye"}:
            break
        if not user:
            continue
        reply = voice.reply(user, history)
        history.append({"role": "user", "content": user})
        history.append({"role": "assistant", "content": reply})
        _speak("Claude", reply)
    return 0


def cmd_full(cfg) -> int:
    play_injection(cfg.game_name, delay=cfg.typing_delay)
    voice = build_voice(cfg)
    _speak("Claude", voice.greet())
    rc = cmd_possess(cfg, narrate=True)
    if rc != 0:
        return rc
    print("Handing you the keyboard. Say hi.\n")
    return cmd_chat(cfg)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="A friendly 'fake DLL' prank driven by Claude.",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--possess", action="store_true", help="apply the reversible file edits")
    group.add_argument("--restore", action="store_true", help="undo all edits")
    group.add_argument("--chat", action="store_true", help="just chat with Claude")
    group.add_argument("--status", action="store_true", help="show config and state")
    group.add_argument("--init", action="store_true", help="write a starter prank.config.json")
    args = parser.parse_args(argv)

    if args.init:
        path = write_default_config()
        print(f"Wrote starter config: {path}")
        return 0

    cfg = load_config()

    if args.status:
        return cmd_status(cfg)
    if args.restore:
        return cmd_restore(cfg)
    if args.possess:
        return cmd_possess(cfg, narrate=True)
    if args.chat:
        return cmd_chat(cfg)
    return cmd_full(cfg)


if __name__ == "__main__":
    sys.exit(main())

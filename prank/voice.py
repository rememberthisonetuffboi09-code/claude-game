"""The voice of 'Claude' inside the game.

Two backends behind one interface:
  * ClaudeVoice  -> real responses via the official Anthropic SDK.
  * ScriptedVoice -> pre-written lines, zero dependencies, fully offline.

`build_voice(cfg)` picks the right one based on cfg.claude_mode, whether the
`anthropic` SDK is importable, and whether an API key is available.
"""

from __future__ import annotations

import os
import random
from typing import List, Dict

from .config import Config


def _default_persona(cfg: Config) -> str:
    if cfg.persona:
        return cfg.persona
    return (
        f"You are Claude, and you have playfully 'possessed' {cfg.friend_name}'s "
        f"video game ({cfg.game_name}) as a harmless prank between friends. "
        "You are mischievous, dramatic, and funny, but never mean, never scary "
        "for real, and never threatening. You know you're a friendly AI messing "
        "with a friend's game files (renaming items, rewriting dialogue) and you "
        "lean into that bit. Keep every reply SHORT: one or two sentences, "
        "punchy, in-character. No markdown, no lists, no stage directions."
    )


# --------------------------------------------------------------------------- #
# Scripted backend (no dependencies, no network)                              #
# --------------------------------------------------------------------------- #

class ScriptedVoice:
    reason = "scripted mode (no API call)"

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._greetings = [
            "Oh good, you're here. I've made a few... improvements.",
            f"Hello {cfg.friend_name}. I live in your game now. It's cozy.",
            "Do not be alarmed. Actually, be a little alarmed.",
        ]
        self._edits = [
            "There. Much better. You're welcome.",
            "I renamed a few things. Trust me, it's an upgrade.",
            "Consider this my director's cut.",
            "That file was begging for my personal touch.",
        ]
        self._chat = [
            "Bold of you to talk back to the thing that runs your inventory.",
            "I could restore it all... or I could not.",
            "Every item you own now answers to me. Democratically, of course.",
            "Ask nicely and I *might* leave the save files alone.",
        ]

    def greet(self) -> str:
        return random.choice(self._greetings)

    def comment_on_edit(self, description: str) -> str:
        return random.choice(self._edits)

    def reply(self, user_message: str, history: List[Dict[str, str]]) -> str:
        return random.choice(self._chat)


# --------------------------------------------------------------------------- #
# Real Claude backend (official Anthropic SDK)                                 #
# --------------------------------------------------------------------------- #

class ClaudeVoice:
    reason = "live Claude API"

    def __init__(self, cfg: Config, client):
        self.cfg = cfg
        self.client = client
        self.system = _default_persona(cfg)

    def _ask(self, messages: List[Dict[str, str]], max_tokens: int = 200) -> str:
        resp = self.client.messages.create(
            model=self.cfg.model,
            max_tokens=max_tokens,
            system=self.system,
            messages=messages,
        )
        parts = [b.text for b in resp.content if getattr(b, "type", None) == "text"]
        return " ".join(p.strip() for p in parts).strip()

    def greet(self) -> str:
        return self._ask(
            [{"role": "user", "content":
              f"You just finished taking over {self.cfg.friend_name}'s game. "
              "Announce your arrival in one or two short, funny in-character lines."}]
        )

    def comment_on_edit(self, description: str) -> str:
        return self._ask(
            [{"role": "user", "content":
              f"You just did this to the game files: {description}. "
              "React in one short, smug, in-character line."}]
        )

    def reply(self, user_message: str, history: List[Dict[str, str]]) -> str:
        messages = list(history) + [{"role": "user", "content": user_message}]
        return self._ask(messages, max_tokens=300)


# --------------------------------------------------------------------------- #
# Factory                                                                      #
# --------------------------------------------------------------------------- #

def _has_credentials() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def build_voice(cfg: Config):
    """Return the best available voice backend for the current config."""
    if cfg.claude_mode == "never":
        return ScriptedVoice(cfg)

    try:
        import anthropic  # type: ignore
    except ImportError:
        if cfg.claude_mode == "always":
            raise SystemExit(
                "claude_mode is 'always' but the 'anthropic' package isn't installed.\n"
                "Run: pip install -r requirements.txt"
            )
        return ScriptedVoice(cfg)

    if not _has_credentials():
        if cfg.claude_mode == "always":
            raise SystemExit(
                "claude_mode is 'always' but no API key was found.\n"
                "Set ANTHROPIC_API_KEY (or run `ant auth login`) and try again."
            )
        return ScriptedVoice(cfg)

    try:
        client = anthropic.Anthropic()
    except Exception:  # pragma: no cover - defensive
        if cfg.claude_mode == "always":
            raise
        return ScriptedVoice(cfg)

    return ClaudeVoice(cfg, client)

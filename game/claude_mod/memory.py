"""
memory.py — the conversation memory.

The Anthropic API is stateless, so "she remembers everything he said" means WE
keep the full running transcript and re-send it every turn. Fable 5's 1M-token
context window makes a whole session's worth of history comfortable.

The transcript is also written to disk so it survives closing/reopening the game
("back so soon?"). Stored as plain JSON under memory/ (git-ignored).
"""

import json
import os
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_MEM_DIR = os.path.join(_HERE, "memory")


class Memory:
    def __init__(self, session_name="default"):
        self.session_name = session_name
        self.path = os.path.join(_MEM_DIR, "%s.json" % session_name)
        # messages: list of {"role": "user"|"assistant", "content": str}
        self.messages = []
        # meta: freeform state we want to persist (escalation, mode, seen facts)
        self.meta = {}
        self._load()

    def _load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.messages = data.get("messages", [])
            self.meta = data.get("meta", {})
        except (IOError, ValueError):
            # No prior save (or unreadable) — start fresh.
            self.messages = []
            self.meta = {}

    def save(self):
        try:
            os.makedirs(_MEM_DIR, exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(
                    {"messages": self.messages, "meta": self.meta, "saved_at": time.time()},
                    f, ensure_ascii=False, indent=2,
                )
            os.replace(tmp, self.path)  # atomic-ish
        except IOError:
            # Never let a save failure crash the game.
            pass

    def add_player(self, text):
        self.messages.append({"role": "user", "content": text})

    def add_doki(self, text):
        # Store the model's raw response verbatim so it stays consistent with
        # its own prior turns (standard multi-turn pattern).
        self.messages.append({"role": "assistant", "content": text})

    def for_api(self):
        """The messages list to send to the API."""
        return list(self.messages)

    def is_returning_player(self):
        """True if there's prior history — lets the game greet a repeat visit."""
        return len(self.messages) > 0

    def reset(self):
        self.messages = []
        self.meta = {}
        self.save()

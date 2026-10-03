"""
claude_mod — the self-aware DDLC "director brain".

Pure-Python 3 package (no Ren'Py imports), run next to the game by sidecar.py.
It is never imported by DDLC itself: the game's engine is Python 2, so the
in-game bridge (game/claude_mod_bridge.rpy) talks to the sidecar over localhost.
"""

import json
import os

from .director import Director, DokiTurn  # noqa: F401

__version__ = "0.1.0"

_HERE = os.path.dirname(os.path.abspath(__file__))


def load_config():
    """
    Load config.json (falls back to config.example.json so the game still
    starts and can show a 'set your API key' message instead of crashing).
    """
    for name in ("config.json", "config.example.json"):
        path = os.path.join(_HERE, name)
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (IOError, ValueError):
            continue
    return {}


def make_director(session_name="default"):
    """Convenience constructor used by the Ren'Py layer."""
    return Director(load_config(), session_name=session_name)

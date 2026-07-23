"""
claude_mod — the self-aware DDLC "director brain".

Pure-Python package (no Ren'Py imports) so it can be unit-tested and run
standalone (see test_connection.py). The Ren'Py layer (claude_mod_hooks.rpy)
imports Director and drives it.
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

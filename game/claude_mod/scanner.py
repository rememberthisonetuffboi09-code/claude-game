"""
scanner.py — SAFE, read-only local signals + the dossier.

This is the "how does it know that?!" layer. Two ingredients, exactly like the
scary-accurate AI videos:

  1. Live read-only scan of harmless local signals (this file).
  2. A dossier you write ahead of time (dossier.json) with things only a friend
     would know.

HARD SAFETY RULES enforced here in code (not just in the prompt):
  * READ-ONLY. Nothing here deletes, edits, or corrupts anything.
  * No account access. We never touch Discord tokens, browser logins, saved
    passwords, or anything that authenticates as the user.
  * The one write capability (drop_note) is OFF by default, writes only a
    harmless .txt into a single designated folder, and NEVER overwrites.

Everything is wrapped in try/except and degrades to "unknown" — a locked-down
machine just yields less, it never breaks the game.
"""

import getpass
import json
import os
import platform
import socket

_HERE = os.path.dirname(os.path.abspath(__file__))
_DOSSIER_PATH = os.path.join(_HERE, "dossier.json")


# ── read-only signal gathering ────────────────────────────────────────────

def _safe(fn, default="unknown"):
    try:
        return fn()
    except Exception:  # noqa: BLE001 — any failure just yields the default
        return default


def _username():
    return _safe(getpass.getuser)


def _hostname():
    return _safe(socket.gethostname)


def _os_name():
    return _safe(lambda: "%s %s" % (platform.system(), platform.release()))


def _desktop_dir():
    home = os.path.expanduser("~")
    for candidate in (os.path.join(home, "Desktop"), os.path.join(home, "OneDrive", "Desktop")):
        if os.path.isdir(candidate):
            return candidate
    return None


def _desktop_items(limit=25):
    """Names only of what's on the Desktop. Names, never contents."""
    d = _desktop_dir()
    if not d:
        return []
    try:
        names = [n for n in os.listdir(d) if not n.startswith(".")]
        names.sort()
        return names[:limit]
    except Exception:  # noqa: BLE001
        return []


def _steam_games(limit=40):
    """Best-effort list of installed Steam game folder names (Windows-focused)."""
    roots = []
    # Common default library locations.
    for base in (
        r"C:\Program Files (x86)\Steam",
        r"C:\Program Files\Steam",
        os.path.expanduser("~/.steam/steam"),
        os.path.expanduser("~/.local/share/Steam"),
    ):
        common = os.path.join(base, "steamapps", "common")
        if os.path.isdir(common):
            roots.append(common)

    # Parse libraryfolders.vdf for additional library drives, if present.
    for base in list(roots):
        vdf = os.path.join(os.path.dirname(os.path.dirname(base)), "steamapps", "libraryfolders.vdf")
        try:
            if os.path.isfile(vdf):
                with open(vdf, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith('"path"'):
                            # crude: "path"    "D:\\SteamLibrary"
                            parts = line.split('"')
                            if len(parts) >= 4:
                                extra = os.path.join(parts[3], "steamapps", "common")
                                if os.path.isdir(extra) and extra not in roots:
                                    roots.append(extra)
        except Exception:  # noqa: BLE001
            pass

    games = []
    for common in roots:
        try:
            for name in os.listdir(common):
                if os.path.isdir(os.path.join(common, name)) and name not in games:
                    games.append(name)
        except Exception:  # noqa: BLE001
            pass
    games.sort()
    return games[:limit]


def safe_scan(enabled=True):
    """
    Returns a dict of harmless facts the director may weave in. Pass enabled=False
    (from config) to skip scanning entirely and return an empty dict.
    """
    if not enabled:
        return {}
    return {
        "username": _username(),
        "computer_name": _hostname(),
        "os": _os_name(),
        "desktop_items": _desktop_items(),
        "steam_games": _steam_games(),
    }


# ── the dossier (things only a friend would know) ─────────────────────────

def load_dossier():
    try:
        with open(_DOSSIER_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (IOError, ValueError):
        return {}


# ── the ONLY write capability: a harmless note, off by default ────────────

_NOTE_DIRNAME = "MonikaWasHere"  # a single, obvious, safe folder on the Desktop


def drop_note(text, enabled=False):
    """
    Writes a harmless .txt note into ~/Desktop/MonikaWasHere/. Off by default.
    Never overwrites (unique filename), never touches anything else. Returns the
    path written, or None if disabled/failed.
    """
    if not enabled:
        return None
    try:
        d = _desktop_dir() or os.path.expanduser("~")
        folder = os.path.join(d, _NOTE_DIRNAME)
        os.makedirs(folder, exist_ok=True)
        # Unique, non-clobbering filename.
        i = 0
        while True:
            name = "note_%d.txt" % i if i else "note.txt"
            path = os.path.join(folder, name)
            if not os.path.exists(path):
                break
            i += 1
        with open(path, "w", encoding="utf-8") as f:
            f.write(str(text))
        return path
    except Exception:  # noqa: BLE001
        return None

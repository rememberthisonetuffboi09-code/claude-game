"""Load prank configuration from prank.config.json, with environment overrides.

Precedence (highest first): environment variable -> prank.config.json -> default.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = REPO_ROOT / "prank.config.json"


# Words the "possession" swaps out in text/config files. Purely cosmetic and
# fully reversible (originals are backed up before any edit). Tweak freely.
DEFAULT_WORD_SWAPS: Dict[str, str] = {
    "Sword": "Cursed Baguette",
    "Shield": "Emotional Support Frisbee",
    "Potion": "Suspicious Juice",
    "Health": "Vibes",
    "Gold": "Bottlecaps",
    "treasure": "an unpaid invoice",
    "Hero": "Chosen Intern",
}


@dataclass
class Config:
    # Who the prank is aimed at (used to personalize Claude's banter).
    friend_name: str = "friend"
    # Cosmetic name for the "game" in the loader theater.
    game_name: str = "the game"
    # Folder the prank reads and (reversibly) edits. Point this at your game's
    # data/mods folder when you're ready. Relative paths resolve from repo root.
    target_dir: str = "sample_game"

    # Claude integration.
    #   "auto"   -> use the real API if the SDK is installed AND a key is set,
    #               otherwise fall back to built-in scripted lines.
    #   "always" -> require the real API (error out if unavailable).
    #   "never"  -> always use scripted lines, no network calls.
    claude_mode: str = "auto"
    model: str = "claude-opus-4-8"
    # Optional persona override for Claude's system prompt. Leave empty to use
    # the built-in mischievous-but-harmless persona.
    persona: str = ""

    # Loader theater speed (seconds between fake log lines). 0 = instant.
    typing_delay: float = 0.35

    word_swaps: Dict[str, str] = field(default_factory=lambda: dict(DEFAULT_WORD_SWAPS))

    def resolved_target(self) -> Path:
        p = Path(self.target_dir)
        return p if p.is_absolute() else (REPO_ROOT / p)


def _apply_env_overrides(cfg: Config) -> Config:
    env_map = {
        "PRANK_FRIEND_NAME": ("friend_name", str),
        "PRANK_GAME_NAME": ("game_name", str),
        "PRANK_TARGET_DIR": ("target_dir", str),
        "PRANK_CLAUDE_MODE": ("claude_mode", str),
        "PRANK_MODEL": ("model", str),
        "PRANK_PERSONA": ("persona", str),
        "PRANK_TYPING_DELAY": ("typing_delay", float),
    }
    for env_key, (attr, caster) in env_map.items():
        raw = os.environ.get(env_key)
        if raw is not None and raw != "":
            try:
                setattr(cfg, attr, caster(raw))
            except (TypeError, ValueError):
                pass
    return cfg


def load_config(path: Path | None = None) -> Config:
    path = path or DEFAULT_CONFIG_PATH
    cfg = Config()
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
        for key, value in data.items():
            if hasattr(cfg, key):
                setattr(cfg, key, value)
    return _apply_env_overrides(cfg)


def write_default_config(path: Path | None = None) -> Path:
    """Write a starter prank.config.json if one doesn't already exist."""
    path = path or DEFAULT_CONFIG_PATH
    if not path.exists():
        path.write_text(json.dumps(asdict(Config()), indent=2) + "\n", encoding="utf-8")
    return path

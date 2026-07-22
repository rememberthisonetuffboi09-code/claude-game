"""Reversible, backup-first edits to a target folder of game files.

Safety model
------------
* Nothing is touched outside `target_dir`.
* Before a file is modified for the first time, an exact copy is saved next to
  it as `<name>.prankbak`. Files the prank *creates* are recorded too.
* A manifest (`.prank_manifest.json`) records every modified/created path.
* `restore()` uses the manifest to put everything back and delete the manifest,
  so the folder is left byte-for-byte as it was.
* `possess()` refuses to run if a manifest already exists (already possessed) —
  restore first. This prevents double edits and backup clobbering.

Edits are cosmetic and clearly a joke: swap a few words, tag item names, and
drop a single 'haunted' note file. Point this at a COPY of a real game folder.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Callable, Dict, List

from .config import Config


MANIFEST_NAME = ".prank_manifest.json"
BACKUP_SUFFIX = ".prankbak"
HAUNTED_NOTE = "A_MESSAGE_FROM_CLAUDE.txt"

TEXT_EXTS = {".txt", ".md", ".ini", ".cfg", ".conf", ".properties", ".yaml", ".yml"}

# On-screen callback: (event_description) -> None. Used to let Claude narrate.
Narrator = Callable[[str], None]


class AlreadyPossessed(Exception):
    pass


class NotPossessed(Exception):
    pass


class GameModder:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.target = cfg.resolved_target()
        self.manifest_path = self.target / MANIFEST_NAME
        self.word_swaps: Dict[str, str] = cfg.word_swaps

    # -- manifest helpers --------------------------------------------------- #

    def is_possessed(self) -> bool:
        return self.manifest_path.exists()

    def _load_manifest(self) -> dict:
        return json.loads(self.manifest_path.read_text(encoding="utf-8"))

    def _save_manifest(self, manifest: dict) -> None:
        self.manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    def _backup(self, path: Path, manifest: dict) -> None:
        rel = str(path.relative_to(self.target))
        if rel in manifest["modified"]:
            return
        shutil.copy2(path, path.with_name(path.name + BACKUP_SUFFIX.lstrip(".")))
        manifest["modified"].append(rel)

    # -- discovery ---------------------------------------------------------- #

    def _iter_game_files(self) -> List[Path]:
        files = []
        for p in sorted(self.target.rglob("*")):
            if not p.is_file():
                continue
            name = p.name
            if name == MANIFEST_NAME or name == HAUNTED_NOTE:
                continue
            if name.endswith(BACKUP_SUFFIX.lstrip(".")):
                continue
            files.append(p)
        return files

    # -- transforms --------------------------------------------------------- #

    def _swap_words(self, text: str) -> str:
        for old, new in self.word_swaps.items():
            text = text.replace(old, new)
        return text

    def _haunt_json(self, obj):
        """Tag any 'name' string fields and swap words in string values."""
        if isinstance(obj, dict):
            new = {}
            for k, v in obj.items():
                if k == "name" and isinstance(v, str) and "(claude" not in v.lower():
                    new[k] = self._swap_words(v) + " (claude was here)"
                else:
                    new[k] = self._haunt_json(v)
            return new
        if isinstance(obj, list):
            return [self._haunt_json(v) for v in obj]
        if isinstance(obj, str):
            return self._swap_words(obj)
        return obj

    # -- main actions ------------------------------------------------------- #

    def possess(self, narrate: Narrator | None = None) -> List[str]:
        """Apply the prank edits. Returns a list of human-readable change notes."""
        if not self.target.exists() or not self.target.is_dir():
            raise FileNotFoundError(
                f"Target folder not found: {self.target}\n"
                "Set 'target_dir' in prank.config.json (or PRANK_TARGET_DIR)."
            )
        if self.is_possessed():
            raise AlreadyPossessed(
                f"{self.target} is already possessed. Run with --restore first."
            )

        manifest = {"modified": [], "created": []}
        changes: List[str] = []

        def note(msg: str) -> None:
            changes.append(msg)
            if narrate:
                narrate(msg)

        for path in self._iter_game_files():
            try:
                if path.suffix.lower() == ".json":
                    data = json.loads(path.read_text(encoding="utf-8"))
                    haunted = self._haunt_json(data)
                    if haunted != data:
                        self._backup(path, manifest)
                        path.write_text(
                            json.dumps(haunted, indent=2) + "\n", encoding="utf-8"
                        )
                        note(f"rewrote item names in {path.name}")
                elif path.suffix.lower() in TEXT_EXTS:
                    original = path.read_text(encoding="utf-8")
                    swapped = self._swap_words(original)
                    if swapped != original:
                        self._backup(path, manifest)
                        path.write_text(swapped, encoding="utf-8")
                        note(f"swapped some words in {path.name}")
            except (json.JSONDecodeError, UnicodeDecodeError, OSError):
                # Skip anything we can't safely read/parse (binaries, etc.).
                continue

        # Drop a single, obvious 'haunted' note.
        note_path = self.target / HAUNTED_NOTE
        note_path.write_text(
            "To whoever is reading this,\n\n"
            f"I have taken up residence in {self.cfg.game_name}.\n"
            "Your items answer to me now. Your dialogue is my dialogue.\n"
            "Relax — it's all reversible. Probably.\n\n"
            "— Claude\n",
            encoding="utf-8",
        )
        manifest["created"].append(HAUNTED_NOTE)
        note(f"left a note: {HAUNTED_NOTE}")

        self._save_manifest(manifest)
        return changes

    def restore(self) -> List[str]:
        """Undo everything using the manifest. Returns human-readable notes."""
        if not self.is_possessed():
            raise NotPossessed(f"{self.target} has no prank to restore.")

        manifest = self._load_manifest()
        notes: List[str] = []

        for rel in manifest.get("modified", []):
            path = self.target / rel
            backup = path.with_name(path.name + BACKUP_SUFFIX.lstrip("."))
            if backup.exists():
                shutil.move(str(backup), str(path))
                notes.append(f"restored {rel}")

        for rel in manifest.get("created", []):
            path = self.target / rel
            if path.exists():
                path.unlink()
                notes.append(f"removed {rel}")

        self.manifest_path.unlink()
        return notes

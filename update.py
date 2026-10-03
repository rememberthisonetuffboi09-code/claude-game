#!/usr/bin/env python3
"""
update.py — bring this folder up to date with the latest version on GitHub.

    python update.py

What it does:
  * downloads the latest version of the mod (this branch) from GitHub,
  * writes every file over your copy - BUT never touches your config.json
    (API key), dossier.json, or the memory/ folder,
  * if you had edited a file that's being replaced (e.g. the character bible
    in game/claude_mod/persona/), the old one is saved in update_backup/ first,
  * removes files the mod no longer uses.

Then restart the sidecar. On startup it installs the matching bridge into your
DDLC folder by itself, so both halves always match.
"""

import io
import os
import shutil
import sys
import time
import urllib.request
import zipfile

REPO = "rememberthisonetuffboi09-code/claude-game"
BRANCH = "claude/ddlc-claude-mod-4xai2o"
ZIP_URL = "https://github.com/%s/archive/refs/heads/%s.zip" % (REPO, BRANCH)

ROOT = os.path.dirname(os.path.abspath(__file__))

# Yours - never overwritten, never deleted.
PROTECTED = {
    "game/claude_mod/config.json",
    "game/claude_mod/dossier.json",
}
PROTECTED_DIRS = ("game/claude_mod/memory/", "update_backup/")

# Files older versions shipped that must not linger. claude_mod_hooks.rpy is a
# Python 3 file that crashes DDLC if it ever ends up in the game folder.
REMOVED = ["game/claude_mod_hooks.rpy"]


def download(url=ZIP_URL):
    with urllib.request.urlopen(url, timeout=60) as resp:
        return resp.read()


def _is_protected(rel):
    return rel in PROTECTED or any(rel.startswith(p) for p in PROTECTED_DIRS)


def apply_zip(data, root=ROOT, stamp=None):
    """
    Overlay a GitHub branch ZIP onto `root`. Returns a report dict:
    updated / added / unchanged / backed_up / removed / skipped.
    """
    zf = zipfile.ZipFile(io.BytesIO(data))
    names = [n for n in zf.namelist() if not n.endswith("/")]
    if not names:
        raise ValueError("the download was empty")
    prefix = names[0].split("/")[0] + "/"
    if prefix + "game/claude_mod/sidecar.py" not in names:
        raise ValueError("that download doesn't look like this mod - nothing changed")

    stamp = stamp or time.strftime("%Y%m%d-%H%M%S")
    backup_root = os.path.join(root, "update_backup", stamp)
    report = {k: [] for k in ("updated", "added", "unchanged", "backed_up",
                              "removed", "skipped")}

    for name in names:
        rel = name[len(prefix):]
        if not rel:
            continue
        if _is_protected(rel):
            report["skipped"].append(rel)
            continue
        new = zf.read(name)
        dest = os.path.join(root, *rel.split("/"))
        if os.path.isfile(dest):
            with open(dest, "rb") as f:
                old = f.read()
            if old == new:
                report["unchanged"].append(rel)
                continue
            keep = os.path.join(backup_root, *rel.split("/"))
            os.makedirs(os.path.dirname(keep), exist_ok=True)
            shutil.copy2(dest, keep)
            report["backed_up"].append(rel)
            report["updated"].append(rel)
        else:
            report["added"].append(rel)
        os.makedirs(os.path.dirname(dest) or root, exist_ok=True)
        tmp = dest + ".updating"
        with open(tmp, "wb") as f:
            f.write(new)
        os.replace(tmp, dest)

    for rel in REMOVED:
        path = os.path.join(root, *rel.split("/"))
        if os.path.isfile(path):
            keep = os.path.join(backup_root, *rel.split("/"))
            os.makedirs(os.path.dirname(keep), exist_ok=True)
            shutil.move(path, keep)
            report["removed"].append(rel)
    return report


def sidecar_version(root=ROOT):
    try:
        with open(os.path.join(root, "game", "claude_mod", "sidecar.py"), encoding="utf-8") as f:
            for line in f:
                if line.startswith("SIDECAR_VERSION"):
                    return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return "?"


def main():
    before = sidecar_version()
    print("Downloading the latest version from GitHub...")
    try:
        data = download()
    except Exception as e:  # noqa: BLE001
        print("[!] Couldn't download: %s" % e)
        print("    Check your internet connection and try again. Nothing was changed.")
        return 1
    try:
        report = apply_zip(data)
    except Exception as e:  # noqa: BLE001
        print("[!] %s" % e)
        return 1
    after = sidecar_version()

    print("")
    print("  updated:   %d file(s)" % len(report["updated"]))
    for rel in report["updated"]:
        print("               %s" % rel)
    print("  added:     %d file(s)" % len(report["added"]))
    print("  unchanged: %d file(s)" % len(report["unchanged"]))
    if report["removed"]:
        print("  removed:   %s" % ", ".join(report["removed"]))
    if report["backed_up"]:
        print("  your previous copies are in update_backup/ (in case you'd edited them)")
    print("  kept yours: config.json, dossier.json, memory/")
    print("")
    print("  sidecar version: %s -> %s" % (before, after))
    print("")
    print("Now restart the sidecar (Ctrl+C in its window, then run it again).")
    print("It installs the matching bridge into DDLC by itself.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# claude-game 🎮👻

A friendly **"fake DLL" prank** for a friend's game — a mod-loader-flavored
program that *looks* like it's injecting a `ClaudeCore.dll`, then hands control
to **Claude**, who banters with your friend and (reversibly) rewrites the game's
files so it looks "possessed."

It's all a bit. Nothing touches game memory or a real process. Every file edit
is backed up and undoes cleanly with one command.

```
   ____ _                 _        ____
  / ___| | __ _ _   _  __| | ___  / ___|___  _ __ ___
 | |   | |/ _` | | | |/ _` |/ _ \| |   / _ \| '__/ _ \
 | |___| | (_| | |_| | (_| |  __/| |__| (_) | | |  __/
  \____|_|\__,_|\__,_|\__,_|\___(_)____\___/|_|  \___|
```

## What it does

1. **Loader theater** — prints a convincing fake DLL-injection sequence.
2. **Possession** — reversibly edits a folder of game files: renames items,
   swaps a few words in dialogue/config, and drops one obvious "haunted" note.
3. **Claude speaks** — a mischievous-but-harmless persona reacts to each edit and
   then chats live with your friend.

## Quick start (works out of the box, no setup)

```bash
python3 claude_prank.py
```

That runs the full bit against the bundled `sample_game/` folder in **scripted
mode** (pre-written lines, no API key, no dependencies). Undo any edits with:

```bash
python3 claude_prank.py --restore
```

### Commands

| Command | What it does |
|---|---|
| `python3 claude_prank.py` | Full prank: loader → possess → chat |
| `python3 claude_prank.py --possess` | Just apply the (reversible) file edits |
| `python3 claude_prank.py --restore` | Undo everything, leave the folder pristine |
| `python3 claude_prank.py --chat` | Just talk to "Claude" in the game |
| `python3 claude_prank.py --status` | Show config + whether the folder is possessed |
| `python3 claude_prank.py --init` | Write a starter `prank.config.json` |

## Making Claude actually respond (live API)

Scripted mode is fully offline. To have **real Claude** generate the banter:

```bash
pip install -r requirements.txt          # installs the official anthropic SDK
export ANTHROPIC_API_KEY="sk-ant-..."    # your Anthropic API key
python3 claude_prank.py                   # now the banter is genuinely generated
```

`claude_mode` in `prank.config.json` controls this:

- `"auto"` (default) — use the live API if the SDK **and** a key are present,
  otherwise fall back to scripted lines. Nothing breaks if the key is missing.
- `"always"` — require the live API (errors out if unavailable).
- `"never"` — always scripted, never makes a network call.

The live backend uses the official Anthropic Python SDK and defaults to the
`claude-opus-4-8` model. For a snappier, cheaper prank you can set
`"model": "claude-haiku-4-5"` in the config.

## Configuration

Edit `prank.config.json` (or override any field with an env var like
`PRANK_FRIEND_NAME`, `PRANK_TARGET_DIR`, `PRANK_CLAUDE_MODE`, `PRANK_MODEL`):

| Field | Meaning |
|---|---|
| `friend_name` | Personalizes Claude's banter |
| `game_name` | Cosmetic name shown in the loader |
| `target_dir` | The folder the prank reads/edits (default `sample_game`) |
| `claude_mode` | `auto` / `always` / `never` |
| `model` | Claude model id for the live backend |
| `persona` | Optional custom system prompt for Claude |
| `typing_delay` | Seconds between fake loader log lines (`0` = instant) |
| `word_swaps` | The `{old: new}` word substitutions applied to text/config |

## Pointing it at a REAL game

Change `target_dir` to your game's editable data/mods folder and re-run. Some
tips:

- **Point at a copy first.** `cp -r "/path/to/game/data" ./my_game_copy`, set
  `target_dir` to `my_game_copy`, and test there. Everything is reversible, but
  a copy means zero risk to the real install while you dial it in.
- The prank only edits `.json` and common text/config files (`.txt`, `.ini`,
  `.cfg`, `.yaml`, …). It **skips binaries** and anything it can't safely parse.
- Every modified file gets a `<name>.prankbak` backup and is listed in a
  `.prank_manifest.json`; `--restore` puts it all back byte-for-byte and deletes
  those artifacts.

## Safety model

- Only ever touches files **inside** `target_dir`.
- Backs up each file **before** editing it; records created files.
- `--possess` refuses to run twice in a row — you must `--restore` first, so
  backups are never clobbered.
- `--restore` is exact: original bytes and formatting are preserved.

## On "forking the game" — the honest version

You asked about forking your game. Two cases:

- **Your game is open source / a git repo** → you can genuinely fork it and mod
  it directly. Point `target_dir` at its data folder (or drop this prank layer
  into the fork).
- **It's a commercial game and "the game files" are the installed game** →
  "fork" doesn't really apply, and you should **not commit those game files into
  this (or any) GitHub repo.** Copying copyrighted game files into a public repo
  is redistribution — and "I'm not making money" doesn't change copyright. This
  prank is built so it **doesn't need** the game in the repo: it operates on the
  files sitting on your (or your friend's) machine. `.gitignore` already excludes
  `real_game/` and `game_files/` to keep them out by accident.

Modding a game you own, for a personal prank, on your own machine, is the normal
and fine path. Publishing the game's assets is the part to avoid.

## Project layout

```
claude_prank.py        # CLI entry point
prank/
  config.py            # config loading (JSON + env overrides)
  loader.py            # fake DLL-injection theater
  voice.py             # Claude voice: live SDK backend + scripted fallback
  gamefiles.py         # reversible, backup-first file edits
prank.config.json      # your settings
sample_game/           # tiny demo "game" to prank safely
requirements.txt       # anthropic SDK (only needed for the live backend)
```

Have fun. Restore responsibly. 👻

# Running it inside DDLC

Base DDLC runs on an old engine (Ren'Py 6.99, Python 2); the director is
Python 3. So the brain runs as a small **sidecar** program next to the game,
and one small file inside the game talks to it over `localhost`.

| Piece | What it is | Where it lives |
|---|---|---|
| **Sidecar** (the brain) | `game/claude_mod/` — director, persona, `sidecar.py`, your `config.json` | Stays in this folder. You run it; it calls OpenRouter. |
| **Bridge** (the visuals) | `game/claude_mod_bridge.rpy` | Inside DDLC's `game/` folder. **The sidecar installs it for you.** |

> Never copy the `claude_mod/` folder into DDLC — it's Python 3 and would crash
> the game's engine. Only the bridge goes in, and the sidecar handles that.

## First run

1. **Your key** — copy `game/claude_mod/config.example.json` to
   `game/claude_mod/config.json` and paste your OpenRouter key into
   `"api_key"`.
2. **Start the sidecar** — open a terminal in this folder and run:
   ```
   python game/claude_mod/sidecar.py
   ```
   Leave that window open. Its banner tells you everything:
   ```
    DDLC director sidecar   (version 8)
    listening: http://127.0.0.1:8765
    model:     anthropic/claude-opus-5  ...
    bridge:    installed (stale .rpyc removed) -> C:\...\DDLC-1.1.1-pc\game
   ```
   It finds DDLC by itself when it sits near this folder (e.g. both in
   Downloads). If it says it couldn't, add `"ddlc_game_dir": "C:/path/to/DDLC-1.1.1-pc"`
   to `config.json`.
3. **Play** — launch DDLC and start a new game. Everything up to and including
   the **day-2 poem** is the untouched real game. When day 3's club meeting
   starts, the AI takes over by itself. (Press **F9** to take over earlier, for
   testing.)

## Controls (secret, during the takeover)

| Key | Does |
|---|---|
| `-` / `=` | creepier / calmer (ignored while the player is typing, so a hyphen in his message can't trigger it) |
| **F5 / F6** | creepier / calmer, works even while he's typing |
| **F10** | model picker. Each id is checked with OpenRouter first (free); the pick survives restarts. |
| **F9** | take over right now (only once per game; does nothing on the main menu) |
| Enter on an empty box | let the club keep talking without saying anything |

F11 is left alone — it's the engine's fullscreen key.

The sidecar window logs every turn: which model answered, tokens, the cost,
the run's running total, and the current intensity. Intensity changes from the
secret keys show up there too, never in the game.

## What it looks like in game

Everything visual reuses DDLC's own pieces, checked against the game's source:

- **Name boxes, quotes, click-to-continue arrow**: DDLC's say screen. Names are
  white with the pink outline, exactly like the real game.
- **His own lines**: DDLC's `mc` character, so his typed message shows with his
  name, and lands in the **History** screen with everyone else's.
- **Typing**: inside the real textbox, same font, wrapping and caret.
- **Sprites**: DDLC's own slots (`t11` for one girl … `t41`–`t44` for four) at
  the game's size; whoever is speaking steps forward (`f`-transforms), and girls
  who leave fade out (`thide`). Leftover sprites from the real game are cleared.
- **Faces**: twelve moods mapped to the exact sprite codes DDLC's script uses
  for each emotion — e.g. Sayori's "Ehehe~" face (`1q`), Natsuki's "Hmph."
  (`5s`), Monika's teasing lean-in (`5a`). Change any in `CLAUDE_FACES`.
- **Poems**: DDLC's own `showpoem` — the real paper, each girl's handwriting
  font, her version of the poem music, the page-turn sound.
- **Music**: the real game's cues (`t2` arriving, `t3` club, `t5` poem sharing,
  `t7` the Natsuki/Yuri fight, `t8` sad, `t9` tense) plus its glitched tracks
  for later; a cue for the song already playing never restarts it.
- **Glitch effect**: DDLC's own screen tear.

The AI is also told exactly where the real game handed over: the day, which
girl his poems have been winning over, and the last ~20 lines he read.

Each takeover is a **fresh run**: the previous transcript is archived (in
`game/claude_mod/memory/archive/`, never deleted), so test sessions don't pile
up into one ever-more-expensive conversation, and your tests never leak into
your friend's game.

## Updating

```
python update.py
```
Downloads the latest version and replaces the code — never your `config.json`,
`dossier.json` or `memory/`. Anything you'd edited (like the character bible)
is saved in `update_backup/` first. Then restart the sidecar, and it installs
the matching bridge into DDLC by itself.

When a takeover starts, the game checks the sidecar's version. If you see
**"OLD SIDECAR"**, the brain wasn't restarted after an update.

## When something's off

| You see | Means |
|---|---|
| `Sidecar not reachable` toast | `sidecar.py` isn't running. Start it, then press F9. |
| `OLD SIDECAR (vX, need v8)` toast | Restart the sidecar (after `python update.py`). |
| Sidecar says **ALREADY RUNNING** on start | An old sidecar window is still open — the game is talking to *that* one. Close it, start again. |
| `Director error: ...402...` toast | Out of OpenRouter credit. |
| `Not switched: OpenRouter doesn't know ...` | That model id doesn't exist on OpenRouter; pick another. |
| The girls say "..." | The real reason is in the toast and in the sidecar window. |

## Giving it to your friend (later)

The friend shouldn't need Python. Once it plays the way you want:

1. `pip install pyinstaller`
2. `pyinstaller --onefile --add-data "game/claude_mod;claude_mod" game/claude_mod/sidecar.py`
   → `dist/sidecar.exe`
3. Ship: your DDLC folder (bridge already inside) + `sidecar.exe` + a
   `Start.bat` that starts `sidecar.exe`, then the game. Set a spend limit on
   the key you ship, and rotate it afterwards.

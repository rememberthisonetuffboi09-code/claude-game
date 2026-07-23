# Putting it into the actual game

Base DDLC runs on an old Python 2 engine; our director is Python 3. So the
brain runs as a small **sidecar** program and the game talks to it locally.
Two pieces:

| Piece | What it is | Where it runs |
|---|---|---|
| **Sidecar** | `game/claude_mod/` (director, persona, `sidecar.py`, your `config.json`) | Runs on your PC as `python sidecar.py`, separate from the game. Makes the OpenRouter calls. |
| **Bridge** | `game/claude_mod_bridge.rpy` (one small file) | Goes **into DDLC's `game/` folder.** Talks to the sidecar over `localhost`. |

> ⚠️ For base DDLC, copy **only** `claude_mod_bridge.rpy` into the game. Do NOT
> copy `claude_mod_hooks.rpy` or the `claude_mod/` folder into DDLC — those are
> Python 3 and will crash the old engine. The `claude_mod/` folder is the
> sidecar; it runs on its own.

## First run (on your machine)

1. **Make your config** — in the unzipped repo, copy
   `game/claude_mod/config.example.json` to `game/claude_mod/config.json` and
   paste your OpenRouter key.
2. **Start the sidecar** — open a terminal in the repo folder and run:
   ```
   python game/claude_mod/sidecar.py
   ```
   Leave that window open. It prints `listening: http://127.0.0.1:8765`.
   (Quick check: `python game/claude_mod/test_connection.py` should print a
   real Monika line now that you have credit.)
3. **Install the bridge** — copy `game/claude_mod_bridge.rpy` into your DDLC's
   `game/` folder (e.g. `ddlc-win/game/`).
4. **Play** — launch DDLC. Play normally. When you want the AI to take over
   (right after the day-2 poem/path choice is the intended spot), press **F9**.
   From then on the club is live.
   - **`-`** = escalate the creep · **`=`** = dial it back (secret, mid-play)

If F9 says "Can't reach the director," the sidecar window isn't running — start
step 2 and press F9 again.

## Making it look right (next tuning passes)

- **Speaker name/box:** the bridge currently narrates lines; to show each girl's
  real DDLC name box, fill the one `renpy.say()` TODO in `claude_mod_bridge.rpy`.
- **Sprites:** fill `CLAUDE_SPRITE` in the bridge with your real expression tags
  (`show monika 1a` style). Backgrounds/music maps are pre-seeded with real
  base-DDLC names — tweak for your HD assets.
- **Auto-seam (optional):** to make F9 automatic, set `CLAUDE_LOG_LABELS = True`
  in the bridge, play to the day-2 choice, open `claude_labels.log`, find the
  label that fired at that moment, and put it in `CLAUDE_SEAM_LABEL`.

## Giving it to your friend (final packaging)

The friend shouldn't need Python. On your Windows machine, once:

1. `pip install pyinstaller`
2. `pyinstaller --onefile --add-data "game/claude_mod;claude_mod" game/claude_mod/sidecar.py`
   → produces `dist/sidecar.exe` (the whole brain in one file, key baked into
   its `config.json` — set a spend cap and rotate after).
3. Ship the friend: your DDLC build (with `claude_mod_bridge.rpy` inside) +
   `sidecar.exe` + a `Start.bat` that launches `sidecar.exe` then the game.
   One double-click, no Python required.

We'll walk through this together once the in-game part looks the way you want.

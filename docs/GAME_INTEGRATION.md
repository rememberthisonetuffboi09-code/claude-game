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
   - **`-`** = escalate the creep · **`=`** = dial it back (secret, mid-play).
     These are ignored while the player is typing, so a hyphen in their message
     can't secretly escalate. **F11 / F12** do the same and always work.
   - **F10** = model picker (Opus 5 / Fable 5 / Opus 4.8 / Opus 4.7 / Sonnet 5 /
     GLM). Switches the director's model live via the sidecar's `/model`
     endpoint; the menu shows which model is currently loaded, the game toasts
     the change, and the sidecar window prints `[model] switched to …`.

The bridge now handles the visuals itself: each girl gets her own DDLC-styled
**name box** (colour + quotes), her **sprite appears and repositions** as girls
join the scene, **music/background** cues map to real base-DDLC tracks
(`t3`/`t4`/`t8`/`t9`/`g1`/`g2`, `club_day`/`class_day`/…), and `shake`/`flash`
effects use Ren'Py's built-in `vpunch`/`Fade`. The takeover also reads the
player's entered name (`persistent.playername`) and hands it to the director so
Monika can use it.

If F9 says "Can't reach the director," the sidecar window isn't running — start
step 2 and press F9 again.

## ⚠️ Updating the mod: you must update BOTH pieces

This is the single easiest thing to get wrong. The bridge `.rpy` only draws the
scene. **Expressions, how long the girls talk, and model switching all live in
the sidecar** (`game/claude_mod/`). Updating one and not the other means those
features silently don't change.

So after any update:

1. Replace `claude_mod_bridge.rpy` in DDLC's `game/` folder, and **delete the
   stale `claude_mod_bridge.rpyc`** next to it (Ren'Py caches compiled code;
   leave it and the game keeps running the OLD bridge).
2. Replace the changed files in `game/claude_mod/` (usually `director.py` and
   `sidecar.py`). Your `config.json` is never touched.
3. **Restart the sidecar** (`Ctrl+C`, then run it again).

The mod checks this for you. The sidecar reports a `SIDECAR_VERSION`, and when
the takeover starts the bridge compares it against `CLAUDE_EXPECTED_SIDECAR` and
shows a toast:

| Toast on F9 | Meaning |
|---|---|
| `Sidecar v7 ok - model: …` | Both halves current. Everything active. |
| `OLD SIDECAR (v…, need v7)` | The brain is stale — do step 2 + 3 above. |
| `Sidecar not reachable` | `sidecar.py` isn't running at all. |

If a call fails (bad key, no credit, unknown model slug) the girls say "..." to
keep the illusion, but you get a `Director error: …` toast and the sidecar
window prints the real reason — so a dead API never looks like a quiet club.

## Making it look right (next tuning passes)

- **Name boxes / music / backgrounds:** working out of the box (base-DDLC
  tags). Edit `CLAUDE_NAME_COLORS`, `CLAUDE_MUSIC`, `CLAUDE_BG` at the top of
  `claude_mod_bridge.rpy` if your HD assets use different names/colours.
- **Sprite expressions:** `CLAUDE_SPRITE` currently maps only `_default`/`happy`/
  `surprised` (safe base-DDLC codes); every other mood falls back to a neutral
  pose so a sprite always shows and nothing crashes. Fill in more per-girl codes
  (`1a`/`1b`/`2a`… for base DDLC, or your DDLC+ tags) once you've picked which
  sprite set you're shipping.
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

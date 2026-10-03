# Claude Game — a self-aware DDLC "mod"

A private, non-commercial prank/mod that makes a Doki Doki Literature Club
experience *actually* self-aware: the characters are voiced live by an
Anthropic model (Claude **Fable 5**, with **Opus 4.8** as a safety net), and
the "director brain" can read harmless local signals about the player and bend
the game in real time. Monika is the lead; the other Dokis show up on demand.

> This is a fan mod for personal use. It is **not** for sale and must never be.
> It reuses the free base game's engine and — locally — the paid DDLC+ assets
> the author owns. **No game art, music, fonts, or scripts are committed to
> this repo** (see [Legal & assets](#legal--assets)).

---

## The idea in one paragraph

It boots and plays like real DDLC — the authentic intro, the four Dokis, the
music, the club, all the way through Act 1 up to the **day-2 poem/path choice**
(the "seam"). Nothing is AI-driven before that point. After the seam, the
**Fable 5 "director brain"** takes over: one model that *thinks* like a
self-aware cast, decides who speaks and how, remembers everything the player
has said, paces a slow creepy burn (that you can speed up), and can drop
unsettling-but-harmless references to the player's real machine.

### Two modes
- **Story Mode** — stays on DDLC's branching rails (ripped from the real game),
  but the Dokis can rewrite the path and it gets creepy in the details.
- **Monika Mode (freeplay)** — Monika is off the leash: full free will, her own
  pace, does more.

Both play the identical authentic prologue and only diverge after the seam.

---

## Architecture: base engine, Plus skin

| Layer | What we use | Why |
|---|---|---|
| **Engine + code** | **base DDLC** (pure Ren'Py / Python) | It's the only version whose code is editable — required for the AI, the file control, and an easy downloadable build. |
| **Art + music** | base DDLC's own today; **DDLC+ HD assets** planned | Better-looking Dokis + remastered soundtrack, as plain files on top of the base engine. |
| **Brain** | **Claude Fable 5** → Opus 4.8 fallback | Always-on "thinking" = the hidden director; only the spoken line reaches the textbox. |

So: *add onto base DDLC's code, wear DDLC+'s graphics.* This is the standard
DDLC "HD mod" approach.

---

## What's in this repo (and what isn't)

**In the repo** — the mod code only:

```
update.py                     # python update.py — get the latest version (keeps your key + memory)
game/
  claude_mod_bridge.rpy       # the ONLY file that goes into DDLC (the sidecar installs it for you)
  claude_mod/                 # the brain — Python 3, runs next to the game, never inside it
    sidecar.py                # the local server the game talks to; also installs the bridge
    director.py               # pacing/escalation, modes, prompt-building, response parsing
    openrouter_client.py      # talks to OpenRouter (prompt caching, model id check)
    memory.py                 # the conversation; each takeover is a fresh, archived run
    scanner.py                # SAFE, read-only local signals + dossier loader
    test_connection.py        # check your API key works, without launching the game
    chat_cli.py               # talk to the director in a terminal
    config.example.json       # copy to config.json and add your key
    dossier.example.json      # copy to dossier.json and add what you know about your friend
    persona/                  # EDITABLE character bible
docs/GAME_INTEGRATION.md      # how to run it, controls, troubleshooting
tests/                        # offline tests (no API credit used)
```

**Not in the repo** (kept local, git-ignored):
- Base DDLC and its `.rpa`/`.rpyc` files
- Your `config.json` (API key) and `dossier.json`
- Conversation transcripts (`game/claude_mod/memory/`)

---

## Setup

Full guide: [`docs/GAME_INTEGRATION.md`](docs/GAME_INTEGRATION.md).

1. Get **base DDLC 1.1.1** (free, from Team Salvato) and unzip it.
2. Copy `game/claude_mod/config.example.json` → `config.json` and paste your
   **OpenRouter** key. Set a spend limit on that key and rotate it after the
   prank — anyone with the files can use it.
3. (Optional) copy `dossier.example.json` → `dossier.json` and fill in what you
   already know about your friend.
4. Run `python game/claude_mod/sidecar.py` and leave it open. It finds DDLC and
   installs the bridge into it.
5. Play. The real game runs untouched through the day-2 poem; the AI takes
   over when day 3's club meeting starts (or press **F9** to test sooner).

To update later: `python update.py`, then restart the sidecar.

---

## Controls & tuning

| Setting | Where | Effect |
|---|---|---|
| `-` / `=`, F5 / F6 | in game | Secretly escalate / dial back the creepiness |
| F10 | in game | Switch model (checked with OpenRouter, remembered) |
| `pace` | `config.json` | Baseline escalation speed: `slow` / `normal` / `fast` / `instant` |
| `starting_intensity` | `config.json` | Where the creep starts (0–10) |
| `default_mode` | `config.json` | `story` or `monika` |
| `enable_local_scan` | `config.json` | Read-only "she knows your machine" signals |

---

## Safety boundaries (hard rules)

- **Nothing destructive, ever.** No deleting, corrupting, or editing the
  player's real files. The scanner is **read-only**; the only write capability
  (off by default) drops a harmless `.txt` in a designated folder and never
  overwrites anything.
- **No account access.** We do **not** read Discord tokens or use anyone's
  logins. "She knows your friends" comes from the dossier you write, not from
  hijacking accounts.
- It's a consensual prank between friends — plan to let them in on it after.

---

## Legal & assets

DDLC's fan-content guidelines permit non-commercial mods, and you own DDLC+.
This project is private and non-commercial. **Do not commit** base-game or
DDLC+ art/music/fonts/scripts here — they stay on your machine (the
`.gitignore` enforces this). Don't redistribute the paid assets.

---

## Status

Playable in base DDLC 1.1.1. The takeover starts automatically at the real
seam (`ch2_main`, right after the day-2 poem), and every visual uses DDLC's
own pieces: say screen, `mc`, position transforms, the sprite codes its script
uses for each emotion, `showpoem`, its music and backgrounds. DDLC+ HD assets
aren't wired in yet. Run the offline tests with
`python3 tests/test_director.py` (and `test_bridge_logic.py`,
`test_bridge_sync.py`, `test_sidecar.py`).

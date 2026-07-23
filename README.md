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
| **Art + music** | **DDLC+ HD assets** (dropped in locally) | Better-looking Dokis + remastered soundtrack, as plain files on top of the base engine. |
| **Brain** | **Claude Fable 5** → Opus 4.8 fallback | Always-on "thinking" = the hidden director; only the spoken line reaches the textbox. |

So: *add onto base DDLC's code, wear DDLC+'s graphics.* This is the standard
DDLC "HD mod" approach.

---

## What's in this repo (and what isn't)

**In the repo** — the mod code only:

```
game/
  claude_mod/                 # the brains (pure Python, engine-agnostic)
    fable_client.py           # talks to the Anthropic API (Fable 5 + Opus 4.8 fallback)
    director.py               # pacing/escalation, modes, prompt-building, response parsing
    memory.py                 # remembers the whole conversation (survives restarts)
    scanner.py                # SAFE, read-only local signals + dossier loader
    test_connection.py        # verify your API key works, without launching the game
    config.example.json       # copy to config.json and add your key
    dossier.example.json      # copy to dossier.json and add what you know about your friend
    persona/                  # EDITABLE character bible (we refine this together)
      characters.json         # how each Doki talks / acts / thinks
      story.md                # the original DDLC story + how it went
      examples.md             # example dialogue per character
  claude_mod_hooks.rpy        # Ren'Py glue: the seam hook, dialogue screen, hotkeys
```

**Not in the repo** (kept local, git-ignored):
- Base DDLC and its `.rpa`/`.rpyc` files
- Your DDLC+ HD art / music / fonts (`game/claude_mod/hd_assets/`)
- Your `config.json` (API key) and `dossier.json`
- Conversation transcripts and saves

---

## Setup (high level — details in `game/claude_mod/README.md`)

1. Get **base DDLC** (free, from Team Salvato) and get it running in Ren'Py.
2. Drop the `game/claude_mod/` folder and `game/claude_mod_hooks.rpy` into
   DDLC's `game/` directory.
3. Copy `config.example.json` → `config.json` and paste your Anthropic API key.
   **Set a spend cap on that key** and rotate/delete it after the prank —
   anyone with the files can use it.
4. Copy `dossier.example.json` → `dossier.json` and fill in what you already
   know about your friend (this is the secret sauce for "how does it know
   that?!").
5. Drop your extracted **DDLC+ HD assets** into `game/claude_mod/hd_assets/`.
6. Run `python game/claude_mod/test_connection.py` to confirm the key works.
7. Launch. The controls you'll care about:
   - **`-` (minus)** = secretly escalate the creepiness (press while your friend plays)
   - **`=` (equals)** = secretly dial it back down

---

## Controls & tuning

| Setting | Where | Effect |
|---|---|---|
| `pace` | `config.json` | Baseline escalation speed: `slow` / `normal` / `fast` / `instant` |
| `-` / `=` keys | in-game | Live nudge the intensity up/down while watching |
| `effort` | `config.json` | Model speed vs. depth (`low` = snappy replies; default) |
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

Scaffold in progress. The AI/director/memory/scanner/config layers and the
Ren'Py glue are stubbed and wired; the character bible is a first draft we edit
together; the exact DDLC day-2 label and HD sprite tags are marked as
integration TODOs (they depend on your local game files).

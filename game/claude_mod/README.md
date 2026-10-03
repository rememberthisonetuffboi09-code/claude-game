# claude_mod — the director brain

This folder is the **sidecar**: pure Python 3, run on its own next to the game.
It is never copied into DDLC (the game's engine is Python 2 and would crash).
How it all fits together, the controls, and updating:
[`docs/GAME_INTEGRATION.md`](../../docs/GAME_INTEGRATION.md).

## Setup

1. **API key** — copy `config.example.json` to `config.json` and paste your
   OpenRouter key into `"api_key"`. Set a spend limit on the key in OpenRouter.
2. **(Optional) dossier** — copy `dossier.example.json` to `dossier.json` and
   fill in what you already know about your friend. It's the secret sauce for
   "how does she know that?!", and it only unlocks late in the night.
3. **Test the key** (no game needed): `python test_connection.py`
4. **Run it**: `python sidecar.py` — it also installs the bridge into DDLC.

## Cost

Prices per million tokens (input / output) on OpenRouter: Fable 5 $10 / $50,
Opus 5 $5 / $25, Sonnet 5 $2 / $10. Opus 5 is the sweet spot; Sonnet 5 is the
cheap way to test. Each turn's cost is printed in the sidecar window. Prompt
caching (on by default for Anthropic models) makes the long, repeated part of
every request about 10% price.

## Editing the character bible

These files are yours — the model reads them every turn:

| File | What it controls |
|---|---|
| `persona/characters.json` | How each Doki talks, acts, thinks; her meta-awareness |
| `persona/story.md` | The original DDLC arc, so it can remix rather than copy |
| `persona/examples.md` | Example lines that lock each voice |

Save, restart the sidecar, done. (`python update.py` backs up your edits
before it replaces these files.)

## Controls & pacing

| Knob | Where | Effect |
|---|---|---|
| `pace` | `config.json` | `slow` / `normal` / `fast` / `instant` — how fast the creep rises on its own |
| `starting_intensity` | `config.json` | where the creep begins (0–10) |
| `default_mode` | `config.json` | `story` or `monika` |
| `ddlc_game_dir` | `config.json` | only if the sidecar can't find DDLC by itself |
| `-` / `=`, F5 / F6 | in game | creepier / calmer |
| F10 | in game | switch model |

## Safety (enforced in code)

- `scanner.py` is **read-only**: harmless signals (username, PC name, Desktop
  file *names*, installed Steam games) — never file contents, passwords or
  account tokens.
- The only write, `drop_note`, is **off by default**, writes one harmless
  `.txt` into `Desktop/MonikaWasHere/`, and never overwrites or deletes.

# claude_mod — setup & editing guide

The "director brain" that makes DDLC self-aware. This folder is pure Python
(no Ren'Py imports), so you can test it on its own before it ever touches the
game.

## 1. Install into DDLC
Drop this whole `claude_mod/` folder and the sibling `claude_mod_hooks.rpy`
into base DDLC's `game/` directory:

```
DDLC/game/claude_mod/          <- this folder
DDLC/game/claude_mod_hooks.rpy <- the Ren'Py glue
```

## 2. Add your API key
```
cp config.example.json config.json
```
Open `config.json` and paste your Anthropic key into `"api_key"`.

> **Money safety:** set a spend cap on this key in the Anthropic console, and
> rotate/delete it after the prank. Fable 5 is premium ($10 / $50 per million
> tokens), and every turn resends the growing transcript — a long session adds
> up. If it feels pricey or slow, switch `"model"` to `"claude-opus-4-8"`
> (cheaper, faster, still excellent). It's already the refusal fallback.

## 3. Fill in the dossier (the secret sauce)
```
cp dossier.example.json dossier.json
```
Put in what YOU already know about your friend — friends' names, inside jokes,
games they love, their Discord handle. This is what makes it feel like it *knows*
them. Leave anything blank you don't have.

## 4. Test the connection (no game needed)
```
python test_connection.py
```
You should see Monika say hello. If the key is wrong or the network's blocked,
you'll get a clear error here instead of a silent game.

## 5. Add your DDLC+ HD assets
Drop your extracted DDLC+ sprites / music / backgrounds into `hd_assets/`
(git-ignored). Then map moods to sprite tags in `claude_mod_hooks.rpy`
(`claude_show`, marked TODO).

## 6. Wire the seam
In DDLC's day-2 script, right after the poem/path choice, add:
```
jump claude_mod_takeover
```

---

## Editing the character bible
These files are yours to tweak — the model reads them every turn:

| File | What it controls |
|---|---|
| `persona/characters.json` | How each Doki talks, acts, thinks; their meta-awareness behavior |
| `persona/story.md` | The original DDLC story, so it can remix rather than copy |
| `persona/examples.md` | Example lines that lock each voice |

Change a voice, add a catchphrase, rewrite how Monika escalates — save the file,
relaunch, done.

## Controls & pacing
| Knob | Where | Effect |
|---|---|---|
| `pace` | `config.json` | `slow` / `normal` / `fast` / `instant` baseline ramp |
| `-` key | in-game | escalate now |
| `=` key | in-game | dial it back |
| `starting_intensity` | `config.json` | where the creep begins (0–10) |
| `default_mode` | `config.json` | `story` or `monika` |
| `effort` | `config.json` | `low` = snappy replies (default) |

## Safety (enforced in code)
- `scanner.py` is **read-only**. It reads harmless signals (username, PC name,
  Desktop file *names*, installed Steam games) — never file contents, never
  passwords, never Discord/account tokens.
- The only write, `drop_note`, is **off by default**, writes one harmless `.txt`
  into `Desktop/MonikaWasHere/`, and never overwrites or deletes anything.
- Nothing here can harm the player's real data.

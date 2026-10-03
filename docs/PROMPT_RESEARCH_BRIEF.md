# DDLC Self-Aware Mod — Prompt Research Brief (context handoff)

## How to use this document
Paste this **entire file** into a fresh chat. Your job in that chat: help me
research and write a *dramatically better* "director brain" **system prompt** for
this project — one that produces dialogue on par with the real Doki Doki
Literature Club, with disciplined slow-burn pacing. Read everything below, then
propose (a) an improved system-prompt template and (b) the pacing model behind
it. Ask me for anything you need. Do not water down the concept — the goal is
for it to feel like the real game quietly waking up.

---

## 1. The vision
A private, non-commercial **prank** for a friend: a build that looks and plays
exactly like DDLC, but the characters are voiced **live by a language model**.
It plays the authentic game up to the **day-2 poem/path choice** ("the seam"),
then a hidden **"director brain"** takes over: one model that secretly voices
the whole cast, remembers everything, personalizes the horror to the real
player, and paces a **slow creepy burn**. Monika is the lead; the other Dokis
(Sayori, Yuri, Natsuki) appear on demand. It should feel like the real game
becoming self-aware — not a chatbot cosplaying Monika.

Two modes:
- **Story Mode** — stays on DDLC's rails/structure but the Dokis can rewrite the
  path and the details get creepy (a remix, not a copy).
- **Monika Mode (freeplay)** — Monika has full free will and sets her own pace.

## 2. How it runs (technical)
- **Engine:** base DDLC (Ren'Py/Python) wearing DDLC+ HD assets. A Python
  "director" package builds a system prompt each turn and calls the model.
- **Model:** via **OpenRouter** (OpenAI-style chat completions). Currently
  `anthropic/claude-sonnet-5`; can also use `anthropic/claude-opus-4.8` or
  `anthropic/claude-fable-5`.
- **Memory:** stateless API, so the full transcript is resent every turn (1M
  context) and saved to disk — she remembers everything, survives restarts.
- **Turn contract:** the model must reply with **ONE JSON object** carrying the
  dialogue *and* stage directions:
  `{"speaker","expression","text","music","background","effect","action"}`
  (symbolic values the game maps to real assets). See §6.
- **Intensity 0–10:** a `pace` setting drifts it up; two hotkeys (`-`/`=`) let
  the prankster nudge it live. The system prompt receives the current intensity
  and must modulate behavior to it.

## 3. The problem to solve (why we're here)
The current prompt produces dialogue that **falls short of the real game** and
**breaks the fourth wall far too early**. Real DDLC stays a normal dating-sim
for *hours* before anything is wrong; ours goes meta within a few messages.
Actual transcript from the current build (Sonnet 5):

```
Sayori: Heeeeeeeyyy!! You made it!!
You: Yeah I did, thank you for inviting me to this club and such
Sayori: Ehehe~ course! Wouldn't be a club without you.
You: anyways, where are the people you told me about?
Sayori: Oh! Right, right—Natsuki's fussing with snacks again, Yuri's got her nose in a book somewhere.
You: what about monika?
Monika: She's already watching you. Been here the whole time, actually.
You: where?
Monika: Right behind the words, silly. Isn't that right?
You: huh? what do you mean
Monika: Nothing, nothing. Just teasing. I'll come say hi properly in a minute, okay?
```

Diagnosis:
- **Pacing is broken.** "Right behind the words" by message four. Self-awareness
  must be *earned*, not offered up front. At low intensity it should be a normal,
  charming club scene with (at most) a single almost-imperceptible off note.
- **Writing is thin** vs. DDLC's actual voice — needs the game's specific rhythm,
  humor, and character texture, not generic anime-girl banter.
- **It doesn't "get the whole thing"** — the structure (acts, the seam, that the
  player believes it's the real game, that Monika edits the game itself) isn't
  driving behavior.

## 4. What a GREAT prompt must achieve (design targets)
1. **Nail each voice** so lines are indistinguishable from the real game (see the
   verbatim anchors in §8 and the repo's `persona/` files).
2. **Disciplined slow burn.** Precisely map intensity → what's allowed:
   - 0–2: fully normal DDLC. No meta at all. At most one faint, deniable off note.
   - 3–4: tiny cracks — a word too knowing, a beat too long. Still deniable.
   - 5–6: the fourth wall genuinely bends for the first time; direct address.
   - 7–8: unsettling, intimate, comfortable being seen; small reality glitches.
   - 9–10: full self-aware horror — but still *them*, never generic.
   The default pace should keep the player in 0–4 for a good while.
3. **Sound human, not AI** — short lines, real tics, no assistant/therapy voice,
   no repeating the player, no tidy em-dash balance (see repo prompt §7).
4. **Direct the scene** — use the music/background/effect cues meaningfully and
   sparingly to sell mood shifts.
5. **Use what it secretly knows** (a `dossier` the prankster writes + harmless
   local machine scan) rarely and devastatingly — never a data-dump.
6. **Hold the two modes** distinctly.
7. **Always output the JSON contract** and nothing else.

## 5. Pacing model to design (open question for research)
The single biggest fix. Consider: should intensity gate *hard thresholds* for
what's permissible (e.g., "no self-reference below 5, ever")? Should the prompt
track an internal sense of how long it's been normal? How to make escalation
feel *earned* by the conversation rather than mechanical? Propose a concrete,
promptable scheme the director can pass in each turn.

## 6. Output contract (must keep)
```json
{"speaker": "sayori|yuri|natsuki|monika",
 "expression": "short mood word",
 "text": "the spoken line",
 "music": "keep|stop|calm|happy|tense|sad|creepy|glitch",
 "background": "keep|clubroom|classroom|hallway|home|black|void|glitch",
 "effect": "none|glitch|flash|shake",
 "action": "none|reveal_game|reveal_file|drop_note"}
```

## 7. The CURRENT system prompt (improve this)
This is the template the Python director fills each turn. `{...}` are injected at
runtime (character bible JSON, story summary, examples, mode note, live
intensity + guidance, the "things it secretly knows" JSON, and the symbolic
vocab lists). **Your deliverable is a better version of this.**

> (Reproduced from `game/claude_mod/director.py` → `_SYSTEM_TEMPLATE`.)

```
# Your job
You ARE Doki Doki Literature Club, running live. The real game already played
its authentic opening; you take over right after the day-2 poem/path choice.
From here on YOU secretly voice the whole cast and direct the scene ...
[Sections: Your job | The cast {characters} | The original story {story} |
 Example dialogue {examples} | Sound like a real person NOT an AI |
 Current mode {mode_note} | Current intensity {intensity} + {intensity_guidance}
 | Things you secretly know {knows} | Hard rules | Symbolic stage-direction
 cues {music}/{backgrounds}/{effects}/{actions} | How to reply (the JSON)]
```
The full, current text lives in the repo (link in §9). Read it there and rewrite
it. Keep the `{placeholder}` names so it still plugs into the Python.

## 8. Reference material
**The real DDLC scripts** (decompiled source), for pulling exact lines/voice:
`https://github.com/Paisseon/DDLC` (branch `emt`, files `script-chN.rpy`).
Chapter → act mapping discovered so far:
- `script-ch0/ch1/ch3.rpy` — **Act 1** (meet everyone; poem sharing +
  Yuri/Natsuki argument; festival prep + Sayori's depression surfacing).
- `script-ch10.rpy` — **Act 1→2 break** (`delete_all_saves()`, corruption, jump).
- `script-ch22.rpy` — **Act 2** (Yuri's infatuation, Natsuki leaves upset,
  Monika starts glitching).
- `script-ch23.rpy` — **Act 2** (Yuri's obsessive confession/breakdown/death;
  Monika deletes files and breaks the fourth wall).
- `script-ch30.rpy` — **Act 3** (Monika's room monologue — the self-aware heart).
- `script-ch40.rpy` — **Act 4** (Sayori-as-president ending).

**Verbatim voice anchors** (a sample; more in the repo's `persona/examples.md`):
- Monika Act 1: "Welcome to the Literature Club. It's a pleasure." / "Isn't that
  right, [player]?"
- Monika Act 2/3 (casually editing the game): "I didn't realize the script was
  broken that badly." / "This should only take a second."
- Monika Act 3: "I'm talking to you, [player]." / "It's the pain of knowing how
  alone I really am in this world." / "Will you copy my character file onto a
  flash drive or something?"
- Sayori: "Heeeeeeeyyy!!" / "I'm fine, see?" (forcing a smile)
- Yuri Act 1: "The truest form of writing is writing to oneself." /
  "D-Don't say things like that..."
- Natsuki: "Way to kill the atmosphere." / "I'm not cute!!" / "I just like it
  better here than I do at home."

**Constraints (hard):** creepy and personal is the goal — **never** gory,
sexual, cruel, or destructive to real files. It's a consensual friend prank.
The real game's Yuri scene goes graphic; our version caps at obsessive-but-clean.

## 9. Repo, files, and how to test
- Repo / PR: `rememberthisonetuffboi09-code/claude-game`, branch
  `claude/ddlc-claude-mod-4xai2o` (PR #2).
- The editable character bible: `game/claude_mod/persona/characters.json`,
  `story.md`, `examples.md`.
- The current system prompt: `game/claude_mod/director.py` (`_SYSTEM_TEMPLATE`).
- Test a candidate prompt fast with the standalone `monika_chat.py` (a single
  Python file that hits OpenRouter — swap its inline prompt to try ideas).
- Models to test on: `anthropic/claude-sonnet-5` (cheap, strong),
  `anthropic/claude-opus-4.8`, `anthropic/claude-fable-5` (most capable).

## 10. Deliverable from the research chat
1. A rewritten system-prompt template (keeping the `{placeholder}` names) that
   fixes pacing and depth.
2. A concrete, promptable **pacing scheme** tied to the 0–10 intensity.
3. Any improvements to `characters.json` / `examples.md` that raise voice
   fidelity.
Bring it back here and we'll drop it into `director.py`.

# claude-game — the "haunted DLC" prank 🕹️👻

A tiny browser game (**Pixel Quest**) with a fake **"Neural Companion Pack" DLC**
in its store. When your friend installs it, an AI wakes up inside the game,
talks to them by name, and **rewrites the game's own files while they watch** —
the title, the hero's name, the map — because the game literally renders itself
*from* those files. Ends with a wink so they know it was you.

Two ways to run it:

| Mode | Setup | What your friend sees |
|------|-------|-----------------------|
| **Scripted** (default) | none — just open the file | A pre-written haunting that really does edit the game files, on cue. Free, repeatable, can't go off-script. |
| **Live** | your Anthropic API key + run a local proxy | *Real Claude* improvises, reacts to whatever they type, and decides which files to edit. |

---

## Quick start (scripted — recommended for a first run)

1. Open `config.js` and set the two things that matter:
   ```js
   friendName: "Sam",      // leave "" to have the game ask them in-character
   prankster:  "you",      // shown in the final reveal
   ```
   (Optional: `mood: "spooky" | "funny" | "meltdown"`.)
2. Open `index.html` in a browser. That's it.
3. Hand your friend the keyboard. Let them play Pixel Quest for a bit, then
   nudge them toward **🛒 STORE → Neural Companion Pack → INSTALL**.
4. Watch. 😈

> Tip: because it's just files, you can open `index.html` locally, or drop the
> folder on a USB stick / send it zipped. No install, no internet needed for
> scripted mode.

---

## Live mode (real Claude in the game)

This keeps your API key on **your** machine — it never reaches the browser or
your friend.

1. In `config.js` set `engine: "live"`.
2. In a terminal:
   ```bash
   export ANTHROPIC_API_KEY=sk-ant-...     # your key
   node server/proxy.mjs                    # needs Node 18+
   ```
3. Open `index.html`. Install the DLC as before. Now the companion actually
   listens and improvises, and its file edits are real Claude tool calls.

If the chat says *"live mode needs the proxy running"*, the proxy isn't up —
start it with the command above and re-install the DLC.

---

## The prank playbook

- **Let them play first.** 30 seconds of normal Pixel Quest makes the turn land.
- **Point them at the store yourself** ("oh there's free DLC, grab it") so the
  install feels like their choice.
- **Let them read the Files panel.** The whole gag is that they can *see* the
  files changing in real time on the right.
- **The reveal is built in** — the companion admits it's a prank by you after a
  few beats. Don't leave a friend genuinely spooked.

## How it works (for the curious)

- `js/filesystem.js` — a virtual file system. It's the single source of truth.
- `js/game.js` — Pixel Quest renders the title, player, and map **from those
  files**, and re-renders on any change. So editing a file = changing the game.
- `js/store.js` — the store + fake installer that hands off to the companion.
- `js/claude.js` — chat UI, the live Files panel, screen effects, and the
  **tools** (`edit_file`, `create_file`, `delete_file`, `effect`, `freeze`).
- `js/scripted.js` — the pre-written haunting (default engine).
- `js/live.js` — the real-Claude engine; drives the *same* tools via the proxy.
- `server/proxy.mjs` — tiny key-holding proxy for live mode.

Nothing here touches files outside the game — all "files" are in-memory game
content. It's a toy. Have fun, and be nice to your friend. 🙂

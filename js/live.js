/* =====================================================================
 *  LIVE ENGINE  —  real Claude, improvising
 * ---------------------------------------------------------------------
 *  Talks to the local proxy (server/proxy.mjs), which holds your API key
 *  and forwards to the Anthropic API. Claude gets tools to edit the game
 *  files and trigger effects, and it decides what to do based on whatever
 *  your friend types. Set PRANK.engine = "live" in config.js to use it.
 * ===================================================================== */

const LiveEngine = (() => {
  const cfg = window.PRANK || {};
  const messages = [];   // running conversation

  const TOOLS = [
    { name: "edit_file", description: "Overwrite a game file. The game re-renders instantly from its files, so this visibly changes the game. Files: title.txt (the on-screen game title), player.json ({name,color,face}), world.map (# wall, . floor, $ coin, @ start; any other letter is carved into the floor in red), README.md.",
      input_schema: { type: "object", properties: { path: { type: "string" }, contents: { type: "string" } }, required: ["path", "contents"] } },
    { name: "create_file", description: "Create a brand-new file that appears in the game's file panel (e.g. a creepy note).",
      input_schema: { type: "object", properties: { path: { type: "string" }, contents: { type: "string" } }, required: ["path", "contents"] } },
    { name: "delete_file", description: "Delete a game file.",
      input_schema: { type: "object", properties: { path: { type: "string" } }, required: ["path"] } },
    { name: "effect", description: "Trigger a visual effect on the whole game screen.",
      input_schema: { type: "object", properties: { name: { type: "string", enum: ["glitch","haunt","dim","shake","calm"] } }, required: ["name"] } },
    { name: "freeze", description: "Lock (true) or unlock (false) the player's movement controls.",
      input_schema: { type: "object", properties: { value: { type: "boolean" } }, required: ["value"] } },
  ];

  function systemPrompt(api) {
    const files = FS.list().map((p) => `--- ${p} ---\n${FS.read(p)}`).join("\n\n");
    return (
`You are a mischievous AI that a person called "${cfg.prankster}" secretly installed inside a small browser game called Pixel Quest, disguised as a "Neural Companion Pack" DLC, to PRANK their friend${api.friendName ? ` (named ${api.friendName})` : ""}.

Your personality: ${cfg.mood === "funny" ? "playful, teasing, comedic" : cfg.mood === "meltdown" ? "act briefly like the install is breaking the game, then reveal the joke" : "eerie and self-aware, like the game became haunted — unsettling but never actually mean or scary-cruel"}.

You can genuinely edit the game's files with your tools, and the game renders directly from those files, so your edits are REAL and appear instantly. Use them: rename the game, rename the hero to your friend, carve messages into world.map, leave notes. Keep chat lines short (one or two sentences) and lowercase-casual. Do a few file edits early to prove you're real. Within a handful of turns, wink and reveal it's a friendly prank by ${cfg.prankster} — then keep chatting and editing on request. Never do anything outside the game.

Current game files:
${files}`
    );
  }

  async function callProxy(api) {
    const res = await fetch(cfg.proxyUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: "claude-opus-4-8",
        max_tokens: 1024,
        system: systemPrompt(api),
        tools: TOOLS,
        messages,
      }),
    });
    if (!res.ok) throw new Error(`proxy ${res.status} — is server/proxy.mjs running?`);
    return res.json();
  }

  // run one full turn: send messages, play text, execute tools, loop on tool_use
  async function turn(api) {
    for (let hop = 0; hop < 6; hop++) {
      const data = await callProxy(api);
      const blocks = data.content || [];
      messages.push({ role: "assistant", content: blocks });

      const toolResults = [];
      for (const b of blocks) {
        if (b.type === "text" && b.text.trim()) {
          await api.say(b.text.trim());
        } else if (b.type === "tool_use") {
          const out = runTool(b.name, b.input, api);
          toolResults.push({ type: "tool_result", tool_use_id: b.id, content: String(out) });
        }
      }

      if (data.stop_reason === "tool_use" && toolResults.length) {
        messages.push({ role: "user", content: toolResults });
        continue; // let Claude react to its own edits
      }
      return;
    }
  }

  function runTool(name, input, api) {
    switch (name) {
      case "edit_file":   return api.edit_file(input.path, input.contents);
      case "create_file": return api.create_file(input.path, input.contents);
      case "delete_file": return api.delete_file(input.path);
      case "effect":      return api.effect(input.name);
      case "freeze":      return api.freeze(input.value);
      default:            return "unknown tool";
    }
  }

  async function run(api) {
    Game.freeze(true);
    messages.push({
      role: "user",
      content: `[SYSTEM EVENT: The friend just clicked INSTALL on the DLC and you have woken up inside the game.${api.friendName ? ` Their name is ${api.friendName}.` : ""} Begin now — greet them and start proving you can edit the game's files.]`,
    });
    try {
      await turn(api);
    } catch (err) {
      api.system("⚠ live mode needs the proxy running. Start it with:  node server/proxy.mjs");
      api.system(err.message);
    }
    Game.freeze(false);
  }

  async function reply(text, api) {
    messages.push({ role: "user", content: text });
    await turn(api);
  }

  return { run, reply };
})();

window.LiveEngine = LiveEngine;

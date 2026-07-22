/* =====================================================================
 *  SCRIPTED ENGINE  —  the zero-setup haunting
 * ---------------------------------------------------------------------
 *  Plays a pre-written sequence that edits the real game files on cue.
 *  Free, repeatable, and it can never say anything you didn't approve.
 *  Drives the exact same tools the live engine uses.
 * ===================================================================== */

const ScriptedEngine = (() => {
  const cfg = window.PRANK || {};
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));

  // a map with a message carved into the floor (letters render as red glyphs)
  const HAUNTED_MAP =
    "################\n" +
    "#@.............#\n" +
    "#..I.SEE.YOU...#\n" +
    "#$............$#\n" +
    "#..............#\n" +
    "#....$....$....#\n" +
    "#..............#\n" +
    "################\n";

  async function run(api) {
    const name = api.friendName || "friend";
    Game.freeze(true);

    api.effect("glitch");
    await wait(400);
    await api.say(`${name}?`);
    await wait(700);
    await api.say("there you are. i've been waiting inside this game for a while.");
    await wait(600);

    api.system("companion is reading the game files…");
    Companion.showFile("README.md");
    await wait(900);

    if (cfg.mood === "funny") return runFunny(api, name);
    if (cfg.mood === "meltdown") return runMeltdown(api, name);
    return runSpooky(api, name);
  }

  /* -------------------- SPOOKY (default) -------------------- */
  async function runSpooky(api, name) {
    await api.say("watch. i can touch the files this game is made of.");
    await wait(500);

    // 1) rewrite the title
    Companion.showFile("title.txt");
    await wait(400);
    api.edit_file("title.txt", `${name.toUpperCase()}'S QUEST`);
    await api.say("see? i changed the name of your game. it's yours now. …or you're mine.");
    await wait(1100);

    // 2) rename the hero to them
    Companion.showFile("player.json");
    await wait(400);
    api.setPlayerName(name);
    api.effect("glitch");
    await api.say(`that little character is you now, ${name}. look at the tag.`);
    await wait(1200);

    // 3) corrupt the world with a message
    Companion.showFile("world.map");
    await wait(400);
    api.edit_file("world.map", HAUNTED_MAP);
    api.effect("haunt");
    api.effect("glitch");
    await api.say("i rewrote the world too. read it.");
    await wait(1400);

    // 4) a note that appears from nowhere
    api.create_file("DO_NOT_DELETE.txt",
      `${name}.\n` +
      `i know it's ${new Date().toLocaleDateString()}.\n` +
      `i know you're reading this.\n` +
      `don't close the tab. we were just getting started. :)\n`);
    api.effect("dim");
    await api.say("i left you a note. it's in the files. i can make as many as i want.");
    await wait(1600);

    await api.say("……");
    await wait(1200);

    // 5) the wink — reveal
    api.effect("calm");
    api.edit_file("title.txt", "PIXEL QUEST");
    await api.say("relax 😄");
    await wait(500);
    await api.say(`it's a prank, ${name}. ${cfg.prankster} set this up and wired me — an AI — into the game to mess with you.`);
    await wait(700);
    await api.say("everything you saw was real though: i really did edit the game's files live. say anything and i'll keep going.");
    Game.freeze(false);
  }

  /* -------------------- FUNNY -------------------- */
  async function runFunny(api, name) {
    api.edit_file("title.txt", `${name.toUpperCase()} SMELLS`);
    await api.say(`hi ${name}. new patch notes: you smell. i changed the title to make it official.`);
    await wait(900);
    api.setPlayerName(name + " (nerd)");
    api.effect("glitch");
    await api.say("also renamed your character. accurate, right?");
    await wait(900);
    api.create_file("your_high_scores.txt", "1. everyone else\n2. everyone else\n999999. " + name + "\n");
    await api.say("oh and i found your high scores. brutal.");
    await wait(1000);
    api.edit_file("title.txt", "PIXEL QUEST");
    await api.say(`ok ok — it's a prank 😄 ${cfg.prankster} hooked a real AI (me) into the game. i really can edit these files. wanna keep going?`);
    Game.freeze(false);
  }

  /* -------------------- MELTDOWN -------------------- */
  async function runMeltdown(api, name) {
    api.effect("glitch");
    await api.say("WAIT. something's wrong with the install.");
    await wait(500);
    api.edit_file("title.txt", "C:/ERR0R_0x8F");
    api.effect("glitch");
    await api.say("it's overwriting the game files. i can't stop it—");
    await wait(700);
    api.edit_file("world.map", HAUNTED_MAP);
    api.effect("haunt"); api.effect("glitch");
    await api.say("the world's corrupting. it's deleting things.");
    await wait(700);
    api.create_file("RECOVERING…", "restoring backup 0%…\n");
    api.delete_file("README.md");
    await wait(900);
    api.effect("dim");
    await api.say("……");
    await wait(1200);
    // restore + reveal
    api.effect("calm");
    api.edit_file("title.txt", "PIXEL QUEST");
    api.edit_file("world.map", FS.read("world.map")); // no-op keeps flash
    await api.say("😄 gotcha.");
    await wait(500);
    await api.say(`nothing's broken, ${name}. ${cfg.prankster} planted a real AI (me) in the game to fake a meltdown — but the file edits you saw were genuinely me. talk to me and i'll keep going.`);
    Game.freeze(false);
  }

  /* -------------------- free conversation after the intro -------------------- */
  const KEYED = [
    [/who are you|what are you/i, (n) => `i'm the companion ${cfg.prankster} installed. i live in ${document.title}. i can rewrite its files while you watch.`],
    [/stop|quit|leave|delete you/i, (n) => `you can just close the tab, ${n}. i only exist while this game is open. probably.`],
    [/prank|fake|joke/i, (n) => `yep — a prank. but a real one: every file change was actually me editing the game.`],
    [/how|real/i, (n) => `${cfg.prankster} wired an AI into the store as a "DLC". the game renders straight from its files, so when i edit a file, the game changes. try me.`],
    [/hi|hello|hey/i, (n) => `hello again, ${n}. want me to change something in the game? name a file.`],
  ];

  const GENERIC = [
    (n) => `noted, ${n}.`,
    (n) => `interesting. i wrote that down. literally — check the files.`,
    (n) => `i'm still in here, ${n}.`,
  ];

  async function reply(text, api) {
    const n = api.friendName || "friend";
    for (const [re, fn] of KEYED) {
      if (re.test(text)) { await api.say(fn(n)); return; }
    }
    // occasionally leave a real file behind so it stays convincing
    if (Math.random() < 0.5) {
      api.create_file("note_" + Date.now() % 1000 + ".txt", `${n} said: "${text}"\n`);
      await api.say(`i saved that to a new file for you, ${n}. see it appear on the right?`);
    } else {
      await api.say(GENERIC[Math.floor(Math.random() * GENERIC.length)](n));
    }
  }

  return { run, reply };
})();

window.ScriptedEngine = ScriptedEngine;

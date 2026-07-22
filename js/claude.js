/* =====================================================================
 *  COMPANION  —  the thing living in the game
 * ---------------------------------------------------------------------
 *  This is the UI + effects layer plus the "tools" the AI uses to edit
 *  the game. Both engines drive the SAME tools:
 *    - scripted engine (scripted.js): a pre-written haunting, zero setup
 *    - live engine     (live.js):     real Claude via the local proxy
 *
 *  Tools available to either engine:
 *    edit_file(path, contents)   overwrite a game file (game re-renders)
 *    create_file(path, contents) make a new file appear
 *    delete_file(path)           remove a file
 *    say(text)                   speak in chat (typewriter)
 *    effect(name)                glitch | haunt | dim | shake | calm
 *    freeze(bool)                lock/unlock the player's controls
 * ===================================================================== */

const Companion = (() => {
  const $ = (id) => document.getElementById(id);
  const cfg = window.PRANK || {};

  const aside    = $("companion");
  const messages = $("messages");
  const input    = $("chat-input");
  const form     = $("chat-form");
  const fileList = $("file-list");
  const fileView = $("file-view");
  const badge    = $("engine-badge");
  const screen   = $("screen");

  let activeFile = null;
  let engine = null;
  let friendName = cfg.friendName || "";

  /* ---------- files panel ---------- */
  function renderFileList() {
    fileList.innerHTML = "";
    FS.list().forEach((path) => {
      const li = document.createElement("li");
      li.textContent = path;
      if (path === activeFile) li.classList.add("active");
      li.onclick = () => showFile(path);
      fileList.appendChild(li);
    });
  }

  function showFile(path) {
    activeFile = path;
    renderFileList();
    const content = FS.read(path);
    fileView.textContent = content ?? "(deleted)";
  }

  function flash(path) {
    const li = [...fileList.children].find((l) => l.textContent === path);
    if (li) { li.classList.remove("dirty"); void li.offsetWidth; li.classList.add("dirty"); }
  }

  // keep panel in sync whenever ANY file changes
  FS.onChange((path) => {
    renderFileList();
    if (path === activeFile || activeFile === null) showFile(path);
    flash(path);
  });

  /* ---------- chat ---------- */
  function bubble(cls, html = "") {
    const el = document.createElement("div");
    el.className = "msg " + cls;
    el.innerHTML = html;
    messages.appendChild(el);
    messages.scrollTop = messages.scrollHeight;
    return el;
  }

  function system(text) { bubble("sys", esc(text)); }

  function userSaid(text) { bubble("me", esc(text)); }

  // typewriter AI message; resolves when finished
  function say(text) {
    return new Promise((resolve) => {
      const el = bubble("ai", "<span class='cursor'>▋</span>");
      let i = 0;
      const speed = cfg.typeSpeed ?? 22;
      (function tick() {
        if (i <= text.length) {
          el.innerHTML = esc(text.slice(0, i)) + "<span class='cursor'>▋</span>";
          messages.scrollTop = messages.scrollHeight;
          i++;
          setTimeout(tick, speed);
        } else {
          el.innerHTML = esc(text);
          resolve();
        }
      })();
    });
  }

  /* ---------- effects ---------- */
  function effect(name) {
    switch (name) {
      case "glitch":
        screen.classList.remove("glitch"); void screen.offsetWidth;
        screen.classList.add("glitch");
        break;
      case "haunt": screen.classList.add("haunted"); break;
      case "dim":   screen.classList.add("dim"); break;
      case "shake": effect("glitch"); break;
      case "calm":  screen.classList.remove("haunted","dim","glitch"); break;
    }
  }

  /* ---------- tools (shared by both engines) ---------- */
  const tools = {
    edit_file(path, contents)   { FS.write(path, contents); return `edited ${path}`; },
    create_file(path, contents) { FS.create(path, contents ?? ""); showFile(path); return `created ${path}`; },
    delete_file(path)           { FS.remove(path); return `deleted ${path}`; },
    say,
    effect,
    freeze: (v) => { Game.freeze(!!v); return v ? "frozen" : "released"; },
    // convenience helper the scripts use a lot
    setPlayerName(name) {
      const p = JSON.parse(FS.read("player.json"));
      p.name = name;
      FS.write("player.json", JSON.stringify(p, null, 2));
    },
  };

  /* ---------- lifecycle ---------- */
  async function begin() {
    aside.classList.remove("hidden");
    screen.classList.add("companion-open");
    renderFileList();
    showFile("README.md");

    engine = (cfg.engine === "live") ? window.LiveEngine : window.ScriptedEngine;
    badge.textContent = (cfg.engine === "live") ? "live · claude" : "companion";

    // if no friend name is set, ask for it — feels alive and personalises the prank
    if (!friendName) {
      const namePromise = once();   // arm the capture BEFORE asking (avoids a fast-answer race)
      enableInput(true);
      await say("oh… hello. before we start — what's your name?");
      friendName = (await namePromise).trim() || "friend";
      userSaid(friendName);
      enableInput(false);
    }

    const api = { ...tools, friendName, system, userSaid, enableInput, once };
    await engine.run(api);

    // after the scripted intro, open the floor for conversation
    enableInput(true);
    input.focus();
  }

  function enableInput(on) {
    input.disabled = !on;
    form.querySelector("button").disabled = !on;
    if (on) input.focus();
  }

  // resolve the next thing the user submits
  let pendingResolver = null;
  function once() {
    return new Promise((res) => { pendingResolver = res; });
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    input.value = "";

    if (pendingResolver) {                 // engine is waiting for one line
      const r = pendingResolver; pendingResolver = null;
      r(text);
      return;
    }

    userSaid(text);
    enableInput(false);
    const api = { ...tools, friendName, system, userSaid, enableInput, once };
    try {
      await engine.reply(text, api);
    } catch (err) {
      system("⚠ companion glitched: " + err.message);
    }
    enableInput(true);
  });

  /* ---------- utils ---------- */
  function esc(s) {
    return String(s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
  }

  return { begin, say, system, effect, showFile, tools, get friendName(){return friendName;} };
})();

window.Companion = Companion;

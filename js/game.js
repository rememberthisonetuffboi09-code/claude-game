/* =====================================================================
 *  PIXEL QUEST  —  the innocent little base game
 * ---------------------------------------------------------------------
 *  Reads everything (title, player, map) from the virtual FS and re-draws
 *  whenever a file changes. So the haunting doesn't "fake" anything: it
 *  edits files, and the real game reacts.
 * ===================================================================== */

const Game = (() => {
  const TILE = 30;
  const canvas = document.getElementById("game");
  const ctx = canvas.getContext("2d");
  const titleEl = document.getElementById("game-title");
  const scoreEl = document.getElementById("score");

  let map = [];          // 2D array of chars
  let player = { x: 1, y: 1, name: "Hero", color: "#ffd166", face: ":)" };
  let coins = new Set(); // "x,y"
  let collected = 0;
  let frozen = false;    // haunting can freeze player control

  function parsePlayer() {
    try {
      const p = JSON.parse(FS.read("player.json"));
      player.name = p.name ?? player.name;
      player.color = p.color ?? player.color;
      player.face = p.face ?? player.face;
    } catch (_) { /* corrupted json? leave last-known-good */ }
  }

  function parseMap() {
    const raw = (FS.read("world.map") || "").replace(/\n+$/,"");
    map = raw.split("\n").map((r) => r.split(""));
    coins.clear();
    for (let y = 0; y < map.length; y++) {
      for (let x = 0; x < map[y].length; x++) {
        const c = map[y][x];
        if (c === "@") { player.x = x; player.y = y; map[y][x] = "."; }
        if (c === "$") coins.add(x + "," + y);
      }
    }
    resize();
  }

  function resize() {
    const w = Math.max(...map.map((r) => r.length), 1);
    canvas.width = w * TILE;
    canvas.height = map.length * TILE;
  }

  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    for (let y = 0; y < map.length; y++) {
      for (let x = 0; x < (map[y] || []).length; x++) {
        const c = map[y][x];
        // floor / walls
        if (c === "#") {
          ctx.fillStyle = getVar("--wall", "#2a3160");
          ctx.fillRect(x * TILE, y * TILE, TILE, TILE);
          ctx.fillStyle = "rgba(255,255,255,.04)";
          ctx.fillRect(x * TILE, y * TILE, TILE, 3);
        } else {
          ctx.fillStyle = getVar("--floor", "#12162e");
          ctx.fillRect(x * TILE, y * TILE, TILE, TILE);
        }
        // coins
        if (coins.has(x + "," + y)) {
          ctx.fillStyle = "#ffd166";
          ctx.beginPath();
          ctx.arc(x * TILE + TILE/2, y * TILE + TILE/2, 6, 0, Math.PI*2);
          ctx.fill();
        }
        // any leftover printable char = "carved" glyph (used by haunting)
        if (c && !".#@$".includes(c)) {
          ctx.fillStyle = getVar("--haunt", "#ff3b6b");
          ctx.font = "bold 20px monospace";
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          ctx.fillText(c, x * TILE + TILE/2, y * TILE + TILE/2 + 1);
        }
      }
    }
    // player
    const px = player.x * TILE, py = player.y * TILE;
    ctx.fillStyle = player.color;
    roundRect(px + 4, py + 4, TILE - 8, TILE - 8, 6);
    ctx.fill();
    ctx.fillStyle = "#201700";
    ctx.font = "12px monospace";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(player.face, px + TILE/2, py + TILE/2 + 1);

    // name label drawn right on the canvas, above the player (always aligned)
    ctx.font = "10px monospace";
    const label = player.name;
    const w = ctx.measureText(label).width + 8;
    const lx = Math.min(Math.max(px + TILE/2 - w/2, 1), canvas.width - w - 1);
    const ly = Math.max(py - 14, 0);
    ctx.fillStyle = "rgba(0,0,0,.7)";
    ctx.fillRect(lx, ly, w, 12);
    ctx.fillStyle = "#fff";
    ctx.textBaseline = "middle";
    ctx.fillText(label, lx + w/2, ly + 6);
  }

  function roundRect(x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }

  function getVar(name, fallback) {
    const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return v || fallback;
  }

  function move(dx, dy) {
    if (frozen) return;
    const nx = player.x + dx, ny = player.y + dy;
    if (map[ny] && map[ny][nx] && map[ny][nx] !== "#") {
      player.x = nx; player.y = ny;
      const key = nx + "," + ny;
      if (coins.has(key)) {
        coins.delete(key);
        collected++;
        scoreEl.textContent = "★ " + collected;
        if (coins.size === 0) setTimeout(() => alert("You collected everything! 🎉"), 60);
      }
      draw();
    }
  }

  function onKey(e) {
    const k = e.key.toLowerCase();
    if (["arrowup","w"].includes(k)) { move(0,-1); e.preventDefault(); }
    else if (["arrowdown","s"].includes(k)) { move(0,1); e.preventDefault(); }
    else if (["arrowleft","a"].includes(k)) { move(-1,0); e.preventDefault(); }
    else if (["arrowright","d"].includes(k)) { move(1,0); e.preventDefault(); }
  }

  function sync(path) {
    titleEl.textContent = FS.read("title.txt");
    document.title = FS.read("title.txt") || "PIXEL QUEST";
    parsePlayer();
    if (path === "world.map" || path === undefined) parseMap();
    draw();
  }

  function init() {
    titleEl.textContent = FS.read("title.txt");
    parsePlayer();
    parseMap();
    draw();
    document.addEventListener("keydown", onKey);
    FS.onChange(sync);
  }

  return {
    init,
    freeze: (v) => { frozen = v; },
    redraw: draw,
    get player() { return player; },
  };
})();

document.addEventListener("DOMContentLoaded", Game.init);
window.Game = Game;

/* =====================================================================
 *  VIRTUAL FILE SYSTEM
 * ---------------------------------------------------------------------
 *  The whole game is rendered FROM these files. Change a file and the
 *  game changes on screen. That is the core of the prank: when the
 *  companion "edits the game's files", the player watches the game
 *  literally rewrite itself.
 * ===================================================================== */

const FS = (() => {
  const files = {
    "title.txt": "PIXEL QUEST",

    "player.json": JSON.stringify(
      { name: "Hero", color: "#ffd166", face: ":)" },
      null, 2
    ),

    // @ = start, # = wall, . = floor, $ = coin
    "world.map":
      "################\n" +
      "#@....#......$.#\n" +
      "#.###.#.####.#.#\n" +
      "#.#...#....#.#.#\n" +
      "#.#.#####.##.#.#\n" +
      "#...#...$....#.#\n" +
      "#.#####.#####.#\n" +
      "#..$..........#\n" +
      "################\n",

    "README.md":
      "Pixel Quest v1.0\n" +
      "----------------\n" +
      "Collect every coin to win.\n" +
      "A cozy little adventure. Nothing to worry about here. :)\n",
  };

  const listeners = new Set();

  function emit(path) {
    listeners.forEach((fn) => fn(path));
  }

  return {
    /** read a file's contents */
    read: (path) => files[path],

    /** list all file names */
    list: () => Object.keys(files),

    /** overwrite a file. This is what "Claude editing the game" calls. */
    write(path, contents) {
      files[path] = contents;
      emit(path);
      return contents;
    },

    /** create a brand-new file (e.g. a creepy note that appears from nowhere) */
    create(path, contents = "") {
      files[path] = contents;
      emit(path);
      return contents;
    },

    /** delete a file (e.g. pretend to nuke their save) */
    remove(path) {
      delete files[path];
      emit(path);
    },

    /** subscribe to any change; returns unsubscribe fn */
    onChange(fn) {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
  };
})();

window.FS = FS;

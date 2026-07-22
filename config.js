/* =====================================================================
 *  PRANK CONFIG  —  the only file you need to edit before pranking
 * =====================================================================
 *  Set your friend's name, pick the engine, and (optionally) tune the
 *  creepiness. Everything else works out of the box.
 * ===================================================================== */

window.PRANK = {
  // The victim's name. Claude will greet them by this. Leave "" to have it
  // ask for their name in-game instead (feels even more alive).
  friendName: "",

  // Who is doing the pranking? Shown in the final wink-reveal.
  prankster: "a friend",

  // ENGINE:
  //   "scripted" -> zero setup. A pre-written haunting plays out on cue.
  //                 Free, repeatable, and it can never go off-script.
  //   "live"     -> real Claude improvises replies and decides which files
  //                 to edit. Needs the local proxy running (see README).
  engine: "scripted",

  // For "live" mode only: where the local proxy is listening.
  proxyUrl: "http://localhost:8787/claude",

  // Typing speed for Claude's messages (ms per character). Lower = faster.
  typeSpeed: 22,

  // How aggressive the haunting feels: "spooky" | "funny" | "meltdown"
  mood: "spooky",
};

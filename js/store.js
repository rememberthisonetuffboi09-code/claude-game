/* =====================================================================
 *  STORE + INSTALLER
 *  The bait. A normal-looking store with one very special "DLC".
 * ===================================================================== */

(function () {
  const $ = (id) => document.getElementById(id);

  const storeBtn   = $("store-btn");
  const store      = $("store");
  const installBtn = $("install-dlc");
  const installer  = $("installer");
  const barFill    = $("bar-fill");
  const stepEl     = $("install-step");

  // open / close store
  storeBtn.addEventListener("click", () => store.classList.remove("hidden"));
  document.querySelectorAll(".close").forEach((b) =>
    b.addEventListener("click", () =>
      $(b.dataset.close).classList.add("hidden")
    )
  );

  // fake install steps — the last few lines plant the seed of dread
  const STEPS = [
    ["Connecting to content server…", 12],
    ["Downloading neural weights (2.4 GB)…", 46],
    ["Verifying checksums…", 60],
    ["Integrating with game engine…", 74],
    ["Requesting file-system access…", 86],
    ["Granting write access to /game/*…", 96],
    ["Waking companion…", 100],
  ];

  installBtn.addEventListener("click", async () => {
    store.classList.add("hidden");
    installer.classList.remove("hidden");
    barFill.style.width = "0%";

    for (const [label, pct] of STEPS) {
      stepEl.textContent = label;
      barFill.style.width = pct + "%";
      await wait(600 + Math.random() * 500);
    }
    await wait(500);
    installer.classList.add("hidden");

    // hand off to the companion — the haunting begins
    Companion.begin();
  });

  function wait(ms) { return new Promise((r) => setTimeout(r, ms)); }
})();

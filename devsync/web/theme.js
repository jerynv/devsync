// Runs before first paint so the chosen theme never flashes. "system" follows the OS.
"use strict";
(function () {
  var pref = "system";
  try { pref = localStorage.getItem("devsync-theme") || "system"; } catch (_) { /* storage blocked */ }
  var dark = pref === "dark" || (pref === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.classList.toggle("dark", dark);
})();

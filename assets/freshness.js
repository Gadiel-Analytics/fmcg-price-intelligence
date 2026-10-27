/* Runs independently of D3 so an old data file never looks like a current quote. */
(function (root) {
  "use strict";
  function state(date, threshold, now) {
    const stamp = Date.parse(date + "T00:00:00Z");
    const age = Math.floor(now / 86400000) - Math.floor(stamp / 86400000);
    return { age, stale: !Number.isFinite(age) || age > threshold || age < 0 };
  }
  function refresh() {
    const el = document.getElementById("data-status");
    if (!el) return;
    if (el.dataset.loadError === "true") return;
    const s = state(el.dataset.date, Number(el.dataset.staleAfter || 2), Date.now());
    const gaps = Number(el.dataset.gaps || 0);
    el.classList.toggle("overdue", s.stale);
    el.textContent = (s.stale ? "Data update overdue. " : "") +
      "Latest observation: " + el.dataset.date + ". " +
      (gaps ? gaps + " collection days missing from the history; no prices have been filled in." :
        "Prices are observations from the latest successful collection.");
  }
  if (typeof module !== "undefined") module.exports = { state };
  if (typeof document !== "undefined") {
    root.updateDataStatus = refresh;
    refresh();
    setInterval(refresh, 60000);
  }
})(typeof window === "undefined" ? globalThis : window);

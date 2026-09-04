/* VisionTrack — shared site behaviour: theme toggle + active nav link.
   Kept tiny and dependency-free; loaded with `defer` on every page. */
(function () {
  var root = document.documentElement;
  var KEY = "vt-theme";

  function systemDark() {
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  }
  function current() {
    return root.getAttribute("data-theme") || (systemDark() ? "dark" : "light");
  }
  function apply(theme) {
    root.setAttribute("data-theme", theme);
    try { localStorage.setItem(KEY, theme); } catch (e) {}
    var btn = document.querySelector(".theme-btn");
    if (btn) {
      var dark = theme === "dark";
      btn.textContent = dark ? "◑ dark" : "◐ light";
      btn.setAttribute("aria-label", "Switch to " + (dark ? "light" : "dark") + " theme");
    }
  }

  // explicit ?theme=dark|light overrides everything (deep-link / QA), no persist
  var forced = null;
  try {
    var p = new URLSearchParams(location.search).get("theme");
    if (p === "dark" || p === "light") { forced = p; root.setAttribute("data-theme", p); }
  } catch (e) {}

  // otherwise restore saved preference (before paint where possible)
  if (!forced) {
    try {
      var saved = localStorage.getItem(KEY);
      if (saved === "dark" || saved === "light") root.setAttribute("data-theme", saved);
    } catch (e) {}
  }

  function init() {
    // sync the toggle label to whatever is active
    var btn = document.querySelector(".theme-btn");
    if (btn) {
      apply(current());
      btn.addEventListener("click", function () {
        apply(current() === "dark" ? "light" : "dark");
      });
    }
    // mark the current section in the nav
    var path = location.pathname.replace(/\/+$/, "") || "/";
    document.querySelectorAll(".nav-links a, .dataset-tabs a").forEach(function (a) {
      var href = (a.getAttribute("href") || "").replace(/\/+$/, "") || "/";
      if (href === path) a.setAttribute("aria-current", "page");
    });

    reveal();
  }

  // Restrained scroll-reveal: fade groups up as they enter. Opt-in via the
  // js-reveal class so no-JS / reduced-motion users see everything immediately.
  function reveal() {
    var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce || !("IntersectionObserver" in window)) return;
    root.classList.add("js-reveal");
    var sel = ".sec-intro, .uses > *, .cards > *, .facts > *, .understory," +
              " .lane > .steps > li, .glossary > *, .stats > *";
    var targets = Array.prototype.slice.call(document.querySelectorAll(sel));
    if (!targets.length) return;
    targets.forEach(function (el) {
      el.classList.add("rv");
      // stagger within a group of siblings for an orchestrated feel
      var i = 0, p = el.previousElementSibling;
      while (p) { if (p.classList && p.classList.contains("rv")) i++; p = p.previousElementSibling; }
      el.style.transitionDelay = Math.min(i, 6) * 55 + "ms";
    });
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); }
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.08 });
    targets.forEach(function (el) { io.observe(el); });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

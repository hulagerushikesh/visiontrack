/* VisionTrack — shared standalone-page shell and active navigation.
   Kept tiny and dependency-free; loaded with `defer` on every page. */
(function () {
  var root = document.documentElement;
  root.setAttribute("data-theme", "light");

  // Keep the favicon and install metadata consistent on standalone legacy pages.
  if (!document.querySelector('link[rel="icon"]')) {
    var icon = document.createElement("link");
    icon.rel = "icon"; icon.href = "/assets/favicon.ico?v=2";
    document.head.appendChild(icon);
  }

  function init() {
    // Replace the pre-rendered legacy navigation with the shared product IA.
    var links = document.querySelector(".nav-links");
    if (links) {
      links.innerHTML = [
        ["Live tracker", "/live"],
        ["Learn", "/teaching"],
        ["Research", "/writeup"],
        ["Results", "/benchmark"],
        ["Docs", "/docs/"]
      ].map(function (item) {
        return '<a href="' + item[1] + '">' + item[0] + '</a>';
      }).join("");
    }
    var btn = document.querySelector(".theme-btn");
    if (btn) btn.remove();
    var brand = document.querySelector(".brand");
    if (brand) brand.innerHTML = '<img src="/assets/visiontrack-mark.svg" alt=""><span>VisionTrack</span>';
    var tag = document.querySelector(".nav-tag");
    if (tag) {
      tag.textContent = "Open research";
      tag.setAttribute("role", "link");
      tag.setAttribute("tabindex", "0");
      tag.addEventListener("click", function () { location.href = "/writeup"; });
      tag.addEventListener("keydown", function (event) {
        if (event.key === "Enter" || event.key === " ") location.href = "/writeup";
      });
    }
    // mark the current section in the nav
    var path = location.pathname.replace(/\/+$/, "") || "/";
    document.querySelectorAll(".nav-links a, .dataset-tabs a").forEach(function (a) {
      var href = (a.getAttribute("href") || "").replace(/\/+$/, "") || "/";
      if (href === path || (href === "/benchmark" && path.indexOf("/benchmark/") === 0)) {
        a.setAttribute("aria-current", "page");
      }
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

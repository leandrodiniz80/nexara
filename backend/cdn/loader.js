(function () {
  if (window.__NEXARA_LOADER__) return;
  window.__NEXARA_LOADER__ = true;

  // The script executes in the embedding page's origin (e.g. "cliente.com"),
  // never in Nexara's own origin — a relative fetch URL would resolve
  // against the CUSTOMER's server, not the Nexara API, and 404 there. The
  // API origin must be explicit: an integrator can override it with
  // data-api="https://api.nexara.com" on the script tag; otherwise it falls
  // back to the default Nexara API host.
  var scriptTag = document.currentScript;
  var API_BASE =
    (scriptTag && scriptTag.getAttribute("data-api")) || "https://api.nexara.com";
  // Host-header-resolved endpoint (Sprint 233/236) — the only branding
  // endpoint that maps an arbitrary embedding domain to its organization.
  // "/branding/public" resolves tenant from a Bearer session token instead,
  // which an anonymous visitor on a client's own domain never carries — it
  // would always fall back to the default Nexara theme.
  var API = API_BASE + "/api/v1/branding/domain";
  var CACHE_KEY = "nexara_theme";
  var CACHE_TTL = 60 * 60 * 1000; // 1h

  function applyTheme(data) {
    if (!data) return;

    // Colors/typography/layout are deliberately NOT re-applied as individual
    // CSS custom properties here: the linked stylesheet below (css_url)
    // already carries the exact same values, generated server-side by
    // BrandingService.to_css() with the real, dash-cased variable names
    // (e.g. --color-primary-bg). Re-deriving them client-side from the raw
    // snake_case field names would just be a second, easily-drifting source
    // of truth for variables that don't even match the real ones.
    if (data.css_url) {
      var link = document.querySelector("[data-nexara-css]");
      if (!link) {
        link = document.createElement("link");
        link.rel = "stylesheet";
        link.setAttribute("data-nexara-css", "true");
        document.head.appendChild(link);
      }
      if (link.getAttribute("href") !== data.css_url) {
        link.setAttribute("href", data.css_url);
      }
    }

    if (data.logo_url) {
      var img = document.querySelector("[data-nexara-logo]");
      if (!img) {
        img = document.createElement("img");
        img.setAttribute("data-nexara-logo", "true");
        img.style.maxHeight = "40px";
        document.body.prepend(img);
      }
      if (img.getAttribute("src") !== data.logo_url) {
        img.setAttribute("src", data.logo_url);
      }
    }
  }

  function loadFromCache() {
    try {
      var raw = localStorage.getItem(CACHE_KEY);
      if (!raw) return null;

      var parsed = JSON.parse(raw);
      if (Date.now() - parsed.time > CACHE_TTL) return null;

      return parsed.data;
    } catch (e) {
      return null;
    }
  }

  function saveCache(data) {
    try {
      localStorage.setItem(CACHE_KEY, JSON.stringify({ time: Date.now(), data: data }));
    } catch (e) {
      // Storage disabled/full — caching is an optimization, not a
      // requirement, so failing silently is correct here.
    }
  }

  function fetchTheme() {
    fetch(API, { credentials: "omit" })
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        // "/branding/domain" is deliberately NOT wrapped in an envelope
        // (no "data" key) — unlike the authenticated, internal endpoints.
        if (!data || !data.css_url) return;

        saveCache(data);
        applyTheme(data);
      })
      .catch(function () {
        // Network/API failure: the page keeps whatever it already rendered
        // (default styling, or the last cached theme applied above) —
        // never blocks or breaks the host page.
      });
  }

  function init() {
    var cached = loadFromCache();
    if (cached) {
      applyTheme(cached);
    }

    fetchTheme();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

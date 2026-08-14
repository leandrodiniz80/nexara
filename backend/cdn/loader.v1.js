(function () {
  var script = document.currentScript;

  var API_BASE = (script && script.dataset.api) || "https://api.nexara.com";
  var DEBUG = !!script && script.dataset.debug === "true";

  var CACHE_KEY = "nexara_theme_cache_v1";
  var CACHE_TTL = 5 * 60 * 1000; // 5 minutos

  var TIMEOUT = 2500;
  var RETRIES = 2;

  var METRICS_PATH = "/api/v1/cdn/metrics";

  function log() {
    if (DEBUG) {
      console.log.apply(console, ["[NEXARA]"].concat(Array.prototype.slice.call(arguments)));
    }
  }

  function loadFromCache() {
    try {
      var raw = localStorage.getItem(CACHE_KEY);
      if (!raw) return null;

      var parsed = JSON.parse(raw);
      if (Date.now() - parsed.timestamp > CACHE_TTL) {
        localStorage.removeItem(CACHE_KEY);
        return null;
      }

      log("Cache hit");
      return parsed.data;
    } catch (e) {
      return null;
    }
  }

  function saveToCache(data) {
    try {
      localStorage.setItem(CACHE_KEY, JSON.stringify({ data: data, timestamp: Date.now() }));
    } catch (e) {
      // Storage disabled/full — caching is an optimization, not a
      // requirement, so failing silently is correct here.
    }
  }

  function sendMetric(payload) {
    try {
      payload.version = "v1";
      payload.domain = location.hostname;

      var body = JSON.stringify(payload);
      // Relative to the embedding page's own origin (e.g. "cliente.com"),
      // NOT to the Nexara API — same reasoning as API_BASE above: this must
      // be an absolute URL against the API host, or the beacon/fetch would
      // silently hit (or 404 on) the customer's own server instead.
      var url = API_BASE + METRICS_PATH;

      if (navigator.sendBeacon) {
        var blob = new Blob([body], { type: "application/json" });
        navigator.sendBeacon(url, blob);
      } else {
        fetch(url, {
          method: "POST",
          body: body,
          headers: { "Content-Type": "application/json" },
          keepalive: true,
          credentials: "omit",
        }).catch(function () {});
      }
    } catch (e) {
      // Telemetry must never break the loader itself.
    }
  }

  function applyTheme(data) {
    if (!data) return;

    if (data.css_url) {
      var link = document.querySelector('link[data-nexara="css"]');

      if (!link) {
        link = document.createElement("link");
        link.rel = "stylesheet";
        link.dataset.nexara = "css";
        document.head.appendChild(link);
      }

      // Compare the raw attribute, not the `.href` property: the browser
      // resolves `.href` to an absolute URL, while `data.css_url` is a
      // relative path — comparing those directly is (almost) always
      // unequal even when unchanged, forcing an unnecessary reload on
      // every fetch.
      if (link.getAttribute("href") !== data.css_url) {
        log("Updating CSS:", data.css_url);
        link.setAttribute("href", data.css_url);
      }
    }

    if (data.logo_url) {
      var img = document.querySelector('img[data-nexara="logo"]');

      if (!img) {
        img = document.createElement("img");
        img.dataset.nexara = "logo";
        img.style.maxHeight = "40px";
        document.body.prepend(img);
      }

      if (img.getAttribute("src") !== data.logo_url) {
        log("Updating logo:", data.logo_url);
        img.setAttribute("src", data.logo_url);
      }
    }
  }

  function sleep(ms) {
    return new Promise(function (resolve) {
      setTimeout(resolve, ms);
    });
  }

  function fetchWithTimeout(url, timeoutMs) {
    var controller = new AbortController();
    var timer = setTimeout(function () {
      controller.abort();
    }, timeoutMs);

    return fetch(url, { signal: controller.signal, credentials: "omit" }).then(
      function (res) {
        clearTimeout(timer);
        return res;
      },
      function (err) {
        clearTimeout(timer);
        throw err;
      }
    );
  }

  function attemptFetchTheme(attempt) {
    log("fetch attempt", attempt + 1);

    return fetchWithTimeout(API_BASE + "/api/v1/branding/domain", TIMEOUT)
      .then(function (res) {
        if (!res.ok) {
          throw new Error("HTTP " + res.status);
        }

        return res.json();
      })
      .then(function (data) {
        if (!data) {
          throw new Error("empty response");
        }

        return data;
      })
      .catch(function (err) {
        log("attempt failed", err);

        // Only backs off and retries if another attempt is actually coming
        // next — sleeping after the final failed attempt would just delay
        // giving up (and falling back to whatever's already on the page)
        // for no benefit.
        if (attempt >= RETRIES) {
          throw err;
        }

        return sleep(200 * (attempt + 1)).then(function () {
          return attemptFetchTheme(attempt + 1);
        });
      });
  }

  function fetchTheme() {
    return attemptFetchTheme(0).then(function (data) {
      saveToCache(data);
      return data;
    });
  }

  function init() {
    var cached = loadFromCache();

    if (cached) {
      log("using cache");
      try {
        applyTheme(cached);
      } catch (err) {
        log("failed to apply cached theme", err);
      }
    }

    var start = Date.now();

    fetchTheme()
      .then(function (fresh) {
        log("fresh theme loaded");
        sendMetric({ event: "success", duration: Date.now() - start });
        applyTheme(fresh);
      })
      .catch(function (err) {
        // Never blocks/breaks the host page: on total failure (API down,
        // every retry timed out, ...) the page just keeps whatever it
        // already had — default styling, or the cached theme applied above.
        log("loader failed", err);
        sendMetric({ event: "error", duration: Date.now() - start, error: String(err) });
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

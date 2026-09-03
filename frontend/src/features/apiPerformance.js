import axios from "axios";

const cache = new Map();
let prefetchScheduled = false;
let lastApiBase = null;
let workoutWarmTimer = null;

const RULES = [
  { test: /\/api\/analytics(?:\?|$)/, ttl: 90000 },
  { test: /\/api\/weekly-report(?:\?|$)/, ttl: 90000 },
  { test: /\/api\/nutrition\/plan(?:\?|$)/, ttl: 60000 },
  { test: /\/api\/nutrition\/adherence\//, ttl: 30000 },
  { test: /\/api\/nutrition\/weight(?:\?|$)/, ttl: 30000 },
];

function normalizedUrl(config) {
  const base = config.baseURL || window.location.origin;
  try {
    const u = new URL(config.url || "", base);
    const params = new URLSearchParams(config.params || {});
    params.sort();
    const qs = params.toString();
    return `${u.origin}${u.pathname}${qs ? `?${qs}` : u.search || ""}`;
  } catch {
    return `${config.url || ""}|${JSON.stringify(config.params || {})}`;
  }
}

function matchingRule(config) {
  if ((config.method || "get").toLowerCase() !== "get") return null;
  const url = normalizedUrl(config);
  return RULES.find(rule => rule.test.test(url)) || null;
}

function clearCache() {
  cache.clear();
}

axios.interceptors.request.use(config => {
  const method = (config.method || "get").toLowerCase();
  if (method !== "get") {
    clearCache();
    return config;
  }

  const rule = matchingRule(config);
  if (!rule) return config;

  const key = normalizedUrl(config);
  const entry = cache.get(key);
  if (!entry || Date.now() - entry.savedAt > rule.ttl) {
    if (entry) cache.delete(key);
    return config;
  }

  config.adapter = async () => ({
    data: entry.data,
    status: entry.status,
    statusText: entry.statusText,
    headers: entry.headers,
    config,
    request: null,
    __forgeCached: true,
  });
  return config;
});

axios.interceptors.response.use(response => {
  const rule = matchingRule(response.config || {});
  if (rule && response.status >= 200 && response.status < 300 && !response.__forgeCached) {
    cache.set(normalizedUrl(response.config), {
      data: response.data,
      status: response.status,
      statusText: response.statusText,
      headers: response.headers,
      savedAt: Date.now(),
    });
  }
  return response;
});

function onIdle(callback) {
  if (typeof window.requestIdleCallback === "function") {
    return window.requestIdleCallback(callback, { timeout: 2500 });
  }
  return window.setTimeout(callback, 900);
}

function warmHeavyScreens(apiBase, includeNutrition = true) {
  if (!apiBase || !localStorage.getItem("forge_token")) return;
  const requests = [
    axios.get(`${apiBase}/analytics`),
  ];
  // The full report is fetched by Analysis when opened; do not generate it on
  // every sign-in/workout completion while the user is using another screen.
  if (includeNutrition) requests.push(axios.get(`${apiBase}/nutrition/plan`));
  Promise.allSettled(requests);
}

export function scheduleForgePrefetch(apiBase) {
  lastApiBase = apiBase;
  if (prefetchScheduled || !localStorage.getItem("forge_token")) return;
  prefetchScheduled = true;

  onIdle(() => {
    window.setTimeout(() => {
      warmHeavyScreens(apiBase, true);
      window.setTimeout(() => { prefetchScheduled = false; }, 90000);
    }, 350);
  });
}

if (typeof window !== "undefined") {
  window.addEventListener("forge:workout-complete", () => {
    clearCache();
    window.clearTimeout(workoutWarmTimer);
    workoutWarmTimer = window.setTimeout(() => {
      onIdle(() => warmHeavyScreens(lastApiBase, false));
    }, 650);
  });
}

export function resetForgePerformanceCache() {
  clearCache();
  prefetchScheduled = false;
  lastApiBase = null;
  window.clearTimeout(workoutWarmTimer);
}

import { createContext, useContext, useEffect, useState, useCallback } from "react";
import axios from "axios";
import { scheduleForgePrefetch, resetForgePerformanceCache } from "./apiPerformance";

const API = `${process.env.REACT_APP_BACKEND_URL || ""}/api`;
const AuthContext = createContext(null);

// O Coach e alguns fluxos com streaming usam fetch (nao Axios). Centralizar a
// autenticacao aqui evita uma classe inteira de falhas 401 silenciosas. O token so e
// anexado ao backend FORGE; requisicoes para outros dominios nunca o recebem.
const originalFetch = window.fetch.bind(window);
const apiBase = new URL(API, window.location.origin);
window.fetch = (input, init = {}) => {
  const requestUrl = new URL(typeof input === "string" ? input : input.url, window.location.origin);
  const isForgeApi = requestUrl.origin === apiBase.origin &&
    requestUrl.pathname.startsWith(apiBase.pathname.replace(/\/$/, ""));
  if (!isForgeApi) return originalFetch(input, init);
  const isRequest = typeof Request !== "undefined" && input instanceof Request;
  const headers = new Headers(isRequest ? input.headers : undefined);
  new Headers(init.headers || {}).forEach((value, key) => headers.set(key, value));
  const token = localStorage.getItem("forge_token");
  if (token && !headers.has("Authorization")) headers.set("Authorization", `Bearer ${token}`);
  return originalFetch(input, { ...init, headers });
};

// Axios interceptor: attach Bearer + surface 401 as auth reset
axios.interceptors.request.use(cfg => {
  const t = localStorage.getItem("forge_token");
  if (t) cfg.headers.Authorization = `Bearer ${t}`;
  return cfg;
});

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);           // logged user object
  const [token, setToken] = useState(() => localStorage.getItem("forge_token") || null);
  const [ready, setReady] = useState(false);
  const [route, setRoute] = useState(() => window.location.pathname);

  useEffect(() => {
    const onPop = () => setRoute(window.location.pathname);
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const navigate = useCallback((path, replace = false) => {
    if (replace) window.history.replaceState({}, "", path);
    else window.history.pushState({}, "", path);
    setRoute(path);
  }, []);

  const loadMe = useCallback(async () => {
    if (!localStorage.getItem("forge_token")) { setUser(null); setReady(true); return; }
    try {
      const { data } = await axios.get(`${API}/auth/me`);
      setUser(data.user);
      scheduleForgePrefetch(API);
    } catch {
      resetForgePerformanceCache();
      localStorage.removeItem("forge_token");
      setToken(null);
      setUser(null);
    } finally { setReady(true); }
  }, []);

  useEffect(() => { loadMe(); }, [loadMe]);

  const signIn = useCallback((newToken, userObj) => {
    localStorage.setItem("forge_token", newToken);
    setToken(newToken);
    setUser(userObj);
    scheduleForgePrefetch(API);
  }, []);

  const signOut = useCallback(() => {
    resetForgePerformanceCache();
    localStorage.removeItem("forge_token");
    localStorage.removeItem("forge_profile_id");
    localStorage.removeItem("forge_onboarded");
    localStorage.removeItem("forge_assessment_complete");
    setToken(null);
    setUser(null);
    navigate("/login", true);
  }, [navigate]);

  return (
    <AuthContext.Provider value={{ user, token, ready, route, navigate, signIn, signOut, reload: loadMe }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
export { API };

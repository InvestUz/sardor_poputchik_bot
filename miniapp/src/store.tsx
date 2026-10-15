import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, ApiError } from "./api";
import { errorText, translate, type Lang } from "./i18n";
import { applyTheme, initialTheme, type Theme } from "./tg";
import type { Config, Loc, Me } from "./types";

type Ctx = {
  me: Me | null;
  config: Config | null;
  locations: Loc[];
  lang: Lang;
  loadError: string | null;
  t: (key: string, params?: Record<string, string | number>) => string;
  err: (e: unknown) => string;
  refreshMe: () => Promise<void>;
  setLang: (lang: Lang) => Promise<void>;
  theme: Theme;
  toggleTheme: () => void;
};

const AppContext = createContext<Ctx | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [config, setConfig] = useState<Config | null>(null);
  const [locations, setLocations] = useState<Loc[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const lang: Lang = me?.lang === "ru" ? "ru" : "uz";
  const [theme, setTheme] = useState<Theme>(initialTheme);
  const toggleTheme = useCallback(() => {
    setTheme((prev) => {
      const next = prev === "dark" ? "light" : "dark";
      applyTheme(next, true);
      return next;
    });
  }, []);
  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const refreshMe = useCallback(async () => {
    setMe(await api<Me>("/me"));
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const m = await api<Me>("/me");
        setMe(m);
        if (m.registered && !m.blocked) {
          const [c, l] = await Promise.all([api<Config>("/config"), api<Loc[]>("/locations")]);
          setConfig(c);
          setLocations(l);
        }
      } catch (e) {
        setLoadError(e instanceof ApiError ? e.code : "generic");
      }
    })();
  }, []);

  const value = useMemo<Ctx>(
    () => ({
      me,
      config,
      locations,
      lang,
      loadError,
      t: (key, params) => translate(lang, key, params),
      err: (e) => (e instanceof ApiError ? errorText(lang, e.code, e.params ?? {}) : errorText(lang, "generic")),
      refreshMe,
      setLang: async (l) => {
        await api("/me", { method: "PATCH", body: { lang: l } });
        await refreshMe();
      },
      theme,
      toggleTheme,
    }),
    [me, config, locations, lang, loadError, refreshMe, theme, toggleTheme],
  );
  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp(): Ctx {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("AppProvider missing");
  return ctx;
}

/** Loads data on mount / when deps change; exposes reload(). */
export function useLoad<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await fn());
    } catch (e) {
      setError(e);
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(() => {
    reload();
  }, [reload]);
  return { data, error, loading, reload, setData };
}

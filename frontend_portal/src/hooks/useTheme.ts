/**
 * useTheme — light/dark theme state with localStorage persistence.
 *
 * The theme class is also applied by an inline script in index.html before
 * React mounts (to prevent first-paint flash); this hook keeps that class in
 * sync with React state and writes the preference back to localStorage.
 *
 * Cross-tab sync via the native `storage` event so toggling in one tab
 * updates the others.
 */

import { useCallback, useEffect, useState } from "react";

export type Theme = "dark" | "light";

const STORAGE_KEY = "omnesvident.theme";

function readTheme(): Theme {
  try {
    const v = localStorage.getItem(STORAGE_KEY);
    if (v === "light" || v === "dark") return v;
  } catch {
    /* localStorage unavailable */
  }
  return "dark";
}

function applyTheme(theme: Theme): void {
  const root = document.documentElement;
  root.classList.remove("dark", "light");
  root.classList.add(theme);
}

export function useTheme() {
  const [theme, setThemeState] = useState<Theme>(readTheme);

  // Apply on mount (in case the inline script didn't run for some reason)
  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  // Cross-tab sync
  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === STORAGE_KEY) setThemeState(readTheme());
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  const setTheme = useCallback((next: Theme) => {
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* ignore */
    }
    applyTheme(next);
    setThemeState(next);
  }, []);

  const toggleTheme = useCallback(() => {
    setTheme(theme === "dark" ? "light" : "dark");
  }, [theme, setTheme]);

  return { theme, setTheme, toggleTheme };
}

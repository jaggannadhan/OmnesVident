/**
 * useAuth — tiny localStorage-backed auth state for the public-API web UI.
 *
 * We persist a slim "AuthUser" record (no API key, no password) so the user
 * can refresh the page or open new tabs and stay "logged in". Cross-tab sync
 * piggy-backs on the native `storage` event.
 *
 * The API key itself is shown ONCE at signup time and not re-derivable from
 * the server (we only keep its sha256 hash). Login confirms identity for the
 * UI; programmatic API calls still need the raw key the user saved.
 */

import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "omnesvident.auth";
const API_BASE =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "/api";

export interface AuthUser {
  user_id:        string;
  name:           string;
  email:          string;
  access_levels:  string[];
  api_key_prefix: string;
  rate_limit_per_min: number | null;
  /** Bearer token for user-action endpoints (e.g. regenerate-key).
   *  Issued at login/signup. May be undefined for older sessions. */
  session_token?: string;
}

/** True when the user's level set grants unlimited rate-limit. */
export function hasUnlimitedAccess(levels: string[] | undefined): boolean {
  if (!levels) return false;
  return levels.includes("super_user") || levels.includes("admin");
}

/** Pretty label for a single access level. */
export function accessLevelLabel(level: string): string {
  switch (level) {
    case "basic":      return "Basic";
    case "super_user": return "Super-user";
    case "admin":      return "Admin";
    case "premium":    return "Premium";
    default:           return level;
  }
}

function readAuth(): AuthUser | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as AuthUser;
    if (parsed && typeof parsed.email === "string") return parsed;
    return null;
  } catch {
    return null;
  }
}

function writeAuth(user: AuthUser | null): void {
  try {
    if (user) localStorage.setItem(STORAGE_KEY, JSON.stringify(user));
    else      localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* localStorage unavailable (private mode); silently ignore */
  }
}

export function initialsOf(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

export function useAuth() {
  const [user, setUser] = useState<AuthUser | null>(readAuth);

  // Cross-tab sync: when the user logs in/out in another tab, mirror it here.
  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === STORAGE_KEY) setUser(readAuth());
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  const login = useCallback(async (email: string, password: string): Promise<AuthUser> => {
    const res = await fetch(`${API_BASE}/v1/auth/login`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ email: email.trim().toLowerCase(), password }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data?.detail || `Login failed (${res.status}).`);
    const next: AuthUser = {
      user_id:            data.user_id,
      name:               data.name,
      email:              data.email,
      access_levels:      Array.isArray(data.access_levels) ? data.access_levels : ["basic"],
      api_key_prefix:     data.api_key_prefix,
      rate_limit_per_min: data.rate_limit_per_min ?? null,
      session_token:      data.session_token,
    };
    writeAuth(next);
    setUser(next);
    return next;
  }, []);

  const logout = useCallback(() => {
    writeAuth(null);
    setUser(null);
  }, []);

  // Used by the signup flow — once the user has been issued an API key, their
  // identity is also known, so we can lift them straight into the logged-in
  // state without a separate /login round-trip.
  const setAuthFromSignup = useCallback((u: AuthUser) => {
    writeAuth(u);
    setUser(u);
  }, []);

  /**
   * Mint a fresh API key for the currently-logged-in user, replacing the old
   * one server-side. Returns the raw key (shown only once) on success.
   * The session token authenticates the call, so no password re-prompt is
   * required.
   */
  const regenerateKey = useCallback(async (): Promise<string> => {
    if (!user) throw new Error("Not logged in.");
    if (!user.session_token) {
      throw new Error("Your session is too old. Log out and log back in to refresh it.");
    }
    const res = await fetch(`${API_BASE}/v1/auth/regenerate-key`, {
      method:  "POST",
      headers: {
        "Content-Type":  "application/json",
        "Authorization": `Bearer ${user.session_token}`,
      },
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data?.detail || `Could not regenerate key (${res.status}).`);
    // Refresh the local auth record with the new prefix
    const next: AuthUser = { ...user, api_key_prefix: data.api_key_prefix };
    writeAuth(next);
    setUser(next);
    return data.api_key as string;
  }, [user]);

  return { user, login, logout, setAuthFromSignup, regenerateKey };
}

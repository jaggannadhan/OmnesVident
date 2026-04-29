import { useEffect, useRef, useState } from "react";
import { accessLevelLabel, hasUnlimitedAccess, initialsOf, useAuth } from "../hooks/useAuth";
import { LoginModal } from "./LoginModal";
import { SignupModal } from "./SignupModal";

/**
 * AuthButton — when logged out, renders a "Log in" pill.
 *               when logged in, renders a circular avatar with the user's
 *               initials. Clicking the avatar opens a dropdown with the
 *               user's identity and a "Log out" action.
 *
 * The signup modal here doesn't surface the API key — the user is just
 * confirmed and lifted into a logged-in state. (The /api-docs page is where
 * keys are revealed; users who go through this lighter signup flow can grab
 * their key from there too if needed.)
 */
export function AuthButton() {
  const { user, logout } = useAuth();
  const [loginOpen,   setLoginOpen]   = useState(false);
  const [signupOpen,  setSignupOpen]  = useState(false);
  const [menuOpen,    setMenuOpen]    = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);

  // Close the avatar menu when clicking outside or pressing Escape
  useEffect(() => {
    if (!menuOpen) return;
    const onPointer = (e: PointerEvent) => {
      if (!wrapperRef.current?.contains(e.target as Node)) setMenuOpen(false);
    };
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setMenuOpen(false); };
    window.addEventListener("pointerdown", onPointer);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("pointerdown", onPointer);
      window.removeEventListener("keydown", onKey);
    };
  }, [menuOpen]);

  // ─── Logged out: single Log-in pill (signup is reachable via the modal) ────
  if (!user) {
    return (
      <>
        <button
          onClick={() => setLoginOpen(true)}
          className="text-[10px] font-semibold uppercase tracking-widest px-2.5 py-1 rounded-md border border-cyan-500/40 text-cyan-300 hover:text-cyan-200 hover:bg-cyan-400/10 transition-colors"
          aria-label="Log in"
        >
          Log in
        </button>

        <LoginModal
          open={loginOpen}
          onClose={() => setLoginOpen(false)}
          onSwitchToSignup={() => setSignupOpen(true)}
        />
        <SignupModal
          open={signupOpen}
          onClose={() => setSignupOpen(false)}
          onSwitchToLogin={() => setLoginOpen(true)}
          onSuccess={() => setSignupOpen(false)}
        />
      </>
    );
  }

  // ─── Logged in: avatar circle + dropdown ───────────────────────────────────
  const levels    = user.access_levels ?? ["basic"];
  const isAdmin   = levels.includes("admin");
  const unlimited = hasUnlimitedAccess(levels);

  // Pick a colour theme based on the highest tier the user holds
  const avatarTheme = isAdmin
    ? "bg-gradient-to-br from-rose-400 to-amber-500 text-slate-900 shadow-[0_0_10px_rgba(251,113,133,0.45)]"
    : levels.includes("super_user")
    ? "bg-gradient-to-br from-amber-400 to-orange-500 text-slate-900 shadow-[0_0_10px_rgba(251,191,36,0.45)]"
    : levels.includes("premium")
    ? "bg-gradient-to-br from-fuchsia-400 to-violet-500 text-slate-900 shadow-[0_0_10px_rgba(217,70,239,0.45)]"
    : "bg-gradient-to-br from-cyan-400 to-violet-500 text-slate-900 shadow-[0_0_10px_rgba(167,139,250,0.45)]";

  const tierColor = (lvl: string) =>
    lvl === "admin"      ? "text-rose-300 bg-rose-400/10 border-rose-400/30" :
    lvl === "super_user" ? "text-amber-300 bg-amber-400/10 border-amber-400/30" :
    lvl === "premium"    ? "text-fuchsia-300 bg-fuchsia-400/10 border-fuchsia-400/30" :
                           "text-cyan-300 bg-cyan-400/10 border-cyan-400/30";

  return (
    <div ref={wrapperRef} className="relative">
      <button
        onClick={() => setMenuOpen((p) => !p)}
        className={`flex items-center justify-center w-7 h-7 rounded-full text-[10px] font-bold uppercase tracking-wider transition-shadow ${avatarTheme}`}
        aria-haspopup="menu"
        aria-expanded={menuOpen}
        title={`${user.name} · ${levels.map(accessLevelLabel).join(", ")}`}
      >
        {initialsOf(user.name)}
      </button>

      {menuOpen && (
        <div
          role="menu"
          className="absolute right-0 top-full mt-2 z-50 w-60 rounded-lg border border-rim bg-base shadow-2xl shadow-black/40 overflow-hidden"
        >
          <div className="px-3 py-2.5 border-b border-rim">
            <p className="text-xs font-semibold text-slate-200 truncate">{user.name}</p>
            <p className="text-[10px] text-slate-500 font-mono truncate">{user.email}</p>
            <div className="flex flex-wrap gap-1 mt-1.5">
              {levels.map((lvl) => (
                <span
                  key={lvl}
                  className={`text-[9px] font-mono uppercase tracking-widest px-1.5 py-0.5 rounded border ${tierColor(lvl)}`}
                >
                  {accessLevelLabel(lvl)}
                </span>
              ))}
            </div>
            <p className="text-[9px] mt-2 font-mono text-slate-500">
              {user.rate_limit_per_min === 0 || (user.rate_limit_per_min == null && unlimited)
                ? "unlimited rate"
                : user.rate_limit_per_min == null
                ? "5 req/min"
                : `${user.rate_limit_per_min} req/min`}
            </p>
          </div>

          <div className="px-3 py-2 border-b border-rim">
            <p className="text-[9px] uppercase tracking-widest text-slate-600 mb-1">API key</p>
            <p className="text-[10px] font-mono text-slate-400">
              {user.api_key_prefix}…
              <span className="text-slate-700"> (saved at signup)</span>
            </p>
          </div>

          <button
            onClick={() => { setMenuOpen(false); logout(); }}
            className="block w-full text-left px-3 py-2 text-xs text-red-400 hover:bg-red-500/10 transition-colors"
          >
            Log out
          </button>
        </div>
      )}
    </div>
  );
}

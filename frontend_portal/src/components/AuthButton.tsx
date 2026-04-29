import { useEffect, useRef, useState } from "react";
import { initialsOf, useAuth } from "../hooks/useAuth";
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

  // ─── Logged out: stacked Log-in + Sign-up pills ────────────────────────────
  if (!user) {
    return (
      <>
        <div className="flex flex-col gap-1 items-stretch shrink-0">
          <button
            onClick={() => setLoginOpen(true)}
            className="text-[10px] font-semibold uppercase tracking-widest px-2.5 py-1 rounded-md border border-cyan-500/40 text-cyan-300 hover:text-cyan-200 hover:bg-cyan-400/10 transition-colors"
            aria-label="Log in"
          >
            Log in
          </button>
          <button
            onClick={() => setSignupOpen(true)}
            className="text-[10px] font-semibold uppercase tracking-widest px-2.5 py-1 rounded-md border border-violet-500/40 text-violet-300 hover:text-violet-200 hover:bg-violet-400/10 transition-colors"
            aria-label="Sign up"
          >
            Sign up
          </button>
        </div>

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
  const isSuper = user.access_level === "super-user";
  return (
    <div ref={wrapperRef} className="relative">
      <button
        onClick={() => setMenuOpen((p) => !p)}
        className={`flex items-center justify-center w-7 h-7 rounded-full text-[10px] font-bold uppercase tracking-wider transition-shadow ${
          isSuper
            ? "bg-gradient-to-br from-amber-400 to-orange-500 text-slate-900 shadow-[0_0_10px_rgba(251,191,36,0.45)]"
            : "bg-gradient-to-br from-cyan-400 to-violet-500 text-slate-900 shadow-[0_0_10px_rgba(167,139,250,0.45)]"
        }`}
        aria-haspopup="menu"
        aria-expanded={menuOpen}
        title={user.name}
      >
        {initialsOf(user.name)}
      </button>

      {menuOpen && (
        <div
          role="menu"
          className="absolute right-0 top-full mt-2 z-50 w-56 rounded-lg border border-rim bg-base shadow-2xl shadow-black/40 overflow-hidden"
        >
          <div className="px-3 py-2.5 border-b border-rim">
            <p className="text-xs font-semibold text-slate-200 truncate">{user.name}</p>
            <p className="text-[10px] text-slate-500 font-mono truncate">{user.email}</p>
            <p className="text-[9px] mt-1.5 font-mono uppercase tracking-widest">
              <span className={isSuper ? "text-amber-400" : "text-cyan-400"}>
                {isSuper ? "Super-user" : "Community"}
              </span>
              <span className="text-slate-700"> · </span>
              <span className="text-slate-500">
                {user.rate_limit_per_min === 0 || user.rate_limit_per_min === null
                  ? (isSuper ? "unlimited" : "5 req/min")
                  : `${user.rate_limit_per_min} req/min`}
              </span>
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

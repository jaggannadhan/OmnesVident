import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { accessLevelLabel, initialsOf, useAuth } from "../hooks/useAuth";
import { useTheme } from "../hooks/useTheme";
import { LoginModal } from "./LoginModal";
import { SignupModal } from "./SignupModal";
import { ForgotPasswordModal } from "./ForgotPasswordModal";

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
  const { user, logout }     = useAuth();
  const { theme, toggleTheme } = useTheme();
  const [loginOpen,   setLoginOpen]   = useState(false);
  const [signupOpen,  setSignupOpen]  = useState(false);
  const [forgotOpen,  setForgotOpen]  = useState(false);
  const [menuOpen,    setMenuOpen]    = useState(false);
  const [menuPos,     setMenuPos]     = useState({ top: 0, right: 0 });
  const wrapperRef = useRef<HTMLDivElement>(null);
  const avatarRef  = useRef<HTMLButtonElement>(null);

  // Compute the dropdown's screen position from the avatar's bounding rect.
  // We portal the menu to <body> (see render) so its z-index isn't trapped
  // by any ancestor that creates a stacking context (e.g. the R3F canvas).
  useEffect(() => {
    if (!menuOpen) return;
    const measure = () => {
      const r = avatarRef.current?.getBoundingClientRect();
      if (r) setMenuPos({ top: r.bottom + 8, right: window.innerWidth - r.right });
    };
    measure();
    window.addEventListener("resize", measure);
    window.addEventListener("scroll", measure, true);
    return () => {
      window.removeEventListener("resize", measure);
      window.removeEventListener("scroll", measure, true);
    };
  }, [menuOpen]);

  // Close the avatar menu when clicking outside or pressing Escape
  useEffect(() => {
    if (!menuOpen) return;
    const onPointer = (e: PointerEvent) => {
      const target = e.target as Node;
      // Allow clicks inside the avatar button OR the portaled menu.
      const inAvatar = wrapperRef.current?.contains(target);
      const menuEl   = document.getElementById("auth-menu-portal");
      const inMenu   = menuEl?.contains(target);
      if (!inAvatar && !inMenu) setMenuOpen(false);
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
          onSwitchToForgotPwd={() => setForgotOpen(true)}
        />
        <SignupModal
          open={signupOpen}
          onClose={() => setSignupOpen(false)}
          onSwitchToLogin={() => setLoginOpen(true)}
          onSuccess={() => setSignupOpen(false)}
        />
        <ForgotPasswordModal
          open={forgotOpen}
          onClose={() => setForgotOpen(false)}
          onSwitchToSignup={() => setSignupOpen(true)}
        />
      </>
    );
  }

  // ─── Logged in: avatar circle + dropdown ───────────────────────────────────
  const levels    = user.access_levels ?? ["basic"];
  const isAdmin   = levels.includes("admin");

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

  const isLight = theme === "light";

  // Dropdown content — extracted so we can portal it to <body> and escape
  // any ancestor stacking context (e.g. the R3F canvas).
  const menu = menuOpen ? (
    <div
      id="auth-menu-portal"
      role="menu"
      style={{
        position: "fixed",
        top:    menuPos.top,
        right:  menuPos.right,
        zIndex: 9999,
      }}
      className="w-60 rounded-lg border border-rim bg-base shadow-2xl shadow-black/40 overflow-hidden"
    >
      {/* Identity panel — name, email, access-level chips */}
      <div className="px-3 py-2.5 border-b border-rim">
        <p className="text-xs font-semibold truncate" style={{ color: "var(--color-text)" }}>
          {user.name}
        </p>
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
      </div>

      {/* Theme toggle row */}
      <button
        onClick={toggleTheme}
        className="flex items-center justify-between w-full px-3 py-2 text-xs hover:bg-panel transition-colors border-b border-rim"
        role="menuitemcheckbox"
        aria-checked={isLight}
      >
        <span className="flex items-center gap-2" style={{ color: "var(--color-text)" }}>
          <span aria-hidden="true">{isLight ? "☀" : "☾"}</span>
          {isLight ? "Light theme" : "Dark theme"}
        </span>

        {/* Toggle pill */}
        <span
          aria-hidden="true"
          className={`relative inline-flex items-center w-9 h-5 rounded-full border transition-colors ${
            isLight
              ? "bg-amber-300/40 border-amber-400/50"
              : "bg-slate-700/50 border-slate-500/40"
          }`}
        >
          <span
            className={`absolute top-0.5 w-4 h-4 rounded-full transition-transform ${
              isLight
                ? "left-0.5 translate-x-4 bg-amber-300"
                : "left-0.5 translate-x-0 bg-slate-300"
            }`}
          />
        </span>
      </button>

      <button
        onClick={() => { setMenuOpen(false); logout(); }}
        className="block w-full text-left px-3 py-2 text-xs text-red-400 hover:bg-red-500/10 transition-colors"
      >
        Log out
      </button>
    </div>
  ) : null;

  return (
    <div ref={wrapperRef} className="relative">
      <button
        ref={avatarRef}
        onClick={() => setMenuOpen((p) => !p)}
        className={`flex items-center justify-center w-7 h-7 rounded-full text-[10px] font-bold uppercase tracking-wider transition-shadow ${avatarTheme}`}
        aria-haspopup="menu"
        aria-expanded={menuOpen}
        title={`${user.name} · ${levels.map(accessLevelLabel).join(", ")}`}
      >
        {initialsOf(user.name)}
      </button>

      {menu && createPortal(menu, document.body)}
    </div>
  );
}

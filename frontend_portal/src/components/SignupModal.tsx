import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useAuth } from "../hooks/useAuth";
import { PasswordInput } from "./PasswordInput";

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "/api";

const PASSWORD_MIN = 8;

// Practical email regex: exactly one @, plausible domain, TLD ≥ 2 letters.
// Backend (Pydantic EmailStr) does the rigorous RFC-compliant check; this is
// only for fast client-side feedback.
const EMAIL_RX = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/;

interface SignupModalProps {
  open: boolean;
  onClose: () => void;
  onSuccess: (key: string, email: string, name: string) => void;
  onSwitchToLogin?: () => void;
}

const inputBaseStyle: React.CSSProperties = {
  background: "rgba(15,23,42,0.6)",
  border: "1px solid rgba(148,163,184,0.18)",
  borderRadius: "8px",
  padding: "9px 12px",
  fontSize: "13px",
  color: "#f1f5f9",
  outline: "none",
  transition: "border-color 0.15s ease",
};

export function SignupModal({ open, onClose, onSuccess, onSwitchToLogin }: SignupModalProps) {
  const { setAuthFromSignup } = useAuth();
  const [name,    setName]    = useState("");
  const [email,   setEmail]   = useState("");
  const [pw,      setPw]      = useState("");
  const [pw2,     setPw2]     = useState("");
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState<string | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);

  // Reset state every time the modal opens
  useEffect(() => {
    if (open) {
      setName("");
      setEmail("");
      setPw("");
      setPw2("");
      setError(null);
      setLoading(false);
    }
  }, [open]);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  // ─── Live email validation ─────────────────────────────────────────────────
  const emailTrim   = email.trim();
  const emailEmpty  = emailTrim.length === 0;
  const emailValid  = !emailEmpty && EMAIL_RX.test(emailTrim);
  const emailBad    = !emailEmpty && !emailValid;

  // ─── Live password validation ──────────────────────────────────────────────
  // Each criterion lights up as the user types. Submit is disabled until all
  // pass AND the confirm field matches.
  const pwChecks = {
    length:  pw.length >= PASSWORD_MIN,
    upper:   /[A-Z]/.test(pw),
    lower:   /[a-z]/.test(pw),
    number:  /\d/.test(pw),
    special: /[^A-Za-z0-9]/.test(pw),
  };
  const pwAllValid = Object.values(pwChecks).every(Boolean);

  const pwMismatch = pw2.length > 0 && pw !== pw2;
  const pwMatched  = pw2.length > 0 && pw === pw2 && pwAllValid;

  if (!open) return null;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (name.trim().length < 2)  { setError("Please enter your name."); return; }
    if (!emailValid)             { setError("Enter a valid email address."); return; }
    if (!pwAllValid)             { setError("Password does not meet all the requirements below."); return; }
    if (pw !== pw2)              { setError("Passwords do not match."); return; }

    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/v1/auth/signup`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({
          name:     name.trim(),
          email:    email.trim().toLowerCase(),
          password: pw,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(data?.detail || `Sign-up failed (${res.status}).`);
        return;
      }
      // Lift the user into the logged-in state directly — no separate login round-trip.
      setAuthFromSignup({
        user_id:            data.user_id,
        name:               data.name,
        email:              data.email,
        access_levels:      Array.isArray(data.access_levels) ? data.access_levels : ["basic"],
        api_key_prefix:     data.api_key_prefix,
        rate_limit_per_min: data.rate_limit_per_min ?? null,
      });
      onSuccess(data.api_key, data.email, data.name);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Network error. Try again.");
    } finally {
      setLoading(false);
    }
  }

  const focusOn = (e: React.FocusEvent<HTMLInputElement>) =>
    (e.target.style.borderColor = "rgba(167,139,250,0.5)");
  const blurOn = (e: React.FocusEvent<HTMLInputElement>) =>
    (e.target.style.borderColor = "rgba(148,163,184,0.18)");

  // Render via a portal so the modal isn't trapped inside the sidebar's
  // transform context (Tailwind's `transform` class re-anchors `position: fixed`).
  return createPortal(
    <div
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
      style={{
        position: "fixed", inset: 0, zIndex: 1000,
        background: "rgba(2,4,16,0.78)", backdropFilter: "blur(6px)",
        display: "flex", alignItems: "center", justifyContent: "center",
        padding: "20px",
      }}
    >
      <div
        ref={dialogRef}
        role="dialog" aria-modal="true" aria-labelledby="signup-title"
        style={{
          width: "100%", maxWidth: "440px",
          background: "rgba(8,10,24,0.98)",
          border: "1px solid rgba(167,139,250,0.25)",
          borderRadius: "14px",
          padding: "24px 24px 20px",
          fontFamily: "Inter, system-ui, sans-serif",
          color: "#e2e8f0",
          boxShadow: "0 12px 48px rgba(0,0,0,0.6), 0 0 24px rgba(167,139,250,0.08)",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "4px" }}>
          <h2 id="signup-title" style={{ margin: 0, fontSize: "16px", fontWeight: 700, letterSpacing: "0.02em" }}>
            Join the OmnesVident community
          </h2>
          <button
            onClick={onClose} aria-label="Close"
            style={{ background: "none", border: "none", color: "#64748b", fontSize: "18px", cursor: "pointer", padding: "0 4px", lineHeight: 1 }}
          >×</button>
        </div>

        <p style={{ margin: "8px 0 18px", fontSize: "11px", color: "#94a3b8", lineHeight: 1.5 }}>
          Sign up to receive an API key for the public REST API. Community members get
          <span style={{ color: "#a78bfa", fontWeight: 600 }}> 5 requests / minute</span>.
          The key is shown once — store it safely. Your password is hashed (bcrypt) before
          we ever write it to the database.
        </p>

        <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          <label style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
            <span style={{ fontSize: "10px", textTransform: "uppercase", letterSpacing: "0.1em", color: "#64748b" }}>Name</span>
            <input
              type="text" value={name} autoFocus required minLength={2} maxLength={80}
              autoComplete="name"
              onChange={(e) => setName(e.target.value)}
              style={inputBaseStyle} onFocus={focusOn} onBlur={blurOn}
            />
          </label>

          <label style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
            <span style={{ fontSize: "10px", textTransform: "uppercase", letterSpacing: "0.1em", color: "#64748b" }}>Email</span>
            <input
              type="email" value={email} required
              autoComplete="email"
              aria-invalid={emailBad || undefined}
              aria-describedby={emailBad ? "email-error" : undefined}
              onChange={(e) => setEmail(e.target.value)}
              style={{
                ...inputBaseStyle,
                borderColor:
                  emailEmpty  ? "rgba(148,163,184,0.18)"
                  : emailValid ? "rgba(74,222,128,0.4)"
                  :              "rgba(239,68,68,0.4)",
              }}
              onFocus={focusOn} onBlur={blurOn}
            />
            {emailBad && (
              <span
                id="email-error"
                role="alert"
                style={{
                  marginTop: "2px",
                  fontSize: "10px",
                  color: "#fca5a5",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "5px",
                }}
              >
                <span aria-hidden="true">✕</span> Enter a valid email address
              </span>
            )}
          </label>

          <label style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
            <span style={{ fontSize: "10px", textTransform: "uppercase", letterSpacing: "0.1em", color: "#64748b" }}>
              Password
            </span>
            <PasswordInput
              value={pw} required minLength={PASSWORD_MIN} maxLength={128}
              autoComplete="new-password"
              onChange={(e) => setPw(e.target.value)}
              style={inputBaseStyle} onFocus={focusOn} onBlur={blurOn}
            />
            {/* Requirement checklist — each item turns green ✓ as it's met. */}
            <div
              role="list"
              aria-label="Password requirements"
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gap: "2px 10px",
                marginTop: "4px",
              }}
            >
              {([
                ["length",  `At least ${PASSWORD_MIN} characters`],
                ["upper",   "One uppercase (A–Z)"],
                ["lower",   "One lowercase (a–z)"],
                ["number",  "One number (0–9)"],
                ["special", "One special character"],
              ] as const).map(([key, label]) => {
                const ok = pwChecks[key];
                return (
                  <span
                    key={key}
                    role="listitem"
                    style={{
                      fontSize: "10px",
                      color: pw.length === 0 ? "#475569" : ok ? "#86efac" : "#fca5a5",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "5px",
                    }}
                  >
                    <span aria-hidden="true">{ok ? "✓" : "•"}</span>
                    {label}
                  </span>
                );
              })}
            </div>
          </label>

          <label style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
            <span style={{ fontSize: "10px", textTransform: "uppercase", letterSpacing: "0.1em", color: "#64748b" }}>Confirm password</span>
            <PasswordInput
              value={pw2} required minLength={PASSWORD_MIN} maxLength={128}
              autoComplete="new-password"
              onChange={(e) => setPw2(e.target.value)}
              aria-invalid={pwMismatch || undefined}
              aria-describedby={pwMismatch ? "pw-mismatch" : undefined}
              style={{
                ...inputBaseStyle,
                borderColor:
                  pw2.length === 0          ? "rgba(148,163,184,0.18)"
                  : pwMatched               ? "rgba(74,222,128,0.4)"
                  :                            "rgba(239,68,68,0.4)",
              }}
              onFocus={focusOn} onBlur={blurOn}
            />
            {/* Live mismatch hint — appears as soon as the user types a
                non-matching character in the confirm field. */}
            {pwMismatch && (
              <span
                id="pw-mismatch"
                role="alert"
                style={{
                  marginTop: "2px",
                  fontSize: "10px",
                  color: "#fca5a5",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "5px",
                }}
              >
                <span aria-hidden="true">✕</span> Passwords do not match
              </span>
            )}
            {pwMatched && (
              <span
                style={{
                  marginTop: "2px",
                  fontSize: "10px",
                  color: "#86efac",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "5px",
                }}
              >
                <span aria-hidden="true">✓</span> Passwords match
              </span>
            )}
          </label>

          {error && (
            <p style={{ margin: 0, fontSize: "11px", color: "#fca5a5", background: "rgba(239,68,68,0.08)", padding: "8px 10px", borderRadius: "6px", border: "1px solid rgba(239,68,68,0.25)" }}>
              {error}
            </p>
          )}

          {(() => {
            const blocked = loading || pwMismatch || !pwAllValid || !emailValid;
            return (
              <button
                type="submit"
                disabled={blocked}
                style={{
                  marginTop: "4px", padding: "10px 14px",
                  fontSize: "12px", fontWeight: 700, letterSpacing: "0.06em", textTransform: "uppercase",
                  background: blocked ? "rgba(167,139,250,0.4)" : "#a78bfa",
                  color: "#0f0f23", border: "none", borderRadius: "8px",
                  cursor: blocked ? "not-allowed" : "pointer",
                  boxShadow: blocked ? "none" : "0 0 16px rgba(167,139,250,0.35)",
                  transition: "background 0.15s ease, box-shadow 0.15s ease",
                }}
              >
                {loading ? "Signing up…" : "Sign up"}
              </button>
            );
          })()}
        </form>

        {onSwitchToLogin && (
          <p style={{ margin: "16px 0 0", fontSize: "11px", color: "#64748b", textAlign: "center" }}>
            Already have an account?{" "}
            <button
              type="button"
              onClick={() => { onClose(); onSwitchToLogin(); }}
              style={{
                background: "none", border: "none", padding: 0,
                color: "#a78bfa", textDecoration: "underline",
                cursor: "pointer", fontSize: "11px",
              }}
            >
              Log in
            </button>
          </p>
        )}
      </div>
    </div>,
    document.body
  );
}

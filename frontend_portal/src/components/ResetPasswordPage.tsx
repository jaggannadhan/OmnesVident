import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { PasswordInput } from "./PasswordInput";

const API_BASE   = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "/api";
const PASSWORD_MIN = 8;

type Phase = "validating" | "invalid" | "ready" | "saving" | "done";

interface ValidateResponse {
  valid: boolean;
  email?: string;
  name?:  string;
}

export function ResetPasswordPage() {
  const { token = "" } = useParams<{ token?: string }>();
  const navigate = useNavigate();

  const [phase,   setPhase]   = useState<Phase>("validating");
  const [user,    setUser]    = useState<{ email?: string; name?: string }>({});
  const [pw,      setPw]      = useState("");
  const [pw2,     setPw2]     = useState("");
  const [error,   setError]   = useState<string | null>(null);

  // ─── Pre-validate the token on mount ─────────────────────────────────────
  useEffect(() => {
    let cancelled = false;
    async function run() {
      if (!token) { setPhase("invalid"); return; }
      try {
        const res = await fetch(`${API_BASE}/v1/auth/reset-password/${encodeURIComponent(token)}`, {
          headers: { Accept: "application/json" },
        });
        const data = (await res.json().catch(() => ({}))) as ValidateResponse;
        if (cancelled) return;
        if (res.ok && data.valid) {
          setUser({ email: data.email, name: data.name });
          setPhase("ready");
        } else {
          setPhase("invalid");
        }
      } catch {
        if (!cancelled) setPhase("invalid");
      }
    }
    run();
    return () => { cancelled = true; };
  }, [token]);

  // ─── Live password validation (mirrors SignupModal) ──────────────────────
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

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!pwAllValid)  { setError("Password does not meet all the requirements below."); return; }
    if (pw !== pw2)   { setError("Passwords do not match."); return; }

    setPhase("saving");
    try {
      const res = await fetch(`${API_BASE}/v1/auth/reset-password`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ token, password: pw }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(data?.detail || `Could not reset password (${res.status}).`);
        setPhase("ready");
        return;
      }
      setPhase("done");
      // Redirect to home after a brief confirmation flash so the user sees
      // the success message; they can also tap the explicit "Go to login" button.
      setTimeout(() => navigate("/", { replace: true }), 1800);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Network error. Try again.");
      setPhase("ready");
    }
  }

  // ─── Shared layout ───────────────────────────────────────────────────────
  const inputBaseStyle: React.CSSProperties = {
    background: "rgba(15,23,42,0.6)",
    border: "1px solid rgba(148,163,184,0.18)",
    borderRadius: "8px",
    padding: "9px 12px",
    fontSize: "13px",
    color: "#f1f5f9",
    outline: "none",
    transition: "border-color 0.15s ease",
    width: "100%",
  };
  const focusOn = (e: React.FocusEvent<HTMLInputElement>) =>
    (e.target.style.borderColor = "rgba(167,139,250,0.5)");
  const blurOn = (e: React.FocusEvent<HTMLInputElement>) =>
    (e.target.style.borderColor = "rgba(148,163,184,0.18)");

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "#020410",
        color: "#e2e8f0",
        fontFamily: "Inter, system-ui, sans-serif",
        display: "flex", alignItems: "center", justifyContent: "center",
        padding: "32px 20px",
      }}
    >
      <div
        style={{
          width: "100%", maxWidth: "440px",
          background: "rgba(8,10,24,0.98)",
          border: "1px solid rgba(167,139,250,0.25)",
          borderRadius: "14px",
          padding: "28px 26px 24px",
          boxShadow: "0 12px 48px rgba(0,0,0,0.6), 0 0 24px rgba(167,139,250,0.08)",
        }}
      >
        {/* Header — logo + brand */}
        <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "16px" }}>
          <img src="/logo-icon.png" alt="" aria-hidden="true" style={{ width: 36, height: 36 }} />
          <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
            <span style={{ fontSize: "13px", fontWeight: 700, letterSpacing: "0.02em" }}>
              Omnes<span style={{ color: "#22d3ee" }}>Vident</span>
            </span>
            <span style={{ fontSize: "9px", color: "#475569", fontFamily: "JetBrains Mono, monospace", letterSpacing: "0.1em", textTransform: "uppercase" }}>
              Reset password
            </span>
          </div>
        </div>

        {/* ─── Phase-specific bodies ─── */}

        {phase === "validating" && (
          <p style={{ margin: 0, fontSize: "12px", color: "#94a3b8" }}>
            Verifying your link…
          </p>
        )}

        {phase === "invalid" && (
          <>
            <h2 style={{ margin: "0 0 8px", fontSize: "16px", color: "#fca5a5", fontWeight: 700 }}>
              This link is invalid or expired
            </h2>
            <p style={{ margin: "0 0 18px", fontSize: "12px", color: "#94a3b8", lineHeight: 1.55 }}>
              Reset links are valid for 60 minutes and can only be used once.
              Request a new one from the login page.
            </p>
            <Link
              to="/"
              style={{
                display: "inline-block", padding: "10px 18px",
                fontSize: "12px", fontWeight: 700, letterSpacing: "0.06em", textTransform: "uppercase",
                background: "#22d3ee", color: "#0f0f23",
                border: "none", borderRadius: "8px", textDecoration: "none",
                boxShadow: "0 0 16px rgba(34,211,238,0.35)",
              }}
            >
              Go to login
            </Link>
          </>
        )}

        {phase === "done" && (
          <>
            <h2 style={{ margin: "0 0 8px", fontSize: "16px", color: "#86efac", fontWeight: 700 }}>
              Password updated
            </h2>
            <p style={{ margin: "0 0 18px", fontSize: "12px", color: "#94a3b8", lineHeight: 1.55 }}>
              You can now log in with your new password. Redirecting you to the login page…
            </p>
            <Link
              to="/"
              style={{
                display: "inline-block", padding: "10px 18px",
                fontSize: "12px", fontWeight: 700, letterSpacing: "0.06em", textTransform: "uppercase",
                background: "#22d3ee", color: "#0f0f23",
                border: "none", borderRadius: "8px", textDecoration: "none",
                boxShadow: "0 0 16px rgba(34,211,238,0.35)",
              }}
            >
              Go to login
            </Link>
          </>
        )}

        {(phase === "ready" || phase === "saving") && (
          <>
            <p style={{ margin: "0 0 18px", fontSize: "12px", color: "#94a3b8", lineHeight: 1.55 }}>
              Set a new password for{" "}
              <span style={{ color: "#22d3ee", fontFamily: "monospace" }}>{user.email}</span>.
              Use a strong password you don't reuse anywhere else.
            </p>

            <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              <label style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                <span style={{ fontSize: "10px", textTransform: "uppercase", letterSpacing: "0.1em", color: "#64748b" }}>
                  New password
                </span>
                <PasswordInput
                  value={pw} required minLength={PASSWORD_MIN} maxLength={128}
                  autoComplete="new-password"
                  onChange={(e) => setPw(e.target.value)}
                  style={inputBaseStyle} onFocus={focusOn} onBlur={blurOn}
                />

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
                          display: "inline-flex", alignItems: "center", gap: "5px",
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
                <span style={{ fontSize: "10px", textTransform: "uppercase", letterSpacing: "0.1em", color: "#64748b" }}>
                  Confirm new password
                </span>
                <PasswordInput
                  value={pw2} required minLength={PASSWORD_MIN} maxLength={128}
                  autoComplete="new-password"
                  onChange={(e) => setPw2(e.target.value)}
                  aria-invalid={pwMismatch || undefined}
                  style={{
                    ...inputBaseStyle,
                    borderColor:
                      pw2.length === 0  ? "rgba(148,163,184,0.18)"
                      : pwMatched       ? "rgba(74,222,128,0.4)"
                      :                   "rgba(239,68,68,0.4)",
                  }}
                  onFocus={focusOn} onBlur={blurOn}
                />
                {pwMismatch && (
                  <span style={{ marginTop: "2px", fontSize: "10px", color: "#fca5a5" }}>
                    ✕ Passwords do not match
                  </span>
                )}
                {pwMatched && (
                  <span style={{ marginTop: "2px", fontSize: "10px", color: "#86efac" }}>
                    ✓ Passwords match
                  </span>
                )}
              </label>

              {error && (
                <p
                  style={{
                    margin: 0, fontSize: "11px", color: "#fca5a5",
                    background: "rgba(239,68,68,0.08)", padding: "8px 10px",
                    borderRadius: "6px", border: "1px solid rgba(239,68,68,0.25)",
                  }}
                >
                  {error}
                </p>
              )}

              {(() => {
                const blocked =
                  phase === "saving" || pwMismatch || !pwAllValid;
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
                    }}
                  >
                    {phase === "saving" ? "Updating…" : "Update password"}
                  </button>
                );
              })()}
            </form>
          </>
        )}
      </div>
    </div>
  );
}

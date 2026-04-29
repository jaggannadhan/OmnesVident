import { useEffect, useState } from "react";
import { useAuth } from "../hooks/useAuth";

interface LoginModalProps {
  open:         boolean;
  onClose:      () => void;
  onSwitchToSignup?: () => void;
}

export function LoginModal({ open, onClose, onSwitchToSignup }: LoginModalProps) {
  const { login } = useAuth();
  const [email,    setEmail]    = useState("");
  const [password, setPassword] = useState("");
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setEmail("");
      setPassword("");
      setError(null);
      setLoading(false);
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!/^\S+@\S+\.\S+$/.test(email)) { setError("Enter a valid email."); return; }
    if (password.length === 0)         { setError("Password is required."); return; }
    setLoading(true);
    try {
      await login(email, password);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed. Try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
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
        role="dialog" aria-modal="true" aria-labelledby="login-title"
        style={{
          width: "100%", maxWidth: "400px",
          background: "rgba(8,10,24,0.98)",
          border: "1px solid rgba(34,211,238,0.25)",
          borderRadius: "14px",
          padding: "24px 24px 20px",
          fontFamily: "Inter, system-ui, sans-serif",
          color: "#e2e8f0",
          boxShadow: "0 12px 48px rgba(0,0,0,0.6), 0 0 24px rgba(34,211,238,0.08)",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "8px" }}>
          <h2 id="login-title" style={{ margin: 0, fontSize: "16px", fontWeight: 700 }}>
            Welcome back
          </h2>
          <button
            onClick={onClose} aria-label="Close"
            style={{ background: "none", border: "none", color: "#64748b", fontSize: "18px", cursor: "pointer", padding: "0 4px", lineHeight: 1 }}
          >×</button>
        </div>

        <p style={{ margin: "4px 0 18px", fontSize: "11px", color: "#94a3b8", lineHeight: 1.5 }}>
          Log in with the email and password you used at signup.
        </p>

        <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          <label style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
            <span style={{ fontSize: "10px", textTransform: "uppercase", letterSpacing: "0.1em", color: "#64748b" }}>Email</span>
            <input
              type="email" autoComplete="email" autoFocus required
              value={email} onChange={(e) => setEmail(e.target.value)}
              style={{
                background: "rgba(15,23,42,0.6)",
                border: "1px solid rgba(148,163,184,0.18)",
                borderRadius: "8px",
                padding: "9px 12px",
                fontSize: "13px", color: "#f1f5f9", outline: "none",
                transition: "border-color 0.15s ease",
              }}
              onFocus={(e) => (e.target.style.borderColor = "rgba(34,211,238,0.5)")}
              onBlur={(e)  => (e.target.style.borderColor = "rgba(148,163,184,0.18)")}
            />
          </label>

          <label style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
            <span style={{ fontSize: "10px", textTransform: "uppercase", letterSpacing: "0.1em", color: "#64748b" }}>Password</span>
            <input
              type="password" autoComplete="current-password" required
              value={password} onChange={(e) => setPassword(e.target.value)}
              style={{
                background: "rgba(15,23,42,0.6)",
                border: "1px solid rgba(148,163,184,0.18)",
                borderRadius: "8px",
                padding: "9px 12px",
                fontSize: "13px", color: "#f1f5f9", outline: "none",
                transition: "border-color 0.15s ease",
              }}
              onFocus={(e) => (e.target.style.borderColor = "rgba(34,211,238,0.5)")}
              onBlur={(e)  => (e.target.style.borderColor = "rgba(148,163,184,0.18)")}
            />
          </label>

          {error && (
            <p style={{
              margin: 0, fontSize: "11px", color: "#fca5a5",
              background: "rgba(239,68,68,0.08)", padding: "8px 10px",
              borderRadius: "6px", border: "1px solid rgba(239,68,68,0.25)",
            }}>{error}</p>
          )}

          <button
            type="submit" disabled={loading}
            style={{
              marginTop: "4px", padding: "10px 14px",
              fontSize: "12px", fontWeight: 700,
              letterSpacing: "0.06em", textTransform: "uppercase",
              background: loading ? "rgba(34,211,238,0.4)" : "#22d3ee",
              color: "#0f0f23", border: "none", borderRadius: "8px",
              cursor: loading ? "wait" : "pointer",
              boxShadow: loading ? "none" : "0 0 16px rgba(34,211,238,0.35)",
              transition: "background 0.15s ease, box-shadow 0.15s ease",
            }}
          >
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </form>

        {onSwitchToSignup && (
          <p style={{ margin: "16px 0 0", fontSize: "11px", color: "#64748b", textAlign: "center" }}>
            Don't have an account?{" "}
            <button
              type="button"
              onClick={() => { onClose(); onSwitchToSignup(); }}
              style={{
                background: "none", border: "none", padding: 0,
                color: "#22d3ee", textDecoration: "underline",
                cursor: "pointer", fontSize: "11px",
              }}
            >
              Sign up
            </button>
          </p>
        )}
      </div>
    </div>
  );
}

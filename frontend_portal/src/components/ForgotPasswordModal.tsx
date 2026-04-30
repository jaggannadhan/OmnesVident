import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "/api";

interface ForgotPasswordModalProps {
  open:    boolean;
  onClose: () => void;
  /** Open the signup modal — used when the email isn't registered. */
  onSwitchToSignup?: () => void;
}

type Phase = "input" | "sent";

export function ForgotPasswordModal({
  open,
  onClose,
  onSwitchToSignup,
}: ForgotPasswordModalProps) {
  const [email, setEmail]     = useState("");
  const [phase, setPhase]     = useState<Phase>("input");
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);
  // When the email isn't registered we want to show a "Sign up" CTA next to
  // the error — track that case separately so we can toggle the button.
  const [unregistered, setUnregistered] = useState(false);

  useEffect(() => {
    if (open) {
      setEmail("");
      setPhase("input");
      setLoading(false);
      setError(null);
      setUnregistered(false);
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
    setUnregistered(false);
    if (!/^\S+@\S+\.\S+$/.test(email)) {
      setError("Enter a valid email address.");
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/v1/auth/forgot-password`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ email: email.trim().toLowerCase() }),
      });
      const data = await res.json().catch(() => ({}));
      if (res.status === 404) {
        // Backend returns 404 when the email isn't registered.
        setUnregistered(true);
        setError(data?.detail || "No account found for this email.");
        return;
      }
      if (!res.ok) {
        setError(data?.detail || `Could not send reset email (${res.status}).`);
        return;
      }
      setPhase("sent");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Network error. Try again.");
    } finally {
      setLoading(false);
    }
  }

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
        role="dialog"
        aria-modal="true"
        aria-labelledby="forgot-title"
        style={{
          width: "100%", maxWidth: "420px",
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
          <h2 id="forgot-title" style={{ margin: 0, fontSize: "16px", fontWeight: 700 }}>
            {phase === "sent" ? "Check your inbox" : "Forgot your password?"}
          </h2>
          <button
            onClick={onClose}
            aria-label="Close"
            style={{ background: "none", border: "none", color: "#64748b", fontSize: "18px", cursor: "pointer", padding: "0 4px", lineHeight: 1 }}
          >×</button>
        </div>

        {phase === "input" ? (
          <>
            <p style={{ margin: "4px 0 18px", fontSize: "11px", color: "#94a3b8", lineHeight: 1.55 }}>
              Enter the email you signed up with. We'll send you a link to reset your password.
              The link is valid for 60 minutes.
            </p>

            <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              <label style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                <span style={{ fontSize: "10px", textTransform: "uppercase", letterSpacing: "0.1em", color: "#64748b" }}>
                  Email
                </span>
                <input
                  type="email"
                  autoComplete="email"
                  autoFocus
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
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
                <div
                  style={{
                    margin: 0, fontSize: "11px", color: "#fca5a5",
                    background: "rgba(239,68,68,0.08)", padding: "8px 10px",
                    borderRadius: "6px", border: "1px solid rgba(239,68,68,0.25)",
                    display: "flex", flexDirection: "column", gap: "6px",
                  }}
                >
                  <span>{error}</span>
                  {unregistered && onSwitchToSignup && (
                    <button
                      type="button"
                      onClick={() => { onClose(); onSwitchToSignup(); }}
                      style={{
                        alignSelf: "flex-start",
                        background: "none",
                        border: "none",
                        padding: 0,
                        color: "#a78bfa",
                        textDecoration: "underline",
                        cursor: "pointer",
                        fontSize: "11px",
                      }}
                    >
                      Sign up →
                    </button>
                  )}
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                style={{
                  marginTop: "4px", padding: "10px 14px",
                  fontSize: "12px", fontWeight: 700, letterSpacing: "0.06em", textTransform: "uppercase",
                  background: loading ? "rgba(34,211,238,0.4)" : "#22d3ee",
                  color: "#0f0f23", border: "none", borderRadius: "8px",
                  cursor: loading ? "wait" : "pointer",
                  boxShadow: loading ? "none" : "0 0 16px rgba(34,211,238,0.35)",
                  transition: "background 0.15s ease, box-shadow 0.15s ease",
                }}
              >
                {loading ? "Sending…" : "Send reset link"}
              </button>
            </form>
          </>
        ) : (
          <>
            <p style={{ margin: "8px 0 8px", fontSize: "13px", color: "#cbd5e1", lineHeight: 1.55 }}>
              A password reset link has been sent to your inbox.
            </p>
            <p style={{ margin: "0 0 18px", fontSize: "11px", color: "#94a3b8", lineHeight: 1.55 }}>
              The link is valid for <strong style={{ color: "#22d3ee" }}>60 min</strong>.
              If it doesn't arrive in a few minutes, check your spam folder or try again.
            </p>
            <button
              onClick={onClose}
              style={{
                width: "100%", padding: "10px 14px",
                fontSize: "12px", fontWeight: 700, letterSpacing: "0.06em", textTransform: "uppercase",
                background: "#22d3ee", color: "#0f0f23",
                border: "none", borderRadius: "8px", cursor: "pointer",
                boxShadow: "0 0 16px rgba(34,211,238,0.35)",
              }}
            >
              Done
            </button>
          </>
        )}
      </div>
    </div>,
    document.body
  );
}

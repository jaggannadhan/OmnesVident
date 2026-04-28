import { useEffect, useRef, useState } from "react";

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "/api";

interface SignupModalProps {
  open: boolean;
  onClose: () => void;
  onSuccess: (key: string, email: string, name: string) => void;
}

export function SignupModal({ open, onClose, onSuccess }: SignupModalProps) {
  const [name,    setName]    = useState("");
  const [email,   setEmail]   = useState("");
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState<string | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);

  // Reset state every time the modal opens
  useEffect(() => {
    if (open) {
      setName("");
      setEmail("");
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

  if (!open) return null;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (name.trim().length < 2)            { setError("Please enter your name."); return; }
    if (!/^\S+@\S+\.\S+$/.test(email))     { setError("Enter a valid email address."); return; }

    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/v1/auth/signup`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ name: name.trim(), email: email.trim().toLowerCase() }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(data?.detail || `Sign-up failed (${res.status}).`);
        return;
      }
      onSuccess(data.api_key, data.email, data.name);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Network error. Try again.");
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
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="signup-title"
        style={{
          width: "100%", maxWidth: "420px",
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
            onClick={onClose}
            aria-label="Close"
            style={{ background: "none", border: "none", color: "#64748b", fontSize: "18px", cursor: "pointer", padding: "0 4px", lineHeight: 1 }}
          >
            ×
          </button>
        </div>

        <p style={{ margin: "8px 0 18px", fontSize: "11px", color: "#94a3b8", lineHeight: 1.5 }}>
          Sign up to receive an API key for the public REST API. Community members get
          <span style={{ color: "#a78bfa", fontWeight: 600 }}> 5 requests / minute</span>.
          The key is shown once — store it safely.
        </p>

        <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          <label style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
            <span style={{ fontSize: "10px", textTransform: "uppercase", letterSpacing: "0.1em", color: "#64748b" }}>
              Name
            </span>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              autoFocus
              required
              minLength={2}
              maxLength={80}
              style={{
                background: "rgba(15,23,42,0.6)",
                border: "1px solid rgba(148,163,184,0.18)",
                borderRadius: "8px",
                padding: "9px 12px",
                fontSize: "13px",
                color: "#f1f5f9",
                outline: "none",
                transition: "border-color 0.15s ease",
              }}
              onFocus={(e) => (e.target.style.borderColor = "rgba(167,139,250,0.5)")}
              onBlur={(e) => (e.target.style.borderColor = "rgba(148,163,184,0.18)")}
            />
          </label>

          <label style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
            <span style={{ fontSize: "10px", textTransform: "uppercase", letterSpacing: "0.1em", color: "#64748b" }}>
              Email
            </span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              style={{
                background: "rgba(15,23,42,0.6)",
                border: "1px solid rgba(148,163,184,0.18)",
                borderRadius: "8px",
                padding: "9px 12px",
                fontSize: "13px",
                color: "#f1f5f9",
                outline: "none",
                transition: "border-color 0.15s ease",
              }}
              onFocus={(e) => (e.target.style.borderColor = "rgba(167,139,250,0.5)")}
              onBlur={(e) => (e.target.style.borderColor = "rgba(148,163,184,0.18)")}
            />
          </label>

          {error && (
            <p style={{ margin: 0, fontSize: "11px", color: "#fca5a5", background: "rgba(239,68,68,0.08)", padding: "8px 10px", borderRadius: "6px", border: "1px solid rgba(239,68,68,0.25)" }}>
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            style={{
              marginTop: "4px",
              padding: "10px 14px",
              fontSize: "12px",
              fontWeight: 700,
              letterSpacing: "0.06em",
              textTransform: "uppercase",
              background: loading ? "rgba(167,139,250,0.4)" : "#a78bfa",
              color: "#0f0f23",
              border: "none",
              borderRadius: "8px",
              cursor: loading ? "wait" : "pointer",
              boxShadow: loading ? "none" : "0 0 16px rgba(167,139,250,0.35)",
              transition: "background 0.15s ease, box-shadow 0.15s ease",
            }}
          >
            {loading ? "Generating key…" : "Generate API key"}
          </button>
        </form>
      </div>
    </div>
  );
}

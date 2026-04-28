import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { SignupModal } from "./SignupModal";

const API_BASE_PUBLIC =
  ((import.meta.env.VITE_API_BASE_URL as string | undefined) ??
    "https://omnesvident-api-naqkmfs2qa-uc.a.run.app").replace(/\/$/, "");

// Dev convenience: when running on localhost, the dev proxy serves /api/v1 too.
// External docs always show the absolute Cloud Run URL so curl examples work copy-pasted.

interface IssuedKey {
  apiKey: string;
  email:  string;
  name:   string;
}

// ─── Code block with copy button ─────────────────────────────────────────────

function CodeBlock({ children, lang = "bash" }: { children: string; lang?: string }) {
  const [copied, setCopied] = useState(false);
  const onCopy = () => {
    navigator.clipboard.writeText(children).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  };
  return (
    <div style={{ position: "relative" }}>
      <pre
        style={{
          margin: 0,
          padding: "12px 14px",
          background: "rgba(15,23,42,0.7)",
          border: "1px solid rgba(148,163,184,0.18)",
          borderRadius: "8px",
          overflowX: "auto",
          fontFamily: "JetBrains Mono, Menlo, monospace",
          fontSize: "11.5px",
          color: "#cbd5e1",
          lineHeight: 1.55,
        }}
      >
        <code data-lang={lang}>{children}</code>
      </pre>
      <button
        onClick={onCopy}
        style={{
          position: "absolute", top: "6px", right: "6px",
          background: "rgba(15,23,42,0.9)",
          border: "1px solid rgba(148,163,184,0.18)",
          color: copied ? "#4ade80" : "#94a3b8",
          fontSize: "9px", letterSpacing: "0.1em", textTransform: "uppercase",
          padding: "3px 7px", borderRadius: "4px", cursor: "pointer",
          transition: "color 0.15s ease",
        }}
      >
        {copied ? "Copied" : "Copy"}
      </button>
    </div>
  );
}

// ─── Endpoint data model ─────────────────────────────────────────────────────

interface EndpointSpec {
  title:        string;            // friendly name shown on the tile
  blurb:        string;            // one-liner shown on the tile
  method:       "GET" | "POST";
  path:         string;            // technical path, only shown in modal
  summary:      string;            // longer description shown in modal
  example:      string;            // curl snippet shown in modal
  responseHint?: string;
  icon:         string;            // single emoji-free glyph for the tile
}

const methodColorFor = (m: string) =>
  m === "GET"  ? "#4ade80" :
  m === "POST" ? "#facc15" :
                 "#a78bfa";

// ─── Endpoint tile (compact card on the grid) ────────────────────────────────

function EndpointTile({ spec, onClick }: { spec: EndpointSpec; onClick: () => void }) {
  const color = methodColorFor(spec.method);
  return (
    <button
      onClick={onClick}
      style={{
        textAlign: "left",
        background: "rgba(8,10,24,0.6)",
        border: "1px solid rgba(148,163,184,0.14)",
        borderRadius: "12px",
        padding: "16px 16px 14px",
        display: "flex", flexDirection: "column", gap: "8px",
        cursor: "pointer",
        color: "inherit",
        fontFamily: "inherit",
        position: "relative",
        transition: "transform 0.12s ease, border-color 0.12s ease, background 0.12s ease",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = `${color}55`;
        e.currentTarget.style.background  = "rgba(8,10,24,0.85)";
        e.currentTarget.style.transform   = "translateY(-1px)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = "rgba(148,163,184,0.14)";
        e.currentTarget.style.background  = "rgba(8,10,24,0.6)";
        e.currentTarget.style.transform   = "translateY(0)";
      }}
    >
      {/* method dot in corner */}
      <span
        title={spec.method}
        style={{
          position: "absolute", top: "12px", right: "12px",
          width: "7px", height: "7px", borderRadius: "50%",
          background: color, boxShadow: `0 0 6px ${color}`,
        }}
      />

      <span style={{ fontSize: "22px", lineHeight: 1, color, fontWeight: 700, fontFamily: "JetBrains Mono, Menlo, monospace" }}>
        {spec.icon}
      </span>

      <h3 style={{ margin: 0, fontSize: "14px", fontWeight: 700, color: "#f1f5f9", letterSpacing: "-0.005em" }}>
        {spec.title}
      </h3>

      <p style={{ margin: 0, fontSize: "11px", color: "#94a3b8", lineHeight: 1.45 }}>
        {spec.blurb}
      </p>

      <span style={{ marginTop: "auto", paddingTop: "6px", fontSize: "9px", letterSpacing: "0.12em", textTransform: "uppercase", color: "#64748b" }}>
        View details →
      </span>
    </button>
  );
}

// ─── Endpoint modal (full details) ───────────────────────────────────────────

function EndpointModal({ spec, onClose }: { spec: EndpointSpec; onClose: () => void }) {
  const color = methodColorFor(spec.method);

  // Close on Escape
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
      style={{
        position: "fixed", inset: 0, zIndex: 998,
        background: "rgba(2,4,16,0.78)", backdropFilter: "blur(6px)",
        display: "flex", alignItems: "center", justifyContent: "center",
        padding: "20px",
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="endpoint-modal-title"
        style={{
          width: "100%", maxWidth: "640px", maxHeight: "85vh",
          overflow: "auto",
          background: "rgba(8,10,24,0.98)",
          border: `1px solid ${color}33`,
          borderRadius: "14px",
          padding: "22px 24px 20px",
          fontFamily: "Inter, system-ui, sans-serif",
          color: "#e2e8f0",
          boxShadow: `0 20px 60px rgba(0,0,0,0.7), 0 0 28px ${color}22`,
        }}
      >
        {/* Header */}
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: "16px", marginBottom: "12px" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: "6px", minWidth: 0 }}>
            <h2 id="endpoint-modal-title" style={{ margin: 0, fontSize: "18px", fontWeight: 700 }}>
              {spec.title}
            </h2>
            <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
              <span
                style={{
                  fontSize: "10px", fontWeight: 800, fontFamily: "monospace",
                  letterSpacing: "0.08em", color, background: `${color}18`,
                  padding: "3px 7px", borderRadius: "4px",
                }}
              >
                {spec.method}
              </span>
              <code style={{ fontSize: "12.5px", color: "#cbd5e1", fontFamily: "JetBrains Mono, Menlo, monospace", wordBreak: "break-all" }}>
                {spec.path}
              </code>
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            style={{
              background: "none", border: "none", color: "#64748b",
              fontSize: "22px", cursor: "pointer", padding: "0 4px", lineHeight: 1,
              flexShrink: 0,
            }}
          >
            ×
          </button>
        </div>

        {/* Description */}
        <p style={{ margin: "0 0 14px", fontSize: "12.5px", color: "#94a3b8", lineHeight: 1.6 }}>
          {spec.summary}
        </p>

        {/* Example */}
        <p style={{ margin: "12px 0 6px", fontSize: "10px", textTransform: "uppercase", letterSpacing: "0.1em", color: "#64748b" }}>
          Example
        </p>
        <CodeBlock>{spec.example}</CodeBlock>

        {/* Response hint */}
        {spec.responseHint && (
          <p style={{ margin: "12px 0 0", fontSize: "11px", color: "#64748b", fontStyle: "italic" }}>
            {spec.responseHint}
          </p>
        )}
      </div>
    </div>
  );
}

// ─── Issued-key reveal panel ─────────────────────────────────────────────────

function KeyReveal({ issued, onClose }: { issued: IssuedKey; onClose: () => void }) {
  const [revealed, setRevealed] = useState(false);
  const [copied, setCopied] = useState(false);

  const masked = `ov_${"•".repeat(48)}`;
  const display = revealed ? issued.apiKey : masked;

  const copyKey = () => {
    navigator.clipboard.writeText(issued.apiKey).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    });
  };

  return (
    <div
      style={{
        position: "fixed", inset: 0, zIndex: 999,
        background: "rgba(2,4,16,0.84)", backdropFilter: "blur(8px)",
        display: "flex", alignItems: "center", justifyContent: "center",
        padding: "20px", fontFamily: "Inter, system-ui, sans-serif",
      }}
    >
      <div
        style={{
          width: "100%", maxWidth: "560px",
          background: "rgba(8,10,24,0.98)",
          border: "1px solid rgba(74,222,128,0.4)",
          borderRadius: "14px",
          padding: "24px",
          color: "#e2e8f0",
          boxShadow: "0 20px 60px rgba(0,0,0,0.7), 0 0 32px rgba(74,222,128,0.12)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "8px" }}>
          <span style={{ width: "10px", height: "10px", borderRadius: "50%", background: "#4ade80", boxShadow: "0 0 10px #4ade80" }} />
          <h2 style={{ margin: 0, fontSize: "16px", fontWeight: 700 }}>
            API key issued for {issued.name}
          </h2>
        </div>
        <p style={{ margin: "0 0 16px", fontSize: "11px", color: "#94a3b8", lineHeight: 1.55 }}>
          Save this key now. It will not be shown again. If you lose it, sign up with a different
          email — keys cannot be recovered.
        </p>

        <div
          style={{
            display: "flex", alignItems: "center", gap: "8px",
            background: "rgba(15,23,42,0.7)",
            border: "1px solid rgba(74,222,128,0.25)",
            borderRadius: "8px", padding: "10px 12px",
            fontFamily: "JetBrains Mono, Menlo, monospace",
            fontSize: "12px", color: "#4ade80",
            wordBreak: "break-all",
          }}
        >
          <span style={{ flex: 1 }}>{display}</span>
          <button
            onClick={() => setRevealed((r) => !r)}
            style={{
              background: "rgba(15,23,42,0.9)", border: "1px solid rgba(148,163,184,0.18)",
              color: "#94a3b8", fontSize: "9px", letterSpacing: "0.1em", textTransform: "uppercase",
              padding: "3px 7px", borderRadius: "4px", cursor: "pointer",
            }}
          >
            {revealed ? "Hide" : "Show"}
          </button>
          <button
            onClick={copyKey}
            style={{
              background: "rgba(15,23,42,0.9)", border: "1px solid rgba(148,163,184,0.18)",
              color: copied ? "#4ade80" : "#94a3b8",
              fontSize: "9px", letterSpacing: "0.1em", textTransform: "uppercase",
              padding: "3px 7px", borderRadius: "4px", cursor: "pointer",
            }}
          >
            {copied ? "Copied" : "Copy"}
          </button>
        </div>

        <div style={{ marginTop: "16px" }}>
          <p style={{ margin: "0 0 6px", fontSize: "10px", textTransform: "uppercase", letterSpacing: "0.1em", color: "#64748b" }}>
            Test it now
          </p>
          <CodeBlock>{`curl -H "x-api-key: ${revealed ? issued.apiKey : "<your-key>"}" \\
  "${API_BASE_PUBLIC}/v1/me"`}</CodeBlock>
        </div>

        <button
          onClick={onClose}
          style={{
            marginTop: "18px", width: "100%",
            padding: "10px 14px", fontSize: "12px", fontWeight: 700,
            letterSpacing: "0.06em", textTransform: "uppercase",
            background: "transparent", color: "#94a3b8",
            border: "1px solid rgba(148,163,184,0.25)", borderRadius: "8px",
            cursor: "pointer",
          }}
        >
          I have saved my key — close
        </button>
      </div>
    </div>
  );
}

// ─── ApiDocsPage ─────────────────────────────────────────────────────────────

// ─── Endpoint catalog ────────────────────────────────────────────────────────

const ENDPOINTS: EndpointSpec[] = [
  {
    title:   "All Stories",
    blurb:   "Search the global feed by region, category, date range, breaking flag, or heat score.",
    method:  "GET",
    path:    "/v1/stories",
    summary: "Paginated story search. Filter by region, category, country, date range, breaking-only, or minimum heat score. Default window is the last 7 days when no dates are supplied.",
    example: `# Tamil Nadu politics — last 7 days
curl -H "x-api-key: $OV_KEY" \\
  "${API_BASE_PUBLIC}/v1/stories?region=IN-TN&category=POLITICS&limit=50"`,
    responseHint: "Returns { total, offset, limit, stories: StoryOut[] }",
    icon: "{ }",
  },
  {
    title:   "Breaking News",
    blurb:   "Last 24h of breaking-news stories, sorted by heat score.",
    method:  "GET",
    path:    "/v1/breaking",
    summary: "Returns stories the AI flagged as breaking in the last 24 hours, sorted by heat_score (highest first). Region and category filters are supported.",
    example: `curl -H "x-api-key: $OV_KEY" \\
  "${API_BASE_PUBLIC}/v1/breaking?category=HEALTH&limit=10"`,
    icon: "!",
  },
  {
    title:   "Single Story",
    blurb:   "Look up one story by its document ID.",
    method:  "GET",
    path:    "/v1/stories/{id}",
    summary: "Fetch a single story by its Firestore document ID. The id is the dedup_group_id field on a StoryOut object.",
    example: `curl -H "x-api-key: $OV_KEY" \\
  "${API_BASE_PUBLIC}/v1/stories/0123abcd4567ef89"`,
    icon: "#",
  },
  {
    title:   "Regions",
    blurb:   "All supported regions (countries + subdivisions like IN-TN).",
    method:  "GET",
    path:    "/v1/regions",
    summary: "Returns the catalog of supported region codes — countries and subdivisions like IN-TN, US-CA, GB-ENG. Use these codes as the region filter on /v1/stories.",
    example: `curl -H "x-api-key: $OV_KEY" \\
  "${API_BASE_PUBLIC}/v1/regions"`,
    icon: "@",
  },
  {
    title:   "Categories",
    blurb:   "The seven story categories with display labels.",
    method:  "GET",
    path:    "/v1/categories",
    summary: "Returns the seven story category codes (WORLD, POLITICS, SCIENCE_TECH, BUSINESS, HEALTH, ENTERTAINMENT, SPORTS) with display labels.",
    example: `curl -H "x-api-key: $OV_KEY" \\
  "${API_BASE_PUBLIC}/v1/categories"`,
    icon: "★",
  },
  {
    title:   "Sign Up",
    blurb:   "Mint a community API key. Returned exactly once.",
    method:  "POST",
    path:    "/v1/auth/signup",
    summary: "Create a community-tier account and receive an API key. The raw key is returned exactly once — store it immediately. Lost keys can only be replaced by signing up with a new email.",
    example: `curl -X POST "${API_BASE_PUBLIC}/v1/auth/signup" \\
  -H "Content-Type: application/json" \\
  -d '{"name":"Ada Lovelace","email":"ada@example.com"}'`,
    icon: "+",
  },
  {
    title:   "Verify Key",
    blurb:   "Echo identity for the supplied key. Useful for setup checks.",
    method:  "GET",
    path:    "/v1/me",
    summary: "Validates the x-api-key header and returns the calling user's identity (name, email, access level, rate limit). Use this for client setup smoke tests.",
    example: `curl -H "x-api-key: $OV_KEY" \\
  "${API_BASE_PUBLIC}/v1/me"`,
    icon: "?",
  },
];

export function ApiDocsPage() {
  const [signupOpen, setSignupOpen] = useState(false);
  const [issued,     setIssued]     = useState<IssuedKey | null>(null);
  const [activeIdx,  setActiveIdx]  = useState<number | null>(null);

  const onSignupSuccess = (apiKey: string, email: string, name: string) => {
    setSignupOpen(false);
    setIssued({ apiKey, email, name });
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "#020410",
        color: "#e2e8f0",
        fontFamily: "Inter, system-ui, sans-serif",
        padding: "32px 20px 80px",
      }}
    >
      <div style={{ maxWidth: "920px", margin: "0 auto" }}>

        {/* Top nav */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "24px" }}>
          <Link to="/" style={{ fontSize: "11px", color: "#94a3b8", textDecoration: "none", letterSpacing: "0.08em", textTransform: "uppercase" }}>
            ← Back to globe
          </Link>
          <span style={{ fontSize: "10px", color: "#475569", fontFamily: "monospace", letterSpacing: "0.1em" }}>
            v1 · public REST API
          </span>
        </div>

        {/* Hero */}
        <header style={{ marginBottom: "32px" }}>
          <h1 style={{ margin: "0 0 8px", fontSize: "28px", fontWeight: 800, letterSpacing: "-0.01em" }}>
            OmnesVident <span style={{ color: "#a78bfa" }}>Public API</span>
          </h1>
          <p style={{ margin: 0, fontSize: "14px", color: "#94a3b8", lineHeight: 1.6, maxWidth: "640px" }}>
            Real-time, geo-located, AI-classified global news as JSON.
            Filter by region, category, date range, breaking-news status, and heat score.
            Authenticate every request with an <code style={{ color: "#a78bfa", fontFamily: "monospace" }}>x-api-key</code> header.
          </p>

          <div style={{ marginTop: "20px", display: "flex", gap: "10px", flexWrap: "wrap", alignItems: "center" }}>
            <button
              onClick={() => setSignupOpen(true)}
              style={{
                padding: "10px 18px",
                fontSize: "12px", fontWeight: 700, letterSpacing: "0.06em", textTransform: "uppercase",
                background: "#a78bfa", color: "#0f0f23",
                border: "none", borderRadius: "8px", cursor: "pointer",
                boxShadow: "0 0 16px rgba(167,139,250,0.35)",
              }}
            >
              Get an API key
            </button>
            <a
              href={`${API_BASE_PUBLIC}/docs`}
              target="_blank" rel="noopener noreferrer"
              style={{
                padding: "10px 14px", fontSize: "12px", fontWeight: 700,
                letterSpacing: "0.06em", textTransform: "uppercase",
                color: "#94a3b8", border: "1px solid rgba(148,163,184,0.25)",
                borderRadius: "8px", textDecoration: "none",
              }}
            >
              OpenAPI / Swagger ↗
            </a>
          </div>

          <p style={{ marginTop: "16px", fontSize: "11px", color: "#64748b", lineHeight: 1.55 }}>
            Community tier: <strong style={{ color: "#cbd5e1" }}>5 requests / minute</strong>.
            Need more? Contact us about partner access.
          </p>
        </header>

        {/* Auth section */}
        <h2 style={{ fontSize: "11px", letterSpacing: "0.16em", textTransform: "uppercase", color: "#475569", margin: "32px 0 14px" }}>
          Authentication
        </h2>
        <p style={{ margin: "0 0 14px", fontSize: "12.5px", color: "#94a3b8", lineHeight: 1.6 }}>
          Every request must include an <code style={{ color: "#a78bfa", fontFamily: "monospace" }}>x-api-key</code> header.
          Requests without a valid key receive HTTP 401. Requests over your rate limit receive HTTP 429 with a <code style={{ color: "#a78bfa", fontFamily: "monospace" }}>Retry-After</code> seconds header.
        </p>
        <CodeBlock>{`curl -H "x-api-key: ov_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" \\
  "${API_BASE_PUBLIC}/v1/me"`}</CodeBlock>

        {/* Endpoints */}
        <h2 style={{ fontSize: "11px", letterSpacing: "0.16em", textTransform: "uppercase", color: "#475569", margin: "32px 0 14px" }}>
          Endpoints
        </h2>
        <p style={{ margin: "-8px 0 14px", fontSize: "11px", color: "#64748b", lineHeight: 1.5 }}>
          Click any tile for the full path, parameters, and a copy-paste curl example.
        </p>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))",
            gap: "12px",
          }}
        >
          {ENDPOINTS.map((ep, i) => (
            <EndpointTile key={ep.path + ep.method} spec={ep} onClick={() => setActiveIdx(i)} />
          ))}
        </div>

        {/* Story shape */}
        <h2 style={{ fontSize: "11px", letterSpacing: "0.16em", textTransform: "uppercase", color: "#475569", margin: "32px 0 14px" }}>
          Story object
        </h2>
        <CodeBlock lang="json">{`{
  "dedup_group_id":   "0123abcd4567ef89",
  "title":            "Tamil Nadu Assembly passes…",
  "snippet":          "Chennai — In a session marked by …",
  "source_url":       "https://…",
  "source_name":      "The Hindu",
  "region_code":      "IN-TN",
  "category":         "POLITICS",
  "mentioned_regions": ["IN-TN"],
  "secondary_sources": ["NDTV"],
  "timestamp":        "2026-04-28T11:24:00Z",
  "processed_at":     "2026-04-28T11:42:18Z",
  "latitude":         13.0827,
  "longitude":        80.2707,
  "is_breaking":      false,
  "heat_score":       42
}`}</CodeBlock>

        <p style={{ marginTop: "32px", fontSize: "11px", color: "#475569", textAlign: "center" }}>
          Built with care · OmnesVident · v1
        </p>

      </div>

      <SignupModal
        open={signupOpen}
        onClose={() => setSignupOpen(false)}
        onSuccess={onSignupSuccess}
      />
      {issued && <KeyReveal issued={issued} onClose={() => setIssued(null)} />}
      {activeIdx !== null && (
        <EndpointModal spec={ENDPOINTS[activeIdx]} onClose={() => setActiveIdx(null)} />
      )}
    </div>
  );
}

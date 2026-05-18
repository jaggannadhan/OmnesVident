import { Link } from "react-router-dom";
import { CATEGORY_META } from "./NewsCard";

// Site-wide footer. Intel Nodes mirrors the in-header category nav: clicking
// a category jumps the user back to the top of the feed with that category
// pre-selected. Legal Protocols currently links to the Privacy Policy only.

// Keep in sync with HeaderCategoryNav's ORDER.
const CATEGORY_ORDER = ["WORLD", "POLITICS", "SCIENCE_TECH", "BUSINESS", "HEALTH", "ENTERTAINMENT", "SPORTS"];

interface AppFooterProps {
  onCategorySelect?: (category: string | undefined) => void;
}

export function AppFooter({ onCategorySelect }: AppFooterProps) {
  function handleCategoryClick(key: string) {
    onCategorySelect?.(key);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  return (
    <footer className="bg-base border-t border-rim mt-auto">
      <div className="max-w-[1440px] mx-auto px-8 py-12">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-10">

          <div>
            <Link to="/" className="flex items-center gap-2.5" style={{ color: "var(--color-text)", cursor: "pointer" }}>
              <span
                className="font-headline text-2xl font-bold tracking-tighter leading-none"
                style={{ cursor: "pointer" }}
              >
                <span className="hover:text-accent transition-colors" style={{ cursor: "pointer" }}>Omnes</span>
                <span className="hover:text-accent transition-colors" style={{ cursor: "pointer" }}>Vident</span>
              </span>
              <img
                src="/favicon.png"
                alt=""
                aria-hidden="true"
                className="w-7 h-7 object-contain"
                style={{ cursor: "pointer" }}
              />
            </Link>
            <p className="font-mono text-[10px] mt-3 uppercase tracking-[0.2em] leading-loose" style={{ color: "var(--color-text)", opacity: 0.65 }}>
              DEFINED BY INTELLECTUAL AUTHORITY.<br />
              OPERATING UNDER ZERO-NOISE PROTOCOLS.
            </p>
          </div>

          {/* Intel Nodes — categories that jump to the top with the filter applied */}
          <div className="flex flex-col gap-3">
            <span className="font-mono text-[11px] font-bold uppercase tracking-widest mb-1" style={{ color: "var(--color-text)" }}>
              INTEL NODES
            </span>
            {CATEGORY_ORDER.map((key) => {
              const meta = CATEGORY_META[key];
              if (!meta) return null;
              return (
                <button
                  key={key}
                  onClick={() => handleCategoryClick(key)}
                  className="font-mono text-[11px] uppercase hover:text-accent transition-colors text-left"
                  style={{ color: "var(--color-text)", opacity: 0.7 }}
                >
                  {meta.label}
                </button>
              );
            })}
          </div>

          <div className="flex flex-col gap-3">
            <span className="font-mono text-[11px] font-bold uppercase tracking-widest mb-1" style={{ color: "var(--color-text)" }}>
              LEGAL PROTOCOLS
            </span>
            <Link to="/privacy" className="font-mono text-[11px] uppercase hover:text-accent transition-colors" style={{ color: "var(--color-text)", opacity: 0.7 }}>
              PRIVACY POLICY
            </Link>
          </div>

          <div className="flex flex-col gap-3">
            <span className="font-mono text-[11px] font-bold uppercase tracking-widest mb-1" style={{ color: "var(--color-text)" }}>
              CONNECT
            </span>
            <Link to="/api-docs" className="font-mono text-[11px] uppercase hover:text-accent transition-colors" style={{ color: "var(--color-text)", opacity: 0.7 }}>
              API ACCESS
            </Link>
            <a
              href="https://www.linkedin.com/in/jvenu94/"
              target="_blank"
              rel="noopener noreferrer"
              className="font-mono text-[11px] uppercase hover:text-accent transition-colors"
              style={{ color: "var(--color-text)", opacity: 0.7 }}
            >
              CONTACT
            </a>
          </div>
        </div>

        <div className="mt-12 pt-6 border-t border-rim/70 flex flex-col md:flex-row justify-between items-center gap-3">
          <p className="font-mono text-[9px] uppercase tracking-widest" style={{ color: "var(--color-text)", opacity: 0.55 }}>
            © {new Date().getFullYear()} OMNESVIDENT. See Everything.
          </p>
          <div className="flex gap-6">
            <span className="font-mono text-[9px] uppercase" style={{ color: "var(--color-text)", opacity: 0.45 }}>
              SYSTEM STATUS: OPTIMAL
            </span>
            <span className="font-mono text-[9px] uppercase" style={{ color: "var(--color-text)", opacity: 0.45 }}>
              LATENCY: 12MS
            </span>
          </div>
        </div>
      </div>
    </footer>
  );
}


import { useState, useCallback, lazy, Suspense } from "react";
import { useNavigate, useParams, Routes, Route, Navigate } from "react-router-dom";
import { Sidebar } from "./components/Sidebar";
import { NewsGrid } from "./components/NewsGrid";
import { WorldMap } from "./components/WorldMap";
import { GlobeErrorBoundary } from "./components/visualizer/GlobeErrorBoundary";

// Lazy-load the heavy R3F bundle so it doesn't block the initial paint
const GlobeScene = lazy(() =>
  import("./components/visualizer/GlobeScene").then((m) => ({ default: m.GlobeScene }))
);

// ---------------------------------------------------------------------------
// Mobile menu icon
// ---------------------------------------------------------------------------

function MenuIcon({ open }: { open: boolean }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5" aria-hidden="true">
      {open ? (
        <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
      ) : (
        <path fillRule="evenodd" d="M2 4.75A.75.75 0 012.75 4h14.5a.75.75 0 010 1.5H2.75A.75.75 0 012 4.75zm0 10.5a.75.75 0 01.75-.75h14.5a.75.75 0 010 1.5H2.75a.75.75 0 01-.75-.75zM2 10a.75.75 0 01.75-.75h14.5a.75.75 0 010 1.5H2.75A.75.75 0 012 10z" clipRule="evenodd" />
      )}
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Main feed view (region is an optional route param)
// ---------------------------------------------------------------------------

function FeedView() {
  const { regionCode } = useParams<{ regionCode?: string }>();
  const navigate = useNavigate();

  const [category, setCategory] = useState<string | undefined>();
  const [offset, setOffset] = useState(0);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [globeOpen, setGlobeOpen] = useState(true);

  const handleRegionSelect = useCallback(
    (region: string | undefined) => {
      setOffset(0);
      if (region) {
        navigate(`/region/${region}`);
      } else {
        navigate("/");
      }
      setSidebarOpen(false);
    },
    [navigate]
  );

  const handleCategorySelect = useCallback((cat: string | undefined) => {
    setCategory(cat);
    setOffset(0);
  }, []);

  const handleCategoryClick = useCallback((cat: string) => {
    setCategory((prev) => (prev === cat ? undefined : cat));
    setOffset(0);
  }, []);

  return (
    <div className="flex h-screen bg-base overflow-hidden">

      {/* ── Sidebar (desktop: static, mobile: overlay) ── */}
      <div
        className={`
          fixed inset-0 z-40 bg-base/80 backdrop-blur-sm lg:hidden
          transition-opacity duration-200
          ${sidebarOpen ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none"}
        `}
        aria-hidden={!sidebarOpen}
        onClick={() => setSidebarOpen(false)}
      />

      <nav
        className={`
          fixed top-0 left-0 z-50 h-full w-64 bg-surface border-r border-rim
          transform transition-transform duration-200 ease-out
          lg:relative lg:translate-x-0 lg:flex lg:flex-col
          ${sidebarOpen ? "translate-x-0" : "-translate-x-full"}
        `}
        aria-label="Navigation"
      >
        <Sidebar
          selectedCategory={category}
          selectedRegion={regionCode}
          onCategorySelect={handleCategorySelect}
          onRegionSelect={handleRegionSelect}
        />
      </nav>

      {/* ── Main content ── */}
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">

        {/* Top bar */}
        <header className="flex items-center gap-3 px-4 py-3 border-b border-rim bg-surface/80 backdrop-blur-sm shrink-0">
          {/* Mobile menu toggle */}
          <button
            onClick={() => setSidebarOpen((p) => !p)}
            className="lg:hidden p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-panel transition-colors"
            aria-label={sidebarOpen ? "Close menu" : "Open menu"}
            aria-expanded={sidebarOpen}
          >
            <MenuIcon open={sidebarOpen} />
          </button>

          {/* Breadcrumb */}
          <div className="flex items-center gap-2 text-sm min-w-0">
            <span className="text-slate-500">Feed</span>
            {regionCode && (
              <>
                <span className="text-slate-700">/</span>
                <span className="font-mono font-semibold text-cyan-400">{regionCode}</span>
              </>
            )}
            {category && (
              <>
                <span className="text-slate-700">/</span>
                <span className="text-slate-300">{category}</span>
              </>
            )}
          </div>

          {/* View toggle + live indicator */}
          <div className="ml-auto flex items-center gap-3">
            <button
              onClick={() => setGlobeOpen((p) => !p)}
              className={`hidden md:inline-flex items-center gap-1.5 text-[10px] font-mono px-2.5 py-1 rounded-md border transition-colors ${
                globeOpen
                  ? "border-cyan-500/40 text-cyan-400 bg-cyan-400/10"
                  : "border-rim text-slate-500 hover:text-slate-300 hover:border-rim-bright"
              }`}
              title={globeOpen ? "Hide globe" : "Show globe"}
            >
              🌐 {globeOpen ? "Globe on" : "Globe off"}
            </button>
            <div className="flex items-center gap-1.5 text-[10px] text-slate-600 font-mono">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse_slow" aria-hidden="true" />
              LIVE · 5m
            </div>
          </div>
        </header>

        {/* Scrollable body */}
        <main className="flex-1 overflow-y-auto p-4 lg:p-6">
          <div className="max-w-7xl mx-auto flex flex-col gap-5">

            {/* 3D Globe — hidden on small screens, toggleable */}
            {globeOpen && (
              <div className="hidden md:block">
                <GlobeErrorBoundary>
                  <Suspense
                    fallback={
                      <div className="w-full rounded-xl border border-rim bg-base flex items-center justify-center text-slate-600 text-xs font-mono" style={{ height: 480 }}>
                        Loading 3D engine…
                      </div>
                    }
                  >
                    <GlobeScene region={regionCode} />
                  </Suspense>
                </GlobeErrorBoundary>
              </div>
            )}

            {/* Fallback tile map (mobile only) */}
            <div className="md:hidden">
              <WorldMap
                selectedRegion={regionCode}
                onRegionSelect={handleRegionSelect}
              />
            </div>

            <NewsGrid
              region={regionCode}
              category={category}
              offset={offset}
              limit={24}
              onOffsetChange={setOffset}
              onCategoryClick={handleCategoryClick}
              onRegionClick={handleRegionSelect}
            />
          </div>
        </main>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// App — router
// ---------------------------------------------------------------------------

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<FeedView />} />
      <Route path="/region/:regionCode" element={<FeedView />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

import { useState, useCallback, lazy, Suspense } from "react";
import { useNavigate, useParams, Routes, Route, Navigate, Link } from "react-router-dom";
import { Sidebar } from "./components/Sidebar";
import { NewsGrid } from "./components/NewsGrid";
import { WorldMap } from "./components/WorldMap";
import { GlobeErrorBoundary } from "./components/visualizer/GlobeErrorBoundary";
import { type DateRange } from "./components/GlobeControls";
import { BreakingNewsCarousel } from "./components/BreakingNewsCarousel";
import { ApiDocsPage } from "./components/ApiDocsPage";
import { ResetPasswordPage } from "./components/ResetPasswordPage";
import { AuthButton } from "./components/AuthButton";
import { useNews } from "./hooks/useNews";

// Lazy-load the heavy R3F bundle so it doesn't block the initial paint
const GlobeScene = lazy(() =>
  import("./components/visualizer/GlobeScene").then((m) => ({ default: m.GlobeScene }))
);

// ---------------------------------------------------------------------------
// GlobeWithCarousel — 70/30 layout: globe left, breaking carousel right
// ---------------------------------------------------------------------------

// When exactly one category is selected, the backend can filter server-side.
// For 0 or 2+ we fetch unfiltered and let consumers apply a client-side filter.
function apiCategoryOf(cats: string[]): string | undefined {
  return cats.length === 1 ? cats[0] : undefined;
}

function applyCategoryFilter<T extends { category: string }>(
  stories: T[],
  categories: string[],
): T[] {
  if (categories.length === 0) return stories;
  if (categories.length === 1) return stories;   // already filtered server-side
  return stories.filter((s) => categories.includes(s.category));
}

interface GlobeWithCarouselProps {
  regionCode?: string;
  categories: string[];
  dateRange: DateRange;
}

function GlobeWithCarousel({ regionCode, categories, dateRange }: GlobeWithCarouselProps) {
  const apiCategory = apiCategoryOf(categories);
  const { data } = useNews({
    region: regionCode,
    category: apiCategory,
    limit: 1000,
    start_date: dateRange.start,
    end_date: dateRange.end,
  });
  const visible = applyCategoryFilter(data?.stories ?? [], categories);
  const breakingStories = visible.filter((s) => s.is_breaking);

  return (
    <div style={{ display: "flex", gap: "12px", alignItems: "stretch", height: "480px" }}>
      {/* Breaking News Carousel — left 30%, only when breaking stories exist */}
      {breakingStories.length > 0 && (
        <div style={{ flex: "0 0 30%", minWidth: 0 }}>
          <BreakingNewsCarousel stories={breakingStories} />
        </div>
      )}

      {/* Globe — right 70%, or full width when no breaking stories */}
      <div style={{ flex: breakingStories.length > 0 ? "0 0 70%" : "1 1 100%", minWidth: 0 }}>
        <GlobeErrorBoundary>
          <Suspense
            fallback={
              <div
                className="w-full rounded-xl border border-rim bg-base flex items-center justify-center text-slate-600 text-xs font-mono"
                style={{ height: "100%" }}
              >
                Loading 3D engine…
              </div>
            }
          >
            <GlobeScene
              region={regionCode}
              categories={categories}
              startDate={dateRange.start}
              endDate={dateRange.end}
            />
          </Suspense>
        </GlobeErrorBoundary>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// MobileBreakingNews — compact carousel shown above the mobile feed.
// React Query dedupes the underlying useNews call against GlobeWithCarousel.
// ---------------------------------------------------------------------------

function MobileBreakingNews({ regionCode, categories, dateRange }: GlobeWithCarouselProps) {
  const apiCategory = apiCategoryOf(categories);
  const { data } = useNews({
    region: regionCode,
    category: apiCategory,
    limit: 1000,
    start_date: dateRange.start,
    end_date: dateRange.end,
  });
  const visible = applyCategoryFilter(data?.stories ?? [], categories);
  const breakingStories = visible.filter((s) => s.is_breaking);
  if (breakingStories.length === 0) return null;
  return (
    <div style={{ height: "260px" }}>
      <BreakingNewsCarousel stories={breakingStories} />
    </div>
  );
}

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

  const [categories, setCategories] = useState<string[]>([]);
  const [offset, setOffset] = useState(0);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [globeOpen, setGlobeOpen] = useState(true);
  const [dateRange, setDateRange] = useState<DateRange>(() => {
    // Default: full day today (midnight → 23:59:59 local)
    const d = new Date();
    const yyyy_mm_dd = d.toISOString().slice(0, 10);
    d.setHours(0, 0, 0, 0);
    const endD = new Date(`${yyyy_mm_dd}T23:59:59`);
    return { start: d.toISOString(), end: endD.toISOString() };
  });

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

  const handleCategoriesChange = useCallback((next: string[]) => {
    setCategories(next);
    setOffset(0);
  }, []);

  // Toggle a single category in/out of the multi-select (used by NewsCard chip click)
  const handleCategoryClick = useCallback((cat: string) => {
    setCategories((prev) =>
      prev.includes(cat) ? prev.filter((c) => c !== cat) : [...prev, cat]
    );
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
          fixed top-0 left-0 z-50 h-full bg-[#161a1d] border-r border-rim
          transform transition-all duration-200 ease-out overflow-hidden
          lg:relative lg:translate-x-0 lg:flex lg:flex-col lg:shrink-0
          ${sidebarOpen ? "translate-x-0 w-64" : "-translate-x-full w-64"}
          ${sidebarCollapsed ? "lg:w-0 lg:border-r-0" : "lg:w-64 lg:translate-x-0"}
        `}
        aria-label="Navigation"
      >
        <Sidebar
          selectedCategories={categories}
          selectedRegion={regionCode}
          dateRange={dateRange}
          onCategoriesChange={handleCategoriesChange}
          onRegionSelect={handleRegionSelect}
          onDateRangeChange={(r) => { setDateRange(r); setOffset(0); }}
        />
      </nav>

      {/* ── Main content ── */}
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">

        {/* Top bar */}
        <header className="flex items-center gap-3 px-4 py-3 border-b border-rim bg-surface/80 backdrop-blur-sm shrink-0">
          {/* Desktop sidebar collapse toggle */}
          <button
            onClick={() => setSidebarCollapsed((p) => !p)}
            className="hidden lg:flex p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-panel transition-colors shrink-0"
            aria-label={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
            title={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5" aria-hidden="true">
              {sidebarCollapsed ? (
                <path fillRule="evenodd" d="M3 5a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zM3 10a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zM3 15a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1z" clipRule="evenodd" />
              ) : (
                <path fillRule="evenodd" d="M3 5a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zM3 10a1 1 0 011-1h6a1 1 0 110 2H4a1 1 0 01-1-1zM3 15a1 1 0 011-1h6a1 1 0 110 2H4a1 1 0 01-1-1z" clipRule="evenodd" />
              )}
            </svg>
          </button>

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
            {categories.length === 1 && (
              <>
                <span className="text-slate-700">/</span>
                <span className="text-slate-300">{categories[0]}</span>
              </>
            )}
            {categories.length > 1 && (
              <>
                <span className="text-slate-700">/</span>
                <span className="text-slate-300 font-mono text-xs">
                  {categories.length} categories
                </span>
              </>
            )}
          </div>

          {/* View toggle + live indicator (date filter lives in the sidebar) */}
          <div className="ml-auto flex items-center gap-3">
            {/* API docs link */}
            <Link
              to="/api-docs"
              className="hidden sm:inline-flex items-center gap-1.5 text-[10px] font-mono px-2.5 py-1 rounded-md border border-violet-500/30 text-violet-300 hover:bg-violet-500/10 hover:border-violet-500/60 transition-colors"
              title="Public REST API documentation"
            >
              {"</> API"}
            </Link>

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

            {/* Auth control — Log in pill when logged out, profile circle when logged in */}
            <AuthButton />
          </div>
        </header>

        {/* Scrollable body */}
        <main className="flex-1 overflow-y-auto p-4 lg:p-6">
          <div className="max-w-7xl mx-auto flex flex-col gap-5">

            {/* 3D Globe + Breaking News Carousel — hidden on small screens, toggleable */}
            {globeOpen && (
              <div className="hidden md:block">
                <GlobeWithCarousel
                  regionCode={regionCode}
                  categories={categories}
                  dateRange={dateRange}
                />
              </div>
            )}

            {/* Mobile-only: breaking news first, then tile-map navigator */}
            <div className="md:hidden flex flex-col gap-4">
              <MobileBreakingNews
                regionCode={regionCode}
                categories={categories}
                dateRange={dateRange}
              />
              <WorldMap
                selectedRegion={regionCode}
                onRegionSelect={handleRegionSelect}
              />
            </div>

            <NewsGrid
              region={regionCode}
              categories={categories}
              offset={offset}
              limit={24}
              startDate={dateRange.start}
              endDate={dateRange.end}
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
      <Route path="/api-docs" element={<ApiDocsPage />} />
      <Route path="/reset-password/:token" element={<ResetPasswordPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

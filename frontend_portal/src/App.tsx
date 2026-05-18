import { useState, useCallback, lazy, Suspense } from "react";
import { useNavigate, useParams, Routes, Route, Navigate } from "react-router-dom";
import { AppHeader } from "./components/AppHeader";
import { NewsGrid } from "./components/NewsGrid";
import { SystemBriefing } from "./components/SystemBriefing";
import { BreakingNewsSection } from "./components/BreakingNewsSection";
import { IntelChannels } from "./components/IntelChannels";
import { AppFooter } from "./components/AppFooter";
import { GlobeErrorBoundary } from "./components/visualizer/GlobeErrorBoundary";
import { type DateRange } from "./components/GlobeControls";
import { ApiDocsPage } from "./components/ApiDocsPage";
import { ResetPasswordPage } from "./components/ResetPasswordPage";
import { PrivacyPolicyPage } from "./components/PrivacyPolicyPage";

// Lazy-load the heavy R3F bundle so it doesn't block the initial paint
const GlobeScene = lazy(() =>
  import("./components/visualizer/GlobeScene").then((m) => ({ default: m.GlobeScene }))
);

// ---------------------------------------------------------------------------
// Main feed view
// ---------------------------------------------------------------------------

function FeedView() {
  const { regionCode } = useParams<{ regionCode?: string }>();
  const navigate = useNavigate();

  const [category, setCategory] = useState<string | undefined>(undefined);
  const [offset, setOffset] = useState(0);
  const [dateRange, setDateRange] = useState<DateRange>(() => {
    // Default: last 30 days. "Today" was too narrow — it surfaced only the
    // stories ingested in the last few hours, which made the feed look empty.
    const start = new Date();
    start.setHours(0, 0, 0, 0);
    start.setDate(start.getDate() - 30);
    return { start: start.toISOString(), end: undefined };
  });

  const handleRegionSelect = useCallback(
    (region: string | undefined) => {
      setOffset(0);
      if (region) navigate(`/region/${region}`);
      else navigate("/");
    },
    [navigate],
  );

  const handleCategoryChange = useCallback((next: string | undefined) => {
    setCategory(next);
    setOffset(0);
  }, []);

  // Clicking a category chip on a card sets that as the single active filter,
  // or clears it if it was already active.
  const handleCategoryClick = useCallback((cat: string) => {
    setCategory((prev) => (prev === cat ? undefined : cat));
    setOffset(0);
  }, []);

  // NewsGrid + GlobeScene both still accept a string[] for forward compatibility,
  // even though the UI is now single-select.
  const categoriesArr = category ? [category] : [];

  return (
    <div className="flex flex-col min-h-screen bg-base">

      <AppHeader
        selectedCategory={category}
        onCategoryChange={handleCategoryChange}
        selectedRegion={regionCode}
        onRegionSelect={handleRegionSelect}
        dateRange={dateRange}
        onDateRangeChange={(r) => { setDateRange(r); setOffset(0); }}
      />

      <main className="flex-grow w-full max-w-[1440px] mx-auto flex flex-col lg:flex-row">

        {/* Left: primary intel feed (2/3) */}
        <section className="flex-grow lg:w-2/3 lg:border-r lg:border-rim">
          <div className="px-6 py-4 border-b border-rim bg-panel/30 backdrop-blur-md">
            <h2 className="font-mono text-[10px] uppercase tracking-[0.3em] font-bold" style={{ color: "var(--color-text)", opacity: 0.55 }}>
              PRIMARY INTEL STREAM
            </h2>
          </div>
          <div className="px-6 py-6">
            <NewsGrid
              region={regionCode}
              categories={categoriesArr}
              offset={offset}
              limit={24}
              startDate={dateRange.start}
              endDate={dateRange.end}
              onOffsetChange={setOffset}
              onCategoryClick={handleCategoryClick}
              onRegionClick={handleRegionSelect}
            />
          </div>
        </section>

        {/* Right: aside (1/3) */}
        <aside className="lg:w-1/3 bg-panel/20 flex flex-col">

          <BreakingNewsSection
            regionCode={regionCode}
            categories={categoriesArr}
            dateRange={dateRange}
          />

          {/* The real R3F globe replaces the decorative wireframe from the mockup */}
          <section className="p-6 border-b border-rim">
            <h4 className="font-mono text-[10px] uppercase tracking-[0.3em] font-bold mb-4 flex justify-between items-center" style={{ color: "var(--color-text)", opacity: 0.6 }}>
              <span>GLOBAL INTELLIGENCE MAP</span>
              <span className="text-accent text-[8px] animate-pulse">LIVE</span>
            </h4>
            <div className="relative aspect-square w-full bg-card/40 border border-rim/70 overflow-hidden">
              <GlobeErrorBoundary>
                <Suspense
                  fallback={
                    <div className="w-full h-full flex items-center justify-center font-mono text-xs" style={{ color: "var(--color-text)", opacity: 0.5 }}>
                      Loading 3D engine…
                    </div>
                  }
                >
                  <GlobeScene
                    region={regionCode}
                    categories={categoriesArr}
                    startDate={dateRange.start}
                    endDate={dateRange.end}
                  />
                </Suspense>
              </GlobeErrorBoundary>
            </div>
          </section>

          <SystemBriefing />

          <IntelChannels />
        </aside>
      </main>

      <AppFooter onCategorySelect={handleCategoryChange} />
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
      <Route path="/privacy" element={<PrivacyPolicyPage />} />
      <Route path="/reset-password/:token" element={<ResetPasswordPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

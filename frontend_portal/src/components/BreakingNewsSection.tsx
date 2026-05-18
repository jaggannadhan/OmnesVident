import { BreakingNewsCarousel } from "./BreakingNewsCarousel";
import { type DateRange } from "./GlobeControls";
import { useNews } from "../hooks/useNews";

// Aside-section wrapper around BreakingNewsCarousel. Pulls the active feed
// query (wide limit so we have enough breaking items to surface), filters
// down to is_breaking, and renders nothing when there's nothing breaking.

interface BreakingNewsSectionProps {
  regionCode?: string;
  categories: string[];
  dateRange: DateRange;
}

export function BreakingNewsSection({ regionCode, categories, dateRange }: BreakingNewsSectionProps) {
  const apiCategory = categories.length === 1 ? categories[0] : undefined;
  const { data } = useNews({
    region: regionCode,
    category: apiCategory,
    limit: 1000,
    start_date: dateRange.start,
    end_date: dateRange.end,
  });

  // If 2+ categories are ever passed (current UI is single-select), filter client-side.
  const visible = categories.length >= 2
    ? (data?.stories ?? []).filter((s) => categories.includes(s.category))
    : (data?.stories ?? []);
  const breakingStories = visible.filter((s) => s.is_breaking);

  if (breakingStories.length === 0) return null;

  return (
    <section className="p-6 border-b border-rim">
      <h4 className="font-mono text-[10px] uppercase tracking-[0.3em] font-bold mb-4 flex justify-between items-center" style={{ color: "var(--color-text)", opacity: 0.6 }}>
        <span>BREAKING NEWS</span>
        <span className="text-accent text-[8px] animate-pulse">LIVE</span>
      </h4>
      <div style={{ height: "380px" }}>
        <BreakingNewsCarousel stories={breakingStories} />
      </div>
    </section>
  );
}

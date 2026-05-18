import { Link } from "react-router-dom";
import { AuthButton } from "./AuthButton";
import { HeaderCategoryNav } from "./HeaderCategoryNav";
import { RegionCombobox } from "./RegionCombobox";
import { GlobeControls, type DateRange } from "./GlobeControls";

interface AppHeaderProps {
  selectedCategory: string | undefined;
  onCategoryChange: (category: string | undefined) => void;
  selectedRegion: string | undefined;
  onRegionSelect: (region: string | undefined) => void;
  dateRange: DateRange;
  onDateRangeChange: (range: DateRange) => void;
}

export function AppHeader({
  selectedCategory,
  onCategoryChange,
  selectedRegion,
  onRegionSelect,
  dateRange,
  onDateRangeChange,
}: AppHeaderProps) {
  return (
    <header className="sticky top-0 z-50 bg-base/80 backdrop-blur-xl border-b border-rim">
      <div className="max-w-[1440px] mx-auto px-6">

        {/* Row 1 — brand + utility controls */}
        <div className="flex justify-between items-center py-4 gap-6">
          <Link
            to="/"
            className="flex items-center gap-2.5 shrink-0"
            style={{ color: "var(--color-text)", cursor: "pointer" }}
          >
            <span
              className="font-headline text-3xl font-bold tracking-tighter leading-none"
              style={{ cursor: "pointer" }}
            >
              <span className="hover:text-accent transition-colors" style={{ cursor: "pointer" }}>Omnes</span>
              <span className="hover:text-accent transition-colors" style={{ cursor: "pointer" }}>Vident</span>
            </span>
            <img
              src="/favicon.png"
              alt=""
              aria-hidden="true"
              className="w-9 h-9 object-contain"
              style={{ cursor: "pointer" }}
            />
          </Link>

          <div className="flex items-center gap-3 shrink-0">
            <Link
              to="/api-docs"
              className="hidden sm:inline-flex items-center gap-1.5 font-mono text-[10px] px-2.5 py-1 rounded-md border border-rim hover:border-accent hover:text-accent transition-colors"
              style={{ color: "var(--color-text)", opacity: 0.8 }}
              title="Public REST API documentation"
            >
              {"</> API"}
            </Link>
            <AuthButton />
          </div>
        </div>

        {/* Row 2 — categories + region/date pickers, all grouped as filter controls */}
        <div className="flex flex-col lg:flex-row lg:justify-between lg:items-center gap-3 py-3 border-t border-rim/60">
          <div className="hidden md:block min-w-0 flex-1">
            <HeaderCategoryNav
              selected={selectedCategory}
              onSelect={onCategoryChange}
            />
          </div>

          <div className="flex items-center gap-3 shrink-0">
            <div className="w-44">
              <RegionCombobox
                selectedRegion={selectedRegion}
                onSelect={onRegionSelect}
              />
            </div>
            <div className="w-56">
              <GlobeControls value={dateRange} onChange={onDateRangeChange} />
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}

import { CATEGORY_META } from "./NewsCard";
import { RegionCombobox } from "./RegionCombobox";
import { CategoryDropdown } from "./CategoryDropdown";
import { GlobeControls, type DateRange } from "./GlobeControls";

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function SidebarSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-slate-600 px-1">
        {title}
      </p>
      {children}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sidebar
// ---------------------------------------------------------------------------

interface SidebarProps {
  selectedCategories: string[];
  selectedRegion: string | undefined;
  dateRange: DateRange;
  onCategoriesChange: (categories: string[]) => void;
  onRegionSelect: (region: string | undefined) => void;
  onDateRangeChange: (range: DateRange) => void;
}

export function Sidebar({
  selectedCategories,
  selectedRegion,
  dateRange,
  onCategoriesChange,
  onRegionSelect,
  onDateRangeChange,
}: SidebarProps) {
  const hasFilters = selectedCategories.length > 0 || !!selectedRegion;

  return (
    <aside className="flex flex-col gap-6 h-full overflow-y-auto py-4 px-3">

      {/* Logo */}
      <div className="flex flex-col gap-0.5 px-1 pb-2 border-b border-rim">
        <h1 className="text-base font-bold tracking-tight text-white">
          Omnes<span className="text-cyan-400">Vident</span>
        </h1>
        <p className="text-[10px] text-slate-600 font-mono">Global News Discovery</p>
      </div>

      {/* Active filters summary */}
      {hasFilters && (
        <div className="flex flex-col gap-1 rounded-lg bg-panel border border-rim px-2.5 py-2">
          <p className="text-[10px] text-slate-500">Active filters</p>
          <div className="flex flex-wrap gap-1">
            {selectedRegion && (
              <span className="text-[10px] font-mono font-semibold text-cyan-400 bg-cyan-400/10 ring-1 ring-cyan-400/30 px-1.5 py-0.5 rounded">
                {selectedRegion}
              </span>
            )}
            {selectedCategories.map((cat) => (
              <span
                key={cat}
                className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ring-1 ${CATEGORY_META[cat]?.bgClass ?? ""} ${CATEGORY_META[cat]?.colorClass ?? ""}`}
              >
                {CATEGORY_META[cat]?.label ?? cat}
              </span>
            ))}
          </div>
          <button
            onClick={() => { onCategoriesChange([]); onRegionSelect(undefined); }}
            className="mt-1 text-[10px] text-slate-500 hover:text-red-400 transition-colors text-left"
          >
            ✕ Clear all filters
          </button>
        </div>
      )}

      {/* Date filter — preset badges + optional custom range */}
      <SidebarSection title="Date">
        <GlobeControls value={dateRange} onChange={onDateRangeChange} />
      </SidebarSection>

      {/* Regions — searchable combobox grouped by continent */}
      <SidebarSection title="Region">
        <RegionCombobox
          selectedRegion={selectedRegion}
          onSelect={onRegionSelect}
        />
      </SidebarSection>

      {/* Category — multi-select dropdown */}
      <SidebarSection title="Category">
        <CategoryDropdown
          selectedCategories={selectedCategories}
          onChange={onCategoriesChange}
        />
      </SidebarSection>

      {/* Fair use footer */}
      <div className="mt-auto pt-4 border-t border-rim px-1">
        <p className="text-[9px] text-slate-700 leading-relaxed">
          OmnesVident displays headlines, short snippets, and source attribution only.
          All articles open on the original publisher's site.
          No content is reproduced in full.
        </p>
      </div>
    </aside>
  );
}

import { CATEGORY_META } from "./NewsCard";
import { RegionCombobox } from "./RegionCombobox";

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
  selectedCategory: string | undefined;
  selectedRegion: string | undefined;
  onCategorySelect: (category: string | undefined) => void;
  onRegionSelect: (region: string | undefined) => void;
}

export function Sidebar({
  selectedCategory,
  selectedRegion,
  onCategorySelect,
  onRegionSelect,
}: SidebarProps) {
  const hasFilters = !!(selectedCategory || selectedRegion);

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
            {selectedCategory && (
              <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ring-1 ${CATEGORY_META[selectedCategory]?.bgClass ?? ""} ${CATEGORY_META[selectedCategory]?.colorClass ?? ""}`}>
                {CATEGORY_META[selectedCategory]?.label ?? selectedCategory}
              </span>
            )}
          </div>
          <button
            onClick={() => { onCategorySelect(undefined); onRegionSelect(undefined); }}
            className="mt-1 text-[10px] text-slate-500 hover:text-red-400 transition-colors text-left"
          >
            ✕ Clear all filters
          </button>
        </div>
      )}

      {/* Categories */}
      <SidebarSection title="Category">
        <div className="flex flex-col gap-0.5">
          {Object.entries(CATEGORY_META).map(([key, meta]) => {
            const isActive = selectedCategory === key;
            return (
              <button
                key={key}
                onClick={() => onCategorySelect(isActive ? undefined : key)}
                className={`flex items-center gap-2.5 w-full text-left rounded-lg px-2.5 py-1.5 text-xs transition-all duration-150 ${
                  isActive
                    ? `${meta.bgClass} ${meta.colorClass} ring-1`
                    : "text-slate-400 hover:text-slate-200 hover:bg-panel"
                }`}
                aria-pressed={isActive}
              >
                <span className="text-sm leading-none w-4 text-center" aria-hidden="true">
                  {meta.icon}
                </span>
                <span className="font-medium">{meta.label}</span>
              </button>
            );
          })}
        </div>
      </SidebarSection>

      {/* Regions — searchable combobox grouped by continent */}
      <SidebarSection title="Region">
        <RegionCombobox
          selectedRegion={selectedRegion}
          onSelect={onRegionSelect}
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

import { CATEGORY_META } from "./NewsCard";

// ---------------------------------------------------------------------------
// Region data — organized for the selector
// ---------------------------------------------------------------------------

const REGION_GROUPS = [
  {
    label: "Americas",
    regions: [
      { code: "US", name: "United States" },
      { code: "CA", name: "Canada" },
      { code: "BR", name: "Brazil" },
      { code: "MX", name: "Mexico" },
      { code: "AR", name: "Argentina" },
    ],
  },
  {
    label: "Europe",
    regions: [
      { code: "GB", name: "United Kingdom" },
      { code: "DE", name: "Germany" },
      { code: "FR", name: "France" },
      { code: "IT", name: "Italy" },
      { code: "UA", name: "Ukraine" },
    ],
  },
  {
    label: "Asia-Pacific",
    regions: [
      { code: "JP", name: "Japan" },
      { code: "CN", name: "China" },
      { code: "IN", name: "India" },
      { code: "AU", name: "Australia" },
      { code: "KR", name: "South Korea" },
    ],
  },
  {
    label: "Middle East & Africa",
    regions: [
      { code: "IL", name: "Israel" },
      { code: "SA", name: "Saudi Arabia" },
      { code: "EG", name: "Egypt" },
      { code: "ZA", name: "South Africa" },
      { code: "NG", name: "Nigeria" },
    ],
  },
];

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

      {/* Regions */}
      <SidebarSection title="Region">
        <div className="flex flex-col gap-3">

          {/* All regions button */}
          <button
            onClick={() => onRegionSelect(undefined)}
            className={`flex items-center gap-2 w-full text-left rounded-lg px-2.5 py-1.5 text-xs transition-all duration-150 ${
              !selectedRegion
                ? "bg-cyan-400/10 text-cyan-400 ring-1 ring-cyan-400/30"
                : "text-slate-400 hover:text-slate-200 hover:bg-panel"
            }`}
            aria-pressed={!selectedRegion}
          >
            <span aria-hidden="true">🌐</span>
            <span className="font-medium">Global</span>
          </button>

          {REGION_GROUPS.map((group) => (
            <div key={group.label} className="flex flex-col gap-0.5">
              <p className="text-[9px] font-semibold uppercase tracking-widest text-slate-700 px-2.5 py-0.5">
                {group.label}
              </p>
              {group.regions.map(({ code, name }) => {
                const isActive = selectedRegion === code;
                return (
                  <button
                    key={code}
                    onClick={() => onRegionSelect(isActive ? undefined : code)}
                    className={`flex items-center gap-2.5 w-full text-left rounded-lg px-2.5 py-1.5 text-xs transition-all duration-150 ${
                      isActive
                        ? "bg-slate-700/50 text-white ring-1 ring-slate-500/50"
                        : "text-slate-400 hover:text-slate-200 hover:bg-panel"
                    }`}
                    aria-pressed={isActive}
                  >
                    <span className="font-mono text-[10px] text-slate-500 w-6 shrink-0">
                      {code}
                    </span>
                    <span className="truncate">{name}</span>
                  </button>
                );
              })}
            </div>
          ))}
        </div>
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

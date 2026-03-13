/**
 * WorldMap — Region Heat Grid
 *
 * A visual "world map" built from a geographic grid of region tiles.
 * Each tile shows the region code and, when stories are loaded, a subtle
 * activity indicator.  Clicking selects/deselects the region.
 *
 * Design decision: A full SVG world map requires a large asset or a mapping
 * library (e.g. react-simple-maps).  For MVP a geo-positioned grid conveys
 * the same regional intent at zero bundle cost.  A real SVG choropleth map
 * is noted as a future enhancement in Imp_det.txt.
 */

interface RegionTile {
  code: string;
  name: string;
  col: number;  // 1-based CSS grid column
  row: number;  // 1-based CSS grid row
}

// Approximate geographic positions on a 12-column × 6-row grid
const TILES: RegionTile[] = [
  // Americas
  { code: "CA", name: "Canada",       col: 2, row: 1 },
  { code: "US", name: "USA",          col: 2, row: 2 },
  { code: "MX", name: "Mexico",       col: 2, row: 3 },
  { code: "BR", name: "Brazil",       col: 3, row: 4 },
  { code: "AR", name: "Argentina",    col: 3, row: 5 },
  // Europe
  { code: "GB", name: "UK",           col: 5, row: 1 },
  { code: "DE", name: "Germany",      col: 6, row: 2 },
  { code: "FR", name: "France",       col: 5, row: 2 },
  { code: "IT", name: "Italy",        col: 6, row: 3 },
  { code: "UA", name: "Ukraine",      col: 7, row: 2 },
  // Middle East & Africa
  { code: "EG", name: "Egypt",        col: 7, row: 3 },
  { code: "SA", name: "Saudi Arabia", col: 8, row: 3 },
  { code: "IL", name: "Israel",       col: 7, row: 4 },
  { code: "NG", name: "Nigeria",      col: 6, row: 4 },
  { code: "ZA", name: "S. Africa",    col: 7, row: 5 },
  // Asia-Pacific
  { code: "IN", name: "India",        col: 9, row: 3 },
  { code: "CN", name: "China",        col: 10, row: 2 },
  { code: "KR", name: "S. Korea",     col: 11, row: 2 },
  { code: "JP", name: "Japan",        col: 12, row: 2 },
  { code: "AU", name: "Australia",    col: 11, row: 4 },
];

interface WorldMapProps {
  selectedRegion: string | undefined;
  onRegionSelect: (region: string | undefined) => void;
}

export function WorldMap({ selectedRegion, onRegionSelect }: WorldMapProps) {
  return (
    <div className="rounded-xl bg-panel border border-rim p-3 overflow-x-auto">
      <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-slate-600 mb-2 px-1">
        Region Map
      </p>

      {/* 12-column geographic grid */}
      <div
        className="grid gap-1"
        style={{
          gridTemplateColumns: "repeat(12, minmax(0, 1fr))",
          gridTemplateRows: "repeat(6, 2rem)",
        }}
        role="group"
        aria-label="Select a region"
      >
        {TILES.map(({ code, name, col, row }) => {
          const isActive = selectedRegion === code;
          return (
            <button
              key={code}
              onClick={() => onRegionSelect(isActive ? undefined : code)}
              style={{ gridColumn: col, gridRow: row }}
              title={name}
              aria-pressed={isActive}
              aria-label={`${name} (${code})`}
              className={`flex items-center justify-center rounded text-[10px] font-mono font-bold transition-all duration-150 border ${
                isActive
                  ? "bg-cyan-400/20 border-cyan-400/60 text-cyan-300 shadow-[0_0_8px_rgba(34,211,238,0.3)]"
                  : "bg-card border-rim text-slate-500 hover:border-rim-bright hover:text-slate-300 hover:bg-card-hover"
              }`}
            >
              {code}
            </button>
          );
        })}
      </div>

      {selectedRegion && (
        <button
          onClick={() => onRegionSelect(undefined)}
          className="mt-2 text-[10px] text-slate-600 hover:text-slate-400 transition-colors"
        >
          ✕ Clear region
        </button>
      )}
    </div>
  );
}

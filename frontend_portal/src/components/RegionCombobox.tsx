import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";

// ─── Region data ─────────────────────────────────────────────────────────────

interface RegionEntry { code: string; name: string; }
interface RegionGroup { label: string; regions: RegionEntry[]; }

const REGION_GROUPS: RegionGroup[] = [
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

const ALL_REGIONS = REGION_GROUPS.flatMap((g) => g.regions);

function regionLabel(code: string | undefined): string {
  if (!code) return "Global";
  return ALL_REGIONS.find((r) => r.code === code)?.name ?? code;
}

// ─── Component ───────────────────────────────────────────────────────────────

interface RegionComboboxProps {
  selectedRegion: string | undefined;
  onSelect: (region: string | undefined) => void;
}

export function RegionCombobox({ selectedRegion, onSelect }: RegionComboboxProps) {
  const [open, setOpen]     = useState(false);
  const [query, setQuery]   = useState("");
  const triggerRef          = useRef<HTMLButtonElement>(null);
  const inputRef            = useRef<HTMLInputElement>(null);
  const dropdownRef         = useRef<HTMLDivElement>(null);
  const [coords, setCoords] = useState({ left: 0, top: 0, width: 0 });

  // Re-measure trigger on open + on resize
  useEffect(() => {
    if (!open) return;
    const measure = () => {
      const r = triggerRef.current?.getBoundingClientRect();
      if (r) setCoords({ left: r.left, top: r.bottom + 4, width: r.width });
    };
    measure();
    window.addEventListener("resize", measure);
    window.addEventListener("scroll", measure, true);
    return () => {
      window.removeEventListener("resize", measure);
      window.removeEventListener("scroll", measure, true);
    };
  }, [open]);

  // Auto-focus the search field when the dropdown opens
  useEffect(() => {
    if (open) {
      // setTimeout to wait for portal mount
      setTimeout(() => inputRef.current?.focus(), 0);
    } else {
      setQuery("");
    }
  }, [open]);

  // Close on Escape, click outside
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    const onPointer = (e: PointerEvent) => {
      const t = e.target as Node;
      if (!dropdownRef.current?.contains(t) && !triggerRef.current?.contains(t)) {
        setOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("pointerdown", onPointer);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("pointerdown", onPointer);
    };
  }, [open]);

  // Filter the groups by the search query (matches name OR code, case-insensitive)
  const filteredGroups = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return REGION_GROUPS;
    return REGION_GROUPS
      .map((g) => ({
        label: g.label,
        regions: g.regions.filter(
          (r) =>
            r.name.toLowerCase().includes(q) ||
            r.code.toLowerCase().includes(q) ||
            g.label.toLowerCase().includes(q)
        ),
      }))
      .filter((g) => g.regions.length > 0);
  }, [query]);

  const matchedTotal = filteredGroups.reduce((acc, g) => acc + g.regions.length, 0);

  function pick(code: string | undefined) {
    onSelect(code);
    setOpen(false);
  }

  // ─── Render ────────────────────────────────────────────────────────────────

  const dropdown = open ? (
    <div
      ref={dropdownRef}
      style={{
        position: "fixed",
        left: coords.left,
        top: coords.top,
        width: Math.max(coords.width, 240),
        zIndex: 100,
      }}
      className="rounded-lg border border-rim bg-base shadow-2xl shadow-black/40 overflow-hidden"
    >
      {/* Search */}
      <div className="border-b border-rim p-2">
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search country or code…"
          className="w-full bg-panel border border-rim rounded-md px-2.5 py-1.5 text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-500/40"
        />
      </div>

      {/* List */}
      <div className="max-h-72 overflow-y-auto py-1">
        {/* Global option (only shown when no query, or "global" matches the typed query) */}
        {(!query || "global".includes(query.trim().toLowerCase())) && (
          <button
            onClick={() => pick(undefined)}
            className={`flex items-center gap-2 w-full text-left px-3 py-1.5 text-xs transition-colors ${
              !selectedRegion
                ? "bg-cyan-400/10 text-cyan-400"
                : "text-slate-300 hover:bg-panel"
            }`}
          >
            <span aria-hidden="true">🌐</span>
            <span className="font-medium">Global</span>
            <span className="ml-auto text-[9px] font-mono text-slate-600">all regions</span>
          </button>
        )}

        {filteredGroups.map((group) => (
          <div key={group.label}>
            <p className="text-[9px] font-semibold uppercase tracking-widest text-slate-700 px-3 pt-2 pb-1">
              {group.label}
            </p>
            {group.regions.map(({ code, name }) => {
              const isActive = selectedRegion === code;
              return (
                <button
                  key={code}
                  onClick={() => pick(code)}
                  className={`flex items-center gap-2.5 w-full text-left px-3 py-1.5 text-xs transition-colors ${
                    isActive
                      ? "bg-slate-700/50 text-white"
                      : "text-slate-300 hover:bg-panel"
                  }`}
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

        {matchedTotal === 0 && !"global".includes(query.trim().toLowerCase()) && (
          <p className="text-[10px] text-slate-600 px-3 py-3 italic text-center">
            No matches for "{query}"
          </p>
        )}
      </div>
    </div>
  ) : null;

  return (
    <>
      <button
        ref={triggerRef}
        onClick={() => setOpen((p) => !p)}
        className={`flex items-center gap-2 w-full text-left rounded-lg px-2.5 py-2 text-xs transition-all duration-150 border ${
          selectedRegion
            ? "bg-slate-700/50 text-white border-slate-500/50"
            : "bg-cyan-400/10 text-cyan-400 border-cyan-400/30"
        }`}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        {!selectedRegion ? (
          <span aria-hidden="true">🌐</span>
        ) : (
          <span className="font-mono text-[10px] text-slate-400 w-6 shrink-0">
            {selectedRegion}
          </span>
        )}
        <span className="font-medium truncate flex-1">{regionLabel(selectedRegion)}</span>
        <span className="text-[9px] text-slate-500 shrink-0">{open ? "▲" : "▼"}</span>
      </button>

      {dropdown && createPortal(dropdown, document.body)}
    </>
  );
}

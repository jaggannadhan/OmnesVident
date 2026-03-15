/**
 * GlobeControls — time-range selector for the 3D globe and news grid.
 *
 * Presets compute ISO-8601 start/end strings relative to "now".
 * A /news/coverage fetch tells us the oldest available document date so we
 * can grey out presets that fall entirely before the data window begins.
 */

import { useEffect, useState } from "react";

const BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "/api";

// ---------------------------------------------------------------------------
// Coverage
// ---------------------------------------------------------------------------

interface Coverage {
  oldest: string | null;   // ISO-8601 or null
  newest: string | null;
  total: number;
}

async function fetchCoverage(): Promise<Coverage> {
  try {
    const res = await fetch(`${BASE_URL}/news/coverage`, {
      headers: { Accept: "application/json" },
    });
    if (!res.ok) return { oldest: null, newest: null, total: -1 };
    return res.json() as Promise<Coverage>;
  } catch {
    return { oldest: null, newest: null, total: -1 };
  }
}

// ---------------------------------------------------------------------------
// Presets
// ---------------------------------------------------------------------------

export interface DateRange {
  start: string | undefined;
  end: string | undefined;
}

interface Preset {
  label: string;
  /** short description shown in tooltip */
  description: string;
  range: () => DateRange;
}

function isoMinus(hours: number): string {
  return new Date(Date.now() - hours * 3_600_000).toISOString();
}

const PRESETS: Preset[] = [
  {
    label: "Live",
    description: "Last 24 hours",
    range: () => ({ start: isoMinus(24), end: undefined }),
  },
  {
    label: "Today",
    description: "Since midnight (local)",
    range: () => {
      const d = new Date();
      d.setHours(0, 0, 0, 0);
      return { start: d.toISOString(), end: undefined };
    },
  },
  {
    label: "Yesterday",
    description: "48 h → 24 h ago",
    range: () => ({ start: isoMinus(48), end: isoMinus(24) }),
  },
  {
    label: "3 Days",
    description: "Last 72 hours",
    range: () => ({ start: isoMinus(72), end: undefined }),
  },
  {
    label: "Week",
    description: "Last 7 days",
    range: () => ({ start: isoMinus(168), end: undefined }),
  },
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface GlobeControlsProps {
  value: DateRange;
  onChange: (range: DateRange) => void;
}

export function GlobeControls({ value, onChange }: GlobeControlsProps) {
  const [coverage, setCoverage] = useState<Coverage | null>(null);

  useEffect(() => {
    fetchCoverage().then(setCoverage);
  }, []);

  const oldestMs = coverage?.oldest ? new Date(coverage.oldest).getTime() : null;

  function isGhosted(preset: Preset): boolean {
    if (!oldestMs) return false;
    const { end } = preset.range();
    // Ghost if the preset window ends before the oldest available doc
    if (end) {
      return new Date(end).getTime() < oldestMs;
    }
    return false;
  }

  function isActive(preset: Preset): boolean {
    const { start, end } = preset.range();
    return value.start === start && value.end === end;
  }

  return (
    <div className="flex items-center gap-1.5" role="group" aria-label="Time range">
      {/* Coverage badge */}
      {coverage && coverage.oldest && (
        <span
          className="hidden lg:inline text-[9px] font-mono text-slate-600 mr-1 whitespace-nowrap"
          title={`Oldest data: ${new Date(coverage.oldest).toLocaleDateString()}`}
        >
          Data from {new Date(coverage.oldest).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
        </span>
      )}

      {PRESETS.map((preset) => {
        const ghosted = isGhosted(preset);
        const active = isActive(preset);
        return (
          <button
            key={preset.label}
            title={ghosted ? `No data for "${preset.description}"` : preset.description}
            disabled={ghosted}
            onClick={() => !ghosted && onChange(preset.range())}
            aria-pressed={active}
            className={[
              "text-[10px] font-mono px-2 py-0.5 rounded border transition-colors",
              active
                ? "border-cyan-500/60 text-cyan-300 bg-cyan-400/10"
                : ghosted
                ? "border-rim/30 text-slate-700 cursor-not-allowed opacity-40"
                : "border-rim text-slate-400 hover:text-slate-200 hover:border-rim-bright",
            ].join(" ")}
          >
            {preset.label}
          </button>
        );
      })}
    </div>
  );
}

/**
 * GlobeControls — time-range selector for the 3D globe and news grid.
 *
 * Presets: Today · Week · Month
 * Range:   dropdown (portal, fixed-position) with From + optional To date
 */

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

const BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "/api";

// ---------------------------------------------------------------------------
// Coverage
// ---------------------------------------------------------------------------

interface Coverage {
  oldest: string | null;
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
// Helpers
// ---------------------------------------------------------------------------

export interface DateRange {
  start: string | undefined;
  end: string | undefined;
}

function todayMidnight(): string {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  return d.toISOString();
}

function daysAgoMidnight(days: number): string {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  d.setDate(d.getDate() - days);
  return d.toISOString();
}

function toDateInputValue(iso: string): string {
  return iso.slice(0, 10);
}

function endOfDay(yyyy_mm_dd: string): string {
  return new Date(`${yyyy_mm_dd}T23:59:59`).toISOString();
}

// ---------------------------------------------------------------------------
// Presets
// ---------------------------------------------------------------------------

type PresetKey = "today" | "week" | "month";

const PRESETS: { key: PresetKey; label: string; description: string; range: () => DateRange }[] = [
  {
    key: "today",
    label: "Today",
    description: "All news today (midnight to end of day)",
    range: () => {
      const today = toDateInputValue(new Date().toISOString());
      return { start: todayMidnight(), end: endOfDay(today) };
    },
  },
  {
    key: "week",
    label: "Week",
    description: "Last 7 days",
    range: () => ({ start: daysAgoMidnight(7), end: undefined }),
  },
  {
    key: "month",
    label: "Month",
    description: "Last 30 days",
    range: () => ({ start: daysAgoMidnight(30), end: undefined }),
  },
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export interface GlobeControlsProps {
  value: DateRange;
  onChange: (range: DateRange) => void;
}

export function GlobeControls({ onChange }: GlobeControlsProps) {
  const [coverage, setCoverage] = useState<Coverage | null>(null);
  const [activePreset, setActivePreset] = useState<PresetKey | "custom">("today");

  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [dropdownPos, setDropdownPos] = useState({ top: 0, right: 0 });
  const [customFrom, setCustomFrom] = useState<string>(() => toDateInputValue(daysAgoMidnight(7)));
  const [toEnabled, setToEnabled] = useState(false);
  const [customTo, setCustomTo] = useState<string>("");

  const rangeButtonRef = useRef<HTMLButtonElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchCoverage().then(setCoverage);
  }, []);

  // Close on outside click
  useEffect(() => {
    if (!dropdownOpen) return;
    function handleClick(e: MouseEvent) {
      const target = e.target as Node;
      const inButton = rangeButtonRef.current?.contains(target);
      const inDropdown = dropdownRef.current?.contains(target);
      if (!inButton && !inDropdown) setDropdownOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [dropdownOpen]);

  function handlePreset(preset: (typeof PRESETS)[number]) {
    setActivePreset(preset.key);
    setDropdownOpen(false);
    onChange(preset.range());
  }

  /** Compute the effective end ISO given current To state. */
  function effectiveEnd(from: string, toChecked: boolean, to: string): string | undefined {
    if (toChecked && to) return endOfDay(to);
    // From-only → single day: end at 23:59:59 of the From date
    return from ? endOfDay(from) : undefined;
  }

  function toggleDropdown() {
    if (!dropdownOpen) {
      const rect = rangeButtonRef.current?.getBoundingClientRect();
      if (rect) {
        setDropdownPos({
          top: rect.bottom + 6,
          right: window.innerWidth - rect.right,
        });
      }
      setActivePreset("custom");
      const from = customFrom || toDateInputValue(daysAgoMidnight(7));
      const fromIso = new Date(`${from}T00:00:00`).toISOString();
      onChange({ start: fromIso, end: effectiveEnd(from, toEnabled, customTo) });
    }
    setDropdownOpen((o) => !o);
  }

  function handleFromChange(val: string) {
    setCustomFrom(val);
    if (!val) return;
    onChange({
      start: new Date(`${val}T00:00:00`).toISOString(),
      end: effectiveEnd(val, toEnabled, customTo),
    });
  }

  function handleToEnabledChange(checked: boolean) {
    setToEnabled(checked);
    if (!checked) {
      setCustomTo("");
      const from = customFrom || toDateInputValue(daysAgoMidnight(7));
      onChange({
        start: new Date(`${from}T00:00:00`).toISOString(),
        end: effectiveEnd(from, false, ""),
      });
    }
  }

  function handleToChange(val: string) {
    setCustomTo(val);
    const from = customFrom || toDateInputValue(daysAgoMidnight(7));
    onChange({
      start: new Date(`${from}T00:00:00`).toISOString(),
      end: effectiveEnd(from, true, val),
    });
  }

  const oldestDateStr = coverage?.oldest ? toDateInputValue(coverage.oldest) : undefined;
  const todayStr = toDateInputValue(new Date().toISOString());

  const btnBase = "text-[10px] font-mono px-2 py-0.5 rounded border transition-colors";
  const btnActive = "border-cyan-500/60 text-cyan-300 bg-cyan-400/10";
  const btnIdle = "border-rim text-slate-400 hover:text-slate-200 hover:border-rim-bright";

  const dropdown = dropdownOpen ? createPortal(
    <div
      ref={dropdownRef}
      style={{
        position: "fixed",
        top: dropdownPos.top,
        right: dropdownPos.right,
        zIndex: 9999,
      }}
      className="min-w-[220px] rounded-lg border border-rim bg-[rgba(8,10,24,0.97)] shadow-2xl p-4 flex flex-col gap-3"
    >
      {/* From */}
      <div className="flex flex-col gap-1">
        <label className="text-[9px] font-semibold uppercase tracking-widest text-slate-500">
          From
        </label>
        <input
          autoFocus
          type="date"
          value={customFrom}
          min={oldestDateStr}
          max={toEnabled && customTo ? customTo : todayStr}
          onChange={(e) => handleFromChange(e.target.value)}
          className="text-[11px] font-mono bg-slate-800/60 border border-rim rounded px-2 py-1 text-slate-300 focus:outline-none focus:border-cyan-500/60 focus:text-cyan-300 cursor-pointer w-full"
        />
      </div>

      {/* To toggle */}
      <div className="flex flex-col gap-1">
        <label className="flex items-center gap-2 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={toEnabled}
            onChange={(e) => handleToEnabledChange(e.target.checked)}
            className="accent-cyan-400 w-3 h-3 cursor-pointer"
          />
          <span className="text-[9px] font-semibold uppercase tracking-widest text-slate-500">
            Set end date
          </span>
        </label>

        {toEnabled && (
          <input
            type="date"
            value={customTo}
            min={customFrom || oldestDateStr}
            max={todayStr}
            onChange={(e) => handleToChange(e.target.value)}
            className="text-[11px] font-mono bg-slate-800/60 border border-rim rounded px-2 py-1 text-slate-300 focus:outline-none focus:border-cyan-500/60 focus:text-cyan-300 cursor-pointer w-full"
          />
        )}
      </div>

      {/* Apply */}
      <button
        onClick={() => setDropdownOpen(false)}
        className="mt-1 text-[10px] font-semibold uppercase tracking-wider text-cyan-400 hover:text-cyan-200 transition-colors self-end"
      >
        Apply ✓
      </button>
    </div>,
    document.body
  ) : null;

  return (
    <div className="flex items-center gap-1.5" role="group" aria-label="Time range">

      {/* Coverage badge */}
      {coverage?.oldest && (
        <span
          className="hidden lg:inline text-[9px] font-mono text-slate-600 mr-1 whitespace-nowrap"
          title={`Oldest available data: ${new Date(coverage.oldest).toLocaleDateString()}`}
        >
          From {new Date(coverage.oldest).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
        </span>
      )}

      {/* Preset buttons */}
      {PRESETS.map((preset) => (
        <button
          key={preset.key}
          title={preset.description}
          onClick={() => handlePreset(preset)}
          aria-pressed={activePreset === preset.key}
          className={`${btnBase} ${activePreset === preset.key ? btnActive : btnIdle}`}
        >
          {preset.label}
        </button>
      ))}

      {/* Range button */}
      <button
        ref={rangeButtonRef}
        onClick={toggleDropdown}
        aria-pressed={activePreset === "custom"}
        aria-expanded={dropdownOpen}
        title="Pick a custom date range"
        className={`${btnBase} ${activePreset === "custom" ? btnActive : btnIdle}`}
      >
        Range {dropdownOpen ? "▲" : "▼"}
      </button>

      {dropdown}
    </div>
  );
}

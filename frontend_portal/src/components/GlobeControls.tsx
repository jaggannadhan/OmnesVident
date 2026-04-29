/**
 * GlobeControls — date filter for the globe + news grid.
 *
 * Single "Date Filter" trigger that opens a portal dropdown with:
 *   • Today  • Week  • Month  • Date Range  badges
 *   • the From / To inputs (only when Date Range is active)
 *   • a "Source from <oldest>" disclaimer at the bottom
 */

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

const BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "/api";

// ─── Coverage ────────────────────────────────────────────────────────────────

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

// ─── Helpers ─────────────────────────────────────────────────────────────────

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

function formatCoverageDate(iso: string): string {
  // "30 Jan 2026"
  return new Date(iso).toLocaleDateString(undefined, {
    day:   "numeric",
    month: "short",
    year:  "numeric",
  });
}

// ─── Presets ─────────────────────────────────────────────────────────────────

type PresetKey = "today" | "week" | "month" | "custom";

interface Preset {
  key:         Exclude<PresetKey, "custom">;
  label:       string;
  description: string;
  range:       () => DateRange;
}

const PRESETS: Preset[] = [
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

// ─── Component ───────────────────────────────────────────────────────────────

export interface GlobeControlsProps {
  value: DateRange;
  onChange: (range: DateRange) => void;
}

export function GlobeControls({ onChange }: GlobeControlsProps) {
  const [coverage, setCoverage] = useState<Coverage | null>(null);
  const [activePreset, setActivePreset] = useState<PresetKey>("today");

  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [dropdownPos, setDropdownPos] = useState({ top: 0, right: 0 });

  const [customFrom, setCustomFrom] = useState<string>(() => toDateInputValue(daysAgoMidnight(7)));
  const [toEnabled, setToEnabled] = useState(false);
  const [customTo, setCustomTo] = useState<string>("");

  const triggerRef  = useRef<HTMLButtonElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchCoverage().then(setCoverage);
  }, []);

  // Close on outside click
  useEffect(() => {
    if (!dropdownOpen) return;
    function handleClick(e: MouseEvent) {
      const target = e.target as Node;
      const inTrigger  = triggerRef.current?.contains(target);
      const inDropdown = dropdownRef.current?.contains(target);
      if (!inTrigger && !inDropdown) setDropdownOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [dropdownOpen]);

  // Close on Escape
  useEffect(() => {
    if (!dropdownOpen) return;
    function onKey(e: KeyboardEvent) { if (e.key === "Escape") setDropdownOpen(false); }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [dropdownOpen]);

  function openDropdown() {
    const rect = triggerRef.current?.getBoundingClientRect();
    if (rect) {
      setDropdownPos({
        top:   rect.bottom + 6,
        right: window.innerWidth - rect.right,
      });
    }
    setDropdownOpen(true);
  }

  function toggleDropdown() {
    if (dropdownOpen) setDropdownOpen(false);
    else              openDropdown();
  }

  function handlePreset(preset: Preset) {
    setActivePreset(preset.key);
    onChange(preset.range());
    setDropdownOpen(false);   // Today/Week/Month auto-close, range stays open
  }

  /** Compute the effective end ISO given current To state. */
  function effectiveEnd(from: string, toChecked: boolean, to: string): string | undefined {
    if (toChecked && to) return endOfDay(to);
    return from ? endOfDay(from) : undefined;
  }

  function activateDateRange() {
    setActivePreset("custom");
    const from = customFrom || toDateInputValue(daysAgoMidnight(7));
    const fromIso = new Date(`${from}T00:00:00`).toISOString();
    onChange({ start: fromIso, end: effectiveEnd(from, toEnabled, customTo) });
  }

  function handleFromChange(val: string) {
    setCustomFrom(val);
    if (!val) return;
    onChange({
      start: new Date(`${val}T00:00:00`).toISOString(),
      end:   effectiveEnd(val, toEnabled, customTo),
    });
  }

  function handleToEnabledChange(checked: boolean) {
    setToEnabled(checked);
    if (!checked) {
      setCustomTo("");
      const from = customFrom || toDateInputValue(daysAgoMidnight(7));
      onChange({
        start: new Date(`${from}T00:00:00`).toISOString(),
        end:   effectiveEnd(from, false, ""),
      });
    }
  }

  function handleToChange(val: string) {
    setCustomTo(val);
    const from = customFrom || toDateInputValue(daysAgoMidnight(7));
    onChange({
      start: new Date(`${from}T00:00:00`).toISOString(),
      end:   effectiveEnd(from, true, val),
    });
  }

  // ─── Trigger label ─────────────────────────────────────────────────────────
  const activeLabel =
    activePreset === "today"  ? "Today"  :
    activePreset === "week"   ? "Week"   :
    activePreset === "month"  ? "Month"  :
                                "Custom" ;

  const oldestDateStr = coverage?.oldest ? toDateInputValue(coverage.oldest) : undefined;
  const todayStr = toDateInputValue(new Date().toISOString());

  const badgeBase   = "text-[10px] font-mono px-2.5 py-1 rounded-md border transition-colors text-left";
  const badgeActive = "border-cyan-500/60 text-cyan-300 bg-cyan-400/10";
  const badgeIdle   = "border-rim text-slate-400 hover:text-slate-200 hover:border-rim-bright";

  const dropdown = dropdownOpen ? createPortal(
    <div
      ref={dropdownRef}
      style={{
        position: "fixed",
        top:      dropdownPos.top,
        right:    dropdownPos.right,
        zIndex:   9999,
      }}
      className="min-w-[240px] rounded-lg border border-rim bg-[rgba(8,10,24,0.97)] shadow-2xl flex flex-col"
    >
      {/* Preset badges */}
      <div className="p-3 flex flex-wrap gap-1.5 border-b border-rim/60">
        {PRESETS.map((preset) => (
          <button
            key={preset.key}
            title={preset.description}
            onClick={() => handlePreset(preset)}
            aria-pressed={activePreset === preset.key}
            className={`${badgeBase} ${activePreset === preset.key ? badgeActive : badgeIdle}`}
          >
            {preset.label}
          </button>
        ))}
        <button
          onClick={activateDateRange}
          aria-pressed={activePreset === "custom"}
          title="Pick a custom From / To date range"
          className={`${badgeBase} ${activePreset === "custom" ? badgeActive : badgeIdle}`}
        >
          Date Range
        </button>
      </div>

      {/* From / To picker — only when Date Range is the active preset */}
      {activePreset === "custom" && (
        <div className="p-3 flex flex-col gap-2 border-b border-rim/60">
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

          <button
            onClick={() => setDropdownOpen(false)}
            className="self-end mt-1 text-[10px] font-semibold uppercase tracking-wider text-cyan-400 hover:text-cyan-200 transition-colors"
          >
            Apply ✓
          </button>
        </div>
      )}

      {/* Coverage disclaimer */}
      {coverage?.oldest && (
        <p
          className="px-3 py-2 text-[9px] font-mono text-slate-600 italic"
          title="Oldest available record in our database"
        >
          Source from {formatCoverageDate(coverage.oldest)}
        </p>
      )}
    </div>,
    document.body
  ) : null;

  return (
    <div className="flex items-center" role="group" aria-label="Date filter">
      <button
        ref={triggerRef}
        onClick={toggleDropdown}
        aria-haspopup="listbox"
        aria-expanded={dropdownOpen}
        title={`Date filter — currently ${activeLabel}`}
        className={`flex items-center gap-1.5 text-[10px] font-mono px-2.5 py-1 rounded-md border transition-colors ${
          dropdownOpen
            ? "border-cyan-500/60 text-cyan-300 bg-cyan-400/10"
            : "border-rim text-slate-300 hover:text-slate-100 hover:border-rim-bright"
        }`}
      >
        <span aria-hidden="true">📅</span>
        <span>Date Filter</span>
        <span className="text-slate-500">·</span>
        <span className="text-cyan-300/80">{activeLabel}</span>
        <span className="text-[8px] text-slate-500">{dropdownOpen ? "▲" : "▼"}</span>
      </button>

      {dropdown}
    </div>
  );
}

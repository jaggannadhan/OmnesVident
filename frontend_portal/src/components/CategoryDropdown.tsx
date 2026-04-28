import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { CATEGORY_META } from "./NewsCard";

interface CategoryDropdownProps {
  selectedCategories: string[];
  onChange: (categories: string[]) => void;
}

export function CategoryDropdown({ selectedCategories, onChange }: CategoryDropdownProps) {
  const [open, setOpen]     = useState(false);
  const triggerRef          = useRef<HTMLButtonElement>(null);
  const dropdownRef         = useRef<HTMLDivElement>(null);
  const [coords, setCoords] = useState({ left: 0, top: 0, width: 0 });

  // Re-measure trigger on open + on resize/scroll
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

  function toggle(key: string) {
    if (selectedCategories.includes(key)) {
      onChange(selectedCategories.filter((c) => c !== key));
    } else {
      onChange([...selectedCategories, key]);
    }
  }

  function clearAll() {
    onChange([]);
  }

  // ─── Trigger label & accent ────────────────────────────────────────────────
  const count = selectedCategories.length;
  let triggerLabel: string;
  let triggerAccent: { bg: string; fg: string; border: string } | null = null;

  if (count === 0) {
    triggerLabel = "All Categories";
  } else if (count === 1) {
    const meta = CATEGORY_META[selectedCategories[0]];
    triggerLabel = meta?.label ?? selectedCategories[0];
    triggerAccent = meta
      ? { bg: meta.bgClass, fg: meta.colorClass, border: "border-current/30" }
      : null;
  } else {
    triggerLabel = `${count} categories`;
  }

  // ─── Render ────────────────────────────────────────────────────────────────

  const dropdown = open ? (
    <div
      ref={dropdownRef}
      style={{
        position: "fixed",
        left: coords.left,
        top: coords.top,
        width: Math.max(coords.width, 220),
        zIndex: 100,
      }}
      className="rounded-lg border border-rim bg-base shadow-2xl shadow-black/40 overflow-hidden"
    >
      {/* All categories — clears the multi-select */}
      <button
        onClick={clearAll}
        className={`flex items-center gap-2.5 w-full text-left px-3 py-1.5 text-xs transition-colors ${
          count === 0
            ? "bg-cyan-400/10 text-cyan-400"
            : "text-slate-300 hover:bg-panel"
        }`}
      >
        <span className="text-sm leading-none w-4 text-center" aria-hidden="true">∗</span>
        <span className="font-medium flex-1">All Categories</span>
        {count > 0 && (
          <span className="text-[9px] font-mono text-slate-500">clear</span>
        )}
      </button>

      <div className="border-t border-rim my-1" />

      {Object.entries(CATEGORY_META).map(([key, meta]) => {
        const isActive = selectedCategories.includes(key);
        return (
          <button
            key={key}
            onClick={() => toggle(key)}
            className={`flex items-center gap-2.5 w-full text-left px-3 py-1.5 text-xs transition-colors ${
              isActive
                ? `${meta.bgClass} ${meta.colorClass}`
                : "text-slate-300 hover:bg-panel"
            }`}
          >
            {/* Checkbox indicator */}
            <span
              className={`w-3.5 h-3.5 rounded-sm border flex items-center justify-center text-[9px] leading-none shrink-0 ${
                isActive
                  ? "bg-current/20 border-current"
                  : "border-slate-600"
              }`}
              aria-hidden="true"
            >
              {isActive && "✓"}
            </span>
            <span className="text-sm leading-none w-4 text-center" aria-hidden="true">
              {meta.icon}
            </span>
            <span className="font-medium">{meta.label}</span>
          </button>
        );
      })}

      {/* Footer — done button (just closes, but visible affordance for multi-select) */}
      {count > 0 && (
        <div className="border-t border-rim mt-1 p-1.5 flex items-center justify-between">
          <span className="text-[9px] font-mono text-slate-600 px-1.5">
            {count} selected
          </span>
          <button
            onClick={() => setOpen(false)}
            className="text-[10px] font-medium text-cyan-400 hover:text-cyan-300 px-2 py-0.5 rounded transition-colors"
          >
            Done ✓
          </button>
        </div>
      )}
    </div>
  ) : null;

  return (
    <>
      <button
        ref={triggerRef}
        onClick={() => setOpen((p) => !p)}
        className={`flex items-center gap-2 w-full text-left rounded-lg px-2.5 py-2 text-xs transition-all duration-150 border ${
          triggerAccent
            ? `${triggerAccent.bg} ${triggerAccent.fg} ${triggerAccent.border}`
            : count > 1
            ? "bg-slate-700/40 text-slate-200 border-slate-500/40"
            : "bg-cyan-400/10 text-cyan-400 border-cyan-400/30"
        }`}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <span className="text-sm leading-none w-4 text-center shrink-0" aria-hidden="true">
          {count === 1 ? CATEGORY_META[selectedCategories[0]]?.icon ?? "∗" : "∗"}
        </span>
        <span className="font-medium truncate flex-1">{triggerLabel}</span>
        <span className="text-[9px] text-slate-500 shrink-0">{open ? "▲" : "▼"}</span>
      </button>

      {dropdown && createPortal(dropdown, document.body)}
    </>
  );
}

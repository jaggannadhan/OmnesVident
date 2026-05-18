import { CATEGORY_META } from "./NewsCard";

// Single-select horizontal category nav for the top header.
// Clicking the active category, or the leading "ALL INTEL" link, clears
// the selection. Active + hover states use the gold accent.

// "All Intel" already includes world stories (it clears the category filter),
// so we don't surface a separate "World" pill — keeping it would be redundant.
const ORDER = ["POLITICS", "SCIENCE_TECH", "BUSINESS", "HEALTH", "ENTERTAINMENT", "SPORTS"];

interface HeaderCategoryNavProps {
  selected: string | undefined;
  onSelect: (category: string | undefined) => void;
}

// Hover prefix beats the inline `style` color because :hover bumps the
// specificity above an inline declaration on its own — but to be safe we
// stick to Tailwind utilities only, and use opacity (not color) for the
// muted state so the hover→accent transition is clean.
const BASE = "font-mono text-[11px] tracking-widest whitespace-nowrap uppercase transition-all pb-1 border-b cursor-pointer";
const ACTIVE   = "font-bold text-accent border-accent opacity-100";
const INACTIVE = "border-transparent text-[var(--color-text)] opacity-70 hover:text-accent hover:opacity-100";

export function HeaderCategoryNav({ selected, onSelect }: HeaderCategoryNavProps) {
  return (
    <nav className="flex items-center gap-7 overflow-x-auto hide-scrollbar">
      <button
        onClick={() => onSelect(undefined)}
        className={`${BASE} ${!selected ? ACTIVE : INACTIVE}`}
      >
        ALL INTEL
      </button>

      {ORDER.map((key) => {
        const meta = CATEGORY_META[key];
        if (!meta) return null;
        const active = selected === key;
        return (
          <button
            key={key}
            onClick={() => onSelect(active ? undefined : key)}
            className={`${BASE} ${active ? ACTIVE : INACTIVE}`}
            title={`Filter by ${meta.label}`}
          >
            {meta.label}
          </button>
        );
      })}
    </nav>
  );
}

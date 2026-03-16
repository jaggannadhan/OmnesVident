import { useState } from "react";
import type { StoryOut } from "../services/api";

// ---------------------------------------------------------------------------
// Shared helpers & constants
// ---------------------------------------------------------------------------

export const CATEGORY_META: Record<
  string,
  { label: string; icon: string; colorClass: string; bgClass: string }
> = {
  ALL:           { label: "All",           icon: "🌐", colorClass: "text-category-world",         bgClass: "bg-category-world" },
  POLITICS:      { label: "Politics",      icon: "🏛️", colorClass: "text-category-politics",      bgClass: "bg-category-politics" },
  SCIENCE_TECH:  { label: "Science & Tech",icon: "🔬", colorClass: "text-category-technology",    bgClass: "bg-category-technology" },
  BUSINESS:      { label: "Business",      icon: "📈", colorClass: "text-category-business",      bgClass: "bg-category-business" },
  HEALTH:        { label: "Health",        icon: "🩺", colorClass: "text-category-health",        bgClass: "bg-category-health" },
  ENTERTAINMENT: { label: "Entertainment", icon: "🎬", colorClass: "text-category-entertainment", bgClass: "bg-category-entertainment" },
  SPORTS:        { label: "Sports",        icon: "🏆", colorClass: "text-category-sports",        bgClass: "bg-category-sports" },
};

function ExternalLinkIcon({ className = "w-3.5 h-3.5" }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className={className} aria-hidden="true">
      <path fillRule="evenodd" d="M4.25 5.5a.75.75 0 0 0-.75.75v8.5c0 .414.336.75.75.75h8.5a.75.75 0 0 0 .75-.75v-4a.75.75 0 0 1 1.5 0v4A2.25 2.25 0 0 1 12.75 17h-8.5A2.25 2.25 0 0 1 2 14.75v-8.5A2.25 2.25 0 0 1 4.25 4h5a.75.75 0 0 1 0 1.5h-5Zm6.5-3a.75.75 0 0 1 .75-.75h3.5a.75.75 0 0 1 .75.75v3.5a.75.75 0 0 1-1.5 0V4.06l-4.97 4.97a.75.75 0 0 1-1.06-1.06l4.97-4.97h-1.69a.75.75 0 0 1-.75-.75Z" clipRule="evenodd" />
    </svg>
  );
}

function ChevronDownIcon({ open }: { open: boolean }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className={`w-3.5 h-3.5 transition-transform duration-200 ${open ? "rotate-180" : ""}`} aria-hidden="true">
      <path fillRule="evenodd" d="M5.22 8.22a.75.75 0 0 1 1.06 0L10 11.94l3.72-3.72a.75.75 0 1 1 1.06 1.06l-4.25 4.25a.75.75 0 0 1-1.06 0L5.22 9.28a.75.75 0 0 1 0-1.06Z" clipRule="evenodd" />
    </svg>
  );
}

function formatRelativeTime(isoString: string): string {
  const diff = Date.now() - new Date(isoString).getTime();
  const minutes = Math.floor(diff / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

// ---------------------------------------------------------------------------
// NewsCard component
// ---------------------------------------------------------------------------

interface NewsCardProps {
  story: StoryOut;
  onCategoryClick?: (category: string) => void;
  onRegionClick?: (region: string) => void;
}

export function NewsCard({ story, onCategoryClick, onRegionClick }: NewsCardProps) {
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const meta = CATEGORY_META[story.category] ?? CATEGORY_META.ALL;
  const hasAlternateSources = story.secondary_sources.length > 0;

  return (
    <article className="group flex flex-col gap-3 rounded-xl bg-card border border-rim hover:border-rim-bright hover:bg-card-hover transition-all duration-200 p-4 animate-fade-in">

      {/* Header: Source name + timestamp */}
      <div className="flex items-center justify-between gap-2 min-w-0">
        <span className="text-xs font-semibold text-slate-400 uppercase tracking-widest truncate">
          {story.source_name}
        </span>
        <time
          dateTime={story.timestamp}
          className="text-xs text-slate-500 shrink-0 font-mono"
        >
          {formatRelativeTime(story.timestamp)}
        </time>
      </div>

      {/* Title — primary action link */}
      <a
        href={story.source_url}
        target="_blank"
        rel="noopener noreferrer"
        className="group/link flex items-start gap-2 text-slate-100 hover:text-white"
        aria-label={`Read full article: ${story.title} (opens in new tab)`}
      >
        <h2 className="text-sm font-semibold leading-snug line-clamp-3 flex-1">
          {story.title}
        </h2>
        <ExternalLinkIcon className="w-3.5 h-3.5 shrink-0 mt-0.5 text-slate-500 group-hover/link:text-slate-300 transition-colors" />
      </a>

      {/* Snippet */}
      <p className="text-xs text-slate-400 leading-relaxed line-clamp-2">
        {story.snippet}
      </p>

      {/* Footer: Category + Regions + Secondary sources */}
      <div className="flex flex-wrap items-center gap-1.5 mt-auto pt-1 border-t border-rim/50">

        {/* Category badge */}
        <button
          onClick={() => onCategoryClick?.(story.category)}
          className={`inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded ring-1 ${meta.bgClass} ${meta.colorClass} transition-opacity hover:opacity-80`}
          title={`Filter by ${meta.label}`}
        >
          <span aria-hidden="true">{meta.icon}</span>
          {meta.label}
        </button>

        {/* Primary region badge */}
        <button
          onClick={() => onRegionClick?.(story.region_code)}
          className="inline-flex items-center text-[10px] font-mono font-semibold px-1.5 py-0.5 rounded ring-1 bg-slate-700/40 ring-slate-600/40 text-slate-300 hover:bg-slate-600/40 transition-colors"
          title={`View ${story.region_code} news`}
        >
          {story.region_code}
        </button>

        {/* Cross-regional tags (beyond primary) */}
        {story.mentioned_regions
          .filter((r) => r !== story.region_code)
          .slice(0, 3)
          .map((r) => (
            <button
              key={r}
              onClick={() => onRegionClick?.(r)}
              className="inline-flex items-center text-[10px] font-mono px-1.5 py-0.5 rounded ring-1 bg-slate-800/40 ring-slate-700/30 text-slate-500 hover:text-slate-300 hover:bg-slate-700/40 transition-colors"
              title={`Also relevant to ${r}`}
            >
              {r}
            </button>
          ))}

        {/* Spacer */}
        <div className="flex-1" />

        {/* Secondary sources toggle */}
        {hasAlternateSources && (
          <button
            onClick={() => setSourcesOpen((p) => !p)}
            className="inline-flex items-center gap-1 text-[10px] text-slate-500 hover:text-slate-300 transition-colors ml-auto"
            aria-expanded={sourcesOpen}
            aria-controls={`sources-${story.dedup_group_id}`}
          >
            +{story.secondary_sources.length} source{story.secondary_sources.length > 1 ? "s" : ""}
            <ChevronDownIcon open={sourcesOpen} />
          </button>
        )}
      </div>

      {/* Secondary sources list */}
      {hasAlternateSources && sourcesOpen && (
        <ul
          id={`sources-${story.dedup_group_id}`}
          className="flex flex-col gap-1 pt-1 border-t border-rim/50 animate-fade-in"
        >
          {story.secondary_sources.map((url) => {
            let displayUrl: string;
            try { displayUrl = new URL(url).hostname.replace(/^www\./, ""); }
            catch { displayUrl = url; }
            return (
              <li key={url}>
                <a
                  href={url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 text-[11px] text-slate-400 hover:text-slate-200 transition-colors"
                >
                  <ExternalLinkIcon className="w-3 h-3 shrink-0" />
                  <span className="truncate">{displayUrl}</span>
                </a>
              </li>
            );
          })}
        </ul>
      )}
    </article>
  );
}

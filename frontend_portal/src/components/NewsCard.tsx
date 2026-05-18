import { useState } from "react";
import type { StoryOut } from "../services/api";
import { regionLabel } from "../utils/regionLabels";

// ---------------------------------------------------------------------------
// Shared helpers & constants
// ---------------------------------------------------------------------------

export const CATEGORY_META: Record<
  string,
  { label: string; icon: string; colorClass: string; bgClass: string }
> = {
  WORLD:         { label: "World",         icon: "🌐", colorClass: "text-category-world",         bgClass: "bg-category-world" },
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
// NewsCard — magazine-style article tile.
// ---------------------------------------------------------------------------

interface NewsCardProps {
  story: StoryOut;
  onCategoryClick?: (category: string) => void;
  onRegionClick?: (region: string) => void;
}

export function NewsCard({ story, onCategoryClick, onRegionClick }: NewsCardProps) {
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const meta = CATEGORY_META[story.category] ?? CATEGORY_META.WORLD;
  const hasAlternateSources = story.secondary_sources.length > 0;

  return (
    <article className="group flex flex-col gap-3 p-6 border border-rim hover:bg-card-hover transition-colors animate-fade-in">

      {/* Top meta row: category pill + region (left) · source (right) */}
      <div className="flex items-start justify-between gap-3 mb-1">
        <div className="flex items-center gap-3 min-w-0">
          <button
            onClick={() => onCategoryClick?.(story.category)}
            className="font-mono text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 shrink-0 hover:opacity-80 transition-opacity"
            style={{ background: "var(--color-text)", color: "var(--color-base)" }}
            title={`Filter by ${meta.label}`}
          >
            {meta.label}
          </button>
          <button
            onClick={() => onRegionClick?.(story.region_code)}
            className="font-mono text-[10px] uppercase tracking-widest truncate hover:text-accent transition-colors"
            style={{ color: "var(--color-text)", opacity: 0.6 }}
            title={`View ${regionLabel(story.region_code)} news`}
          >
            {regionLabel(story.region_code)}
          </button>
        </div>
        <span
          className="font-mono text-[10px] uppercase tracking-wider shrink-0 truncate max-w-[40%]"
          style={{ color: "var(--color-text)", opacity: 0.45 }}
          title={story.source_name}
        >
          {story.source_name}
        </span>
      </div>

      {/* Headline — serif, the visual centerpiece */}
      <a
        href={story.source_url}
        target="_blank"
        rel="noopener noreferrer"
        className="group/link flex items-start gap-2"
        aria-label={`Read full article: ${story.title} (opens in new tab)`}
      >
        <h2
          className="font-headline text-xl leading-tight flex-1 group-hover:text-accent group-hover/link:text-accent transition-colors"
          style={{ color: "var(--color-text)" }}
        >
          {story.title}
        </h2>
        <ExternalLinkIcon
          className="w-3.5 h-3.5 shrink-0 mt-1.5 opacity-40 group-hover/link:opacity-100 transition-opacity"
        />
      </a>

      {/* Snippet */}
      {story.snippet && (
        <p
          className="font-sans text-[13px] leading-relaxed line-clamp-2"
          style={{ color: "var(--color-text)", opacity: 0.7 }}
        >
          {story.snippet}
        </p>
      )}

      {/* Footer: timestamp + cross-regional tags + secondary sources */}
      <div className="flex flex-wrap items-center gap-3 mt-auto pt-3 border-t border-rim/60">
        <time
          dateTime={story.timestamp}
          className="font-mono text-[10px] uppercase tracking-wider"
          style={{ color: "var(--color-text)", opacity: 0.55 }}
        >
          {formatRelativeTime(story.timestamp)}
        </time>

        {story.mentioned_regions
          .filter((r) => r !== story.region_code)
          .slice(0, 2)
          .map((r) => (
            <button
              key={r}
              onClick={() => onRegionClick?.(r)}
              className="font-mono text-[9px] uppercase tracking-wider px-1.5 py-0.5 border border-rim/70 hover:border-accent hover:text-accent transition-colors"
              style={{ color: "var(--color-text)", opacity: 0.55 }}
              title={`Also relevant to ${regionLabel(r)}`}
            >
              {regionLabel(r)}
            </button>
          ))}

        {hasAlternateSources && (
          <button
            onClick={() => setSourcesOpen((p) => !p)}
            className="inline-flex items-center gap-1 font-mono text-[10px] uppercase tracking-wider ml-auto hover:text-accent transition-colors"
            style={{ color: "var(--color-text)", opacity: 0.55 }}
            aria-expanded={sourcesOpen}
            aria-controls={`sources-${story.dedup_group_id}`}
          >
            +{story.secondary_sources.length} source{story.secondary_sources.length > 1 ? "s" : ""}
            <ChevronDownIcon open={sourcesOpen} />
          </button>
        )}
      </div>

      {/* Secondary sources list — collapsible */}
      {hasAlternateSources && sourcesOpen && (
        <ul
          id={`sources-${story.dedup_group_id}`}
          className="flex flex-col gap-1 pt-2 border-t border-rim/60 animate-fade-in"
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
                  className="inline-flex items-center gap-1.5 font-mono text-[11px] hover:text-accent transition-colors"
                  style={{ color: "var(--color-text)", opacity: 0.7 }}
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

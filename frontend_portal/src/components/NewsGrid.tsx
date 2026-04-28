import { useNews } from "../hooks/useNews";
import { NewsCard } from "./NewsCard";

// ---------------------------------------------------------------------------
// Skeleton loader
// ---------------------------------------------------------------------------

function SkeletonCard() {
  return (
    <div className="flex flex-col gap-3 rounded-xl bg-card border border-rim p-4 animate-pulse">
      <div className="flex justify-between">
        <div className="h-2.5 w-24 rounded bg-rim" />
        <div className="h-2.5 w-12 rounded bg-rim" />
      </div>
      <div className="space-y-1.5">
        <div className="h-3 w-full rounded bg-rim" />
        <div className="h-3 w-4/5 rounded bg-rim" />
      </div>
      <div className="space-y-1">
        <div className="h-2.5 w-full rounded bg-rim/60" />
        <div className="h-2.5 w-3/4 rounded bg-rim/60" />
      </div>
      <div className="flex gap-1.5 pt-1 border-t border-rim/50">
        <div className="h-4 w-16 rounded bg-rim/60" />
        <div className="h-4 w-8 rounded bg-rim/60" />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Empty & error states
// ---------------------------------------------------------------------------

function EmptyState({ region, categories }: { region?: string; categories: string[] }) {
  const catFilter =
    categories.length === 0 ? null
    : categories.length === 1 ? `category: ${categories[0]}`
    : `${categories.length} categories`;
  const filters = [region && `region: ${region}`, catFilter]
    .filter(Boolean)
    .join(", ");
  return (
    <div className="col-span-full flex flex-col items-center justify-center py-24 text-slate-500 gap-3">
      <span className="text-4xl select-none">📡</span>
      <p className="text-sm font-medium">No stories found{filters ? ` for ${filters}` : ""}.</p>
      <p className="text-xs">The ingestion pipeline may still be running.</p>
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="col-span-full flex flex-col items-center justify-center py-24 text-red-400 gap-3">
      <span className="text-4xl select-none">⚠️</span>
      <p className="text-sm font-medium">Failed to load stories</p>
      <p className="text-xs font-mono text-red-500/70">{message}</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Pagination controls
// ---------------------------------------------------------------------------

interface PaginationProps {
  offset: number;
  limit: number;
  total: number;
  onPageChange: (offset: number) => void;
}

function Pagination({ offset, limit, total, onPageChange }: PaginationProps) {
  const currentPage = Math.floor(offset / limit);
  const totalPages = Math.ceil(total / limit);
  if (totalPages <= 1) return null;

  return (
    <div className="col-span-full flex items-center justify-between pt-4 border-t border-rim">
      <span className="text-xs text-slate-500">
        {offset + 1}–{Math.min(offset + limit, total)} of {total}
      </span>
      <div className="flex gap-2">
        <button
          disabled={offset === 0}
          onClick={() => onPageChange(Math.max(0, offset - limit))}
          className="px-3 py-1.5 text-xs rounded-lg bg-panel border border-rim text-slate-300 hover:border-rim-bright disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          ← Prev
        </button>
        <span className="px-3 py-1.5 text-xs text-slate-400 font-mono">
          {currentPage + 1} / {totalPages}
        </span>
        <button
          disabled={offset + limit >= total}
          onClick={() => onPageChange(offset + limit)}
          className="px-3 py-1.5 text-xs rounded-lg bg-panel border border-rim text-slate-300 hover:border-rim-bright disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          Next →
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// NewsGrid
// ---------------------------------------------------------------------------

interface NewsGridProps {
  region?: string;
  /** Multi-select category state. [] = all. 1 = server-side filter. 2+ = client-side filter. */
  categories: string[];
  offset?: number;
  limit?: number;
  startDate?: string;
  endDate?: string;
  onOffsetChange?: (offset: number) => void;
  onCategoryClick?: (category: string) => void;
  onRegionClick?: (region: string) => void;
}

export function NewsGrid({
  region,
  categories,
  offset = 0,
  limit = 24,
  startDate,
  endDate,
  onOffsetChange,
  onCategoryClick,
  onRegionClick,
}: NewsGridProps) {
  // Server-side filter only when exactly one category is picked. Otherwise we
  // fetch a wider page (limit 1000) and paginate client-side after filtering.
  const multi        = categories.length >= 2;
  const apiCategory  = categories.length === 1 ? categories[0] : undefined;
  const apiOffset    = multi ? 0    : offset;
  const apiLimit     = multi ? 1000 : limit;

  const { data, isLoading, isError, error, isFetching } = useNews({
    region,
    category: apiCategory,
    offset: apiOffset,
    limit: apiLimit,
    start_date: startDate,
    end_date: endDate,
  });

  // Client-side filter + paginate when 2+ categories are picked.
  const allFiltered = multi
    ? (data?.stories ?? []).filter((s) => categories.includes(s.category))
    : (data?.stories ?? []);
  const total       = multi ? allFiltered.length : (data?.total ?? 0);
  const pageStories = multi ? allFiltered.slice(offset, offset + limit) : allFiltered;

  return (
    <div className="flex flex-col gap-4">

      {/* Status bar */}
      <div className="flex items-center justify-between h-5">
        {data && (
          <p className="text-xs text-slate-500">
            <span className="text-slate-300 font-semibold">{total}</span> stories
            {region && <> in <span className="font-mono text-slate-300">{region}</span></>}
            {categories.length === 1 && (
              <> · <span className="text-slate-300">{categories[0]}</span></>
            )}
            {categories.length >= 2 && (
              <> · <span className="text-slate-300">{categories.length} categories</span></>
            )}
          </p>
        )}
        {isFetching && !isLoading && (
          <span className="ml-auto text-xs text-slate-500 flex items-center gap-1.5">
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse_slow" />
            Refreshing…
          </span>
        )}
      </div>

      {/* Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
        {isLoading &&
          Array.from({ length: limit }).map((_, i) => <SkeletonCard key={i} />)}

        {isError && (
          <ErrorState message={(error as Error).message} />
        )}

        {pageStories.length === 0 && !isLoading && (
          <EmptyState region={region} categories={categories} />
        )}

        {pageStories.map((story) => (
          <NewsCard
            key={story.dedup_group_id}
            story={story}
            onCategoryClick={onCategoryClick}
            onRegionClick={onRegionClick}
          />
        ))}

        {/* Pagination */}
        {data && (
          <Pagination
            offset={offset}
            limit={limit}
            total={total}
            onPageChange={(o) => onOffsetChange?.(o)}
          />
        )}
      </div>
    </div>
  );
}

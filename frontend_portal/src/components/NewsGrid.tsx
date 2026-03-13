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

function EmptyState({ region, category }: { region?: string; category?: string }) {
  const filters = [region && `region: ${region}`, category && `category: ${category}`]
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
  category?: string;
  offset?: number;
  limit?: number;
  onOffsetChange?: (offset: number) => void;
  onCategoryClick?: (category: string) => void;
  onRegionClick?: (region: string) => void;
}

export function NewsGrid({
  region,
  category,
  offset = 0,
  limit = 24,
  onOffsetChange,
  onCategoryClick,
  onRegionClick,
}: NewsGridProps) {
  const { data, isLoading, isError, error, isFetching } = useNews({
    region,
    category,
    offset,
    limit,
  });

  return (
    <div className="flex flex-col gap-4">

      {/* Status bar */}
      <div className="flex items-center justify-between h-5">
        {data && (
          <p className="text-xs text-slate-500">
            <span className="text-slate-300 font-semibold">{data.total}</span> stories
            {region && <> in <span className="font-mono text-slate-300">{region}</span></>}
            {category && <> · <span className="text-slate-300">{category}</span></>}
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

        {data?.stories.length === 0 && !isLoading && (
          <EmptyState region={region} category={category} />
        )}

        {data?.stories.map((story) => (
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
            total={data.total}
            onPageChange={(o) => onOffsetChange?.(o)}
          />
        )}
      </div>
    </div>
  );
}

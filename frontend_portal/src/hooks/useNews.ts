import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { fetchNews, type FetchNewsParams, type PaginatedStoriesResponse } from "../services/api";

/**
 * React Query hook for paginated, filtered news stories.
 *
 * - staleTime / refetchInterval are set globally in QueryClient (5 minutes).
 * - keepPreviousData prevents layout flicker during page/filter transitions.
 * - queryKey includes all filter params so each unique combination is cached
 *   independently.
 */
export function useNews(params: FetchNewsParams = {}) {
  const { region, category, limit = 50, offset = 0, start_date, end_date } = params;

  return useQuery<PaginatedStoriesResponse>({
    queryKey: ["news", region ?? "global", category ?? "all", limit, offset, start_date ?? "", end_date ?? ""],
    queryFn: () => fetchNews({ region, category, limit, offset, start_date, end_date }),
    placeholderData: keepPreviousData,
  });
}

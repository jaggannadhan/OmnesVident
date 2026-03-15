/**
 * Client-side API wrapper for the OmnesVident FastAPI backend.
 *
 * All requests go through /api/* which Vite proxies to http://localhost:8000
 * in development.  Set VITE_API_BASE_URL in production.
 */

const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "/api";

export interface StoryOut {
  dedup_group_id: string;
  title: string;
  snippet: string;
  source_url: string;
  source_name: string;
  region_code: string;
  category: string;
  mentioned_regions: string[];
  secondary_sources: string[];
  timestamp: string;
  processed_at: string;
  latitude: number | null;
  longitude: number | null;
}

export interface PaginatedStoriesResponse {
  total: number;
  offset: number;
  limit: number;
  stories: StoryOut[];
}

export interface FetchNewsParams {
  region?: string;
  category?: string;
  limit?: number;
  offset?: number;
}

async function apiFetch<T>(path: string): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`API error ${response.status}: ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export function fetchNews({
  region,
  category,
  limit = 50,
  offset = 0,
}: FetchNewsParams = {}): Promise<PaginatedStoriesResponse> {
  const params = new URLSearchParams();
  // "WORLD" is the catch-all view — omit the filter so all stories are returned
  if (category && category !== "WORLD") params.set("category", category);
  params.set("limit", String(limit));
  params.set("offset", String(offset));

  const qs = params.toString();
  const base = region ? `/news/${encodeURIComponent(region)}` : "/news";
  return apiFetch<PaginatedStoriesResponse>(`${base}${qs ? `?${qs}` : ""}`);
}

export function fetchHealth(): Promise<{ status: string; version: string }> {
  return apiFetch("/health");
}

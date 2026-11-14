const API = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') || '';

async function request<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API}${path}`, { signal, headers: { Accept: 'application/json' } });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json() as { detail?: string; error?: string };
      message = body.detail || body.error || message;
    } catch {}
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export interface OverviewResponse {
  dataset_label: string;
  dataset_note: string;
  kpis: { users: number; content: number; interactions: number; positive_events: number; unique_user_content_pairs: number };
  daily_activity: { date: string; events: number }[];
  genre_distribution: { genre: string; interactions: number }[];
  event_distribution: { event: string; count: number }[];
  model: Record<string, unknown> & { loaded: boolean; algorithm?: string };
}

export interface DatasetSummary {
  name: string;
  description: string;
  rows: number;
  columns: number;
  missing_values: number;
  duplicate_rows: number;
  fields: string[];
}

export interface DatasetPreview {
  name: string;
  columns: string[];
  rows: Record<string, unknown>[];
}

export interface DatasetProfileColumn {
  name: string;
  dtype: string;
  missing: number;
  missing_pct: number;
  unique: number;
  statistics?: { min: number | null; median: number | null; mean: number | null; max: number | null };
  top_values?: { value: string; count: number }[];
}

export interface DatasetProfile {
  name: string;
  rows: number;
  duplicate_rows: number;
  columns: DatasetProfileColumn[];
}

export interface RankingMetrics {
  precision_at_k: number | null;
  recall_at_k: number | null;
  ndcg_at_k: number | null;
}

export interface ModelMetrics {
  algorithm: string;
  content_weight: number;
  collaborative_weight: number;
  users: number;
  items: number;
  positive_user_item_pairs: number;
  latent_factors: number;
  score_semantics: string;
  evaluation_protocol: string;
  k: number;
  seed: number;
  evaluated_users: number;
  train_positive_pairs: number;
  holdout_positive_pairs: number;
  catalog_items: number;
  hybrid: RankingMetrics;
  popularity_baseline: RankingMetrics;
  dataset_label: string;
  dataset_fingerprint_sha256: string;
  trained_at_utc: string;
  training_seed: number;
}

export interface Recommendation {
  user_id: string;
  content_id: string;
  title: string;
  genre: string;
  content_type: string;
  hybrid_score: number;
  content_score: number;
  collaborative_score: number;
  score_type: string;
  reasons: string[];
  rank: number;
}

export interface ForecastResponse {
  content_id: string;
  title: string;
  method: string;
  method_label: string;
  history_end_date: string;
  history: { date: string; actual: number }[];
  forecast: { date: string; value: number; lower: number; upper: number }[];
  interval_note: string;
}

export const api = {
  overview: (signal?: AbortSignal) => request<OverviewResponse>('/api/overview', signal),
  datasets: (signal?: AbortSignal) => request<{ label: string; datasets: DatasetSummary[] }>('/api/datasets', signal),
  preview: (name: string, signal?: AbortSignal) => request<DatasetPreview>(`/api/datasets/${encodeURIComponent(name)}/preview`, signal),
  profile: (name: string, signal?: AbortSignal) => request<DatasetProfile>(`/api/datasets/${encodeURIComponent(name)}/profile`, signal),
  metrics: (signal?: AbortSignal) => request<ModelMetrics>('/api/model/metrics', signal),
  recommendations: (user: string, limit = 8, signal?: AbortSignal) => request<{ user_id: string; items: Recommendation[]; score_semantics: string }>(`/api/recommendations/${encodeURIComponent(user)}?limit=${limit}`, signal),
  users: (search = '', signal?: AbortSignal) => request<{ items: { user_id: string; preferred_genre: string; customer_segment: string }[] }>(`/api/users?search=${encodeURIComponent(search)}&limit=100`, signal),
  content: (signal?: AbortSignal) => request<{ items: { content_id: string; title: string; genre: string; content_type: string }[] }>('/api/content?limit=250', signal),
  forecast: (contentId: string, method: string, periods: number, signal?: AbortSignal) => request<ForecastResponse>(`/api/forecast/${encodeURIComponent(contentId)}?method=${method}&periods=${periods}`, signal),
};
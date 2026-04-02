const BASE = "http://localhost:8000";

export interface ResultEntry {
  name: string;
  inclusion: number;
  num_decks: number;
  source: string;
  price?: number | null;
}

export interface UniqueEntry {
  name: string;
  inclusion: number;
  overall_inclusion: number;
  lift: number;
  price?: number | null;
}

export interface PackageEntry {
  cards: string[];
  avg_lift: number;
  avg_inclusion: number;
}

export interface AntiCorrelationEntry {
  name: string;
  inclusion: number;
  overall_inclusion: number;
  anti_lift: number;
  price?: number | null;
}

export interface ExclusiveEntry {
  name: string;
  inclusion: number;
  max_single_inclusion: number;
  exclusivity: number;
  price?: number | null;
}

export interface RecommendResponse {
  source_used: string;
  deck_count: number;
  matching_decks: number;
  matching_deck_ids: number[];
  consensus: number;
  results: ResultEntry[];
  unique_includes: UniqueEntry[];
  packages: PackageEntry[];
  anti_correlations: AntiCorrelationEntry[];
  exclusive: ExclusiveEntry[];
}

export async function recommend(cards: string[], filter?: string | null): Promise<RecommendResponse> {
  const res = await fetch(`${BASE}/api/recommend`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cards, filter: filter || null }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function autocomplete(q: string): Promise<string[]> {
  if (q.length < 2) return [];
  const res = await fetch(`${BASE}/api/autocomplete?q=${encodeURIComponent(q)}`);
  if (!res.ok) return [];
  return res.json();
}

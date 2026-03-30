const BASE = "http://localhost:8000";

export interface ResultEntry {
  name: string;
  inclusion: number;
  num_decks: number;
  source: string;
}

export interface UniqueEntry {
  name: string;
  inclusion: number;
  overall_inclusion: number;
  lift: number;
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
}

export interface ExclusiveEntry {
  name: string;
  inclusion: number;
  max_single_inclusion: number;
  exclusivity: number;
}

export interface RecommendResponse {
  source_used: string;
  deck_count: number;
  matching_decks: number;
  consensus: number;
  results: ResultEntry[];
  unique_includes: UniqueEntry[];
  packages: PackageEntry[];
  anti_correlations: AntiCorrelationEntry[];
  exclusive: ExclusiveEntry[];
}

export async function recommend(cards: string[]): Promise<RecommendResponse> {
  const res = await fetch(`${BASE}/api/recommend`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cards }),
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

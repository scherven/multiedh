const BASE = "http://localhost:8000";

export interface ResultEntry {
  name: string;
  inclusion: number;
  num_decks: number;
  source: string;
}

export interface RecommendResponse {
  source_used: string;
  deck_count: number;
  matching_decks: number;
  results: ResultEntry[];
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

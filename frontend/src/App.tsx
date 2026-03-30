import { useState, useEffect, useRef } from "react";
import { recommend, type RecommendResponse } from "./api";
import CardInput from "./components/CardInput";
import CardTag from "./components/CardTag";
import ResultCard from "./components/ResultCard";

export default function App() {
  const [cards, setCards] = useState<string[]>([]);
  const [response, setResponse] = useState<RecommendResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (cards.length === 0) { setResponse(null); return; }
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await recommend(cards);
        setResponse(res);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Request failed");
      } finally {
        setLoading(false);
      }
    }, 400);
  }, [cards]);

  function addCard(name: string) {
    if (!cards.includes(name)) setCards(c => [...c, name]);
  }

  function removeCard(name: string) {
    setCards(c => c.filter(x => x !== name));
  }

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      <div className="max-w-2xl mx-auto px-4 py-12">
        <h1 className="text-3xl font-bold mb-1">Multi-Card Recommender</h1>
        <p className="text-gray-400 mb-8 text-sm">
          Find cards that appear in decks with all of your selected cards.
        </p>

        {cards.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-4">
            {cards.map(c => (
              <CardTag key={c} name={c} onRemove={() => removeCard(c)} />
            ))}
          </div>
        )}

        <CardInput onAdd={addCard} existing={cards} />

        {response && (
          <p className="mt-4 text-xs text-gray-500">
            {response.matching_decks.toLocaleString()} matching decks out of{" "}
            {response.deck_count.toLocaleString()} total ·{" "}
            <span className="capitalize">{response.source_used}</span>
          </p>
        )}
        {loading && <p className="mt-4 text-xs text-gray-500">Loading…</p>}
        {error && <p className="mt-4 text-xs text-red-400">{error}</p>}

        {response && response.results.length === 0 && !loading && (
          <p className="mt-8 text-center text-gray-500">No cards found in common.</p>
        )}
        {response && response.results.length > 0 && (
          <div className="mt-6 flex flex-col gap-2">
            {response.results.map((r, i) => (
              <ResultCard key={r.name} entry={r} rank={i + 1} />
            ))}
          </div>
        )}

        {cards.length === 0 && (
          <p className="mt-12 text-center text-gray-600 text-sm">
            Start typing a card name above.
          </p>
        )}
      </div>
    </div>
  );
}

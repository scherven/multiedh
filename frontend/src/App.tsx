import { useState, useEffect, useRef } from "react";
import { recommend, type RecommendResponse } from "./api";
import CardInput from "./components/CardInput";
import CardTag from "./components/CardTag";
import ResultCard from "./components/ResultCard";

function SkeletonRow({ opacity }: { opacity: number }) {
  return (
    <div
      className="flex items-center gap-3 px-3 py-2 bg-gray-800/60 border border-white/5 rounded-xl"
      style={{ opacity }}
    >
      <div className="w-10 h-14 bg-gray-700 rounded animate-pulse shrink-0" />
      <div className="flex-1 space-y-2">
        <div className="h-3 bg-gray-700 rounded animate-pulse w-2/3" />
        <div className="h-2 bg-gray-700/60 rounded-full animate-pulse w-full" />
      </div>
      <div className="w-10 h-3 bg-gray-700 rounded animate-pulse shrink-0" />
    </div>
  );
}

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

        {/* Header */}
        <h1 className="text-4xl font-extrabold tracking-tight bg-gradient-to-r from-indigo-400 to-violet-400 bg-clip-text text-transparent mb-1">
          EDH Recommender
        </h1>
        <p className="text-gray-500 mb-8 text-sm">
          Find cards that appear in decks with all of your selected cards.
        </p>

        {/* Selected card tags */}
        {cards.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-4">
            {cards.map(c => (
              <CardTag key={c} name={c} onRemove={() => removeCard(c)} />
            ))}
          </div>
        )}

        <CardInput onAdd={addCard} existing={cards} />

        {/* Error */}
        {error && (
          <div className="mt-4 px-3 py-2 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
            {error}
          </div>
        )}

        {/* Skeleton loader */}
        {loading && (
          <div className="mt-6 flex flex-col gap-2">
            {Array.from({ length: 6 }).map((_, i) => (
              <SkeletonRow key={i} opacity={1 - i * 0.12} />
            ))}
          </div>
        )}

        {/* Results */}
        {!loading && response && response.results.length > 0 && (
          <>
            <div className="mt-6 mb-3 flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-widest text-gray-500">
                Top Results
              </span>
              <span className="text-xs text-gray-600">
                {response.matching_decks.toLocaleString()} / {response.deck_count.toLocaleString()} decks ·{" "}
                <span className="capitalize">{response.source_used}</span>
              </span>
            </div>
            <div className="flex flex-col gap-2">
              {response.results.map((r, i) => (
                <ResultCard
                  key={r.name}
                  entry={r}
                  rank={i + 1}
                  animationDelay={Math.min(i * 40, 400)}
                />
              ))}
            </div>
          </>
        )}

        {/* No results */}
        {!loading && response && response.results.length === 0 && (
          <div className="mt-16 flex flex-col items-center gap-3 text-center">
            <span className="text-5xl opacity-20" aria-hidden>🔍</span>
            <p className="text-gray-400 text-sm font-medium">No cards found in common.</p>
            <p className="text-gray-600 text-xs">Try removing one of your selected cards.</p>
          </div>
        )}

        {/* Initial empty state */}
        {cards.length === 0 && (
          <div className="mt-16 flex flex-col items-center gap-3 text-center">
            <span className="text-5xl opacity-20" aria-hidden>🃏</span>
            <p className="text-gray-500 text-sm">Search for a card to get started.</p>
          </div>
        )}

      </div>
    </div>
  );
}

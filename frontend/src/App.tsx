import { useState, useEffect, useRef } from "react";
import { recommend, type RecommendResponse, type UniqueEntry, type PackageEntry, type AntiCorrelationEntry, type ExclusiveEntry } from "./api";
import CardInput from "./components/CardInput";
import CardTag from "./components/CardTag";
import ResultCard from "./components/ResultCard";
import { useCardImage, toSize } from "./scryfall";

type Tab = "results" | "unique" | "packages" | "anti" | "exclusive" | "decks";

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

function CardRow({ name, metric, metricLabel, sub, price }: { name: string; metric: string; metricLabel?: string; sub?: string; price?: number | null }) {
  const img = useCardImage(name);
  const slug = name.toLowerCase().replace(/[^a-z0-9\s-]/g, "").replace(/\s+/g, "-");
  return (
    <div className="relative flex items-center gap-3 px-3 py-2 bg-gray-800/60 border border-white/5 rounded-xl hover:bg-gray-700/50 transition-colors group animate-fade-in-up">
      <div className="w-10 shrink-0">
        {img ? (
          <img src={img} alt={name} className="w-10 rounded shadow" />
        ) : (
          <div className="w-10 h-14 bg-gray-700 rounded animate-pulse" />
        )}
      </div>
      {img && (
        <div className="pointer-events-none absolute left-0 bottom-full mb-2 z-30 opacity-0 scale-95 group-hover:opacity-100 group-hover:scale-100 transition-all duration-150 delay-200 group-hover:delay-0">
          <img src={toSize(img, "normal")} alt={name} className="w-52 rounded-xl shadow-2xl ring-1 ring-white/10" />
        </div>
      )}
      <div className="flex-1 min-w-0">
        <a
          href={`https://edhrec.com/cards/${slug}`}
          target="_blank"
          rel="noreferrer"
          className="text-white font-medium hover:text-indigo-400 hover:underline truncate block"
        >
          {name}
        </a>
        {sub && <p className="text-gray-500 text-xs mt-0.5">{sub}</p>}
      </div>
      {price != null && (
        <span className="text-green-400 text-xs font-medium tabular-nums shrink-0">
          ${price.toFixed(2)}
        </span>
      )}
      <span className="text-indigo-300 text-sm font-medium tabular-nums shrink-0">
        {metric}
        {metricLabel && <span className="text-gray-500 text-xs ml-1">{metricLabel}</span>}
      </span>
    </div>
  );
}

function UniqueSection({ items }: { items: UniqueEntry[] }) {
  return (
    <div className="flex flex-col gap-2">
      {items.map(e => (
        <CardRow
          key={e.name}
          name={e.name}
          metric={`${e.lift.toFixed(1)}×`}
          metricLabel="lift"
          sub={`${Math.round(e.inclusion * 100)}% in matching · ${Math.round(e.overall_inclusion * 100)}% overall`}
          price={e.price}
        />
      ))}
    </div>
  );
}

function PackagesSection({ items }: { items: PackageEntry[] }) {
  return (
    <div className="flex flex-col gap-3">
      {items.map((pkg, i) => (
        <div key={i} className="px-3 py-2 bg-gray-800/60 border border-white/5 rounded-xl animate-fade-in-up">
          <div className="flex flex-wrap gap-1.5 mb-2">
            {pkg.cards.map(c => (
              <a
                key={c}
                href={`https://edhrec.com/cards/${c.toLowerCase().replace(/[^a-z0-9\s-]/g, "").replace(/\s+/g, "-")}`}
                target="_blank"
                rel="noreferrer"
                className="px-2 py-0.5 rounded-full bg-indigo-500/20 border border-indigo-500/30 text-indigo-300 text-xs hover:bg-indigo-500/30 transition-colors"
              >
                {c}
              </a>
            ))}
          </div>
          <div className="flex gap-4 text-xs text-gray-500">
            <span>avg lift <span className="text-gray-400">{pkg.avg_lift.toFixed(1)}×</span></span>
            <span>avg inclusion <span className="text-gray-400">{Math.round(pkg.avg_inclusion * 100)}%</span></span>
          </div>
        </div>
      ))}
    </div>
  );
}

function AntiSection({ items }: { items: AntiCorrelationEntry[] }) {
  return (
    <div className="flex flex-col gap-2">
      {items.map(e => (
        <CardRow
          key={e.name}
          name={e.name}
          metric={`${e.anti_lift.toFixed(2)}×`}
          metricLabel="anti-lift"
          sub={`${Math.round(e.inclusion * 100)}% in matching · ${Math.round(e.overall_inclusion * 100)}% overall`}
          price={e.price}
        />
      ))}
    </div>
  );
}

function ExclusiveSection({ items }: { items: ExclusiveEntry[] }) {
  return (
    <div className="flex flex-col gap-2">
      {items.map(e => (
        <CardRow
          key={e.name}
          name={e.name}
          metric={`${e.exclusivity.toFixed(1)}×`}
          metricLabel="exclusivity"
          sub={`${Math.round(e.inclusion * 100)}% combo · ${Math.round(e.max_single_inclusion * 100)}% single-card max`}
          price={e.price}
        />
      ))}
    </div>
  );
}

function DecksSection({ ids }: { ids: number[] }) {
  return (
    <div className="flex flex-col gap-1.5">
      {ids.map(id => (
        <a
          key={id}
          href={`https://archidekt.com/decks/${id}`}
          target="_blank"
          rel="noreferrer"
          className="px-3 py-2 bg-gray-800/60 border border-white/5 rounded-xl text-indigo-300 text-sm hover:bg-gray-700/50 hover:text-indigo-200 transition-colors animate-fade-in-up"
        >
          archidekt.com/decks/{id}
        </a>
      ))}
    </div>
  );
}

export default function App() {
  const [cards, setCards] = useState<string[]>([]);
  const [filterQuery, setFilterQuery] = useState("");
  const [debouncedFilter, setDebouncedFilter] = useState("");
  const [response, setResponse] = useState<RecommendResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("results");
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const filterDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (filterDebounceRef.current) clearTimeout(filterDebounceRef.current);
    filterDebounceRef.current = setTimeout(() => setDebouncedFilter(filterQuery), 900);
  }, [filterQuery]);

  useEffect(() => {
    if (cards.length === 0) { setResponse(null); return; }
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await recommend(cards, debouncedFilter || null);
        setResponse(res);
        setActiveTab("results");
      } catch (e) {
        setError(e instanceof Error ? e.message : "Request failed");
      } finally {
        setLoading(false);
      }
    }, 400);
  }, [cards, debouncedFilter]);

  function addCard(name: string) {
    if (!cards.includes(name)) setCards(c => [...c, name]);
  }

  function removeCard(name: string) {
    setCards(c => c.filter(x => x !== name));
  }

  const tabs: { id: Tab; label: string; count: number }[] = response ? [
    { id: "results", label: "Results", count: response.results.length },
    { id: "unique", label: "Unique", count: response.unique_includes.length },
    { id: "packages", label: "Packages", count: response.packages.length },
    { id: "anti", label: "Anti", count: response.anti_correlations.length },
    ...(response.exclusive.length > 0 ? [{ id: "exclusive" as Tab, label: "Exclusive", count: response.exclusive.length }] : []),
    ...(response.matching_deck_ids?.length > 0 ? [{ id: "decks" as Tab, label: "Decks", count: response.matching_deck_ids.length }] : []),
  ] : [];

  const hasResults = response && (
    response.results.length > 0 ||
    response.unique_includes.length > 0 ||
    response.packages.length > 0 ||
    response.anti_correlations.length > 0 ||
    response.exclusive.length > 0
  );

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

        {/* Scryfall filter */}
        <div className="mt-3 flex items-center gap-2">
          <input
            type="text"
            value={filterQuery}
            onChange={e => setFilterQuery(e.target.value)}
            placeholder="Scryfall filter (e.g. type:creature cmc<=3)"
            className="flex-1 px-3 py-1.5 bg-gray-800 border border-white/10 rounded-lg text-sm text-white placeholder-gray-600 focus:outline-none focus:border-indigo-500/50 transition-colors"
          />
          {filterQuery && (
            <button
              onClick={() => setFilterQuery("")}
              className="text-gray-500 hover:text-gray-300 text-xs transition-colors shrink-0"
            >
              clear
            </button>
          )}
        </div>

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
        {!loading && response && hasResults && (
          <>
            {/* Metadata bar */}
            <div className="mt-6 mb-3 flex items-center justify-between">
              <div className="flex gap-1 flex-wrap">
                {tabs.map(t => (
                  <button
                    key={t.id}
                    onClick={() => setActiveTab(t.id)}
                    className={`px-3 py-1 rounded-full text-xs font-semibold transition-colors ${
                      activeTab === t.id
                        ? "bg-indigo-500/30 text-indigo-300 border border-indigo-500/40"
                        : "bg-gray-800 text-gray-400 border border-white/5 hover:bg-gray-700"
                    }`}
                  >
                    {t.label}
                    <span className="ml-1.5 text-gray-500">{t.count}</span>
                  </button>
                ))}
              </div>
              <span className="text-xs text-gray-600 shrink-0 ml-2">
                {response.matching_decks.toLocaleString()} / {response.deck_count.toLocaleString()} decks
                {response.consensus != null && ` · ${Math.round(response.consensus * 100)}% consensus`}
              </span>
            </div>

            <div className="flex flex-col gap-2">
              {activeTab === "results" && response.results.map((r, i) => (
                <ResultCard key={r.name} entry={r} rank={i + 1} animationDelay={Math.min(i * 40, 400)} />
              ))}
              {activeTab === "unique" && <UniqueSection items={response.unique_includes} />}
              {activeTab === "packages" && <PackagesSection items={response.packages} />}
              {activeTab === "anti" && <AntiSection items={response.anti_correlations} />}
              {activeTab === "exclusive" && <ExclusiveSection items={response.exclusive} />}
              {activeTab === "decks" && <DecksSection ids={response.matching_deck_ids ?? []} />}
            </div>
          </>
        )}

        {/* No results */}
        {!loading && response && !hasResults && (
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

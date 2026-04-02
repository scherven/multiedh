import type { ResultEntry } from "../api";
import { useCardImage, toSize } from "../scryfall";

interface Props {
  entry: ResultEntry;
  rank: number;
  animationDelay?: number;
}

export default function ResultCard({ entry, rank, animationDelay = 0 }: Props) {
  const pct = Math.round(entry.inclusion * 100);
  const edhrecSlug = entry.name
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, "")
    .replace(/\s+/g, "-");
  const smallImg = useCardImage(entry.name);

  return (
    <div
      className="relative flex items-center gap-3 px-3 py-2 bg-gray-800/60 border border-white/5 rounded-xl hover:bg-gray-700/50 transition-colors group animate-fade-in-up"
      style={{ animationDelay: `${animationDelay}ms` }}
    >
      {/* Thumbnail */}
      <div className="w-10 shrink-0">
        {smallImg ? (
          <img src={smallImg} alt={entry.name} className="w-10 rounded shadow" />
        ) : (
          <div className="w-10 h-14 bg-gray-700 rounded animate-pulse" />
        )}
      </div>

      {/* Hover preview — fades in after 200ms, hides instantly */}
      {smallImg && (
        <div className="pointer-events-none absolute left-0 bottom-full mb-2 z-30 opacity-0 scale-95 group-hover:opacity-100 group-hover:scale-100 transition-all duration-150 delay-200 group-hover:delay-0">
          <img
            src={toSize(smallImg, "normal")}
            alt={entry.name}
            className="w-52 rounded-xl shadow-2xl ring-1 ring-white/10"
          />
        </div>
      )}

      <span className="w-7 text-right text-gray-600 text-xs font-mono tabular-nums shrink-0">
        {rank}
      </span>

      <div className="flex-1 min-w-0">
        <a
          href={`https://edhrec.com/cards/${edhrecSlug}`}
          target="_blank"
          rel="noreferrer"
          className="text-white font-medium hover:text-indigo-400 hover:underline truncate block"
        >
          {entry.name}
        </a>
        <div className="mt-1 h-2 bg-gray-700/60 rounded-full overflow-hidden">
          <div
            className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-violet-500"
            style={{ width: `${Math.min(pct, 100)}%` }}
          />
        </div>
      </div>

      <span className="text-indigo-300 text-sm font-medium tabular-nums shrink-0">{pct}%</span>
      {entry.price != null && (
        <span className="text-green-400 text-xs font-medium tabular-nums shrink-0">
          ${entry.price.toFixed(2)}
        </span>
      )}
      {entry.num_decks > 0 && (
        <span className="text-gray-600 text-xs shrink-0">
          {entry.num_decks.toLocaleString()} decks
        </span>
      )}
    </div>
  );
}

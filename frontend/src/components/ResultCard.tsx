import type { ResultEntry } from "../api";
import { useCardImage, toSize } from "../scryfall";

interface Props {
  entry: ResultEntry;
  rank: number;
}

export default function ResultCard({ entry, rank }: Props) {
  const pct = Math.round(entry.inclusion * 100);
  const edhrecSlug = entry.name
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, "")
    .replace(/\s+/g, "-");
  const smallImg = useCardImage(entry.name);

  return (
    <div className="relative flex items-center gap-3 px-3 py-2 bg-gray-800 rounded-lg hover:bg-gray-750 transition-colors group">

      {/* Thumbnail */}
      <div className="w-10 shrink-0">
        {smallImg ? (
          <img src={smallImg} alt={entry.name} className="w-10 rounded shadow" />
        ) : (
          <div className="w-10 h-14 bg-gray-700 rounded animate-pulse" />
        )}
      </div>

      {/* Hover preview – full normal image floats above the row */}
      {smallImg && (
        <div className="pointer-events-none absolute left-0 bottom-full mb-2 z-30 hidden group-hover:block">
          <img
            src={toSize(smallImg, "normal")}
            alt={entry.name}
            className="w-52 rounded-xl shadow-2xl ring-1 ring-white/10"
          />
        </div>
      )}

      <span className="w-7 text-right text-gray-500 text-sm font-mono shrink-0">{rank}</span>

      <div className="flex-1 min-w-0">
        <a
          href={`https://edhrec.com/cards/${edhrecSlug}`}
          target="_blank"
          rel="noreferrer"
          className="text-white font-medium hover:text-indigo-400 truncate block"
        >
          {entry.name}
        </a>
        <div className="mt-1 h-1.5 bg-gray-700 rounded-full overflow-hidden">
          <div
            className="h-full bg-indigo-500 rounded-full"
            style={{ width: `${Math.min(pct, 100)}%` }}
          />
        </div>
      </div>

      <span className="text-indigo-300 text-sm font-medium shrink-0">{pct}%</span>
      {entry.num_decks > 0 && (
        <span className="text-gray-500 text-xs shrink-0">
          {entry.num_decks.toLocaleString()} decks
        </span>
      )}
    </div>
  );
}

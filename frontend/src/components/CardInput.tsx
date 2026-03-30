import { useState, useRef, useEffect } from "react";
import { autocomplete } from "../api";
import { fetchCardImage } from "../scryfall";

interface Props {
  onAdd: (card: string) => void;
  existing: string[];
}

/** Bolds the first occurrence of `query` inside `text`. */
function HighlightMatch({ text, query }: { text: string; query: string }) {
  if (!query) return <>{text}</>;
  const idx = text.toLowerCase().indexOf(query.toLowerCase());
  if (idx === -1) return <>{text}</>;
  return (
    <>
      {text.slice(0, idx)}
      <span className="font-semibold text-white">{text.slice(idx, idx + query.length)}</span>
      {text.slice(idx + query.length)}
    </>
  );
}

/** Tiny card thumbnail used inside the autocomplete dropdown. */
function SuggestionThumb({ name }: { name: string }) {
  const [img, setImg] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    fetchCardImage(name).then((url) => { if (active) setImg(url); });
    return () => { active = false; };
  }, [name]);

  return img ? (
    <img src={img} alt="" className="w-8 h-11 object-cover rounded shrink-0" />
  ) : (
    <div className="w-8 h-11 bg-gray-700 rounded shrink-0 animate-pulse" />
  );
}

export default function CardInput({ onAdd, existing }: Props) {
  const [value, setValue] = useState("");
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [activeIdx, setActiveIdx] = useState(-1);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (value.length < 2) { setSuggestions([]); return; }
    debounceRef.current = setTimeout(async () => {
      const results = await autocomplete(value);
      setSuggestions(results.filter((r) => !existing.includes(r)));
    }, 200);
  }, [value, existing]);

  function commit(name: string) {
    if (!name.trim()) return;
    onAdd(name.trim());
    setValue("");
    setSuggestions([]);
    setActiveIdx(-1);
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") {
      setActiveIdx((i) => Math.min(i + 1, suggestions.length - 1));
    } else if (e.key === "ArrowUp") {
      setActiveIdx((i) => Math.max(i - 1, -1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (activeIdx >= 0 && suggestions[activeIdx]) {
        commit(suggestions[activeIdx]);
      } else if (value.trim()) {
        commit(value);
      }
    } else if (e.key === "Escape") {
      setSuggestions([]);
      setActiveIdx(-1);
    }
  }

  return (
    <div className="relative">
      <input
        type="text"
        value={value}
        onChange={(e) => { setValue(e.target.value); setActiveIdx(-1); }}
        onKeyDown={onKeyDown}
        placeholder="Add a card…"
        className="w-full px-4 py-2 rounded-lg bg-gray-800 border border-gray-600 text-white placeholder-gray-400 focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/50 transition-shadow"
      />
      {suggestions.length > 0 && (
        <ul className="absolute z-10 mt-1 w-full bg-gray-800 border border-gray-600 rounded-lg overflow-hidden shadow-lg max-h-72 overflow-y-auto animate-fade-in-up">
          {suggestions.map((s, i) => (
            <li
              key={s}
              className={`flex items-center gap-3 px-3 py-1.5 cursor-pointer text-sm ${
                i === activeIdx ? "bg-indigo-600 text-white" : "text-gray-300 hover:bg-gray-700"
              }`}
              onMouseDown={() => commit(s)}
            >
              <SuggestionThumb name={s} />
              <span className="truncate">
                <HighlightMatch text={s} query={value} />
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

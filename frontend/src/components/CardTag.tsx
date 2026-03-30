import { useCardImage, toSize } from "../scryfall";

interface Props {
  name: string;
  onRemove: () => void;
}

export default function CardTag({ name, onRemove }: Props) {
  const smallImg = useCardImage(name);

  return (
    <span className="relative group inline-flex items-center gap-1 px-3 py-1 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 text-sm font-medium animate-fade-in-up">
      {name}
      <button
        onClick={onRemove}
        className="ml-1 text-indigo-400 hover:text-white leading-none transition-colors"
        aria-label={`Remove ${name}`}
      >
        ×
      </button>

      {/* Hover preview — fades in smoothly */}
      {smallImg && (
        <div className="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-30 opacity-0 scale-95 group-hover:opacity-100 group-hover:scale-100 transition-all duration-150">
          <img
            src={toSize(smallImg, "normal")}
            alt={name}
            className="w-52 rounded-xl shadow-2xl ring-1 ring-white/10"
          />
        </div>
      )}
    </span>
  );
}

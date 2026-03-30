import { useCardImage, toSize } from "../scryfall";

interface Props {
  name: string;
  onRemove: () => void;
}

export default function CardTag({ name, onRemove }: Props) {
  const smallImg = useCardImage(name);

  return (
    <span className="relative group inline-flex items-center gap-1 px-3 py-1 rounded-full bg-indigo-600 text-white text-sm font-medium">
      {name}
      <button
        onClick={onRemove}
        className="ml-1 text-indigo-200 hover:text-white leading-none"
        aria-label={`Remove ${name}`}
      >
        ×
      </button>

      {/* Hover: float a full card image above the tag */}
      {smallImg && (
        <div className="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-30 hidden group-hover:block">
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

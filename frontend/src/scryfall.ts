import { useState, useEffect } from "react";

// ── throttled fetch queue ────────────────────────────────────────────────────
// Scryfall asks for ≤10 req/s; we cap at 5 concurrent to be polite.
const MAX_CONCURRENT = 5;
let inFlight = 0;
const queue: Array<() => void> = [];

function drainQueue() {
  while (inFlight < MAX_CONCURRENT && queue.length > 0) {
    inFlight++;
    queue.shift()!();
  }
}

// ── image cache (keyed by lowercased card name) ──────────────────────────────
const imageCache = new Map<string, Promise<string | null>>();

async function searchOldest(name: string): Promise<string | null> {
  // Searching with order=released&dir=asc&unique=prints gives us the oldest
  // physical printing as the first result.
  const q = encodeURIComponent(`!"${name}"`);
  const res = await fetch(
    `https://api.scryfall.com/cards/search?q=${q}&order=released&dir=asc&unique=prints`,
    { headers: { Accept: "application/json" } },
  );
  if (!res.ok) return null;
  const data = await res.json();
  const card = data.data?.[0];
  if (!card) return null;
  // Double-faced cards store images on card_faces[0]
  return (
    card.image_uris?.small ??
    card.card_faces?.[0]?.image_uris?.small ??
    null
  );
}

/** Return (and cache) the small image URL for the oldest printing of a card. */
export function fetchCardImage(name: string): Promise<string | null> {
  const key = name.toLowerCase();
  if (imageCache.has(key)) return imageCache.get(key)!;

  const promise = new Promise<string | null>((resolve) => {
    queue.push(async () => {
      try {
        resolve(await searchOldest(name));
      } catch {
        resolve(null);
      } finally {
        inFlight--;
        drainQueue();
      }
    });
    drainQueue();
  });

  imageCache.set(key, promise);
  return promise;
}

/**
 * Swap the size segment in a Scryfall CDN URL.
 * e.g. toSize(url, "normal") turns a /small/ URL into a /normal/ one.
 */
export function toSize(smallUrl: string, size: "normal" | "large"): string {
  return smallUrl.replace(/\/small\//, `/${size}/`);
}

// ── React hook ───────────────────────────────────────────────────────────────

/** Resolves the oldest-printing small image URL for a card name. */
export function useCardImage(name: string): string | null {
  const [img, setImg] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    fetchCardImage(name).then((url) => {
      if (active) setImg(url);
    });
    return () => {
      active = false;
    };
  }, [name]);
  return img;
}

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

// ── localStorage persistence ──────────────────────────────────────────────────
const LS_PREFIX = "scryfall:img:";

function lsGet(key: string): string | null | undefined {
  try {
    const raw = localStorage.getItem(LS_PREFIX + key);
    if (raw === null) return undefined;          // never stored
    return raw === "" ? null : raw;              // "" encodes a null result
  } catch {
    return undefined;
  }
}

function lsSet(key: string, url: string | null): void {
  try {
    localStorage.setItem(LS_PREFIX + key, url ?? "");
  } catch {
    // localStorage full or unavailable — silently ignore
  }
}

// ── in-memory cache (keyed by lowercased card name) ──────────────────────────
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

  // 1. In-memory cache (fastest)
  if (imageCache.has(key)) return imageCache.get(key)!;

  // 2. localStorage cache (free across page loads / restarts)
  const stored = lsGet(key);
  if (stored !== undefined) {
    const hit = Promise.resolve(stored);
    imageCache.set(key, hit);
    return hit;
  }

  // 3. Network fetch, then persist to both caches
  const promise = new Promise<string | null>((resolve) => {
    queue.push(async () => {
      try {
        const url = await searchOldest(name);
        lsSet(key, url);
        resolve(url);
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

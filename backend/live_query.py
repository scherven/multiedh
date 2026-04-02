"""
Live on-demand deck query via Archidekt API with file-based caching.

Flow:
  1. For each input card, fetch all Commander deck IDs that contain it
     (paginated, cached to cache/cards/{slug}.json)
  2. Intersect the ID sets across all cards
  3. Fetch full deck details for each intersecting ID
     (cached to cache/decks/{id}.json)
  4. Return parsed deck dicts ready for DeckIndex.build()

On HTTP 429: immediately prints an error and raises RateLimitError.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path
import tqdm

import httpx

from archidekt import _extract_cards

CARDS_URL = "https://archidekt.com/api/decks/v3/"
DECK_URL = "https://archidekt.com/api/decks/{id}/"
PAGE_SIZE = 100
_ID_DELAY = 2.0    # seconds between pagination requests for a single card
_DECK_DELAY = 2.0  # seconds between individual deck fetches (uncached only)

# Serializes all get_deck_ids_for_card network fetches across concurrent requests.
# New requests queue here rather than interrupting an in-progress paginating fetch.
_id_lock = asyncio.Lock()


class RateLimitError(Exception):
    pass


def _slug(card_name: str) -> str:
    return re.sub(r"[^\w]", "_", card_name.lower())


def _ensure_cache(cache_dir: Path) -> None:
    (cache_dir / "cards").mkdir(parents=True, exist_ok=True)
    (cache_dir / "decks").mkdir(parents=True, exist_ok=True)


async def _fetch_ids_inner(
    client: httpx.AsyncClient,
    card_name: str,
    cache_file: Path,
) -> list[int]:
    """Paginate Archidekt and write results to cache_file. Called under _id_lock."""
    ids: list[int] = []
    page = 1

    with tqdm.tqdm(desc=f"IDs for '{card_name}'", unit="id") as bar:
        while True:
            resp = await client.get(
                CARDS_URL,
                params={
                    "cardName": card_name,
                    "formats": 3,
                    "orderBy": "-updatedAt",
                    "pageSize": PAGE_SIZE,
                    "page": page,
                },
                timeout=30,
            )

            if resp.status_code == 429:
                print(f"[live_query] 429 rate-limited while fetching IDs for '{card_name}' — stopping", flush=True)
                raise RateLimitError(f"Rate limited on card '{card_name}' page {page}")

            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])

            if not results:
                break

            for deck in results:
                if "id" in deck:
                    ids.append(deck["id"])

            bar.update(len(results))
            bar.set_postfix(page=page)
            page += 1
            await asyncio.sleep(_ID_DELAY)

    cache_file.write_text(json.dumps(ids))
    print(f"[live_query] cached {len(ids)} deck IDs for '{card_name}'", flush=True)
    return ids


async def get_deck_ids_for_card(
    client: httpx.AsyncClient,
    card_name: str,
    cache_dir: Path,
) -> list[int]:
    """
    Return all Archidekt Commander deck IDs that contain card_name.
    Results are cached to cache_dir/cards/{slug}.json.

    Concurrent calls are serialized via _id_lock so only one paginating fetch
    runs at a time. The actual network work is wrapped in asyncio.shield() so
    that if the outer task is cancelled (by a newer request), the fetch runs to
    completion and writes the cache before the lock is released.
    """
    slug = _slug(card_name)
    cache_file = cache_dir / "cards" / f"{slug}.json"

    # Fast path: already cached — no need to acquire the lock.
    if cache_file.exists():
        print(f"[live_query] card cache hit: {card_name}", flush=True)
        return json.loads(cache_file.read_text())

    async with _id_lock:
        # Double-check: another request may have populated the cache while
        # we were waiting to acquire the lock.
        if cache_file.exists():
            print(f"[live_query] card cache hit (post-lock): {card_name}", flush=True)
            return json.loads(cache_file.read_text())

        # Shield the network work so that a cancellation of the outer task
        # does not interrupt an in-progress paginating fetch.  The inner task
        # will finish and write the cache; the lock is released only after it
        # does, so the next queued caller will see the cache hit.
        return await asyncio.shield(_fetch_ids_inner(client, card_name, cache_file))


async def get_deck_details(
    client: httpx.AsyncClient,
    deck_id: int,
    cache_dir: Path,
) -> dict | None:
    """
    Return the raw Archidekt deck JSON for deck_id.
    Cached to cache_dir/decks/{deck_id}.json.
    """
    cache_file = cache_dir / "decks" / f"{deck_id}.json"

    if cache_file.exists():
        return json.loads(cache_file.read_text())

    resp = await client.get(DECK_URL.format(id=deck_id), timeout=30)

    if resp.status_code == 429:
        print(f"[live_query] 429 rate-limited while fetching deck {deck_id} — stopping", flush=True)
        raise RateLimitError(f"Rate limited on deck {deck_id}")

    if resp.status_code != 200:
        print(f"[live_query] deck {deck_id} returned {resp.status_code}, skipping", flush=True)
        return None

    cache_file.write_text(resp.text)
    return resp.json()


async def fetch_matching_decks(
    client: httpx.AsyncClient,
    cards: list[str],
    cache_dir: Path,
) -> tuple[list[dict], list[set[int]]]:
    """
    For each card, fetch all Commander deck IDs that contain it (cached).
    Intersect the ID sets, then fetch full deck details for matching IDs (cached).

    Returns:
        (decks, per_card_id_sets)
        - decks: list of dicts with keys "id", "cards", "commanders"
        - per_card_id_sets: one set[int] per input card (for future exclusive metric)
    """
    _ensure_cache(cache_dir)

    per_card_id_sets: list[set[int]] = []
    for card in cards:
        ids = await get_deck_ids_for_card(client, card, cache_dir)
        per_card_id_sets.append(set(ids))

    if not per_card_id_sets:
        return [], []

    matching_ids: set[int] = per_card_id_sets[0].copy()
    for s in per_card_id_sets[1:]:
        matching_ids &= s

    print(f"[live_query] {len(matching_ids)} decks contain all {len(cards)} card(s)", flush=True)

    decks: list[dict] = []
    matching_list = sorted(list(matching_ids))
    for deck_id in tqdm.tqdm(matching_list):
        cache_file = cache_dir / "decks" / f"{deck_id}.json"
        was_cached = cache_file.exists()

        raw = await get_deck_details(client, deck_id, cache_dir)
        if raw is None:
            continue

        card_set, commanders = _extract_cards(raw)
        if card_set:
            decks.append({
                "id": deck_id,
                "cards": sorted(card_set),
                "commanders": commanders,
            })

        # Only sleep if we hit the network (not a cache hit)
        if not was_cached:
            await asyncio.sleep(_DECK_DELAY)

    print(f"[live_query] fetched {len(decks)} non-empty matching decks", flush=True)
    return decks, per_card_id_sets

from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from index import DeckIndex
from live_query import RateLimitError, fetch_matching_decks

_DIR = Path(__file__).parent
_CACHE_DIR = _DIR / "cache"
SCRYFALL_SEARCH = "https://api.scryfall.com/cards/search"
SCRYFALL_AUTOCOMPLETE = "https://api.scryfall.com/cards/autocomplete"
SCRYFALL_COLLECTION = "https://api.scryfall.com/cards/collection"
SCRYFALL_MAX_PAGES = 5  # cap at 875 cards per filter query

_search_cache: dict[str, frozenset[str]] = {}
_price_cache: dict[str, float | None] = {}

# Persistent HTTP client (shared across requests so shielded card-ID tasks can
# continue using it even after the outer recommend task is cancelled).
_http_client: httpx.AsyncClient | None = None

# The asyncio Task currently running a recommend request.  A new request
# cancels this before starting its own work.
_active_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _http_client
    _http_client = httpx.AsyncClient()
    yield
    await _http_client.aclose()


app = FastAPI(title="Multi-Card Recommender", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Models ────────────────────────────────────────────────────────────────────

class RecommendRequest(BaseModel):
    cards: list[str]
    filter: str | None = None  # Scryfall query to filter recommendation outputs


# ── Scryfall filter resolution ────────────────────────────────────────────────

async def _resolve_filter(client: httpx.AsyncClient, query: str) -> frozenset[str]:
    if query in _search_cache:
        return _search_cache[query]

    names: list[str] = []
    url: str | None = SCRYFALL_SEARCH
    params: dict | None = {"q": query, "unique": "cards"}
    pages = 0

    while url and pages < SCRYFALL_MAX_PAGES:
        resp = await client.get(url, params=params, timeout=10)
        if resp.status_code == 404:
            break
        if resp.status_code != 200:
            return frozenset()  # invalid query → no-op filter
        data = resp.json()
        for card in data.get("data", []):
            if card.get("name"):
                names.append(card["name"].lower())
        url = data.get("next_page")
        params = None
        pages += 1

    result = frozenset(names)
    _search_cache[query] = result
    return result


def _apply_filter(items: list[dict], filter_set: frozenset[str]) -> list[dict]:
    return [item for item in items if item["name"].lower() in filter_set]


async def _fetch_prices(client: httpx.AsyncClient, names: list[str]) -> dict[str, float | None]:
    """Batch-fetch USD prices from Scryfall for a list of (lowercase) card names."""
    to_fetch = [n for n in names if n not in _price_cache]
    for i in range(0, len(to_fetch), 75):
        chunk = to_fetch[i : i + 75]
        try:
            resp = await client.post(
                SCRYFALL_COLLECTION,
                json={"identifiers": [{"name": n} for n in chunk]},
                timeout=10,
            )
            if resp.status_code != 200:
                for n in chunk:
                    _price_cache[n] = None
                continue
            data = resp.json()
            found: dict[str, float | None] = {}
            for card in data.get("data", []):
                key = card.get("name", "").lower()
                price_str = card.get("prices", {}).get("usd")
                found[key] = float(price_str) if price_str else None
            for n in chunk:
                _price_cache[n] = found.get(n)
        except Exception:
            for n in chunk:
                _price_cache[n] = None
    return {n: _price_cache.get(n) for n in names}


# ── Routes ────────────────────────────────────────────────────────────────────

@app.post("/api/recommend")
async def recommend(req: RecommendRequest) -> dict[str, Any]:
    global _active_task
    print(1)

    # Register this task first (before any await) so we have an accurate
    # reference, then cancel the previous in-flight request if there was one.
    prev = _active_task
    _active_task = asyncio.current_task()
    if prev is not None and not prev.done():
        prev.cancel()
        try:
            await prev
        except (asyncio.CancelledError, Exception):
            pass
    print(2)
    if not req.cards:
        raise HTTPException(400, "Provide at least one card")
    print(3)
    input_cards = [c.lower().strip() for c in req.cards]
    print(4)
    try:
        decks, _ = await fetch_matching_decks(_http_client, input_cards, _CACHE_DIR)
    except asyncio.CancelledError:
        # A newer request superseded us — tell the client to retry.
        raise HTTPException(503, "Request superseded by a newer query")
    except RateLimitError as e:
        raise HTTPException(429, str(e))
    print(5)
    if not decks:
        raise HTTPException(404, "No decks found containing all specified cards")
    print(6)
    index = DeckIndex()
    index.build([set(d["cards"]) for d in decks])
    results, unique, packages, anti, exclusive, consensus = index.query(input_cards)
    print(7)
    filter_info = None
    if req.filter:
        filter_set = await _resolve_filter(_http_client, req.filter)
        filter_info = {"query": req.filter, "card_count": len(filter_set)}
        results = _apply_filter(results, filter_set)
        unique = _apply_filter(unique, filter_set)
        anti = _apply_filter(anti, filter_set)
        exclusive = _apply_filter(exclusive, filter_set)
    print(8)
    all_names = list(dict.fromkeys(
        e["name"] for lst in (results, unique, anti, exclusive) for e in lst
    ))
    prices = await _fetch_prices(_http_client, all_names)
    print(9)
    for lst in (results, unique, anti, exclusive):
        for entry in lst:
            entry["price"] = prices.get(entry["name"])
    print(10)
    return {
        "deck_count": len(decks),
        "matching_decks": len(decks),
        "matching_deck_ids": [d["id"] for d in decks],
        "consensus": round(consensus, 4),
        "filter": filter_info,
        "results": results,
        "unique_includes": unique,
        "packages": packages,
        "anti_correlations": anti,
        "exclusive": exclusive,
    }


@app.get("/api/autocomplete")
async def autocomplete(q: str = Query(..., min_length=2)) -> list[str]:
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(SCRYFALL_AUTOCOMPLETE, params={"q": q}, timeout=5)
            resp.raise_for_status()
            return resp.json().get("data", [])
    except Exception:
        return []


@app.get("/api/status")
async def status() -> dict[str, Any]:
    cache_cards = len(list((_CACHE_DIR / "cards").glob("*.json"))) if (_CACHE_DIR / "cards").exists() else 0
    cache_decks = len(list((_CACHE_DIR / "decks").glob("*.json"))) if (_CACHE_DIR / "decks").exists() else 0
    return {
        "cached_cards": cache_cards,
        "cached_decks": cache_decks,
    }

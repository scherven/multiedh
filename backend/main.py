from __future__ import annotations
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


app = FastAPI(title="Multi-Card Recommender")

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
    limit: int = 100


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
            detail = resp.json().get("details", resp.text)
            raise HTTPException(400, f"Scryfall error: {detail}")
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
    if not req.cards:
        raise HTTPException(400, "Provide at least one card")

    input_cards = [c.lower().strip() for c in req.cards]

    async with httpx.AsyncClient() as client:
        try:
            decks, _ = await fetch_matching_decks(client, input_cards, _CACHE_DIR)
        except RateLimitError as e:
            raise HTTPException(429, str(e))

        if not decks:
            raise HTTPException(404, "No decks found containing all specified cards")

        index = DeckIndex()
        index.build([set(d["cards"]) for d in decks])
        results, unique, packages, anti, exclusive, consensus = index.query(input_cards, limit=req.limit)

        filter_info = None
        if req.filter:
            filter_set = await _resolve_filter(client, req.filter)
            filter_info = {"query": req.filter, "card_count": len(filter_set)}
            results = _apply_filter(results, filter_set)
            unique = _apply_filter(unique, filter_set)
            anti = _apply_filter(anti, filter_set)
            exclusive = _apply_filter(exclusive, filter_set)

        all_names = list(dict.fromkeys(
            e["name"] for lst in (results, unique, anti, exclusive) for e in lst
        ))
        prices = await _fetch_prices(client, all_names)

    for lst in (results, unique, anti, exclusive):
        for entry in lst:
            entry["price"] = prices.get(entry["name"])

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

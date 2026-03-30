from __future__ import annotations
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from index import deck_index

_DECKS_FILE = Path(__file__).parent / "decks.json"
SCRYFALL_SEARCH = "https://api.scryfall.com/cards/search"
SCRYFALL_AUTOCOMPLETE = "https://api.scryfall.com/cards/autocomplete"
SCRYFALL_MAX_PAGES = 5  # cap at 875 cards per filter query

_search_cache: dict[str, frozenset[str]] = {}


# ── Startup ───────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    if _DECKS_FILE.exists():
        raw = json.loads(_DECKS_FILE.read_text())
        decks = [set(deck) for deck in raw]
        deck_index.build(decks)
        print(f"[startup] loaded {len(decks)} decks from {_DECKS_FILE.name}")
    else:
        print(f"[startup] {_DECKS_FILE} not found — run download.py first")
    yield


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


# ── Routes ────────────────────────────────────────────────────────────────────

@app.post("/api/recommend")
async def recommend(req: RecommendRequest) -> dict[str, Any]:
    if not req.cards:
        raise HTTPException(400, "Provide at least one card")
    if not deck_index.loaded:
        raise HTTPException(503, "Deck data not loaded — run download.py first")

    input_cards = [c.lower().strip() for c in req.cards]
    results, unique, packages, anti, exclusive, consensus = deck_index.query(input_cards, limit=req.limit)

    sets = [deck_index.inverted.get(c, set()) for c in input_cards]
    matching = sets[0].copy()
    for s in sets[1:]:
        matching &= s

    filter_info = None
    if req.filter:
        async with httpx.AsyncClient() as client:
            filter_set = await _resolve_filter(client, req.filter)
        filter_info = {"query": req.filter, "card_count": len(filter_set)}
        results = _apply_filter(results, filter_set)
        unique = _apply_filter(unique, filter_set)
        anti = _apply_filter(anti, filter_set)
        exclusive = _apply_filter(exclusive, filter_set)

    return {
        "deck_count": len(deck_index.decks),
        "matching_decks": len(matching),
        "consensus": round(consensus, 4),
        "filter": filter_info,
        "results": results,
        "unique_includes": unique,
        "packages": packages,
        "anti_correlations": anti,
        "exclusive": exclusive,
    }


@app.post("/api/reload")
async def reload() -> dict[str, Any]:
    if _DECKS_FILE.exists():
        raw = json.loads(_DECKS_FILE.read_text())
        decks = [set(deck) for deck in raw]
        deck_index.build(decks)
        return {"deck_count": len(decks)}
    return {"deck_count": 0}


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
    return {
        "deck_count": len(deck_index.decks),
        "data_file": str(_DECKS_FILE),
        "data_file_exists": _DECKS_FILE.exists(),
    }

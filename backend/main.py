from contextlib import asynccontextmanager
import json
from pathlib import Path
import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from edhrec import query_edhrec
from index import deck_index

_DECKS_FILE = Path(__file__).parent / "decks.json"


@asynccontextmanager
async def lifespan(app: FastAPI):
    _load_index_from_file()
    yield


app = FastAPI(title="Multi-Card Recommender", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _load_index_from_file() -> int:
    if not _DECKS_FILE.exists():
        print(f"[startup] {_DECKS_FILE} not found — run download.py first. Starting with empty index.")
        return 0
    raw = json.loads(_DECKS_FILE.read_text())
    decks = [set(deck) for deck in raw]
    deck_index.build(decks)
    print(f"[startup] loaded {len(decks)} decks from {_DECKS_FILE.name}")
    return len(decks)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class RecommendRequest(BaseModel):
    cards: list[str]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.post("/api/recommend")
async def recommend(req: RecommendRequest):
    if len(req.cards) < 1:
        raise HTTPException(status_code=400, detail="Provide at least one card")

    if deck_index.loaded:
        results = deck_index.query(req.cards)
        normalized = [c.lower() for c in req.cards]
        matching = deck_index.inverted.get(normalized[0], set()).copy() if normalized else set()
        for c in normalized[1:]:
            matching &= deck_index.inverted.get(c, set())
        return {
            "source_used": "archidekt",
            "deck_count": len(deck_index.decks),
            "matching_decks": len(matching),
            "results": results[:100],
        }
    else:
        print("[recommend] Archidekt index empty, falling back to EDHREC")
        results = await query_edhrec(req.cards)
        return {
            "source_used": "edhrec",
            "deck_count": 0,
            "matching_decks": 0,
            "results": results[:100],
        }


@app.post("/api/reload")
async def reload():
    deck_count = _load_index_from_file()
    return {"deck_count": deck_count}


@app.get("/api/autocomplete")
async def autocomplete(q: str = Query(..., min_length=2)):
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.scryfall.com/cards/autocomplete",
                params={"q": q},
                timeout=5,
            )
            resp.raise_for_status()
            return resp.json().get("data", [])
    except Exception:
        return []

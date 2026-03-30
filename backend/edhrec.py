import asyncio
import re
import math
import httpx
from intersection import ResultEntry

BASE_URL = "https://json.edhrec.com/pages/cards"


def _slug(card_name: str) -> str:
    s = card_name.lower()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"\s+", "-", s.strip())
    return s


def _parse_cardlist(data: dict) -> list[dict]:
    """Extract the flat card list from an EDHREC JSON response."""
    try:
        json_dict = data["container"]["json_dict"]
        cards = []
        for section in json_dict.get("cardlists", []):
            cards.extend(section.get("cardviews", []))
        return cards
    except (KeyError, TypeError):
        return []


async def _fetch_one(client: httpx.AsyncClient, card_name: str) -> list[dict]:
    slug = _slug(card_name)
    try:
        resp = await client.get(f"{BASE_URL}/{slug}.json", timeout=15)
        resp.raise_for_status()
        return _parse_cardlist(resp.json())
    except Exception as e:
        print(f"[edhrec] failed for '{card_name}': {e}")
        return []


async def query_edhrec(cards: list[str]) -> list[ResultEntry]:
    """Fallback: fetch per-card EDHREC data and intersect results."""
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(*[_fetch_one(client, c) for c in cards])

    # Build name→inclusion map per input card
    maps: list[dict[str, float]] = []
    for card_list in results:
        m: dict[str, float] = {}
        for entry in card_list:
            name = entry.get("name", "")
            inclusion = entry.get("inclusion", 0) / 100  # EDHREC returns 0-100
            if name:
                m[name.lower()] = inclusion
        maps.append(m)

    if not maps:
        return []

    # Intersect: only cards present in all maps
    common_keys = set(maps[0].keys())
    for m in maps[1:]:
        common_keys &= m.keys()

    input_set = {c.lower() for c in cards}
    output: list[ResultEntry] = []
    for key in common_keys:
        if key in input_set:
            continue
        inclusions = [m[key] for m in maps]
        # Geometric mean
        geo_mean = math.exp(sum(math.log(max(i, 1e-9)) for i in inclusions) / len(inclusions))
        # Use original casing from first map's card list
        display_name = key
        for card_list in results:
            for entry in card_list:
                if entry.get("name", "").lower() == key:
                    display_name = entry["name"]
                    break
        output.append({
            "name": display_name,
            "inclusion": geo_mean,
            "num_decks": 0,
            "source": "edhrec",
        })

    output.sort(key=lambda r: r["inclusion"], reverse=True)
    return output

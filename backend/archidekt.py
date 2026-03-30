import asyncio
import httpx
from tqdm import tqdm

LIST_URL = "https://archidekt.com/api/decks/v3/"
DECK_URL = "https://archidekt.com/api/decks/{id}/"
# Format 3 = Commander/EDH
LIST_PARAMS = {"formats": 3, "pageSize": 100, "orderBy": "-createdAt"}

# Seconds between list-page requests
_LIST_DELAY = 2.0
# Max concurrent individual-deck fetches
_CONCURRENCY = 10


async def fetch_all_decks(client: httpx.AsyncClient, start_page: int = 1) -> list[set[str]]:
    """
    Paginate Archidekt Commander deck list, then fetch each deck individually
    to retrieve card data. Returns each deck as a set of lowercased card names.
    """
    deck_ids = await _collect_deck_ids(client, start_page=start_page)
    print(f"[archidekt] fetching {len(deck_ids)} individual decks…")
    decks = await _fetch_decks_concurrent(client, deck_ids)
    print(f"[archidekt] done — {len(decks)} non-empty decks")
    return decks


async def _collect_deck_ids(client: httpx.AsyncClient, start_page: int = 1) -> list[int]:
    """Page through the deck list endpoint and collect all deck IDs."""
    ids: list[int] = []
    page = start_page

    with tqdm(total=1000, desc="fetching pages") as bar:
        while True:
            try:
                resp = await client.get(
                    LIST_URL,
                    params={**LIST_PARAMS, "page": page},
                    timeout=30,
                )
                resp.raise_for_status()
            except (httpx.HTTPError, httpx.TimeoutException) as e:
                bar.write(f"[archidekt] list stopped at page {page}: {e}")
                break

            data = resp.json()
            results = data.get("results", [])
            if not results:
                break

            ids.extend(deck["id"] for deck in results)

            # If the API tells us the total count, derive exact page total
            total_count = data.get("count")
            if total_count is not None:
                page_size = LIST_PARAMS["pageSize"]
               # bar.total = -(-total_count // page_size)  # ceil division

            bar.set_postfix(decks=len(ids))
            bar.update(1)
            page += 1

            await asyncio.sleep(_LIST_DELAY)

    return ids


async def _fetch_decks_concurrent(
    client: httpx.AsyncClient, deck_ids: list[int]
) -> list[set[str]]:
    """Fetch individual deck details concurrently with a progress bar."""
    sem = asyncio.Semaphore(_CONCURRENCY)

    async def fetch_one(deck_id: int) -> set[str]:
        async with sem:
            try:
                resp = await client.get(DECK_URL.format(id=deck_id), timeout=30)
                resp.raise_for_status()
                return _extract_cards(resp.json())
            except (httpx.HTTPError, httpx.TimeoutException) as e:
                print(f"[archidekt] failed deck {deck_id}: {e}")
                return set()

    tasks = [fetch_one(did) for did in deck_ids]
    results = await asyncio.gather(*tasks)
    return [r for r in results if r]


def _extract_cards(deck: dict) -> set[str]:
    """Extract card names from an Archidekt deck detail object."""
    cards: set[str] = set()
    for card_entry in deck.get("cards", []):
        name = _card_name(card_entry)
        if name:
            cards.add(name.lower())
    return cards


def _card_name(entry: dict) -> str | None:
    """Resolve card name from an Archidekt card entry."""
    card = entry.get("card", {})
    if isinstance(card, dict):
        name = card.get("oracleCard", {}).get("name") or card.get("name")
        if name:
            return name
    if isinstance(card, str):
        return card
    return entry.get("name") or entry.get("cardName")

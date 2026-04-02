import asyncio
import json
from pathlib import Path

import httpx
from tqdm import tqdm

LIST_URL = "https://archidekt.com/api/decks/v3/"
DECK_URL = "https://archidekt.com/api/decks/{id}/"
# Format 3 = Commander/EDH
LIST_PARAMS = {"formats": 3, "pageSize": 100, "orderBy": "-createdAt"}

# Seconds between list-page requests
_LIST_DELAY = 2.0
# Seconds between individual-deck fetches
_DECK_DELAY = 1.0
# Write checkpoint to disk after every N completed decks
_CHECKPOINT_EVERY = 200


def _flush(decks: list[dict], path: Path) -> None:
    """Atomically write decks to path as JSON."""
    path.write_text(json.dumps(decks))


async def fetch_all_decks(
    client: httpx.AsyncClient,
    output_path: Path,
    ids_path: Path,
    errors_path: Path,
    start_page: int = 1,
) -> list[dict]:
    """
    Paginate Archidekt Commander deck list, then fetch each deck individually.
    Returns each deck as a dict with metadata + sorted card list.

    Intermediate state is written to output_path every _CHECKPOINT_EVERY decks
    and on keyboard interrupt, so re-running resumes where it left off.
    The deck-ID listing is cached in ids_path to skip the listing phase on resume.
    IDs that error are saved to errors_path and skipped on resume.
    """
    # ── Listing phase ─────────────────────────────────────────────────────────
    if ids_path.exists():
        listing: list[dict] = json.loads(ids_path.read_text())
        print(f"[archidekt] resuming — loaded {len(listing)} deck IDs from {ids_path.name}")
    else:
        listing = await _collect_deck_listing(client, start_page, ids_path)
        print(f"[archidekt] saved {len(listing)} deck IDs to {ids_path.name}")

    # ── Resume: skip already-fetched deck IDs ─────────────────────────────────
    existing_decks: list[dict] = []
    already_fetched: set[int] = set()
    if output_path.exists():
        try:
            raw: list = json.loads(output_path.read_text())
            existing_decks = [d for d in raw if isinstance(d, dict) and "id" in d]
            already_fetched = {d["id"] for d in existing_decks}
            if already_fetched:
                print(f"[archidekt] skipping {len(already_fetched)} already-fetched decks")
        except Exception:
            pass

    # ── Resume: skip previously errored deck IDs ──────────────────────────────
    existing_errors: set[int] = set()
    if errors_path.exists():
        try:
            existing_errors = set(json.loads(errors_path.read_text()))
            if existing_errors:
                print(f"[archidekt] skipping {len(existing_errors)} previously errored decks")
        except Exception:
            pass

    skip = already_fetched | existing_errors
    pending = [item for item in listing if item["id"] not in skip]
    print(f"[archidekt] fetching {len(pending)} individual decks…")

    # ── Fetch phase ───────────────────────────────────────────────────────────
    new_decks = await _fetch_decks_concurrent(client, pending, existing_decks, output_path, existing_errors, errors_path)
    all_decks = existing_decks + new_decks
    print(f"[archidekt] done — {len(all_decks)} non-empty decks total")
    return all_decks


async def _collect_deck_listing(
    client: httpx.AsyncClient, start_page: int = 1, ids_path: Path | None = None
) -> list[dict]:
    """
    Page through the deck-list endpoint and collect deck IDs + basic metadata.
    Checkpoints to ids_path after every page. Handles keyboard interrupt
    gracefully, saving progress and returning whatever was collected.
    """
    listing: list[dict] = []
    page = start_page

    try:
        with tqdm(desc="listing pages") as bar:
            while True and page < 10000:
                try:
                    resp = await client.get(
                        LIST_URL,
                        params={**LIST_PARAMS, "page": page},
                        timeout=30,
                    )
                    resp.raise_for_status()
                except (httpx.HTTPError, httpx.TimeoutException) as e:
                    bar.write(f"[archidekt] listing stopped at page {page}: {e}")
                    break

                data = resp.json()
                results = data.get("results", [])
                if not results:
                    break

                for deck in results:
                    owner = deck.get("owner", "")
                    listing.append({
                        "id": deck["id"],
                        "name": deck.get("name", ""),
                        "owner": owner.get("username", "") if isinstance(owner, dict) else str(owner),
                        "created_at": deck.get("createdAt", ""),
                        "updated_at": deck.get("updatedAt", ""),
                    })

                if ids_path is not None:
                    _flush(listing, ids_path)

                bar.set_postfix(decks=len(listing))
                bar.update(1)
                page += 1
                await asyncio.sleep(_LIST_DELAY)

    except KeyboardInterrupt:
        if ids_path is not None:
            _flush(listing, ids_path)
        print(f"\n[archidekt] listing interrupted — collected {len(listing)} IDs so far")

    return listing


async def _fetch_decks_concurrent(
    client: httpx.AsyncClient,
    pending: list[dict],
    existing: list[dict],
    output_path: Path,
    existing_errors: set[int],
    errors_path: Path,
) -> list[dict]:
    """
    Fetch individual deck details sequentially with a delay between requests.
    Writes a checkpoint to output_path every _CHECKPOINT_EVERY completions
    and always flushes on exit (including keyboard interrupt).
    Failed deck IDs are accumulated and saved to errors_path.
    """
    completed: list[dict] = []
    new_errors: set[int] = set()
    all_errors = existing_errors | new_errors

    def _flush_errors() -> None:
        errors_path.write_text(json.dumps(sorted(all_errors)))

    try:
        with tqdm(total=len(pending), desc="fetching decks") as bar:
            for i, item in enumerate(pending):
                try:
                    resp = await client.get(DECK_URL.format(id=item["id"]), timeout=30)
                    resp.raise_for_status()
                    cards, commanders = _extract_cards(resp.json())
                    if cards:
                        completed.append({
                            "id": item["id"],
                            "name": item.get("name", ""),
                            "owner": item.get("owner", ""),
                            "created_at": item.get("created_at", ""),
                            "url": f"https://archidekt.com/decks/{item['id']}",
                            "commanders": commanders,
                            "cards": sorted(cards),
                        })
                except (httpx.HTTPError, httpx.TimeoutException) as e:
                    tqdm.write(f"[archidekt] failed deck {item['id']}: {e}")
                    new_errors.add(item["id"])
                    all_errors.add(item["id"])

                bar.update(1)
                n_done = bar.n
                if n_done % _CHECKPOINT_EVERY == 0:
                    _flush(existing + completed, output_path)
                    _flush_errors()
                    bar.write(
                        f"[archidekt] checkpoint — {len(existing) + len(completed)} decks saved, {len(all_errors)} errors"
                    )

                if i < len(pending) - 1:
                    await asyncio.sleep(_DECK_DELAY)

    except KeyboardInterrupt:
        print(f"\n[archidekt] interrupted — saving {len(existing) + len(completed)} decks…")
    finally:
        _flush(existing + completed, output_path)
        _flush_errors()

    if new_errors:
        print(f"[archidekt] {len(new_errors)} decks failed — IDs saved to {errors_path.name}")

    return completed


def _extract_cards(deck: dict) -> tuple[set[str], list[str]]:
    """
    Extract card names and commander names from an Archidekt deck detail object.
    Returns (cards, commanders) — both use the original-casing name;
    cards are lowercased when stored.
    """
    cards: set[str] = set()
    commanders: list[str] = []
    for card_entry in deck.get("cards", []):
        name = _card_name(card_entry)
        if not name:
            continue
        cards.add(name.lower())
        # Detect the "Commander" category (list of strings or dicts)
        categories = card_entry.get("categories", [])
        if isinstance(categories, list) and any(
            (c if isinstance(c, str) else c.get("name", "")).lower() == "commander"
            for c in categories
        ):
            commanders.append(name)
    return cards, commanders


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

"""
Download all Archidekt Commander decks and save to decks.json.

Saves a checkpoint every 200 decks — re-run at any time to resume.
Deck IDs are cached in deck_ids.json to skip the listing phase on resume.

Usage:
    python download.py                  # download (or resume)
    python download.py --start-page 42  # resume listing from a specific page
    python download.py --fresh          # discard progress and start over
"""

import argparse
import asyncio
import json
from pathlib import Path

import httpx

from archidekt import fetch_all_decks

_DIR = Path(__file__).parent
OUTPUT = _DIR / "decks.json"
IDS_FILE = _DIR / "deck_ids.json"


async def main(start_page: int, fresh: bool) -> None:
    if fresh:
        for f in (OUTPUT, IDS_FILE):
            if f.exists():
                f.unlink()
                print(f"[download] removed {f.name}")

    async with httpx.AsyncClient() as client:
        decks = await fetch_all_decks(
            client,
            output_path=OUTPUT,
            ids_path=IDS_FILE,
            start_page=start_page,
        )

    # Final authoritative write
    OUTPUT.write_text(json.dumps(decks))
    print(f"[download] saved {len(decks)} decks to {OUTPUT}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download Archidekt Commander decks")
    parser.add_argument(
        "--start-page",
        type=int,
        default=1,
        metavar="N",
        help="listing page to start from (default: 1; ignored when resuming from deck_ids.json)",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="discard deck_ids.json and decks.json and start from scratch",
    )
    args = parser.parse_args()

    try:
        asyncio.run(main(start_page=args.start_page, fresh=args.fresh))
    except KeyboardInterrupt:
        print("\n[download] interrupted — progress saved; re-run to resume")

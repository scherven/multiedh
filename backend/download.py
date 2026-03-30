"""
Download all Archidekt Commander decks and save to decks.json.

Usage:
    python download.py
    python download.py --start-page 42
"""

import argparse
import asyncio
import json
from pathlib import Path

import httpx

from archidekt import fetch_all_decks

OUTPUT = Path(__file__).parent / "decks.json"


async def main(start_page: int) -> None:
    print(f"[download] fetching Archidekt decks (starting at page {start_page})…")
    async with httpx.AsyncClient() as client:
        decks = await fetch_all_decks(client, start_page=start_page)

    # Sets aren't JSON-serializable; store as sorted lists
    serializable = [sorted(deck) for deck in decks]
    OUTPUT.write_text(json.dumps(serializable))
    print(f"[download] saved {len(decks)} decks to {OUTPUT}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download Archidekt Commander decks")
    parser.add_argument(
        "--start-page",
        type=int,
        default=1,
        metavar="N",
        help="page number to start fetching from (default: 1)",
    )
    args = parser.parse_args()
    asyncio.run(main(start_page=args.start_page))

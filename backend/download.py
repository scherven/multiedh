"""
Download all Archidekt Commander decks and save to decks.json.

Saves a checkpoint every 200 decks — re-run at any time to resume.
Deck IDs are cached in deck_ids.json to skip the listing phase on resume.

Usage:
    python download.py                  # download (or resume)
    python download.py --start-page 42  # resume listing from a specific page
    python download.py --fresh          # discard progress and start over
    python download.py --saved          # resume using deck_ids_saved.json / decks_saved.json
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
ERRORS_FILE = _DIR / "decks_error.json"
OUTPUT_SAVED = _DIR / "decks_saved.json"
IDS_FILE_SAVED = _DIR / "deck_ids_saved.json"
ERRORS_FILE_SAVED = _DIR / "decks_saved_error.json"


async def main(start_page: int, fresh: bool, saved: bool) -> None:
    output = OUTPUT_SAVED if saved else OUTPUT
    ids_file = IDS_FILE_SAVED if saved else IDS_FILE
    errors_file = ERRORS_FILE_SAVED if saved else ERRORS_FILE

    if saved:
        print(f"[download] --saved mode: using {ids_file.name} → {output.name} (errors: {errors_file.name})")

    if fresh:
        for f in (output, ids_file, errors_file):
            if f.exists():
                f.unlink()
                print(f"[download] removed {f.name}")

    async with httpx.AsyncClient() as client:
        decks = await fetch_all_decks(
            client,
            output_path=output,
            ids_path=ids_file,
            errors_path=errors_file,
            start_page=start_page,
        )

    # Final authoritative write
    output.write_text(json.dumps(decks))
    print(f"[download] saved {len(decks)} decks to {output}")


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
    parser.add_argument(
        "--saved",
        action="store_true",
        help="resume using deck_ids_saved.json as the ID source and decks_saved.json as output",
    )
    args = parser.parse_args()

    try:
        asyncio.run(main(start_page=args.start_page, fresh=args.fresh, saved=args.saved))
    except KeyboardInterrupt:
        print("\n[download] interrupted — progress saved; re-run to resume")

#!/usr/bin/env python3
"""
Import seed poems and sources into the database.
Run from the project root: python scripts/import_seeds.py
"""
import sys
from pathlib import Path

# Allow importing from backend/
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend import db, feeds

POEMS_FILE = Path(__file__).parent.parent / "data" / "seed_poems.txt"
SOURCES_FILE = Path(__file__).parent.parent / "data" / "seed_sources.txt"


def load_lines(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]


def main():
    db.init_db()

    # Import sources
    sources = load_lines(SOURCES_FILE)
    print(f"Importing {len(sources)} sources...")
    for url in sources:
        db.source_upsert({"url": url})
    print(f"  Done.")

    # Import individual poem URLs
    poems = load_lines(POEMS_FILE)
    print(f"Importing {len(poems)} poem URLs...")
    added = 0
    skipped = 0
    for url in poems:
        try:
            db.poem_upsert({"url": url, "scrape_status": "pending"})
            added += 1
        except Exception as e:
            print(f"  Skipping {url}: {e}")
            skipped += 1

    print(f"  Added: {added}, Skipped: {skipped}")
    stats = db.stats()
    print(f"\nDatabase now contains:")
    print(f"  {stats['total_poems']} poems ({stats['pending']} pending scrape)")
    print(f"  {stats['active_sources']} sources")
    print(f"\nRun the app and visit /api/scrape-pending to fetch poem text.")


if __name__ == "__main__":
    main()

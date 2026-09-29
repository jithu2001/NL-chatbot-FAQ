#!/usr/bin/env python
"""Delete and recreate the ChromaDB collection (downloaded documents are kept).

Usage:
    python scripts/reset_vector_db.py        # asks for confirmation
    python scripts/reset_vector_db.py --yes  # no prompt
Then re-run: python scripts/ingest_sources.py
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.config import get_settings
from app.rag import vector_store


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    args = parser.parse_args()

    settings = get_settings()
    before = vector_store.stored_count_any_model()
    if not args.yes:
        reply = input(f"Delete all {before} chunks in collection '{settings.collection_name}'? [y/N] ")
        if reply.strip().lower() not in {"y", "yes"}:
            print("Aborted.")
            return 1
    vector_store.reset_collection()
    print(f"Collection '{settings.collection_name}' recreated ({before} chunks removed, now {vector_store.count()}).")
    print("Run `python scripts/ingest_sources.py` to rebuild the index.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

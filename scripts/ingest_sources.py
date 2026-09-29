#!/usr/bin/env python
"""Ingest every official source in data/sources.csv into ChromaDB.

Usage (from the project root, with the backend virtualenv active):
    python scripts/ingest_sources.py            # skip unchanged sources
    python scripts/ingest_sources.py --refresh  # re-download documents
    python scripts/ingest_sources.py --force    # re-embed everything
    python scripts/ingest_sources.py --only SRC-001 SRC-004
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.rag.ingest import main

if __name__ == "__main__":
    sys.exit(main())

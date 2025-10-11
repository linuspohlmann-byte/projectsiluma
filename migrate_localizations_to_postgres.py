#!/usr/bin/env python3
"""
One-time utility to seed the PostgreSQL `localization` table from `localization_complete.csv`.

Usage:
    DATABASE_URL=postgres://user:pass@host:port/dbname python migrate_localizations_to_postgres.py [--csv path/to/file.csv]
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from server import postgres
from server.postgres import RealDictCursor
from server.db import seed_postgres_localization_from_csv

ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_CSV = ROOT_DIR / "localization_complete.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed PostgreSQL localization table from CSV.")
    parser.add_argument(
        "--csv",
        dest="csv_path",
        type=Path,
        default=DEFAULT_CSV,
        help=f"Path to localization CSV (default: {DEFAULT_CSV})",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    csv_path = args.csv_path

    if not csv_path.exists():
        print(f"❌ Localization CSV not found at {csv_path}")
        return 1

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL environment variable not set.")
        return 1

    print(f"🚀 Seeding PostgreSQL localization table using {csv_path}")
    try:
        conn = postgres.connect(database_url, cursor_factory=RealDictCursor)
    except Exception as exc:
        print(f"❌ Failed to connect to PostgreSQL: {exc}")
        return 1

    try:
        seed_postgres_localization_from_csv(conn, csv_path)
        conn.commit()
        print("✅ Localization data synchronized successfully.")
        return 0
    except Exception as exc:  # pragma: no cover - manual script
        print(f"❌ Localization synchronization failed: {exc}")
        conn.rollback()
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())

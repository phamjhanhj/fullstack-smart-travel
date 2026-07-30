"""Idempotently import the local Data directory into PostgreSQL."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from app.db.session import AsyncSessionLocal
from app.services.place_data_service import import_dataset

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "Data"


async def run(data_dir: Path, dry_run: bool) -> None:
    async with AsyncSessionLocal() as db:
        report = await import_dataset(db, data_dir, dry_run=dry_run)
    result = report.as_dict()
    result.pop("issues", None)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(args.data_dir, args.dry_run))


if __name__ == "__main__":
    main()

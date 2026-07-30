"""Validate the local Data directory without changing the database."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.services.place_data_service import scan_dataset

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "Data"


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--show-issues", type=int, default=30)
    args = parser.parse_args()

    report, _ = scan_dataset(args.data_dir)
    result = report.as_dict()
    result["issues"] = result["issues"][:max(args.show_issues, 0)]
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if report.rejected:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

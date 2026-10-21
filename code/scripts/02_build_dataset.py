#!/usr/bin/env python3
"""Build the common processed dataset from cached raw and interim data."""

from __future__ import annotations

import argparse
import logging

from wargame.data.build_dataset import build_dataset


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--start", help="First operating day (YYYY-MM-DD)")
    parser.add_argument("--end", help="Last operating day, inclusive (YYYY-MM-DD)")
    parser.add_argument("--days", type=int, help="Only process the first N selected days")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    tables = build_dataset(
        args.config,
        start=args.start,
        end=args.end,
        days=args.days,
        show_progress=True,
    )
    for name, table in tables.items():
        logging.info("%-32s %d rows", name, len(table))


if __name__ == "__main__":
    main()


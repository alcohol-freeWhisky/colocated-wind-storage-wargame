#!/usr/bin/env python3
"""Download the public inputs for the Workshop 1 dataset."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from tqdm import tqdm

from wargame.data.build_dataset import load_config, pool_resources, selected_days
from wargame.data.eia import build_eia860_summary
from wargame.data.ercot import fetch_cop_day, fetch_dam_day, fetch_prices, fetch_sced_wind_day


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--start", help="First operating day (YYYY-MM-DD)")
    parser.add_argument("--end", help="Last operating day, inclusive (YYYY-MM-DD)")
    parser.add_argument("--days", type=int, help="Only process the first N selected days")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    raw = Path(config["paths"]["raw"])
    interim = Path(config["paths"]["interim"])
    processed = Path(config["paths"]["processed"])
    log_path = Path(config["paths"]["results"]) / "logs" / "download.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(log_path), logging.StreamHandler()],
    )
    logger = logging.getLogger(__name__)
    dates = selected_days(config, start=args.start, end=args.end, days=args.days)
    resources = pool_resources(config)

    fetch_prices(int(config["data"]["price_year"]), str(config["data"]["hub"]), raw)
    for day in tqdm(dates, desc="ERCOT operating days", unit="day"):
        fetch_sced_wind_day(day, resources, interim)
        fetch_cop_day(day, resources, interim)
        fetch_dam_day(day, resources, interim)

    try:
        build_eia860_summary(config["data"]["eia860_url"], raw, processed)
    except Exception:
        logger.exception("Failed to download or summarize EIA-860")
    logger.info("Download run complete for %d operating days", len(dates))


if __name__ == "__main__":
    main()


"""Write hourly dispatch trajectories (all regimes) for specific operating days.

Usage:
    .venv/bin/python code/scripts/03b_trajectories.py --config config/base.yaml --days 2025-04-26 2025-03-10

Reuses the per-day worker of 03_run_regimes.py so the trajectories are identical
to those of the full run; useful for illustrative figures without re-running the window.
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code"))

spec = importlib.util.spec_from_file_location("run_regimes", Path(__file__).with_name("03_run_regimes.py"))
run_regimes = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(run_regimes)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/base.yaml"))
    parser.add_argument("--days", nargs="+", required=True, help="Operating days YYYY-MM-DD")
    args = parser.parse_args()
    cfg = yaml.safe_load(args.config.read_text())
    agents = list(cfg["data"]["primary_agents"])
    out_dir = ROOT / cfg["paths"]["results"] / "tables" / "trajectories"
    out_dir.mkdir(parents=True, exist_ok=True)
    for day in args.days:
        t0 = time.time()
        item = run_regimes._run_day((day, agents, cfg))
        if "error" in item and item.get("error"):
            print(f"{day}: FAILED {item['error']}")
            continue
        for regime, frame in item["trajectories"].items():
            run_regimes.write_table(frame, out_dir / f"{day}_{regime}.csv", cfg, time.time() - t0, day=day, regime=regime)
        print(f"{day}: wrote {len(item['trajectories'])} trajectory files in {time.time() - t0:.1f} s")


if __name__ == "__main__":
    main()

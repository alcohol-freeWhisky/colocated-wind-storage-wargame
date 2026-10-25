#!/usr/bin/env python3
"""Tune proximal PRICE coordination over selected days and matrix cells."""

from __future__ import annotations

import argparse
import copy
import multiprocessing as mp
import os
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from wargame.experiments.io import assess_complete_days, load_config, write_table
from wargame.model.env import build_episode
from wargame.solvers.design_matrix import solve_cell

PRICE_CELLS = ("D_P_INJ_PRICE", "D_P_EQ_PRICE", "D_F_INJ_PRICE")
DEFAULT_DAYS = ("2025-03-01", "2025-03-02", "2025-04-26")


def _flatten(values: list[str], cast: type = str) -> list[Any]:
    return [cast(part) for value in values for part in value.split(",") if part.strip()]


def _run_task(task: tuple[float, float, str, list[str], dict[str, Any]]) -> dict[str, Any]:
    tau, rho, day, agents, base = task
    cfg = copy.deepcopy(base)
    coordination = cfg.setdefault("design_matrix", {}).setdefault("price_coordination", {})
    coordination.update(
        {
            "proximal_tau": tau,
            "step_usd_per_mwh_per_mw": rho,
            "step_decay": "none",
        }
    )
    episode = build_episode(day, agents, cfg)
    converged: list[bool] = []
    iterations: list[int] = []
    for cell in PRICE_CELLS:
        result = solve_cell(episode, cell, cfg)
        converged.extend(result.price_converged_by_hour or [])
        iterations.extend(result.price_iterations_by_hour or [])
    return {
        "proximal_tau": tau,
        "rho": rho,
        "day": day,
        "converged_hours": int(sum(converged)),
        "total_hours": len(converged),
        "iterations_sum": int(sum(iterations)),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/base.yaml"))
    parser.add_argument("--scenario", type=Path)
    parser.add_argument("--days", nargs="+", default=list(DEFAULT_DAYS))
    parser.add_argument("--taus", nargs="+", default=["0.1", "0.5", "2.0"])
    parser.add_argument("--rhos", nargs="+", default=["0.2", "0.5", "1.0"])
    parser.add_argument("--workers", type=int, default=min(4, os.cpu_count() or 1))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    started = time.perf_counter()
    cfg = load_config(args.config, args.scenario)
    days = _flatten(args.days)
    taus = _flatten(args.taus, float)
    rhos = _flatten(args.rhos, float)
    if not days or not taus or not rhos or any(value <= 0 for value in taus + rhos):
        raise SystemExit("--days must be nonempty and --taus/--rhos must be positive")

    agents = list(cfg["data"]["primary_agents"])
    complete, _ = assess_complete_days(cfg, agents)
    available = {day.date().isoformat() for day in complete}
    missing = [day for day in days if day not in available]
    if missing:
        raise SystemExit(f"Requested days are not complete/available: {missing}")

    tasks = [
        (tau, rho, day, agents, cfg)
        for tau in taus
        for rho in rhos
        for day in days
    ]
    workers = max(1, min(args.workers, len(tasks)))
    if workers == 1:
        raw = [_run_task(task) for task in tasks]
    else:
        with mp.get_context("fork").Pool(workers) as pool:
            raw = pool.map(_run_task, tasks)

    daily = pd.DataFrame(raw)
    table = (
        daily.groupby(["proximal_tau", "rho"], as_index=False, sort=True)
        .agg(
            converged_hours=("converged_hours", "sum"),
            total_hours=("total_hours", "sum"),
            iterations_sum=("iterations_sum", "sum"),
        )
    )
    table["converged_hours_frac"] = table["converged_hours"] / table["total_hours"]
    table["mean_iterations"] = table["iterations_sum"] / table["total_hours"]
    ranked = table.sort_values(
        ["converged_hours_frac", "mean_iterations"], ascending=[False, True]
    )
    chosen_index = ranked.index[0]
    table["chosen"] = table.index == chosen_index
    table = table.drop(columns="iterations_sum")

    output = Path(str(cfg.get("paths", {}).get("results", "results"))) / "tables" / "price_tuning.csv"
    write_table(
        table,
        output,
        cfg,
        time.perf_counter() - started,
        days=days,
        cells=list(PRICE_CELLS),
        workers=workers,
    )
    print(table.to_string(index=False, float_format=lambda value: f"{value:.4f}"))
    chosen = table.loc[table["chosen"]].iloc[0]
    if float(chosen["converged_hours_frac"]) < 0.9:
        raise SystemExit("No tuning pair reached 90% converged hours")


if __name__ == "__main__":
    main()

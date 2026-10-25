#!/usr/bin/env python3
"""Run the revised four-factor design matrix over complete operating days."""

from __future__ import annotations

import argparse
import json
import logging
import multiprocessing as mp
import os
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from wargame.experiments.design import CELL_ORDER, parse_cell
from wargame.experiments.io import assess_complete_days, load_config, write_table
from wargame.experiments.metrics import episode_metrics
from wargame.experiments.plots import plot_design_effects, plot_design_matrix
from wargame.model.env import Episode, build_episode
from wargame.solvers.design_matrix import solve_cell

LOGGER = logging.getLogger("wargame.design_matrix")
LIST_COLUMNS = {
    "per_agent_profit",
    "per_agent_profit_planned",
    "per_agent_penalty_minus",
    "per_agent_penalty_plus",
    "per_agent_net_profit",
    "per_agent_penalty_minus_eq",
    "per_agent_penalty_plus_eq",
    "sweeps_by_hour",
    "game_converged_by_hour",
    "price_iterations_by_hour",
    "price_converged_by_hour",
    "price_max_overflow_by_hour",
    "price_max_mu_by_hour",
}


def _trajectory(episode: Episode, cell: str, realization: Any) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for t in range(episode.T):
        for i, agent in enumerate(episode.agents):
            mu = np.nan
            if realization.mu_by_hour is not None:
                mu = realization.mu_by_hour[t, t]
            records.append(
                {
                    "day": str(episode.day),
                    "hour": t,
                    "cell": cell,
                    "agent": agent.name,
                    "q_i": realization.q[i, t],
                    "q_i_planned": realization.q_planned[i, t],
                    "c_i": realization.c[i, t],
                    "d_i": realization.d[i, t],
                    "r_i": realization.r[i, t],
                    "soc_i": realization.soc[i, t + 1],
                    "w_minus_i": realization.w_minus[i, t],
                    "w_plus_i": realization.w_plus[i, t],
                    "mu": mu,
                    "Q": realization.q[:, t].sum(),
                    "Q_planned": realization.q_planned[:, t].sum(),
                    "K": episode.K,
                    "D": episode.D[t],
                    "pi_RT": episode.pi_RT[t],
                }
            )
    return pd.DataFrame.from_records(records)


def _run_day(task: tuple[str, list[str], dict[str, Any], list[str]]) -> dict[str, Any]:
    day, agents, cfg, cells = task
    try:
        episode = build_episode(day, agents, cfg)
        rows: list[dict[str, Any]] = []
        trajectories: dict[str, pd.DataFrame] = {}
        for cell in cells:
            started = time.perf_counter()
            realization = solve_cell(episode, cell, cfg)
            elapsed = time.perf_counter() - started
            factors = parse_cell(cell)
            row = episode_metrics(episode, realization, cell)
            row.pop("regime", None)
            row.update({"cell": cell, **factors})
            row["price_iterations_mean"] = (
                float(np.mean(realization.price_iterations_by_hour))
                if realization.price_iterations_by_hour
                else np.nan
            )
            row["price_max_overflow_mwh"] = (
                float(np.max(realization.price_max_overflow_by_hour))
                if realization.price_max_overflow_by_hour
                else np.nan
            )
            row["price_max_mu_usd_per_mwh"] = (
                float(np.max(realization.price_max_mu_by_hour))
                if realization.price_max_mu_by_hour
                else np.nan
            )
            row["price_iterations_by_hour"] = realization.price_iterations_by_hour
            row["price_converged_by_hour"] = realization.price_converged_by_hour
            row["price_max_overflow_by_hour"] = realization.price_max_overflow_by_hour
            row["price_max_mu_by_hour"] = realization.price_max_mu_by_hour
            row["game_converged_by_hour"] = realization.game_converged_by_hour
            row["converged"] = (
                realization.converged
                if factors["info"] in {"FULL", "PRICE"}
                else np.nan
            )
            row["elapsed_s"] = elapsed
            for key in LIST_COLUMNS.intersection(row):
                row[key] = json.dumps(row[key])
            rows.append(row)
            trajectories[cell] = _trajectory(episode, cell, realization)
            LOGGER.info("cell=%s day=%s elapsed_s=%.3f", cell, day, elapsed)
        return {"day": day, "rows": rows, "trajectories": trajectories}
    except Exception as exc:
        return {"day": day, "error": f"{type(exc).__name__}: {exc}"}


def _summary(by_day: pd.DataFrame) -> pd.DataFrame:
    excluded = {"day", "cell", "control", "foresight", "share", "info", *LIST_COLUMNS}
    numeric = [
        column
        for column in by_day.columns
        if column not in excluded and pd.api.types.is_numeric_dtype(by_day[column])
    ]
    grouped = by_day.groupby("cell", sort=False, observed=True)
    summary = grouped[numeric].agg(["mean", "median", "std"])
    summary.columns = [f"{metric}_{stat}" for metric, stat in summary.columns]
    summary = summary.reset_index()
    summary.insert(1, "n_days", grouped.size().reindex(summary["cell"]).to_numpy())
    summary["cell"] = pd.Categorical(summary["cell"], CELL_ORDER, ordered=True)
    return summary.sort_values("cell").reset_index(drop=True)


def _contrast_rows(by_day: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    objective = by_day.pivot_table(
        index="day",
        columns="cell",
        values="system_objective",
        aggfunc="first",
        observed=True,
    )
    rows: list[dict[str, Any]] = []
    daily_rows: list[dict[str, Any]] = []

    def add(factor: str, contrast: str, held: str, values: pd.Series) -> None:
        values = values.dropna()
        cp = objective.loc[values.index, "C_P"] if "C_P" in objective else pd.Series(np.nan, index=values.index)
        pct = 100.0 * values / cp.replace(0.0, np.nan)
        rows.append(
            {
                "factor": factor,
                "contrast": contrast,
                "held_fixed": held,
                "mean_usd": values.mean(),
                "median_usd": values.median(),
                "mean_pct_cp": pct.mean(),
                "n_days": int(values.size),
            }
        )
        daily_rows.extend(
            {
                "day": day,
                "factor": factor,
                "contrast": contrast,
                "held_fixed": held,
                "difference_usd": value,
            }
            for day, value in values.items()
        )

    for foresight in ("P", "F"):
        central = f"C_{foresight}"
        decentral = [cell for cell in CELL_ORDER if cell.startswith(f"D_{foresight}_")]
        present = [cell for cell in decentral if cell in objective]
        if central in objective and present:
            add(
                "F1",
                f"{central} - mean(D_{foresight}_*)",
                f"foresight={foresight}",
                objective[central] - objective[present].mean(axis=1),
            )
            for cell in present:
                factors = parse_cell(cell)
                add(
                    "F1",
                    f"{central} - {cell}",
                    f"foresight={foresight}; share={factors['share']}; info={factors['info']}",
                    objective[central] - objective[cell],
                )

    if {"C_P", "C_F"}.issubset(objective):
        add("F2", "C_P - C_F", "control=C", objective["C_P"] - objective["C_F"])
    for share in ("INJ", "EQ"):
        for info in ("FULL", "PRICE", "NONE"):
            perfect = f"D_P_{share}_{info}"
            forecast = f"D_F_{share}_{info}"
            if {perfect, forecast}.issubset(objective):
                add(
                    "F2",
                    f"{perfect} - {forecast}",
                    f"control=D; share={share}; info={info}",
                    objective[perfect] - objective[forecast],
                )

    for foresight in ("P", "F"):
        for info in ("FULL", "PRICE", "NONE"):
            injection = f"D_{foresight}_INJ_{info}"
            equal = f"D_{foresight}_EQ_{info}"
            if {injection, equal}.issubset(objective):
                add(
                    "F3",
                    f"{injection} - {equal}",
                    f"control=D; foresight={foresight}; info={info}",
                    objective[injection] - objective[equal],
                )

    for foresight in ("P", "F"):
        for share in ("INJ", "EQ"):
            ids = {info: f"D_{foresight}_{share}_{info}" for info in ("FULL", "PRICE", "NONE")}
            for left, right in (("FULL", "PRICE"), ("PRICE", "NONE"), ("FULL", "NONE")):
                if {ids[left], ids[right]}.issubset(objective):
                    add(
                        "F4",
                        f"{ids[left]} - {ids[right]}",
                        f"control=D; foresight={foresight}; share={share}",
                        objective[ids[left]] - objective[ids[right]],
                    )
    columns = ["factor", "contrast", "held_fixed", "mean_usd", "median_usd", "mean_pct_cp", "n_days"]
    return pd.DataFrame(rows, columns=columns), pd.DataFrame(daily_rows)


def _pivot(by_day: pd.DataFrame) -> pd.DataFrame:
    categories = [
        ("C", lambda foresight: f"C_{foresight}"),
        *[
            (f"{share}_{info}", lambda foresight, share=share, info=info: f"D_{foresight}_{share}_{info}")
            for share in ("INJ", "EQ")
            for info in ("FULL", "PRICE", "NONE")
        ],
    ]
    objective = by_day.pivot_table(
        index="day",
        columns="cell",
        values="system_objective",
        aggfunc="first",
        observed=True,
    )
    records: list[dict[str, Any]] = []
    for foresight in ("P", "F"):
        row: dict[str, Any] = {"foresight": foresight}
        for label, cell_for in categories:
            cell = cell_for(foresight)
            if cell in objective:
                values = objective[cell]
                row[f"{label}_mean_J"] = values.mean()
                row[f"{label}_mean_pct_cp"] = (
                    100.0 * values / objective["C_P"].replace(0.0, np.nan)
                ).mean()
            else:
                row[f"{label}_mean_J"] = np.nan
                row[f"{label}_mean_pct_cp"] = np.nan
        records.append(row)
    return pd.DataFrame(records)


def _write_outputs(
    by_day: pd.DataFrame,
    cfg: dict[str, Any],
    runtime: float,
    metadata: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    results = Path(str(cfg.get("paths", {}).get("results", "results")))
    tables = results / "tables"
    summary = _summary(by_day)
    effects, effects_daily = _contrast_rows(by_day)
    pivot = _pivot(by_day)
    write_table(by_day, tables / "design_matrix_by_day.csv", cfg, runtime, **metadata)
    write_table(summary, tables / "design_matrix_summary.csv", cfg, runtime, **metadata)
    write_table(effects, tables / "design_matrix_effects.csv", cfg, runtime, **metadata)
    write_table(pivot, tables / "design_matrix_pivot.csv", cfg, runtime, **metadata)
    figures = results / "figures"
    plot_design_matrix(by_day, figures / "fig_design_matrix.png")
    plot_design_effects(effects_daily, figures / "fig_design_effects.png")
    return summary, effects, pivot, effects_daily


def _source_metadata(path: Path) -> dict[str, Any]:
    """Preserve nonstandard provenance fields when rebuilding summaries."""

    meta_path = path.with_suffix(".meta.json")
    if not meta_path.exists():
        return {}
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    standard = {"git_hash", "created_utc", "config_sha256", "runtime_s", "rows"}
    return {key: value for key, value in metadata.items() if key not in standard}


def _requested_cells(args_cells: list[str] | None, cfg: dict[str, Any]) -> list[str]:
    configured = cfg.get("design_matrix", {}).get("cells", "all")
    raw: Any = args_cells if args_cells is not None else configured
    if isinstance(raw, str):
        cells = CELL_ORDER.copy() if raw.lower() == "all" else raw.split(",")
    else:
        cells = [part for item in raw for part in str(item).split(",")]
    normalized = ["_".join(str(cell).strip().upper().split("_")) for cell in cells if str(cell).strip()]
    for cell in normalized:
        parse_cell(cell)
    return [cell for cell in CELL_ORDER if cell in set(normalized)]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/base.yaml"))
    parser.add_argument("--scenario", type=Path, help="Optional YAML overrides")
    parser.add_argument("--days", type=int, help="Run at most N selected complete days")
    parser.add_argument(
        "--day-list",
        nargs="+",
        help="Exact ISO days to run, separated by spaces or commas",
    )
    parser.add_argument("--workers", type=int, default=min(4, os.cpu_count() or 1))
    parser.add_argument("--cells", nargs="+", help="Cell ids, separated by spaces or commas")
    parser.add_argument(
        "--summarize-only",
        action="store_true",
        help="Rebuild derived outputs from design_matrix_by_day.csv",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    started = time.perf_counter()
    cfg = load_config(args.config, args.scenario)
    results_root = Path(str(cfg.get("paths", {}).get("results", "results")))
    log_path = results_root / "logs" / "design_matrix.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(log_path, encoding="utf-8")],
    )
    tables = results_root / "tables"
    by_day_path = tables / "design_matrix_by_day.csv"
    if args.summarize_only:
        if not by_day_path.exists():
            raise SystemExit(f"Missing per-day input: {by_day_path}")
        by_day = pd.read_csv(by_day_path)
        source_meta = _source_metadata(by_day_path)
        _write_outputs(
            by_day,
            cfg,
            time.perf_counter() - started,
            {**source_meta, "summarize_only": True},
        )
        print(by_day.groupby("cell", observed=True)[["system_objective", "elapsed_s"]].mean().to_string())
        return

    cells = _requested_cells(args.cells, cfg)
    if not cells:
        raise SystemExit("No design-matrix cells selected")
    agents = list(cfg["data"]["primary_agents"])
    complete_days, _ = assess_complete_days(cfg, agents)
    stride = int(cfg.get("design_matrix", {}).get("day_stride", 1))
    if stride < 1:
        raise SystemExit("design_matrix.day_stride must be positive")
    complete_days = complete_days[::stride]
    requested_day_list: list[str] | None = None
    if args.day_list:
        requested_day_list = [
            day.strip()
            for item in args.day_list
            for day in str(item).split(",")
            if day.strip()
        ]
        available = {day.date().isoformat(): day for day in complete_days}
        missing = [day for day in requested_day_list if day not in available]
        if missing:
            raise SystemExit(f"Requested days are not complete/available: {missing}")
        complete_days = [available[day] for day in requested_day_list]
    if args.days is not None:
        if args.days < 1:
            raise SystemExit("--days must be positive")
        complete_days = complete_days[: args.days]
    if not complete_days:
        raise SystemExit("No complete operating days are available for the selected agents")

    tasks = [(day.date().isoformat(), agents, cfg, cells) for day in complete_days]
    workers = max(1, min(args.workers, len(tasks)))
    if workers == 1:
        outcomes = [_run_day(task) for task in tasks]
    else:
        with mp.get_context("fork").Pool(workers) as pool:
            outcomes = pool.map(_run_day, tasks)
    failures = [item for item in outcomes if "error" in item]
    for failure in failures:
        LOGGER.error("day=%s failed: %s", failure["day"], failure["error"])
    completed = [item for item in outcomes if "rows" in item]
    if not completed:
        raise SystemExit("Every selected day failed; see results/logs/design_matrix.log")

    by_day = pd.DataFrame([row for item in completed for row in item["rows"]])
    by_day["cell"] = pd.Categorical(by_day["cell"], CELL_ORDER, ordered=True)
    by_day = by_day.sort_values(["day", "cell"]).reset_index(drop=True)
    runtime = time.perf_counter() - started
    metadata = {
        "workers": workers,
        "requested_days": args.days,
        "requested_day_list": requested_day_list,
        "agents": agents,
        "cells": cells,
        "failed_days": {item["day"]: item["error"] for item in failures},
    }
    _write_outputs(by_day, cfg, runtime, metadata)

    illustrative_path = tables / "illustrative_days.csv"
    selected_days: set[str] = set()
    if illustrative_path.exists():
        selected_days = set(pd.read_csv(illustrative_path)["day"].astype(str))
        selected_days.intersection_update(item["day"] for item in completed)
    if not selected_days:
        selected_days = {completed[0]["day"]}
    trajectory_dir = tables / "trajectories"
    for item in completed:
        if item["day"] not in selected_days:
            continue
        for cell, frame in item["trajectories"].items():
            write_table(
                frame,
                trajectory_dir / f"design_{item['day']}_{cell}.csv",
                cfg,
                runtime,
                day=item["day"],
                cell=cell,
            )

    report = by_day.copy()
    report["converged_fraction"] = report["game_converged_hours_frac"].combine_first(
        report["price_converged_hours_frac"]
    )
    report["mean_sweeps_or_iterations"] = np.where(
        report["info"].eq("FULL"),
        report["sweeps"] / float(cfg.get("episode", {}).get("horizon_h", 24)),
        report["price_iterations_mean"],
    )
    means = report.groupby("cell", observed=True)[
        [
            "system_objective",
            "elapsed_s",
            "converged_fraction",
            "mean_sweeps_or_iterations",
        ]
    ].mean()
    wall_per_day = runtime / len(completed)
    LOGGER.info(
        "Wrote %d day-cell rows for %d day(s) in %.2f s (%.2f wall s/day)",
        len(by_day),
        len(completed),
        runtime,
        wall_per_day,
    )
    print("\nPer-cell means")
    print(means.to_string(float_format=lambda value: f"{value:,.3f}"))
    print(f"\nFull-matrix wall time: {wall_per_day:.3f} s/day with {workers} worker(s)")


if __name__ == "__main__":
    main()

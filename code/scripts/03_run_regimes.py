#!/usr/bin/env python3
"""Run all operating regimes over complete base-case operating days."""

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

from wargame.experiments.io import assess_complete_days, load_config, write_table
from wargame.experiments.metrics import add_system_objective, gaps
from wargame.experiments.run_episode import run_all_regimes
from wargame.model.env import Episode, build_episode

LOGGER = logging.getLogger("wargame.run_regimes")
REGIME_ORDER = ["R1", "R1_f", "R2", "R2_f", "R3a", "R3b", "R4a", "R4a_f", "R4b", "R4b_f"]
MATRIX_REGIMES = {
    "C": {"perfect": "R1", "forecast": "R1_f"},
    "G": {"perfect": "R2", "forecast": "R2_f"},
    "A": {"perfect": "R4a", "forecast": "R4a_f"},
    "L": {"perfect": "R4b", "forecast": "R4b_f"},
}


def _trajectory(episode: Episode, regime: str, result: Any) -> pd.DataFrame:
    realization = result.realization
    records: list[dict[str, Any]] = []
    for t in range(episode.T):
        for i, agent in enumerate(episode.agents):
            records.append(
                {
                    "day": str(episode.day),
                    "hour": t,
                    "regime": regime,
                    "agent": agent.name,
                    "q_i": realization.q[i, t],
                    "c_i": realization.c[i, t],
                    "d_i": realization.d[i, t],
                    "r_i": realization.r[i, t],
                    "soc_i": realization.soc[i, t + 1],
                    "Q": realization.q[:, t].sum(),
                    "K": episode.K,
                    "D": episode.D[t],
                    "pi_RT": episode.pi_RT[t],
                }
            )
    return pd.DataFrame.from_records(records)


def _run_day(task: tuple[str, list[str], dict[str, Any]]) -> dict[str, Any]:
    day, agents, cfg = task
    try:
        episode = build_episode(day, agents, cfg)
        results = run_all_regimes(episode, cfg)
        rows: list[dict[str, Any]] = []
        trajectories: dict[str, pd.DataFrame] = {}
        for regime in REGIME_ORDER:
            result = results[regime]
            row = dict(result.metrics)
            for key in ("per_agent_profit", "per_agent_profit_planned", "sweeps_by_hour"):
                row[key] = json.dumps(row[key])
            row["elapsed_s"] = result.elapsed_s
            rows.append(row)
            trajectories[regime] = _trajectory(episode, regime, result)
        return {
            "day": day,
            "rows": rows,
            "trajectories": trajectories,
            "mean_price": float(np.mean(episode.pi_RT)),
            "wind_mwh": float(episode.W.sum()),
        }
    except Exception as exc:  # worker errors must be recorded, not lose the entire window
        return {"day": day, "error": f"{type(exc).__name__}: {exc}"}


def _summary(by_day: pd.DataFrame) -> pd.DataFrame:
    excluded = {"day", "regime", "per_agent_profit", "per_agent_profit_planned"}
    numeric = [
        column
        for column in by_day.columns
        if column not in excluded and pd.api.types.is_numeric_dtype(by_day[column])
    ]
    summary = by_day.groupby("regime", sort=False, observed=True)[numeric].agg(
        ["mean", "median", "std"]
    )
    summary.columns = [f"{metric}_{stat}" for metric, stat in summary.columns]
    summary = summary.reset_index()
    summary.insert(
        1,
        "n_days",
        by_day.groupby("regime", observed=True).size().reindex(summary["regime"]).to_numpy(),
    )

    day_gaps = gaps(by_day)
    gap_statistics: dict[str, float] = {}
    for metric in day_gaps.columns.difference(["day"], sort=False):
        values = day_gaps[metric]
        for stat, value in {
            "mean": values.mean(),
            "median": values.median(),
            "std": values.std(),
            "min": values.min(),
            "q25": values.quantile(0.25),
            "q75": values.quantile(0.75),
            "max": values.max(),
        }.items():
            gap_statistics[f"{metric}_{stat}"] = value
    gap_columns = pd.DataFrame(
        {column: [value] * len(summary) for column, value in gap_statistics.items()}
    )
    summary = pd.concat([summary.reset_index(drop=True), gap_columns], axis=1)
    summary["regime"] = pd.Categorical(summary["regime"], REGIME_ORDER, ordered=True)
    return summary.sort_values("regime").reset_index(drop=True)


def _matrix_summary(by_day: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return objective-led and raw-profit information matrices."""

    means = by_day.groupby("regime", observed=True)[
        ["system_objective", "system_profit_realized"]
    ].mean()
    rows = [
        {
            "coordination": level,
            "perfect": means.loc[mapping["perfect"], "system_objective"],
            "forecast": means.loc[mapping["forecast"], "system_objective"],
            "perfect_profit": means.loc[mapping["perfect"], "system_profit_realized"],
            "forecast_profit": means.loc[mapping["forecast"], "system_profit_realized"],
        }
        for level, mapping in MATRIX_REGIMES.items()
    ]
    matrix = pd.DataFrame(rows)
    objective_denominator = float(means.loc["R1", "system_objective"])
    profit_denominator = float(means.loc["R1", "system_profit_realized"])
    percent = matrix.copy()
    percent[["perfect", "forecast"]] = np.where(
        objective_denominator > 0,
        100.0 * percent[["perfect", "forecast"]] / objective_denominator,
        np.nan,
    )
    percent[["perfect_profit", "forecast_profit"]] = np.where(
        profit_denominator > 0,
        100.0 * percent[["perfect_profit", "forecast_profit"]] / profit_denominator,
        np.nan,
    )
    return matrix, percent


def _illustrative_days(
    completed: list[dict[str, Any]], by_day: pd.DataFrame
) -> pd.DataFrame:
    descriptors = pd.DataFrame(
        {
            "day": [item["day"] for item in completed],
            "mean_price_usd_per_mwh": [item["mean_price"] for item in completed],
            "wind_mwh": [item["wind_mwh"] for item in completed],
        }
    )
    r1 = by_day[by_day["regime"] == "R1"][["day", "system_objective"]]
    r1 = r1.assign(day=r1["day"].astype(str))
    descriptors = descriptors.merge(r1, on="day", how="left")
    high_price = descriptors.loc[descriptors["mean_price_usd_per_mwh"].idxmax()]
    high_wind = descriptors.loc[descriptors["wind_mwh"].idxmax()]
    ordered = descriptors.sort_values("system_objective").reset_index(drop=True)
    median = ordered.iloc[(len(ordered) - 1) // 2]
    # Day with the largest strategic gap J_R1 - J_R2 (used for the trajectory figure).
    objective = by_day.pivot_table(index="day", columns="regime", values="system_objective", aggfunc="first")
    gap = (objective["R1"] - objective["R2"]).rename("strategic_gap").reset_index()
    gap["day"] = gap["day"].astype(str)
    descriptors = descriptors.merge(gap, on="day", how="left")
    largest_gap = descriptors.loc[descriptors["strategic_gap"].idxmax()]
    rows = []
    for role, row, basis in (
        ("highest_price", high_price, "mean_price_usd_per_mwh"),
        ("highest_wind", high_wind, "wind_mwh"),
        ("median", median, "system_objective"),
        ("largest_strategic_gap", largest_gap, "strategic_gap"),
    ):
        rows.append(
            {
                "role": role,
                "day": row["day"],
                "selection_basis": basis,
                "selection_value": row[basis],
            }
        )
    return pd.DataFrame(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/base.yaml"))
    parser.add_argument("--scenario", type=Path, help="Optional YAML overrides")
    parser.add_argument("--days", type=int, help="Run at most N complete days")
    parser.add_argument("--workers", type=int, default=min(4, os.cpu_count() or 1))
    parser.add_argument(
        "--summarize-only",
        action="store_true",
        help="Rebuild summaries from regimes_by_day.csv without running solvers",
    )
    return parser.parse_args()


def _source_metadata(path: Path) -> dict[str, Any]:
    """Keep nonstandard provenance fields when refreshing an existing table."""

    meta_path = path.with_suffix(".meta.json")
    if not meta_path.exists():
        return {}
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    standard = {"git_hash", "created_utc", "config_sha256", "runtime_s", "rows"}
    return {key: value for key, value in metadata.items() if key not in standard}


def _write_summaries(
    by_day: pd.DataFrame,
    cfg: dict[str, Any],
    runtime: float,
    metadata: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Normalize the day table and write every derived base-case summary."""

    results_root = Path(str(cfg.get("paths", {}).get("results", "results")))
    tables_dir = results_root / "tables"
    by_day_path = tables_dir / "regimes_by_day.csv"
    lambda_minus = float(cfg.get("poi", {}).get("lambda_minus", 250.0))
    normalized = add_system_objective(by_day, lambda_minus)
    normalized["regime"] = pd.Categorical(normalized["regime"], REGIME_ORDER, ordered=True)
    normalized = normalized.sort_values(["day", "regime"]).reset_index(drop=True)
    summary = _summary(normalized)
    matrix, matrix_pct = _matrix_summary(normalized)
    write_table(normalized, by_day_path, cfg, runtime, **metadata)
    write_table(summary, tables_dir / "regimes_summary.csv", cfg, runtime, **metadata)
    write_table(matrix, tables_dir / "matrix_summary.csv", cfg, runtime, **metadata)
    write_table(
        matrix_pct,
        tables_dir / "matrix_summary_pct_r1.csv",
        cfg,
        runtime,
        **metadata,
    )
    return matrix, matrix_pct


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
    started = time.perf_counter()
    cfg = load_config(args.config, args.scenario)
    results_root = Path(str(cfg.get("paths", {}).get("results", "results")))
    tables_dir = results_root / "tables"
    by_day_path = tables_dir / "regimes_by_day.csv"
    if args.summarize_only:
        if not by_day_path.exists():
            raise SystemExit(f"Missing per-day input: {by_day_path}")
        by_day = pd.read_csv(by_day_path)
        source_meta = _source_metadata(by_day_path)
        matrix, matrix_pct = _write_summaries(
            by_day,
            cfg,
            time.perf_counter() - started,
            {**source_meta, "summarize_only": True},
        )
        LOGGER.info("Rebuilt summaries from %d existing day-regime rows", len(by_day))
        print("\nMean daily system objective ($/day)")
        print(matrix.to_string(index=False, float_format=lambda value: f"{value:,.2f}"))
        print("\nMean daily system objective (% of R1)")
        print(matrix_pct.to_string(index=False, float_format=lambda value: f"{value:,.2f}"))
        return

    agents = list(cfg["data"]["primary_agents"])
    complete_days, skipped = assess_complete_days(cfg, agents)
    if args.days is not None:
        if args.days < 1:
            raise SystemExit("--days must be positive")
        complete_days = complete_days[: args.days]
    LOGGER.info(
        "Base agents=%s; running %d complete day(s); %d configured day(s) incomplete",
        ",".join(agents),
        len(complete_days),
        len(skipped),
    )
    if not complete_days:
        raise SystemExit("No complete operating days are available for the selected agents")

    tasks = [(day.date().isoformat(), agents, cfg) for day in complete_days]
    workers = max(1, min(args.workers, len(tasks)))
    if workers == 1:
        results = [_run_day(task) for task in tasks]
    else:
        with mp.get_context("fork").Pool(workers) as pool:
            results = pool.map(_run_day, tasks)

    failures = [item for item in results if "error" in item]
    if failures:
        failed_rows = pd.DataFrame(
            [{"day": item["day"], "reason": item["error"]} for item in failures]
        )
        skipped = pd.concat([skipped, failed_rows], ignore_index=True)
        for item in failures:
            LOGGER.error("Skipping %s after worker failure: %s", item["day"], item["error"])
    completed = [item for item in results if "rows" in item]
    if not completed:
        raise SystemExit("Every selected day failed; see logged errors")

    by_day = pd.DataFrame([row for item in completed for row in item["rows"]])
    by_day = add_system_objective(by_day, float(cfg["poi"]["lambda_minus"]))
    by_day["regime"] = pd.Categorical(by_day["regime"], REGIME_ORDER, ordered=True)
    by_day = by_day.sort_values(["day", "regime"]).reset_index(drop=True)
    matrix, matrix_pct = _matrix_summary(by_day)
    illustrative = _illustrative_days(completed, by_day)
    runtime = time.perf_counter() - started

    common_meta = {"workers": workers, "requested_days": args.days, "agents": agents}
    _write_summaries(by_day, cfg, runtime, common_meta)
    write_table(skipped, tables_dir / "regimes_skipped_days.csv", cfg, runtime, **common_meta)
    write_table(illustrative, tables_dir / "illustrative_days.csv", cfg, runtime, **common_meta)

    trajectory_dir = tables_dir / "trajectories"
    selected = set(illustrative["day"])
    for item in completed:
        if item["day"] not in selected:
            continue
        for regime, frame in item["trajectories"].items():
            path = trajectory_dir / f"{item['day']}_{regime}.csv"
            write_table(frame, path, cfg, runtime, day=item["day"], regime=regime)

    LOGGER.info(
        "Wrote %d day-regime rows and %d trajectory files in %.2f s",
        len(by_day),
        len(selected) * len(REGIME_ORDER),
        runtime,
    )
    print("\nMean daily system objective ($/day; raw-profit columns suffixed _profit)")
    print(matrix.to_string(index=False, float_format=lambda value: f"{value:,.2f}"))
    print("\nMean daily system objective (% of R1; raw-profit columns suffixed _profit)")
    print(matrix_pct.to_string(index=False, float_format=lambda value: f"{value:,.2f}"))


if __name__ == "__main__":
    main()

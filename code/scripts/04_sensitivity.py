#!/usr/bin/env python3
"""Run correlation, POI-tightness, and storage-design sensitivity cases."""

from __future__ import annotations

import argparse
import itertools
import json
import logging
import multiprocessing as mp
import os
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from wargame.experiments.io import (
    full_coverage_resources,
    load_config,
    write_table,
)
from wargame.experiments.metrics import add_system_objective, episode_metrics, gaps
from wargame.experiments.run_episode import RegimeResult
from wargame.model.env import build_episode, load_processed
from wargame.solvers.central import solve_central
from wargame.solvers.game import solve_r2, solve_r3a, solve_r3b
from wargame.solvers.mpc import solve_r4a, solve_r4b
from wargame.solvers.realize import realize

LOGGER = logging.getLogger("wargame.sensitivity")
REGIMES = ["R1", "R1_f", "R2", "R2_f", "R3a", "R3b", "R4a", "R4a_f", "R4b", "R4b_f"]
SCENARIO_COLUMNS = [
    "kappa_K",
    "correlation_set",
    "storage_design",
    "p_ratio",
    "duration_h",
]


def _pool(cfg: dict[str, Any]) -> list[str]:
    return list(dict.fromkeys(name for group in cfg["data"]["pool"] for name in group))


def choose_agent_sets(cfg: dict[str, Any]) -> pd.DataFrame:
    """Choose distinct complete four-agent sets nearest configured correlation targets."""

    root = Path(str(cfg.get("paths", {}).get("processed", "data/processed")))
    corr = pd.read_csv(root / "corr_matrix.csv", index_col="resource")
    resources = load_processed(cfg)["resources"].set_index("resource")
    complete, market_days = full_coverage_resources(cfg)
    eligible = [name for name in _pool(cfg) if name in complete and name in corr.index]
    n_agents = int(cfg["sensitivity"].get("n_agents_for_sets", 4))
    if len(eligible) < n_agents:
        raise ValueError(
            f"Only {len(eligible)} pool resources have full wind/forecast coverage over "
            f"{len(market_days)} available days; need {n_agents}"
        )

    candidates: list[tuple[tuple[str, ...], float, float, float]] = []
    for members in itertools.combinations(eligible, n_agents):
        values = np.asarray(
            [corr.loc[a, b] for a, b in itertools.combinations(members, 2)], dtype=float
        )
        if np.isfinite(values).all():
            candidates.append((members, float(values.mean()), float(values.min()), float(values.max())))
    if not candidates:
        raise ValueError("No full-coverage agent combination has finite pairwise correlations")

    targets = cfg["sensitivity"]["correlation_targets"]
    used: set[tuple[str, ...]] = set()
    rows: list[dict[str, Any]] = []
    for label in ("low", "medium", "high"):
        target = float(targets[label])
        available = [item for item in candidates if item[0] not in used]
        members, mean_rho, min_rho, max_rho = min(
            available, key=lambda item: (abs(item[1] - target), item[0])
        )
        used.add(members)
        row = {
            "correlation_set": label,
            "members": json.dumps(members),
            "target_rho": target,
            "mean_rho": mean_rho,
            "min_rho": min_rho,
            "max_rho": max_rho,
            "total_nameplate_mw": float(resources.loc[list(members), "nameplate_mw"].sum()),
            "coverage_days": len(market_days),
        }
        row.update({f"member_{i + 1}": name for i, name in enumerate(members)})
        rows.append(row)
    return pd.DataFrame(rows)


def _run_regimes(episode: Any, cfg: dict[str, Any], wanted: list[str]) -> dict[str, Any]:
    """Run only the requested non-forecast regimes (the _f regimes are the slowest)."""

    unsupported = sorted(set(wanted) - {"R1", "R2", "R3a", "R3b", "R4a", "R4b"})
    if unsupported:
        raise ValueError(f"sensitivity.regimes supports only non-forecast regimes, got {unsupported}")
    out: dict[str, RegimeResult] = {}

    def record(name: str, started: float, solution: Any, physical: Any) -> None:
        out[name] = RegimeResult(
            solution, physical, episode_metrics(episode, physical, name), time.perf_counter() - started
        )

    started = time.perf_counter()
    central = solve_central(episode, cfg)  # needed by R1 and as the R3b dual source
    if "R1" in wanted:
        record("R1", started, central, realize(episode, central))
    steps = {
        "R2": lambda: solve_r2(episode, cfg),
        "R3a": lambda: solve_r3a(episode, cfg),
        "R3b": lambda: solve_r3b(episode, central.duals, cfg),
    }
    for name, run in steps.items():
        if name in wanted:
            started = time.perf_counter()
            sol = run()
            record(name, started, sol, realize(episode, sol))
    for name, run in (("R4a", solve_r4a), ("R4b", solve_r4b)):
        if name in wanted:
            started = time.perf_counter()
            sol = run(episode, cfg)
            record(name, started, sol, sol)
    return out


def _selected_regimes(episode: Any, cfg: dict[str, Any]) -> list[dict[str, Any]]:
    wanted = list(cfg.get("sensitivity", {}).get("regimes", REGIMES))
    results = _run_regimes(episode, cfg, wanted)
    return [
        {**results[regime].metrics, "elapsed_s": results[regime].elapsed_s}
        for regime in REGIMES
        if regime in results
    ]


def _run_case(task: dict[str, Any]) -> dict[str, Any]:
    cfg = task["cfg"]
    try:
        overrides = {
            "poi": {"kappa_K": task["kappa_K"]},
            "battery": {
                "p_ratio": task["p_ratio"],
                "duration_h": task["duration_h"],
            },
        }
        episode = build_episode(task["day"], task["agents"], cfg, overrides=overrides)
        rows = _selected_regimes(episode, episode.cfg)
        for row in rows:
            for key in ("per_agent_profit", "per_agent_profit_planned", "sweeps_by_hour"):
                row[key] = json.dumps(row[key])
            row.update({key: task[key] for key in SCENARIO_COLUMNS})
            row["mean_rho"] = task["mean_rho"]
        return {"rows": rows}
    except Exception as exc:
        identity = {key: task[key] for key in [*SCENARIO_COLUMNS, "day"]}
        return {"error": f"{type(exc).__name__}: {exc}", **identity}


def _summary(frame: pd.DataFrame) -> pd.DataFrame:
    group_columns = [*SCENARIO_COLUMNS, "mean_rho", "regime"]
    excluded = {"day", "per_agent_profit", "per_agent_profit_planned", *group_columns}
    numeric = [
        column
        for column in frame.columns
        if column not in excluded and pd.api.types.is_numeric_dtype(frame[column])
    ]
    summary = frame.groupby(group_columns, as_index=False, observed=True)[numeric].mean()
    counts = frame.groupby(group_columns, observed=True).size().rename("n_days").reset_index()
    summary = summary.merge(counts, on=group_columns)

    scenario_index = [*SCENARIO_COLUMNS, "mean_rho", "day"]
    gap_frame = gaps(frame, index_columns=scenario_index)
    gap_columns = [column for column in gap_frame if column not in scenario_index]
    grouped = gap_frame.groupby([*SCENARIO_COLUMNS, "mean_rho"])[gap_columns].agg(
        ["mean", "median", "std"]
    )
    grouped.columns = [f"{metric}_{stat}" for metric, stat in grouped.columns]
    grouped = grouped.reset_index()
    for metric in gap_columns:
        grouped[metric] = grouped[f"{metric}_mean"]
    summary = summary.merge(grouped, on=[*SCENARIO_COLUMNS, "mean_rho"], how="left")
    summary["regime"] = pd.Categorical(summary["regime"], REGIMES, ordered=True)
    return summary.sort_values([*SCENARIO_COLUMNS, "regime"]).reset_index(drop=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/base.yaml"))
    parser.add_argument("--scenario", type=Path, help="Optional YAML overrides")
    parser.add_argument("--quick", action="store_true", help="Use two endpoint kappa values and two days")
    parser.add_argument("--workers", type=int, default=min(4, os.cpu_count() or 1))
    parser.add_argument(
        "--summarize-only",
        action="store_true",
        help="Rebuild sensitivity_summary.csv from sensitivity.csv without solvers",
    )
    return parser.parse_args()


def _source_metadata(path: Path) -> dict[str, Any]:
    """Keep run-shape metadata while refreshing an existing case table."""

    meta_path = path.with_suffix(".meta.json")
    if not meta_path.exists():
        return {}
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    standard = {"git_hash", "created_utc", "config_sha256", "runtime_s", "rows"}
    return {key: value for key, value in metadata.items() if key not in standard}


def _write_summary(
    sensitivity: pd.DataFrame,
    cfg: dict[str, Any],
    runtime: float,
    metadata: dict[str, Any],
) -> pd.DataFrame:
    """Normalize a per-case table and write it with its derived summary."""

    root = Path(str(cfg.get("paths", {}).get("results", "results"))) / "tables"
    normalized = add_system_objective(
        sensitivity, float(cfg.get("poi", {}).get("lambda_minus", 250.0))
    )
    normalized["regime"] = pd.Categorical(normalized["regime"], REGIMES, ordered=True)
    normalized = normalized.sort_values(
        [*SCENARIO_COLUMNS, "day", "regime"]
    ).reset_index(drop=True)
    summary = _summary(normalized)
    write_table(normalized, root / "sensitivity.csv", cfg, runtime, **metadata)
    write_table(summary, root / "sensitivity_summary.csv", cfg, runtime, **metadata)
    return summary


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
    started = time.perf_counter()
    cfg = load_config(args.config, args.scenario)
    root = Path(str(cfg.get("paths", {}).get("results", "results"))) / "tables"
    sensitivity_path = root / "sensitivity.csv"
    if args.summarize_only:
        if not sensitivity_path.exists():
            raise SystemExit(f"Missing per-case input: {sensitivity_path}")
        sensitivity = pd.read_csv(sensitivity_path)
        metadata = _source_metadata(sensitivity_path)
        summary = _write_summary(
            sensitivity,
            cfg,
            time.perf_counter() - started,
            {**metadata, "summarize_only": True},
        )
        LOGGER.info(
            "Rebuilt %d summary rows from %d existing sensitivity rows; agent_sets.csv untouched",
            len(summary),
            len(sensitivity),
        )
        return

    agent_sets = choose_agent_sets(cfg)
    _, available_days = full_coverage_resources(cfg)
    stride = int(cfg["sensitivity"].get("day_stride", 3))
    selected_days = available_days[::stride]
    kappa_grid = [float(value) for value in cfg["sensitivity"]["kappa_K_grid"]]
    if args.quick:
        kappa_grid = [kappa_grid[0], kappa_grid[-1]]
        selected_days = available_days[:2]
    if not selected_days:
        raise SystemExit("No complete market days are available for sensitivity experiments")

    tasks: list[dict[str, Any]] = []
    for kappa, set_row, design, day in itertools.product(
        kappa_grid,
        agent_sets.to_dict("records"),
        cfg["sensitivity"]["storage_designs"],
        selected_days,
    ):
        p_ratio = float(design["p_ratio"])
        duration = float(design["duration_h"])
        tasks.append(
            {
                "cfg": cfg,
                "day": day.date().isoformat(),
                "agents": json.loads(set_row["members"]),
                "kappa_K": kappa,
                "correlation_set": set_row["correlation_set"],
                "mean_rho": set_row["mean_rho"],
                "storage_design": f"p={p_ratio:g}, duration={duration:g} h",
                "p_ratio": p_ratio,
                "duration_h": duration,
            }
        )
    workers = max(1, min(args.workers, len(tasks)))
    LOGGER.info(
        "Running %d scenario-days (%d kappa x %d sets x %d designs x %d days) with %d workers",
        len(tasks),
        len(kappa_grid),
        len(agent_sets),
        len(cfg["sensitivity"]["storage_designs"]),
        len(selected_days),
        workers,
    )
    if workers == 1:
        results = [_run_case(task) for task in tasks]
    else:
        with mp.get_context("fork").Pool(workers) as pool:
            results = pool.map(_run_case, tasks)

    failure_columns = [*SCENARIO_COLUMNS, "day", "error"]
    failures = pd.DataFrame(
        [item for item in results if "error" in item], columns=failure_columns
    )
    completed = [item for item in results if "rows" in item]
    if not completed:
        raise SystemExit("Every sensitivity case failed")
    sensitivity = pd.DataFrame([row for item in completed for row in item["rows"]])
    sensitivity = add_system_objective(sensitivity, float(cfg["poi"]["lambda_minus"]))
    sensitivity["regime"] = pd.Categorical(sensitivity["regime"], REGIMES, ordered=True)
    sensitivity = sensitivity.sort_values([*SCENARIO_COLUMNS, "day", "regime"]).reset_index(drop=True)
    runtime = time.perf_counter() - started

    meta = {"workers": workers, "quick": args.quick, "scenario_days": len(tasks)}
    write_table(agent_sets, root / "agent_sets.csv", cfg, runtime, **meta)
    summary = _write_summary(sensitivity, cfg, runtime, meta)
    write_table(failures, root / "sensitivity_failures.csv", cfg, runtime, **meta)
    LOGGER.info(
        "Wrote %d sensitivity rows (%d failed cases) in %.2f s",
        len(sensitivity),
        len(failures),
        runtime,
    )


if __name__ == "__main__":
    main()

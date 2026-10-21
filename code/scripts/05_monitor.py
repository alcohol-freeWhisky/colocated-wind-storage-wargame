#!/usr/bin/env python3
"""Calibrate monitoring noise and produce detection/deterrence outputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import subprocess
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from wargame.monitor.calibration import (
    define_regimes,
    load_error_samples,
    synthetic_error_samples,
)
from wargame.monitor.detection import deterrence_grid, roc_curve

LOGGER = logging.getLogger("wargame.monitor")


def _pyplot():
    """Import headless pyplot only when a figure is actually requested."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def _deep_update(base: dict[str, object], override: Mapping[str, object]) -> dict[str, object]:
    for key, value in override.items():
        current = base.get(key)
        if isinstance(current, dict) and isinstance(value, Mapping):
            _deep_update(current, value)
        else:
            base[key] = value
    return base


def _load_config(config_path: Path, scenario_path: Path | None) -> dict[str, object]:
    with config_path.open("r", encoding="utf-8") as stream:
        loaded = yaml.safe_load(stream)
    if not isinstance(loaded, dict):
        raise ValueError(f"Configuration must be a mapping: {config_path}")
    if scenario_path is not None:
        with scenario_path.open("r", encoding="utf-8") as stream:
            scenario = yaml.safe_load(stream)
        if not isinstance(scenario, Mapping):
            raise ValueError(f"Scenario must be a mapping: {scenario_path}")
        _deep_update(loaded, scenario)
    return loaded


def _mapping(cfg: Mapping[str, object], key: str) -> Mapping[str, object]:
    value = cfg.get(key, {})
    if not isinstance(value, Mapping):
        raise TypeError(f"cfg[{key!r}] must be a mapping")
    return value


def _roc_table(regimes: pd.DataFrame, cfg: Mapping[str, object]) -> pd.DataFrame:
    monitor_cfg = _mapping(cfg, "monitor")
    thresholds = np.asarray(monitor_cfg["thresholds_sigma"], dtype=float)
    withholding = np.asarray(monitor_cfg["withholding_grid_frac"], dtype=float)
    parts: list[pd.DataFrame] = []
    for row in regimes.itertuples(index=False):
        sigma = float(row.sigma)
        for m_frac in withholding:
            curve = roc_curve(row.eps_sample, float(m_frac), thresholds * sigma)
            curve.insert(0, "m_frac", float(m_frac))
            curve.insert(0, "tau_sigma", thresholds)
            curve.insert(0, "sigma", sigma)
            curve.insert(0, "regime", row.regime)
            parts.append(curve)
    return pd.concat(parts, ignore_index=True)


def _closest(values: pd.Series, target: float) -> float:
    unique = values.dropna().unique().astype(float)
    return float(unique[np.argmin(np.abs(unique - target))])


def _plot_roc(roc: pd.DataFrame, path: Path) -> None:
    plt = _pyplot()
    withholding = np.sort(roc["m_frac"].dropna().unique().astype(float))
    ncols = min(2, len(withholding))
    nrows = int(np.ceil(len(withholding) / ncols))
    fig, axes = plt.subplots(
        nrows,
        ncols,
        figsize=(6.4 * ncols, 3.8 * nrows),
        constrained_layout=True,
        squeeze=False,
    )
    for ax, m_frac in zip(axes.flat, withholding, strict=False):
        selected = roc[np.isclose(roc["m_frac"], m_frac)]
        for regime, group in selected.groupby("regime", sort=False):
            ordered = group.sort_values("q0")
            ax.plot(ordered["q0"], ordered["q1"], marker="o", label=str(regime))
        ax.plot([0, 1], [0, 1], color="0.65", linestyle="--", linewidth=1)
        ax.set(
            xlabel="False-positive rate q0",
            ylabel="Detection rate q1",
            xlim=(0, 1),
            ylim=(0, 1),
        )
        ax.set_title(f"Withholding m = {m_frac:.2f} of nameplate")
        ax.grid(alpha=0.25)
    for ax in axes.flat[len(withholding) :]:
        ax.set_visible(False)
    axes.flat[0].legend(title="Noise regime")
    fig.suptitle("Empirical ROC by fixed physical withholding")
    fig.savefig(path, dpi=220)
    plt.close(fig)


def _fixed_grid_slice(grid: pd.DataFrame) -> pd.DataFrame:
    tau_value = _closest(grid["tau_frac"], 0.05)
    delta_value = float(grid["delta"].max())
    delay_value = float(grid["d"].min())
    return grid[
        np.isclose(grid["tau_frac"], tau_value)
        & np.isclose(grid["delta"], delta_value)
        & np.isclose(grid["d"], delay_value)
        & (
            np.isclose(grid["m_frac"], 0.05)
            | np.isclose(grid["m_frac"], 0.10)
        )
    ].copy()


def _plot_fine(grid: pd.DataFrame, path: Path) -> None:
    plt = _pyplot()
    selected = _fixed_grid_slice(grid)
    fig, ax = plt.subplots(figsize=(6.4, 4.0), constrained_layout=True)
    for m_frac, group in selected.groupby("m_frac"):
        ordered = group.sort_values("sigma")
        ax.plot(
            ordered["sigma"],
            ordered["F_star_over_g"],
            marker="o",
            label=f"m = {m_frac:.2f}",
        )
    ax.set(
        xlabel="Forecast-error σ (normalized share of capacity)",
        ylabel="Required fine / deviation gain (F*/g)",
    )
    tau_frac = float(selected["tau_frac"].iloc[0])
    delay = int(selected["d"].iloc[0])
    ax.set_title(
        f"Required fine vs. noise (τ = {tau_frac:.2f}, d = {delay} h)"
    )
    ax.grid(alpha=0.25)
    ax.legend(
        title="Withholding\n(nameplate fraction)",
        loc="center left",
        bbox_to_anchor=(1.02, 0.5),
    )
    fig.savefig(path, dpi=220)
    plt.close(fig)


def _plot_duration(grid: pd.DataFrame, path: Path) -> None:
    plt = _pyplot()
    selected = _fixed_grid_slice(grid)
    fig, ax = plt.subplots(figsize=(6.4, 4.0), constrained_layout=True)
    for m_frac, group in selected.groupby("m_frac"):
        ordered = group.sort_values("sigma")
        duration = ordered["T_star"].astype(float).replace(np.inf, np.nan)
        ax.plot(ordered["sigma"], duration, marker="o", label=f"m = {m_frac:.2f}")
    ax.set(
        xlabel="Forecast-error σ (normalized share of capacity)",
        ylabel="Minimum correction duration T* (periods)",
    )
    tau_frac = float(selected["tau_frac"].iloc[0])
    delay = int(selected["d"].iloc[0])
    ax.set_title(
        f"Correction duration vs. noise (τ = {tau_frac:.2f}, d = {delay} h)"
    )
    ax.grid(alpha=0.25)
    ax.legend(
        title="Withholding\n(nameplate fraction)",
        loc="center left",
        bbox_to_anchor=(1.02, 0.5),
    )
    fig.savefig(path, dpi=220)
    plt.close(fig)


def _git_hash() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _write_metadata(table_path: Path, cfg: Mapping[str, object], synthetic: bool) -> None:
    canonical = yaml.safe_dump(dict(cfg), sort_keys=True).encode("utf-8")
    metadata = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "git_hash": _git_hash(),
        "config_sha256": hashlib.sha256(canonical).hexdigest(),
        "synthetic": synthetic,
    }
    meta_path = table_path.with_suffix(".meta.json")
    meta_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/base.yaml"))
    parser.add_argument("--scenario", type=Path, help="Optional YAML overrides")
    parser.add_argument(
        "--synthetic",
        action="store_true",
        help="Explicitly use generated calibration data instead of processed parquet files",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    logging.getLogger("matplotlib").setLevel(logging.WARNING)
    cfg = _load_config(args.config, args.scenario)
    paths_cfg = _mapping(cfg, "paths")
    processed_dir = Path(str(paths_cfg.get("processed", "data/processed")))
    results_dir = Path(str(paths_cfg.get("results", "results")))

    if args.synthetic:
        warning = "*** WARNING: USING SYNTHETIC MONITOR CALIBRATION DATA ***"
        LOGGER.warning(warning)
        samples = synthetic_error_samples(int(cfg.get("seed", 6974)))
    else:
        try:
            samples = load_error_samples(processed_dir)
        except FileNotFoundError as exc:
            raise SystemExit(
                f"ERROR: {exc}. Build the processed data first, or explicitly pass "
                "--synthetic for an offline smoke test."
            ) from None
        except ValueError as exc:
            # The current dataset builder uses explicit ``*_actual`` names;
            # normalize those losslessly to the monitor contract at read time.
            system_path = processed_dir / "forecast_error_system.parquet"
            resource_path = processed_dir / "forecast_error_resource.parquet"
            system = pd.read_parquet(system_path).rename(
                columns={"gen_actual": "gen", "hsl_actual": "hsl"}
            )
            resource = pd.read_parquet(resource_path)
            if not {"gen", "hsl"}.issubset(system.columns):
                raise SystemExit(f"ERROR: {exc}") from None
            samples = {"system": system, "resource": resource}
            LOGGER.info("Normalized processed system forecast-error column aliases")

    regimes = define_regimes(samples, cfg)
    roc = _roc_table(regimes, cfg)
    deterrence = deterrence_grid(cfg, regimes)

    tables_dir = results_dir / "tables"
    figures_dir = results_dir / "figures"
    tables_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        tables_dir / "monitor_regimes.csv": regimes.drop(columns="eps_sample"),
        tables_dir / "monitor_roc.csv": roc,
        tables_dir / "monitor_deterrence.csv": deterrence,
    }
    for path, table in outputs.items():
        table.to_csv(path, index=False)
        _write_metadata(path, cfg, args.synthetic)
        LOGGER.info("Wrote %s (%d rows)", path, len(table))

    _plot_roc(roc, figures_dir / "monitor_roc.png")
    _plot_fine(deterrence, figures_dir / "monitor_Fstar_vs_sigma.png")
    _plot_duration(deterrence, figures_dir / "monitor_Tstar_vs_sigma.png")
    LOGGER.info("Wrote monitor figures to %s", figures_dir)


if __name__ == "__main__":
    main()

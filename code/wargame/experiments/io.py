"""Configuration, completeness, and reproducibility helpers for experiments."""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from wargame.model.env import load_processed


def deep_update(base: dict[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    """Recursively apply a scenario mapping to a configuration."""

    for key, value in override.items():
        if isinstance(base.get(key), dict) and isinstance(value, Mapping):
            deep_update(base[key], value)
        else:
            base[key] = deepcopy(value)
    return base


def load_config(config_path: Path, scenario_path: Path | None = None) -> dict[str, Any]:
    """Load base YAML and optional recursive scenario overrides."""

    with config_path.open(encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    if not isinstance(config, dict):
        raise ValueError(f"Configuration must be a mapping: {config_path}")
    if scenario_path is not None:
        with scenario_path.open(encoding="utf-8") as stream:
            scenario = yaml.safe_load(stream)
        if not isinstance(scenario, Mapping):
            raise ValueError(f"Scenario must be a mapping: {scenario_path}")
        deep_update(config, scenario)
    return config


def config_hash(cfg: Mapping[str, Any]) -> str:
    """Return a stable SHA-256 digest of the effective configuration."""

    canonical = yaml.safe_dump(dict(cfg), sort_keys=True).encode()
    return hashlib.sha256(canonical).hexdigest()


def git_hash() -> str | None:
    """Return the current commit hash when the directory is a Git work tree."""

    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def write_metadata(
    table_path: Path,
    cfg: Mapping[str, Any],
    runtime_s: float,
    **extra: Any,
) -> Path:
    """Write the required sibling ``.meta.json`` for one result table."""

    metadata = {
        "git_hash": git_hash(),
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "config_sha256": config_hash(cfg),
        "runtime_s": float(runtime_s),
        **extra,
    }
    meta_path = table_path.with_suffix(".meta.json")
    meta_path.write_text(json.dumps(metadata, indent=2, default=str) + "\n", encoding="utf-8")
    return meta_path


def write_table(
    frame: pd.DataFrame,
    path: Path,
    cfg: Mapping[str, Any],
    runtime_s: float,
    **metadata: Any,
) -> None:
    """Write a CSV and its reproducibility metadata."""

    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    write_metadata(path, cfg, runtime_s, rows=len(frame), **metadata)


def configured_days(cfg: Mapping[str, Any]) -> list[pd.Timestamp]:
    """Return all calendar days in the configured inclusive window."""

    data_cfg = cfg.get("data", {})
    return list(
        pd.date_range(
            str(data_cfg["window_start"]),
            str(data_cfg["window_end"]),
            freq="D",
        )
    )


def _dated(frame: pd.DataFrame, tz: str) -> pd.DataFrame:
    result = frame.copy()
    if "Interval Start" in result:
        times = pd.to_datetime(result["Interval Start"])
    elif isinstance(result.index, pd.DatetimeIndex):
        times = pd.Series(result.index, index=result.index)
    else:
        raise ValueError("Processed table lacks an Interval Start datetime")
    if times.dt.tz is None:
        times = times.dt.tz_localize(tz)
    else:
        times = times.dt.tz_convert(tz)
    result["_date"] = times.dt.date.to_numpy()
    result["_time_key"] = times.astype(str).to_numpy()
    return result


def assess_complete_days(
    cfg: Mapping[str, Any],
    agents: Sequence[str],
) -> tuple[list[pd.Timestamp], pd.DataFrame]:
    """Identify complete episode days and explain every skipped configured day."""

    names = list(agents)
    tables = load_processed(cfg)
    tz = str(cfg.get("data", {}).get("tz", "US/Central"))
    horizon = int(cfg.get("episode", {}).get("horizon_h", 24))
    prices = _dated(tables["prices"], tz)
    wind = _dated(tables["wind"], tz)
    forecast = _dated(tables["forecast"], tz)

    valid_prices = prices.dropna(subset=["pi_DA", "pi_RT"])
    price_counts = valid_prices.groupby("_date")["_time_key"].nunique()
    valid_wind = wind[wind["resource"].isin(names)].dropna(subset=["W_avail"])
    wind_counts = valid_wind.groupby(["_date", "resource"])["_time_key"].nunique()
    valid_forecast = forecast[forecast["resource"].isin(names)].dropna(
        subset=["What_cop", "b_baseline"]
    )
    forecast_counts = valid_forecast.groupby(["_date", "resource"])["_time_key"].nunique()

    complete: list[pd.Timestamp] = []
    skipped: list[dict[str, Any]] = []
    for day in configured_days(cfg):
        date = day.date()
        reasons: list[str] = []
        count = int(price_counts.get(date, 0))
        if count != horizon:
            reasons.append(f"prices {count}/{horizon}")
        missing_wind = [
            name for name in names if int(wind_counts.get((date, name), 0)) != horizon
        ]
        if missing_wind:
            reasons.append("wind incomplete: " + ",".join(missing_wind))
        missing_forecast = [
            name for name in names if int(forecast_counts.get((date, name), 0)) != horizon
        ]
        if missing_forecast:
            reasons.append("forecast incomplete: " + ",".join(missing_forecast))
        if reasons:
            skipped.append({"day": date.isoformat(), "reason": "; ".join(reasons)})
        else:
            complete.append(day)
    return complete, pd.DataFrame(skipped, columns=["day", "reason"])


def full_coverage_resources(cfg: Mapping[str, Any]) -> tuple[list[str], list[pd.Timestamp]]:
    """Return resources complete on every currently available complete market day."""

    market_days, _ = assess_complete_days(cfg, [])
    if not market_days:
        return [], []
    tables = load_processed(cfg)
    tz = str(cfg.get("data", {}).get("tz", "US/Central"))
    horizon = int(cfg.get("episode", {}).get("horizon_h", 24))
    valid_dates = {day.date() for day in market_days}
    wind = _dated(tables["wind"], tz)
    forecast = _dated(tables["forecast"], tz)
    wind = wind[wind["_date"].isin(valid_dates)].dropna(subset=["W_avail"])
    forecast = forecast[forecast["_date"].isin(valid_dates)].dropna(
        subset=["What_cop", "b_baseline"]
    )
    expected = horizon * len(valid_dates)
    wind_counts = wind.groupby("resource")["_time_key"].nunique()
    forecast_counts = forecast.groupby("resource")["_time_key"].nunique()
    metadata = tables["resources"].set_index("resource")
    eligible = [
        str(name)
        for name in metadata.index
        if float(metadata.loc[name, "nameplate_mw"]) > 0
        and int(wind_counts.get(name, 0)) == expected
        and int(forecast_counts.get(name, 0)) == expected
    ]
    return eligible, market_days

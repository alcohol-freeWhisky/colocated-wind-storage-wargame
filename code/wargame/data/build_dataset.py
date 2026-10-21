"""Assemble daily ERCOT extracts into the common processed dataset."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from pandas.api.types import is_datetime64_dtype

from wargame.data.ercot import _price_paths
from wargame.data.forecast_errors import (
    build_resource_forecast_errors,
    build_system_forecast_errors,
)

LOGGER = logging.getLogger(__name__)


def load_config(path: str | Path) -> dict[str, Any]:
    """Load a YAML configuration file."""
    with Path(path).open(encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def pool_resources(config: Mapping[str, Any]) -> list[str]:
    """Flatten the configured resource groups without changing their order."""
    return list(dict.fromkeys(resource for group in config["data"]["pool"] for resource in group))


def selected_days(
    config: Mapping[str, Any],
    start: str | None = None,
    end: str | None = None,
    days: int | None = None,
) -> pd.DatetimeIndex:
    """Return the inclusive operating-day range after CLI overrides."""
    first = pd.Timestamp(start or config["data"]["window_start"])
    last = pd.Timestamp(end or config["data"]["window_end"])
    if last < first:
        raise ValueError(f"End date {last.date()} precedes start date {first.date()}")
    dates = pd.date_range(first.normalize(), last.normalize(), freq="D")
    if days is not None:
        if days < 1:
            raise ValueError("--days must be positive")
        dates = dates[:days]
    return dates


def _as_local_time(values: pd.Series, tz: str) -> pd.Series:
    if isinstance(values.dtype, pd.DatetimeTZDtype):
        return values.dt.tz_convert(tz)
    parsed = pd.to_datetime(values, errors="coerce")
    if isinstance(parsed.dtype, pd.DatetimeTZDtype):
        return parsed.dt.tz_convert(tz)
    if is_datetime64_dtype(parsed.dtype):
        return parsed.dt.tz_localize(tz, ambiguous="infer", nonexistent="shift_forward")
    return pd.to_datetime(values, errors="coerce", utc=True).dt.tz_convert(tz)


def _read_daily(
    directory: Path,
    days: Iterable[pd.Timestamp],
    show_progress: bool,
) -> pd.DataFrame:
    dates: Iterable[pd.Timestamp] = days
    if show_progress:
        from tqdm import tqdm

        dates = tqdm(list(days), desc=f"Read {directory.name}", leave=False)
    frames = []
    for day in dates:
        path = directory / f"{day:%Y-%m-%d}.parquet"
        if path.exists():
            frames.append(pd.read_parquet(path))
        else:
            LOGGER.warning("Missing interim file: %s", path)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _window(frame: pd.DataFrame, column: str, days: pd.DatetimeIndex, tz: str) -> pd.DataFrame:
    if frame.empty:
        return frame
    result = frame.copy()
    result[column] = _as_local_time(result[column], tz)
    first = pd.Timestamp(days[0].date(), tz=tz)
    after_last = pd.Timestamp((days[-1] + pd.DateOffset(days=1)).date(), tz=tz)
    return result.loc[result[column].ge(first) & result[column].lt(after_last)].copy()


def _mode_or_missing(values: pd.Series) -> object:
    modes = values.dropna().mode()
    return modes.iloc[0] if not modes.empty else pd.NA


def _site(resource: str) -> str:
    prefixes = {
        "HHGT_": "Horse Hollow",
        "CAPRIDGE_": "Capricorn Ridge",
        "ANCHOR_": "Anchor Wind",
        "VERAWIND_": "Vera Wind",
        "WHMESA_": "White Mesa",
        "VORTEX_": "Vortex Wind",
        "LACY_CRK_": "Lacy Creek",
        "CANYONWD_": "Canyon Wind",
    }
    return next((site for prefix, site in prefixes.items() if resource.startswith(prefix)), resource)


def _build_prices(
    raw_dir: Path,
    days: pd.DatetimeIndex,
    year: int,
    hub: str,
    tz: str,
) -> pd.DataFrame:
    _, _, path = _price_paths(raw_dir, year, hub)
    if not path.exists():
        raise FileNotFoundError(f"Hourly price cache is missing: {path}; run 01_download_raw.py")
    prices = _window(pd.read_parquet(path), "Interval Start", days, tz)
    for column in ("pi_DA", "pi_RT"):
        prices[column] = pd.to_numeric(prices[column], errors="coerce")
    prices["hub"] = hub
    prices["t_utc"] = prices["Interval Start"].dt.tz_convert("UTC")
    return prices[["Interval Start", "t_utc", "pi_DA", "pi_RT", "hub"]].sort_values(
        "Interval Start"
    )


def _build_wind(sced: pd.DataFrame, days: pd.DatetimeIndex, tz: str) -> pd.DataFrame:
    columns = [
        "Interval Start",
        "t_utc",
        "resource",
        "W_avail",
        "W_out",
        "basepoint_mean",
        "curtail_obs",
        "n_5min",
    ]
    if sced.empty:
        return pd.DataFrame(columns=columns)
    sced = _window(sced, "SCED Timestamp", days, tz)
    sced["Interval Start"] = (
        sced["SCED Timestamp"]
        .dt.tz_convert("UTC")
        .dt.floor("h")
        .dt.tz_convert(tz)
    )
    for column in ("HSL", "Telemetered Net Output ", "Base Point"):
        sced[column] = pd.to_numeric(sced[column], errors="coerce")
    wind = (
        sced.groupby(["Interval Start", "Resource Name"], as_index=False, observed=True)
        .agg(
            W_avail=("HSL", "mean"),
            W_out=("Telemetered Net Output ", "mean"),
            basepoint_mean=("Base Point", "mean"),
            n_5min=("HSL", "size"),
        )
        .rename(columns={"Resource Name": "resource"})
    )
    wind["curtail_obs"] = wind["W_avail"] - wind["basepoint_mean"]
    wind["t_utc"] = wind["Interval Start"].dt.tz_convert("UTC")
    return wind[columns].sort_values(["Interval Start", "resource"], ignore_index=True)


def _build_forecast(
    cop: pd.DataFrame,
    dam: pd.DataFrame,
    days: pd.DatetimeIndex,
    tz: str,
) -> pd.DataFrame:
    columns = ["Interval Start", "t_utc", "resource", "What_cop", "b_dam", "b_baseline"]
    if cop.empty:
        cop_hourly = pd.DataFrame(columns=["Interval Start", "resource", "What_cop"])
    else:
        cop = _window(cop, "Interval Start", days, tz)
        cop["High Sustained Limit"] = pd.to_numeric(
            cop["High Sustained Limit"], errors="coerce"
        )
        cop_hourly = (
            cop.groupby(["Interval Start", "Resource Name"], as_index=False, observed=True)[
                "High Sustained Limit"
            ]
            .mean()
            .rename(columns={"Resource Name": "resource", "High Sustained Limit": "What_cop"})
        )
    if dam.empty:
        dam_hourly = pd.DataFrame(columns=["Interval Start", "resource", "b_dam"])
    else:
        dam = _window(dam, "Interval Start", days, tz)
        dam["Awarded Quantity"] = pd.to_numeric(dam["Awarded Quantity"], errors="coerce")
        dam_hourly = (
            dam.groupby(["Interval Start", "Resource Name"], as_index=False, observed=True)[
                "Awarded Quantity"
            ]
            .mean()
            .rename(columns={"Resource Name": "resource", "Awarded Quantity": "b_dam"})
        )
    forecast = cop_hourly.merge(
        dam_hourly, on=["Interval Start", "resource"], how="outer", validate="one_to_one"
    )
    if forecast.empty:
        return pd.DataFrame(columns=columns)
    forecast["b_baseline"] = forecast["b_dam"].where(
        forecast["b_dam"].gt(0), forecast["What_cop"]
    )
    forecast["t_utc"] = forecast["Interval Start"].dt.tz_convert("UTC")
    return forecast[columns].sort_values(["Interval Start", "resource"], ignore_index=True)


def _build_resources(
    sced: pd.DataFrame,
    wind: pd.DataFrame,
    configured: list[str],
    days: pd.DatetimeIndex,
    quantile: float,
) -> pd.DataFrame:
    base = pd.DataFrame({"resource": configured})
    if sced.empty:
        metadata = pd.DataFrame(columns=["resource", "dme", "qse"])
    else:
        metadata = (
            sced.groupby("Resource Name", as_index=False, observed=True)
            .agg(dme=("DME", _mode_or_missing), qse=("QSE", _mode_or_missing))
            .rename(columns={"Resource Name": "resource"})
        )
    if wind.empty:
        statistics = pd.DataFrame(
            columns=["resource", "nameplate_mw", "hsl_max", "n_hours", "mean_wind_mw"]
        )
    else:
        statistics = (
            wind.groupby("resource", as_index=False, observed=True)
            .agg(
                nameplate_mw=("W_avail", lambda values: values.quantile(quantile)),
                hsl_max=("W_avail", "max"),
                n_hours=("W_avail", "count"),
                mean_wind_mw=("W_avail", "mean"),
            )
        )
    resources = base.merge(metadata, on="resource", how="left").merge(
        statistics, on="resource", how="left"
    )
    resources["site"] = resources["resource"].map(_site)
    resources["n_hours"] = resources["n_hours"].fillna(0).astype(int)
    tz = wind["Interval Start"].dt.tz if not wind.empty else "US/Central"
    expected_hours = len(
        pd.date_range(
            pd.Timestamp(days[0].date(), tz=tz),
            pd.Timestamp((days[-1] + pd.DateOffset(days=1)).date(), tz=tz),
            freq="h",
            inclusive="left",
        )
    )
    resources["coverage_frac"] = resources["n_hours"] / expected_hours
    resources["mean_cf"] = resources["mean_wind_mw"] / resources["nameplate_mw"]
    return resources[
        [
            "resource",
            "site",
            "dme",
            "qse",
            "nameplate_mw",
            "hsl_max",
            "n_hours",
            "coverage_frac",
            "mean_cf",
        ]
    ]


def _latest_input_timestamp(*roots: Path) -> str:
    modified = [
        path.stat().st_mtime
        for root in roots
        if root.exists()
        for path in root.rglob("*")
        if path.is_file()
    ]
    if not modified:
        return "unknown"
    return datetime.fromtimestamp(max(modified), tz=timezone.utc).isoformat()


def _write_readme(output: Path, timestamp: str, download_timestamp: str) -> None:
    text = f"""# Processed data

Built at `{timestamp}` from public ERCOT and EIA source reports. Latest local
source-cache modification (download timestamp): `{download_timestamp}`. All interval
timestamps are timezone-aware `US/Central`; `t_utc`/`interval_start_utc` is the
same instant in UTC.

| File | Columns and source | Classification |
|---|---|---|
| `prices_hourly.parquet` | index `Interval Start`; `t_utc`, `pi_DA`, `pi_RT`, `hub`; ERCOT NP4-180-ER and NP6-785-ER | Empirical |
| `wind_hourly.parquet` | `Interval Start`, `t_utc`, `resource`, hourly SCED means `W_avail`, `W_out`, `basepoint_mean`, observed `curtail_obs`, and row count `n_5min`; ERCOT NP3-965-ER | Empirical |
| `forecast_hourly.parquet` | `Interval Start`, `t_utc`, `resource`, COP `What_cop`, DAM `b_dam`, and `b_baseline` (positive DAM award, otherwise COP); ERCOT COP/NP3-966-ER | Empirical with documented baseline construction |
| `resources.csv` | resource/site identifiers, modal DME/QSE, 99.5th-percentile and maximum HSL, coverage, and mean capacity factor | Empirical summary |
| `corr_matrix.csv` | Pairwise Pearson correlation of hourly SCED HSL | Empirical summary |
| `forecast_error_system.parquet` | `publish_time`, interval timestamps, `horizon_h`, `region`, latest reported `hsl_actual` and `gen_actual`, publication-vintage `stwpf`, `wgrpp`, and `cop_hsl`, constant regional `cap_proxy` (maximum observed realised HSL), HSL-based normalized forecast errors, and the curtailment-contaminated `err_stwpf_vs_gen_norm`; ERCOT NP4-732-CD/NP4-742-CD | Empirical summary |
| `forecast_error_resource.parquet` | COP HSL versus SCED HSL, `cap_proxy` (resource nameplate), and nameplate-normalized error | Empirical summary |
| `eia860_summary.json`, `eia860_tx_storage.csv` | Horse Hollow wind and Texas battery/hybrid calibration summaries; EIA-860 2023 | Empirical summary |

Episodes are views of these tables, constructed by operating day and agent set;
they are not separately materialized here. Battery sizing, shared POI limit `K`,
minimum delivery `D_t`, information regimes, monitoring thresholds, sanction
duration, and attack type are designed wargame variables from the configuration,
not historical observations.
"""
    (output / "README.md").write_text(text, encoding="utf-8")


def build_dataset(
    config: Mapping[str, Any] | str | Path,
    *,
    raw_dir: str | Path | None = None,
    interim_dir: str | Path | None = None,
    processed_dir: str | Path | None = None,
    start: str | None = None,
    end: str | None = None,
    days: int | None = None,
    show_progress: bool = False,
) -> dict[str, pd.DataFrame]:
    """Build every materialized table in DESIGN.md section 2."""
    cfg = load_config(config) if isinstance(config, (str, Path)) else dict(config)
    raw = Path(raw_dir or cfg["paths"]["raw"])
    interim = Path(interim_dir or cfg["paths"]["interim"])
    output = Path(processed_dir or cfg["paths"]["processed"])
    output.mkdir(parents=True, exist_ok=True)
    dates = selected_days(cfg, start=start, end=end, days=days)
    if dates.empty:
        raise ValueError("Selected operating-day window is empty")
    data_cfg = cfg["data"]
    tz = data_cfg.get("tz", "US/Central")
    configured = pool_resources(cfg)

    sced = _read_daily(interim / "sced_wind", dates, show_progress)
    cop = _read_daily(interim / "cop", dates, show_progress)
    dam = _read_daily(interim / "dam", dates, show_progress)
    prices = _build_prices(
        raw, dates, int(data_cfg["price_year"]), str(data_cfg["hub"]), tz
    )
    wind = _build_wind(sced, dates, tz)
    forecast = _build_forecast(cop, dam, dates, tz)
    resources = _build_resources(
        sced, wind, configured, dates, float(data_cfg.get("nameplate_quantile", 0.995))
    )
    correlation = (
        wind.pivot(index="Interval Start", columns="resource", values="W_avail")
        .reindex(columns=configured)
        .corr(min_periods=2)
        .reindex(index=configured, columns=configured)
    )

    prices.set_index("Interval Start").to_parquet(output / "prices_hourly.parquet")
    wind.to_parquet(output / "wind_hourly.parquet", index=False)
    forecast.to_parquet(output / "forecast_hourly.parquet", index=False)
    resources.to_csv(output / "resources.csv", index=False)
    correlation.to_csv(output / "corr_matrix.csv", index_label="resource")
    system_errors = build_system_forecast_errors(
        raw, output / "forecast_error_system.parquet"
    )
    resource_errors = build_resource_forecast_errors(
        wind, forecast, resources, output / "forecast_error_resource.parquet"
    )
    timestamp = datetime.now(timezone.utc).isoformat()
    _write_readme(output, timestamp, _latest_input_timestamp(raw, interim))
    LOGGER.info("Built processed dataset for %s through %s", dates[0].date(), dates[-1].date())
    return {
        "prices_hourly": prices,
        "wind_hourly": wind,
        "forecast_hourly": forecast,
        "resources": resources,
        "corr_matrix": correlation,
        "forecast_error_system": system_errors,
        "forecast_error_resource": resource_errors,
    }

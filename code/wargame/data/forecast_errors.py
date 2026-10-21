"""Construct system-, region-, and resource-level wind forecast errors."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

LOGGER = logging.getLogger(__name__)

SYSTEM_COLUMNS = [
    "publish_time",
    "interval_start",
    "interval_start_utc",
    "horizon_h",
    "region",
    "hsl_actual",
    "gen_actual",
    "stwpf",
    "wgrpp",
    "cop_hsl",
    "cap_proxy",
    "err_stwpf_norm",
    "err_wgrpp_norm",
    "err_cop_norm",
    "err_stwpf_vs_gen_norm",
]
RESOURCE_COLUMNS = [
    "Interval Start",
    "t_utc",
    "resource",
    "What_cop",
    "W_avail",
    "cap_proxy",
    "err_norm",
]


def _forecast_directories(raw_dir: str | Path) -> tuple[Path, Path]:
    root = Path(raw_dir)
    ercot = root if root.name == "ercot" else root / "ercot"
    return ercot / "wind_forecast_hourly", ercot / "wind_forecast_region_hourly"


def _read_snapshots(directory: Path) -> pd.DataFrame:
    files = sorted(directory.glob("*.parquet"))
    if not files:
        LOGGER.warning("No wind forecast snapshots found in %s", directory)
        return pd.DataFrame()
    frames = [pd.read_parquet(path) for path in files]
    combined = pd.concat(frames, ignore_index=True)
    return combined.drop_duplicates(["Publish Time", "Interval Start"], keep="last")


def _regions(frame: pd.DataFrame) -> list[str]:
    names = []
    for column in frame.columns:
        if not column.startswith("GEN "):
            continue
        region = column.removeprefix("GEN ")
        if f"STWPF {region}" in frame and f"WGRPP {region}" in frame:
            names.append(region)
    return names


def _one_region(frame: pd.DataFrame, region: str) -> pd.DataFrame:
    gen_col = f"GEN {region}"
    stwpf_col = f"STWPF {region}"
    wgrpp_col = f"WGRPP {region}"
    hsl_col = f"HSL {region}"
    cop_hsl_col = f"COP HSL {region}"

    actual_hsl_col = hsl_col if hsl_col in frame else cop_hsl_col
    if actual_hsl_col not in frame:
        LOGGER.warning("No realised HSL column found for region %s", region)
        return pd.DataFrame(columns=SYSTEM_COLUMNS)

    actual_columns = ["Interval Start", "Publish Time", gen_col, actual_hsl_col]
    actual_mask = frame[gen_col].notna() & frame[actual_hsl_col].notna()
    actual = frame.loc[actual_mask, actual_columns].copy()
    actual = actual.sort_values("Publish Time").drop_duplicates("Interval Start", keep="last")
    actual = actual.rename(
        columns={gen_col: "gen_actual", actual_hsl_col: "hsl_actual"}
    )
    actual = actual[["Interval Start", "gen_actual", "hsl_actual"]]
    cap_proxy = pd.to_numeric(actual["hsl_actual"], errors="coerce").max()
    if not np.isfinite(cap_proxy) or cap_proxy <= 0:
        cap_proxy = np.nan

    forecast_columns = ["Publish Time", "Interval Start", stwpf_col, wgrpp_col]
    if cop_hsl_col in frame:
        forecast_columns.append(cop_hsl_col)
    forecasts = frame[forecast_columns].rename(
        columns={stwpf_col: "stwpf", wgrpp_col: "wgrpp", cop_hsl_col: "cop_hsl"}
    )
    if "cop_hsl" not in forecasts:
        forecasts["cop_hsl"] = np.nan
    forecasts["horizon_h"] = (
        (forecasts["Interval Start"] - forecasts["Publish Time"])
        .dt.total_seconds()
        .div(3600)
        .round()
        .astype("Int64")
    )
    forecasts = forecasts.loc[
        forecasts["horizon_h"].ge(0)
        & (forecasts["stwpf"].notna() | forecasts["wgrpp"].notna())
    ]
    result = forecasts.merge(actual, on="Interval Start", how="inner", validate="many_to_one")
    result["cap_proxy"] = cap_proxy
    result["err_stwpf_norm"] = (result["stwpf"] - result["hsl_actual"]) / cap_proxy
    result["err_wgrpp_norm"] = (result["wgrpp"] - result["hsl_actual"]) / cap_proxy
    result["err_cop_norm"] = (result["cop_hsl"] - result["hsl_actual"]) / cap_proxy
    result["err_stwpf_vs_gen_norm"] = (
        result["stwpf"] - result["gen_actual"]
    ) / cap_proxy
    result["region"] = region
    result = result.rename(
        columns={"Publish Time": "publish_time", "Interval Start": "interval_start"}
    )
    result["interval_start_utc"] = result["interval_start"].dt.tz_convert("UTC")
    return result[SYSTEM_COLUMNS]


def build_system_forecast_errors(
    raw_dir: str | Path,
    output_path: str | Path | None = None,
) -> pd.DataFrame:
    """Build forecast errors using later publications as the actual-value source."""
    hourly_dir, region_dir = _forecast_directories(raw_dir)
    hourly = _read_snapshots(hourly_dir)
    regional = _read_snapshots(region_dir)
    pieces: list[pd.DataFrame] = []
    if not hourly.empty:
        pieces.extend(_one_region(hourly, region) for region in _regions(hourly))
    if not regional.empty:
        pieces.extend(
            _one_region(regional, region)
            for region in _regions(regional)
            if region != "SYSTEM WIDE"
        )
    pieces = [piece for piece in pieces if not piece.empty]
    result = (
        pd.concat(pieces, ignore_index=True)
        if pieces
        else pd.DataFrame(columns=SYSTEM_COLUMNS)
    )
    if not result.empty:
        result = result.sort_values(
            ["region", "publish_time", "interval_start"], ignore_index=True
        )
    if output_path is not None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        result.to_parquet(path, index=False)
    LOGGER.info("Built %d system/regional forecast-error rows", len(result))
    return result


def build_resource_forecast_errors(
    wind_hourly: pd.DataFrame,
    forecast_hourly: pd.DataFrame,
    resources: pd.DataFrame,
    output_path: str | Path | None = None,
) -> pd.DataFrame:
    """Compare COP HSL forecasts with hourly SCED HSL by resource."""
    required = {"Interval Start", "resource", "What_cop"}
    if wind_hourly.empty or forecast_hourly.empty or not required.issubset(forecast_hourly):
        result = pd.DataFrame(columns=RESOURCE_COLUMNS)
    else:
        names = resources[["resource", "nameplate_mw"]]
        result = (
            forecast_hourly[["Interval Start", "resource", "What_cop"]]
            .merge(
                wind_hourly[["Interval Start", "resource", "W_avail"]],
                on=["Interval Start", "resource"],
                how="inner",
                validate="one_to_one",
            )
            .merge(names, on="resource", how="left", validate="many_to_one")
        )
        denominator = pd.to_numeric(result["nameplate_mw"], errors="coerce").replace(0, np.nan)
        result["cap_proxy"] = denominator
        result["err_norm"] = (result["W_avail"] - result["What_cop"]) / denominator
        result["t_utc"] = result["Interval Start"].dt.tz_convert("UTC")
        result = result[RESOURCE_COLUMNS].sort_values(
            ["Interval Start", "resource"], ignore_index=True
        )
    if output_path is not None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        result.to_parquet(path, index=False)
    LOGGER.info("Built %d resource forecast-error rows", len(result))
    return result

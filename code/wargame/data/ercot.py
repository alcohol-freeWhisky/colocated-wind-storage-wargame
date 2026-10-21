"""ERCOT downloads used by the wargame data pipeline."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

import pandas as pd
from gridstatus import Ercot

LOGGER = logging.getLogger(__name__)

SCED_COLUMNS = [
    "SCED Timestamp",
    "Resource Name",
    "QSE",
    "DME",
    "HSL",
    "Base Point",
    "Telemetered Net Output ",
    "Output Schedule",
    "Telemetered Resource Status",
]
COP_COLUMNS = [
    "Interval Start",
    "Resource Name",
    "QSE",
    "Status",
    "High Sustained Limit",
]
DAM_COLUMNS = [
    "Interval Start",
    "Resource Name",
    "Resource Type",
    "HSL",
    "Awarded Quantity",
    "Settlement Point Name",
    "Energy Settlement Point Price",
]


def _ensure_download_log() -> None:
    """Install a file handler when the caller has not configured logging."""
    path = Path("results/logs/download.log")
    path.parent.mkdir(parents=True, exist_ok=True)
    resolved = path.resolve()
    root = logging.getLogger()
    if any(
        isinstance(handler, logging.FileHandler)
        and Path(handler.baseFilename) == resolved
        for handler in root.handlers
    ):
        return
    handler = logging.FileHandler(resolved)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root.addHandler(handler)
    if root.level > logging.INFO:
        root.setLevel(logging.INFO)


def _write_parquet_atomic(frame: pd.DataFrame, path: Path) -> None:
    """Write a parquet file atomically so interrupted runs remain resumable."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_parquet(temporary, index=False)
    temporary.replace(path)


def _read_or_download(
    path: Path,
    label: str,
    download: Callable[[], pd.DataFrame],
) -> pd.DataFrame:
    """Read a completed daily file or download it, logging any failure."""
    _ensure_download_log()
    try:
        if path.exists():
            LOGGER.info("Skipping existing %s: %s", label, path)
            return pd.read_parquet(path)
        frame = download()
        _write_parquet_atomic(frame, path)
        LOGGER.info("Saved %s (%d rows): %s", label, len(frame), path)
        return frame
    except Exception:
        LOGGER.exception("Failed to fetch %s", label)
        return pd.DataFrame()


def _slug(value: str) -> str:
    return "".join(character if character.isalnum() else "_" for character in value)


def _price_paths(raw_dir: str | Path, year: int, hub: str) -> tuple[Path, Path, Path]:
    directory = Path(raw_dir) / "ercot" / "prices"
    suffix = f"{year}_{_slug(hub)}.parquet"
    return (
        directory / f"dam_{suffix}",
        directory / f"rtm_{suffix}",
        directory / f"prices_hourly_{suffix}",
    )


def fetch_prices(year: int, hub: str, raw_dir: str | Path) -> pd.DataFrame:
    """Fetch and cache DAM and RTM prices for one ERCOT settlement hub.

    The source reports are filtered immediately to the requested hub. RTM's
    15-minute prices are averaged by local clock hour.
    """
    _ensure_download_log()
    dam_path, rtm_path, hourly_path = _price_paths(raw_dir, year, hub)
    try:
        if hourly_path.exists():
            LOGGER.info("Skipping existing hourly price cache: %s", hourly_path)
            return pd.read_parquet(hourly_path)

        iso = Ercot()
        if dam_path.exists():
            dam = pd.read_parquet(dam_path)
        else:
            dam_all = iso.get_dam_spp(year)
            dam = dam_all.loc[dam_all["Location"].eq(hub)].copy()
            del dam_all
            if dam.empty:
                raise ValueError(f"No DAM prices found for hub {hub!r} in {year}")
            _write_parquet_atomic(dam, dam_path)

        if rtm_path.exists():
            rtm = pd.read_parquet(rtm_path)
        else:
            rtm_all = iso.get_rtm_spp(year)
            rtm = rtm_all.loc[rtm_all["Location"].eq(hub)].copy()
            del rtm_all
            if rtm.empty:
                raise ValueError(f"No RTM prices found for hub {hub!r} in {year}")
            _write_parquet_atomic(rtm, rtm_path)

        dam_hourly = (
            dam.assign(pi_DA=pd.to_numeric(dam["SPP"], errors="coerce"))
            .groupby("Interval Start", as_index=False, observed=True)["pi_DA"]
            .mean()
        )
        rtm_hours = (
            rtm["Interval Start"]
            .dt.tz_convert("UTC")
            .dt.floor("h")
            .dt.tz_convert(rtm["Interval Start"].dt.tz)
        )
        rtm_hourly = (
            rtm.assign(
                **{
                    "Interval Start": rtm_hours,
                    "pi_RT": pd.to_numeric(rtm["SPP"], errors="coerce"),
                }
            )
            .groupby("Interval Start", as_index=False, observed=True)["pi_RT"]
            .mean()
        )
        hourly = dam_hourly.merge(rtm_hourly, on="Interval Start", how="outer")
        hourly["hub"] = hub
        hourly = hourly.sort_values("Interval Start", ignore_index=True)
        _write_parquet_atomic(hourly, hourly_path)
        LOGGER.info("Saved hourly price cache (%d rows): %s", len(hourly), hourly_path)
        return hourly
    except Exception:
        LOGGER.exception("Failed to fetch ERCOT prices for year=%s hub=%s", year, hub)
        return pd.DataFrame()


def fetch_sced_wind_day(
    day: str | pd.Timestamp,
    resources: list[str],
    interim_dir: str | Path,
) -> pd.DataFrame:
    """Fetch one operating day's wind rows from the 60-day SCED disclosure."""
    date = pd.Timestamp(day).strftime("%Y-%m-%d")
    path = Path(interim_dir) / "sced_wind" / f"{date}.parquet"

    def download() -> pd.DataFrame:
        payload = Ercot().get_60_day_sced_disclosure(
            pd.Timestamp(date), output_format="pg_array_as_string"
        )
        frame = payload.pop("sced_gen_resource")
        payload.clear()
        selected = frame.loc[
            frame["Resource Type"].eq("WIND") & frame["Resource Name"].isin(resources),
            SCED_COLUMNS,
        ].copy()
        del frame, payload
        return selected

    return _read_or_download(path, f"SCED wind {date}", download)


def fetch_cop_day(
    day: str | pd.Timestamp,
    resources: list[str],
    interim_dir: str | Path,
) -> pd.DataFrame:
    """Fetch one operating day's COP adjustment-period resource snapshot."""
    date = pd.Timestamp(day).strftime("%Y-%m-%d")
    path = Path(interim_dir) / "cop" / f"{date}.parquet"

    def download() -> pd.DataFrame:
        frame = Ercot().get_cop_adjustment_period_snapshot_60_day(pd.Timestamp(date))
        return frame.loc[frame["Resource Name"].isin(resources), COP_COLUMNS].copy()

    return _read_or_download(path, f"COP {date}", download)


def fetch_dam_day(
    day: str | pd.Timestamp,
    resources: list[str],
    interim_dir: str | Path,
) -> pd.DataFrame:
    """Fetch one operating day's generation rows from the 60-day DAM disclosure."""
    date = pd.Timestamp(day).strftime("%Y-%m-%d")
    path = Path(interim_dir) / "dam" / f"{date}.parquet"

    def download() -> pd.DataFrame:
        payload = Ercot().get_60_day_dam_disclosure(
            pd.Timestamp(date), output_format="pg_array_as_string"
        )
        frame = payload.pop("dam_gen_resource")
        payload.clear()
        selected = frame.loc[
            frame["Resource Name"].isin(resources), DAM_COLUMNS
        ].copy()
        del frame, payload
        return selected

    return _read_or_download(path, f"DAM {date}", download)

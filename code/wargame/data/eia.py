"""EIA-860 download and asset-summary helpers."""

from __future__ import annotations

import json
import logging
import re
import zipfile
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

import pandas as pd
import requests

LOGGER = logging.getLogger(__name__)


def _normalise(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).casefold())


def _find_column(columns: Iterable[object], *aliases: str) -> object:
    """Find a column by case- and punctuation-insensitive aliases."""
    normalised = {column: _normalise(column) for column in columns}
    targets = [_normalise(alias) for alias in aliases]
    for target in targets:
        for column, candidate in normalised.items():
            if candidate == target:
                return column
    for target in targets:
        for column, candidate in normalised.items():
            if target in candidate or candidate in target:
                return column
    raise KeyError(f"Could not find any of {aliases!r} in {list(columns)!r}")


def _detect_header(path: Path, sheet: str) -> tuple[int, int]:
    preview = pd.read_excel(path, sheet_name=sheet, header=None, nrows=30)
    tokens = ("plantcode", "plantname", "state", "nameplatecapacity")
    scores = []
    for row_number, row in preview.iterrows():
        cells = {_normalise(value) for value in row.dropna()}
        score = sum(any(token in cell for cell in cells) for token in tokens)
        scores.append((score, int(row_number)))
    return max(scores)


def _read_eia_workbook(path: Path) -> pd.DataFrame:
    """Read the most table-like sheet while detecting EIA's preamble rows."""
    workbook = pd.ExcelFile(path)
    candidates = []
    for position, sheet in enumerate(workbook.sheet_names):
        score, header = _detect_header(path, sheet)
        preferred = int(sheet.casefold() in {"operable", "operating"})
        candidates.append((score, preferred, -position, header, sheet))
    score, _, _, header, sheet = max(candidates)
    if score < 3:
        raise ValueError(f"Could not detect an EIA table header in {path}")
    frame = pd.read_excel(path, sheet_name=sheet, header=header)
    frame = frame.dropna(axis="columns", how="all").dropna(axis="rows", how="all")
    LOGGER.info("Read %s sheet=%s header_row=%d rows=%d", path.name, sheet, header + 1, len(frame))
    return frame


def download_eia860(url: str, raw_dir: str | Path) -> Path:
    """Download and extract the EIA-860 archive, returning its directory."""
    directory = Path(raw_dir) / "eia"
    directory.mkdir(parents=True, exist_ok=True)
    filename = Path(urlparse(url).path).name or "eia8602023.zip"
    archive = directory / filename
    if not archive.exists():
        partial = archive.with_suffix(archive.suffix + ".part")
        LOGGER.info("Downloading EIA-860 from %s", url)
        with requests.get(url, stream=True, timeout=120) as response:
            response.raise_for_status()
            with partial.open("wb") as output:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        output.write(chunk)
        partial.replace(archive)
    else:
        LOGGER.info("Skipping existing EIA-860 archive: %s", archive)

    extracted = directory / archive.stem
    expected = list(extracted.rglob("*.xlsx")) if extracted.exists() else []
    if not expected:
        extracted.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(extracted)
        LOGGER.info("Extracted EIA-860 to %s", extracted)
    return extracted


def _workbook(directory: Path, pattern: str) -> Path:
    matches = sorted(path for path in directory.rglob("*.xlsx") if pattern in path.name.casefold())
    if not matches:
        raise FileNotFoundError(f"No EIA workbook matching {pattern!r} under {directory}")
    return matches[0]


def _standard_asset_columns(frame: pd.DataFrame, *, storage: bool = False) -> pd.DataFrame:
    state = _find_column(frame.columns, "Plant State", "State")
    plant_name = _find_column(frame.columns, "Plant Name")
    plant_code = _find_column(frame.columns, "Plant Code")
    generator_id = _find_column(frame.columns, "Generator ID", "Generator Id")
    power = _find_column(frame.columns, "Nameplate Capacity (MW)")
    columns: dict[str, object] = {
        "state": state,
        "plant_name": plant_name,
        "plant_code": plant_code,
        "generator_id": generator_id,
        "power_mw": power,
    }
    if storage:
        columns["energy_mwh"] = _find_column(
            frame.columns,
            "Nameplate Energy Capacity (MWh)",
            "Nameplate Energy Capacity",
        )
    result = pd.DataFrame({name: frame[column] for name, column in columns.items()})
    result["state"] = result["state"].astype("string").str.strip().str.upper()
    result["plant_name"] = result["plant_name"].astype("string").str.strip()
    result["generator_id"] = result["generator_id"].astype("string").str.strip()
    result["plant_code"] = pd.to_numeric(result["plant_code"], errors="coerce").astype("Int64")
    result["power_mw"] = pd.to_numeric(result["power_mw"], errors="coerce")
    if storage:
        result["energy_mwh"] = pd.to_numeric(result["energy_mwh"], errors="coerce")
    return result


def build_eia860_summary(
    url: str,
    raw_dir: str | Path,
    processed_dir: str | Path,
) -> dict[str, object]:
    """Build Texas wind/storage calibration summaries from EIA-860 2023."""
    extracted = download_eia860(url, raw_dir)
    wind = _standard_asset_columns(_read_eia_workbook(_workbook(extracted, "3_2_wind")))
    storage = _standard_asset_columns(
        _read_eia_workbook(_workbook(extracted, "3_4_energy_storage")), storage=True
    )

    tx_wind = wind.loc[wind["state"].eq("TX") & wind["power_mw"].gt(0)].copy()
    horse_hollow = tx_wind.loc[
        tx_wind["plant_name"].str.contains("Horse Hollow", case=False, na=False)
    ].copy()
    units = [
        {
            "plant_code": int(row.plant_code),
            "plant_name": str(row.plant_name),
            "generator_id": str(row.generator_id),
            "nameplate_mw": float(row.power_mw),
        }
        for row in horse_hollow.itertuples(index=False)
        if pd.notna(row.plant_code) and pd.notna(row.power_mw)
    ]

    tx_storage = storage.loc[
        storage["state"].eq("TX")
        & storage["power_mw"].gt(0)
        & storage["energy_mwh"].gt(0)
    ].copy()
    durations = tx_storage["energy_mwh"] / tx_storage["power_mw"]
    probability_points = [0.0, 0.25, 0.5, 0.75, 1.0]
    duration_quantiles = {
        f"p{int(probability * 100):02d}": float(durations.quantile(probability))
        for probability in probability_points
    }

    wind_by_plant = (
        tx_wind.groupby(["plant_code", "plant_name"], as_index=False, dropna=True)["power_mw"]
        .sum()
        .rename(columns={"power_mw": "wind_power_mw"})
    )
    storage_by_plant = (
        tx_storage.groupby("plant_code", as_index=False, dropna=True)
        .agg(storage_power_mw=("power_mw", "sum"), storage_energy_mwh=("energy_mwh", "sum"))
    )
    hybrids = wind_by_plant.merge(storage_by_plant, on="plant_code", how="inner")
    hybrids["storage_to_wind_power_ratio"] = (
        hybrids["storage_power_mw"] / hybrids["wind_power_mw"]
    )
    hybrids = hybrids.sort_values("plant_code", ignore_index=True)

    summary: dict[str, object] = {
        "source_url": url,
        "horse_hollow": {
            "nameplate_mw": float(horse_hollow["power_mw"].sum()),
            "n_units": len(units),
            "units": units,
        },
        "tx_battery_duration_h": {
            "n_units": int(durations.size),
            "mean": float(durations.mean()) if not durations.empty else None,
            "quantiles": duration_quantiles if not durations.empty else {},
        },
        "tx_colocated_hybrids": {
            "n_plants": int(len(hybrids)),
            "ratio_quantiles": (
                {
                    f"p{int(probability * 100):02d}": float(
                        hybrids["storage_to_wind_power_ratio"].quantile(probability)
                    )
                    for probability in probability_points
                }
                if not hybrids.empty
                else {}
            ),
        },
    }

    output = Path(processed_dir)
    output.mkdir(parents=True, exist_ok=True)
    summary_path = output / "eia860_summary.json"
    temporary = summary_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(summary_path)
    hybrids.to_csv(output / "eia860_tx_storage.csv", index=False)
    LOGGER.info(
        "EIA summary: Horse Hollow %.1f MW across %d units; %d TX batteries; %d hybrids",
        horse_hollow["power_mw"].sum(),
        len(units),
        len(tx_storage),
        len(hybrids),
    )
    return summary

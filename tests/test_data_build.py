"""Offline integration tests for the raw-to-processed data builder."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from wargame.data.build_dataset import build_dataset
from wargame.experiments import io as experiment_io


def test_build_dataset_from_tiny_interim_fixture(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    interim = tmp_path / "interim"
    processed = tmp_path / "processed"
    for directory in (
        raw / "ercot" / "prices",
        raw / "ercot" / "wind_forecast_hourly",
        raw / "ercot" / "wind_forecast_region_hourly",
        interim / "sced_wind",
        interim / "cop",
        interim / "dam",
    ):
        directory.mkdir(parents=True)

    hours = pd.date_range("2025-03-01", periods=2, freq="h", tz="US/Central")
    prices = pd.DataFrame(
        {
            "Interval Start": hours,
            "pi_DA": [20.0, 30.0],
            "pi_RT": [21.0, 29.0],
            "hub": "HB_WEST",
        }
    )
    prices.to_parquet(raw / "ercot" / "prices" / "prices_hourly_2025_HB_WEST.parquet")

    sced_rows = []
    for hour_index, hour in enumerate(hours):
        for resource, base_hsl in (("WIND_A", 10.0), ("WIND_B", 20.0)):
            for minute in (5, 35):
                hsl = base_hsl + hour_index + minute / 100
                sced_rows.append(
                    {
                        "SCED Timestamp": hour + timedelta(minutes=minute),
                        "Resource Name": resource,
                        "QSE": f"Q_{resource[-1]}",
                        "DME": "D_TEST",
                        "HSL": hsl,
                        "Base Point": hsl - 1,
                        "Telemetered Net Output ": hsl - 2,
                        "Output Schedule": hsl - 1,
                        "Telemetered Resource Status": "ON",
                    }
                )
    pd.DataFrame(sced_rows).to_parquet(interim / "sced_wind" / "2025-03-01.parquet")

    cop = pd.DataFrame(
        [
            {
                "Interval Start": hour,
                "Resource Name": resource,
                "QSE": f"Q_{resource[-1]}",
                "Status": "ON",
                "High Sustained Limit": value,
            }
            for hour in hours
            for resource, value in (("WIND_A", 9.0), ("WIND_B", 19.0))
        ]
    )
    cop.to_parquet(interim / "cop" / "2025-03-01.parquet")

    dam = pd.DataFrame(
        [
            {
                "Interval Start": hour,
                "Resource Name": resource,
                "Resource Type": "WIND",
                "HSL": 10.0,
                "Awarded Quantity": award,
                "Settlement Point Name": "HB_WEST",
                "Energy Settlement Point Price": 20.0,
            }
            for hour in hours
            for resource, award in (("WIND_A", 0.0), ("WIND_B", 7.0))
        ]
    )
    dam.to_parquet(interim / "dam" / "2025-03-01.parquet")

    early_publish = hours[0] - timedelta(minutes=5)
    late_publish = hours[1] + timedelta(hours=2)
    system_snapshot = pd.DataFrame(
        {
            "Interval Start": [hours[0], hours[1], hours[0], hours[1]],
            "Interval End": [
                hours[0] + timedelta(hours=1),
                hours[1] + timedelta(hours=1),
                hours[0] + timedelta(hours=1),
                hours[1] + timedelta(hours=1),
            ],
            "Publish Time": [early_publish, early_publish, late_publish, late_publish],
            "GEN SYSTEM WIDE": [np.nan, np.nan, 90.0, 180.0],
            "COP HSL SYSTEM WIDE": [105.0, 135.0, 118.0, 149.0],
            "STWPF SYSTEM WIDE": [100.0, 200.0, 91.0, 181.0],
            "WGRPP SYSTEM WIDE": [95.0, 190.0, 89.0, 179.0],
            "HSL SYSTEM WIDE": [np.nan, np.nan, 120.0, 150.0],
        }
    )
    system_snapshot.to_parquet(
        raw / "ercot" / "wind_forecast_hourly" / "2025-03-01.parquet"
    )
    region_snapshot = system_snapshot.drop(columns="HSL SYSTEM WIDE").rename(
        columns={
            "GEN SYSTEM WIDE": "GEN WEST",
            "COP HSL SYSTEM WIDE": "COP HSL WEST",
            "STWPF SYSTEM WIDE": "STWPF WEST",
            "WGRPP SYSTEM WIDE": "WGRPP WEST",
        }
    )
    region_snapshot["COP HSL WEST"] = [100.0, 130.0, 110.0, 140.0]
    region_snapshot.to_parquet(
        raw / "ercot" / "wind_forecast_region_hourly" / "2025-03-01.parquet"
    )

    config = {
        "paths": {"raw": str(raw), "interim": str(interim), "processed": str(processed)},
        "data": {
            "price_year": 2025,
            "hub": "HB_WEST",
            "window_start": "2025-03-01",
            "window_end": "2025-03-01",
            "tz": "US/Central",
            "pool": [["WIND_A", "WIND_B"]],
            "nameplate_quantile": 0.995,
        },
    }
    tables = build_dataset(config)

    assert len(tables["wind_hourly"]) == 4
    assert set(tables["wind_hourly"]["n_5min"]) == {2}
    assert np.allclose(tables["wind_hourly"]["curtail_obs"], 1.0)
    baseline = tables["forecast_hourly"].set_index("resource")["b_baseline"]
    assert set(baseline.loc["WIND_A"]) == {9.0}
    assert set(baseline.loc["WIND_B"]) == {7.0}
    assert tables["resources"]["nameplate_mw"].notna().all()
    assert set(tables["forecast_error_system"]["region"]) == {"SYSTEM WIDE", "WEST"}
    assert list(tables["forecast_error_system"].columns) == [
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
    system_error = tables["forecast_error_system"].query(
        "region == 'SYSTEM WIDE' and horizon_h == 0"
    ).iloc[0]
    assert system_error["horizon_h"] == 0
    assert system_error["hsl_actual"] == 120.0
    assert system_error["gen_actual"] == 90.0
    assert system_error["cap_proxy"] == 150.0
    assert np.isclose(system_error["err_stwpf_norm"], (100.0 - 120.0) / 150.0)
    assert np.isclose(system_error["err_wgrpp_norm"], (95.0 - 120.0) / 150.0)
    assert np.isclose(system_error["err_cop_norm"], (105.0 - 120.0) / 150.0)
    assert np.isclose(system_error["err_stwpf_vs_gen_norm"], (100.0 - 90.0) / 150.0)
    west_error = tables["forecast_error_system"].query(
        "region == 'WEST' and horizon_h == 0"
    ).iloc[0]
    assert west_error["hsl_actual"] == 110.0
    assert west_error["cap_proxy"] == 140.0
    assert np.isclose(west_error["err_stwpf_norm"], (100.0 - 110.0) / 140.0)
    assert len(tables["forecast_error_resource"]) == 4
    resource_errors = tables["forecast_error_resource"]
    nameplates = tables["resources"].set_index("resource")["nameplate_mw"]
    assert np.allclose(
        resource_errors["cap_proxy"], resource_errors["resource"].map(nameplates)
    )
    assert (processed / "README.md").exists()
    assert pd.read_parquet(processed / "prices_hourly.parquet").index.name == "Interval Start"


def test_dst_spring_day_is_explicitly_skipped(monkeypatch) -> None:
    hours = pd.date_range("2025-03-09", "2025-03-10", inclusive="left", freq="h", tz="US/Central")
    assert len(hours) == 23
    prices = pd.DataFrame({"Interval Start": hours, "pi_DA": 10.0, "pi_RT": 11.0})
    wind = pd.DataFrame(
        {
            "Interval Start": hours,
            "resource": "WIND_A",
            "W_avail": 5.0,
        }
    )
    forecast = pd.DataFrame(
        {
            "Interval Start": hours,
            "resource": "WIND_A",
            "What_cop": 5.0,
            "b_baseline": 5.0,
        }
    )
    monkeypatch.setattr(
        experiment_io,
        "load_processed",
        lambda cfg: {
            "prices": prices,
            "wind": wind,
            "forecast": forecast,
            "resources": pd.DataFrame(),
        },
    )
    cfg = {
        "data": {
            "window_start": "2025-03-09",
            "window_end": "2025-03-09",
            "tz": "US/Central",
        },
        "episode": {"horizon_h": 24},
    }
    complete, skipped = experiment_io.assess_complete_days(cfg, ["WIND_A"])
    assert complete == []
    assert skipped.to_dict("records") == [
        {
            "day": "2025-03-09",
            "reason": "prices 23/24; wind incomplete: WIND_A; forecast incomplete: WIND_A",
        }
    ]

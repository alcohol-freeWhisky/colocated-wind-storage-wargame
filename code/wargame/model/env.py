"""Episode container and processed-data loading."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike, NDArray

from wargame.model.physics import Agent, Battery


def _merge(base: dict[str, Any], updates: Mapping[str, Any] | None) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in (updates or {}).items():
        if isinstance(value, Mapping) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def _as_2d(name: str, value: ArrayLike, shape: tuple[int, int]) -> NDArray[np.float64]:
    array = np.asarray(value, dtype=float)
    if array.shape != shape:
        raise ValueError(f"{name} must have shape {shape}, got {array.shape}")
    if np.any(~np.isfinite(array)):
        raise ValueError(f"{name} contains missing or non-finite values")
    return array


@dataclass(slots=True)
class Episode:
    """Complete physical and market inputs for one operating day."""

    agents: list[Agent]
    W: NDArray[np.float64]
    What: NDArray[np.float64]
    b: NDArray[np.float64]
    pi_DA: NDArray[np.float64]
    pi_RT: NDArray[np.float64]
    K: float
    D: NDArray[np.float64]
    cfg: dict[str, Any]
    day: Any

    def __post_init__(self) -> None:
        n_agents = len(self.agents)
        if n_agents == 0:
            raise ValueError("Episode requires at least one agent")
        if sum(agent.nameplate for agent in self.agents) <= 0:
            raise ValueError("Episode aggregate nameplate must be positive")
        self.W = np.asarray(self.W, dtype=float)
        if self.W.ndim != 2 or self.W.shape[0] != n_agents:
            raise ValueError("W must have shape (number of agents, T)")
        shape = self.W.shape
        self.What = _as_2d("What", self.What, shape)
        self.b = _as_2d("b", self.b, shape)
        self.pi_DA = np.asarray(self.pi_DA, dtype=float)
        self.pi_RT = np.asarray(self.pi_RT, dtype=float)
        self.D = np.asarray(self.D, dtype=float)
        for name, array in (("pi_DA", self.pi_DA), ("pi_RT", self.pi_RT), ("D", self.D)):
            if array.shape != (shape[1],) or np.any(~np.isfinite(array)):
                raise ValueError(f"{name} must be a finite length-{shape[1]} vector")
        if np.any(~np.isfinite(self.W)) or np.any(self.W < 0):
            raise ValueError("W must be complete, finite, and non-negative")
        if np.any(self.What < 0) or np.any(self.b < 0) or np.any(self.D < 0):
            raise ValueError("Forecasts, baselines, and D must be non-negative")
        if not np.isfinite(self.K) or self.K < 0:
            raise ValueError("K must be finite and non-negative")

    @property
    def N(self) -> int:
        """Number of agents."""

        return len(self.agents)

    @property
    def T(self) -> int:
        """Number of hourly periods."""

        return self.W.shape[1]

    @property
    def nameplates(self) -> NDArray[np.float64]:
        """Agent nameplate capacities as a vector."""

        return np.asarray([agent.nameplate for agent in self.agents], dtype=float)

    @classmethod
    def from_arrays(
        cls,
        W: ArrayLike,
        *,
        What: ArrayLike | None = None,
        b: ArrayLike | None = None,
        pi_DA: ArrayLike | None = None,
        pi_RT: ArrayLike | None = None,
        agents: Sequence[Agent] | None = None,
        nameplates: ArrayLike | None = None,
        agent_names: Sequence[str] | None = None,
        K: float | None = None,
        D: ArrayLike | None = None,
        cfg: Mapping[str, Any] | None = None,
        day: Any = "synthetic",
    ) -> "Episode":
        """Build a validated synthetic episode, deriving omitted designed inputs."""

        wind = np.asarray(W, dtype=float)
        if wind.ndim != 2:
            raise ValueError("W must be a two-dimensional (N, T) array")
        if np.any(~np.isfinite(wind)) or np.any(wind < 0):
            raise ValueError("W must be complete, finite, and non-negative")
        n_agents, horizon = wind.shape
        config = _merge(_minimal_config(), cfg)
        if agents is None:
            if nameplates is None:
                plates = np.maximum(np.max(wind, axis=1), 1.0)
            else:
                plates = np.asarray(nameplates, dtype=float)
                if plates.shape != (n_agents,):
                    raise ValueError("nameplates must have length N")
            names = list(agent_names or [f"agent_{i}" for i in range(n_agents)])
            if len(names) != n_agents:
                raise ValueError("agent_names must have length N")
            agents = [_make_agent(name, plate, config) for name, plate in zip(names, plates, strict=True)]
        else:
            agents = list(agents)
            if len(agents) != n_agents:
                raise ValueError("agents must have the same first dimension as W")
            plates = np.asarray([agent.nameplate for agent in agents], dtype=float)
        forecast = wind.copy() if What is None else np.asarray(What, dtype=float)
        baseline = forecast.copy() if b is None else np.asarray(b, dtype=float)
        da = np.zeros(horizon) if pi_DA is None else np.asarray(pi_DA, dtype=float)
        rt = da.copy() if pi_RT is None else np.asarray(pi_RT, dtype=float)
        capacity = float(config["poi"]["kappa_K"] * plates.sum()) if K is None else float(K)
        delivery = (
            float(config["poi"]["delta_D"]) * np.asarray(baseline, dtype=float).sum(axis=0)
            if D is None
            else np.asarray(D, dtype=float)
        )
        return cls(
            agents=list(agents),
            W=wind,
            What=forecast,
            b=baseline,
            pi_DA=da,
            pi_RT=rt,
            K=capacity,
            D=delivery,
            cfg=config,
            day=day,
        )


def _minimal_config() -> dict[str, Any]:
    return {
        "paths": {"processed": "data/processed"},
        "data": {"tz": "US/Central"},
        "battery": {
            "p_ratio": 0.25,
            "duration_h": 2.0,
            "eta_c": 0.922,
            "eta_d": 0.922,
            "c_deg_usd_per_mwh": 10.0,
            "eps_tiebreak_usd_per_mwh": 1e-3,
            "soc_init_frac": 0.5,
            "terminal_soc": "return",
            "allow_grid_charging": True,
        },
        "poi": {
            "kappa_K": 0.7,
            "delta_D": 0.5,
            "lambda_minus": 250.0,
            "lambda_plus": 100.0,
        },
        "game": {
            "max_sweeps": 200,
            "tol_rel": 1e-5,
            "damping": 0.5,
            "deviation_check": True,
            "injection_shortfall": "own",
        },
        "solver": "HIGHS",
    }


def _make_agent(name: str, nameplate: float, cfg: Mapping[str, Any]) -> Agent:
    battery_cfg = cfg["battery"]
    power = float(battery_cfg["p_ratio"]) * float(nameplate)
    energy = float(battery_cfg["duration_h"]) * power
    battery = Battery(
        E=energy,
        P=power,
        eta_c=float(battery_cfg["eta_c"]),
        eta_d=float(battery_cfg["eta_d"]),
        c_deg=float(battery_cfg["c_deg_usd_per_mwh"]),
        soc0=float(battery_cfg["soc_init_frac"]) * energy,
    )
    return Agent(name=str(name), nameplate=float(nameplate), battery=battery)


def load_processed(cfg: Mapping[str, Any]) -> dict[str, pd.DataFrame]:
    """Read the four processed input tables documented in DESIGN.md section 2."""

    root = Path(cfg.get("paths", {}).get("processed", "data/processed"))
    files = {
        "prices": root / "prices_hourly.parquet",
        "wind": root / "wind_hourly.parquet",
        "forecast": root / "forecast_hourly.parquet",
        "resources": root / "resources.csv",
    }
    missing = [str(path) for path in files.values() if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing processed input file(s): " + ", ".join(missing))
    return {
        "prices": pd.read_parquet(files["prices"]),
        "wind": pd.read_parquet(files["wind"]),
        "forecast": pd.read_parquet(files["forecast"]),
        "resources": pd.read_csv(files["resources"]),
    }


def _time_column(frame: pd.DataFrame) -> pd.Series:
    if "Interval Start" in frame.columns:
        return pd.to_datetime(frame["Interval Start"])
    if isinstance(frame.index, pd.DatetimeIndex):
        return pd.Series(frame.index, index=frame.index)
    raise ValueError("Processed table lacks an 'Interval Start' datetime column/index")


def _select_day(frame: pd.DataFrame, day: Any, tz: str) -> pd.DataFrame:
    result = frame.copy()
    times = _time_column(result)
    if getattr(times.dt, "tz", None) is None:
        times = times.dt.tz_localize(tz)
    else:
        times = times.dt.tz_convert(tz)
    target = pd.Timestamp(day)
    if target.tzinfo is None:
        target = target.tz_localize(tz)
    else:
        target = target.tz_convert(tz)
    mask = times.dt.date == target.date()
    result = result.loc[np.asarray(mask)].copy()
    result["_time"] = np.asarray(times.loc[mask])
    return result.sort_values("_time")


def build_episode(
    day: Any,
    agent_names: Sequence[str],
    cfg: Mapping[str, Any],
    overrides: Mapping[str, Any] | None = None,
) -> Episode:
    """Build one complete-day episode from the documented processed tables."""

    config = _merge(dict(cfg), overrides)
    tables = load_processed(config)
    tz = str(config.get("data", {}).get("tz", "US/Central"))
    names = list(agent_names)
    if not names:
        raise ValueError("agent_names cannot be empty")
    wind = _select_day(tables["wind"], day, tz)
    forecast = _select_day(tables["forecast"], day, tz)
    prices = _select_day(tables["prices"], day, tz)
    horizon = int(config.get("episode", {}).get("horizon_h", 24))

    price_cols = ["_time", "pi_DA", "pi_RT"]
    if any(column not in prices for column in price_cols):
        raise ValueError("prices_hourly.parquet must contain pi_DA and pi_RT")
    prices = prices.drop_duplicates("_time").set_index("_time").sort_index()
    if len(prices) != horizon or prices[["pi_DA", "pi_RT"]].isna().any().any():
        raise ValueError(f"Price data for {day} is not a complete {horizon}-hour day")
    hours = prices.index

    wind = wind[wind["resource"].isin(names)]
    wind_pivot = wind.pivot_table(index="resource", columns="_time", values="W_avail", aggfunc="mean")
    wind_pivot = wind_pivot.reindex(index=names, columns=hours)
    missing_wind = wind_pivot.isna()
    if missing_wind.any().any():
        missing_agents = wind_pivot.index[missing_wind.any(axis=1)].tolist()
        raise ValueError(
            f"Incomplete W for {day}; selected agents with missing hours: {missing_agents}"
        )

    forecast = forecast[forecast["resource"].isin(names)]
    required = {"What_cop", "b_baseline"}
    if not required.issubset(forecast.columns):
        raise ValueError("forecast_hourly.parquet must contain What_cop and b_baseline")
    what_pivot = forecast.pivot_table(
        index="resource", columns="_time", values="What_cop", aggfunc="mean"
    ).reindex(index=names, columns=hours)
    b_pivot = forecast.pivot_table(
        index="resource", columns="_time", values="b_baseline", aggfunc="mean"
    ).reindex(index=names, columns=hours)
    if what_pivot.isna().any().any() or b_pivot.isna().any().any():
        raise ValueError(f"Incomplete forecast/baseline data for selected agents on {day}")

    resources = tables["resources"].set_index("resource")
    absent = [name for name in names if name not in resources.index]
    if absent:
        raise ValueError(f"Missing resources.csv metadata for: {absent}")
    agents = [_make_agent(name, float(resources.loc[name, "nameplate_mw"]), config) for name in names]
    plates = np.asarray([agent.nameplate for agent in agents])
    baseline = b_pivot.to_numpy(dtype=float)
    return Episode(
        agents=agents,
        W=wind_pivot.to_numpy(dtype=float),
        What=what_pivot.to_numpy(dtype=float),
        b=baseline,
        pi_DA=prices["pi_DA"].to_numpy(dtype=float),
        pi_RT=prices["pi_RT"].to_numpy(dtype=float),
        K=float(config["poi"]["kappa_K"]) * float(plates.sum()),
        D=float(config["poi"]["delta_D"]) * baseline.sum(axis=0),
        cfg=config,
        day=pd.Timestamp(day).date(),
    )

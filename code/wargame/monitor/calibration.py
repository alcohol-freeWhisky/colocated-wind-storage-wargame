"""Calibration of monitoring-noise regimes from wind forecast errors."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Mapping

import numpy as np
import pandas as pd
from scipy import stats

LOGGER = logging.getLogger(__name__)

SYSTEM_COLUMNS = {
    "publish_time",
    "interval_start",
    "horizon_h",
    "region",
    "gen",
    "stwpf",
    "wgrpp",
    "hsl",
    "err_stwpf_norm",
    "err_wgrpp_norm",
}
RESOURCE_COLUMNS = {
    "Interval Start",
    "resource",
    "What_cop",
    "W_avail",
    "err_norm",
}


def _require_columns(frame: pd.DataFrame, required: set[str], name: str) -> None:
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"{name} is missing required columns: {', '.join(missing)}")


def load_error_samples(processed_dir: str | Path) -> dict[str, pd.DataFrame]:
    """Load and validate the system- and resource-level forecast-error tables."""
    processed_dir = Path(processed_dir)
    system_path = processed_dir / "forecast_error_system.parquet"
    resource_path = processed_dir / "forecast_error_resource.parquet"
    missing = [path for path in (system_path, resource_path) if not path.is_file()]
    if missing:
        names = ", ".join(str(path) for path in missing)
        raise FileNotFoundError(f"Required monitor calibration data not found: {names}")

    system = pd.read_parquet(system_path)
    resource = pd.read_parquet(resource_path)
    _require_columns(system, SYSTEM_COLUMNS, system_path.name)
    _require_columns(resource, RESOURCE_COLUMNS, resource_path.name)
    return {"system": system, "resource": resource}


def synthetic_error_samples(seed: int = 6974) -> dict[str, pd.DataFrame]:
    """Generate schema-compatible, heteroskedastic errors for offline tests."""
    rng = np.random.default_rng(seed)

    n_system = 3_600
    horizon = rng.integers(1, 49, size=n_system)
    system_scale = 0.025 + 0.0018 * horizon
    system_error = stats.t.rvs(
        df=7.0, loc=0.004, scale=system_scale, size=n_system, random_state=rng
    )
    wgrpp_error = system_error + rng.normal(0.0, 0.018, n_system)
    hsl = rng.uniform(18_000.0, 25_000.0, n_system)
    gen = rng.uniform(0.15, 0.85, n_system) * hsl
    publish_time = pd.Timestamp("2025-03-01", tz="US/Central") + pd.to_timedelta(
        np.arange(n_system), unit="h"
    )
    interval_start = publish_time + pd.to_timedelta(horizon, unit="h")
    system = pd.DataFrame(
        {
            "publish_time": publish_time,
            "interval_start": interval_start,
            "horizon_h": horizon.astype(float),
            "region": "SYSTEM_WIDE",
            "gen": gen,
            "stwpf": gen + system_error * hsl,
            "wgrpp": gen + wgrpp_error * hsl,
            "hsl": hsl,
            "err_stwpf_norm": system_error,
            "err_wgrpp_norm": wgrpp_error,
        }
    )

    n_resource = 2_400
    resource_names = np.array([f"SYNTH_WIND_{idx}" for idx in range(1, 6)])
    resource = rng.choice(resource_names, size=n_resource)
    nameplate = rng.uniform(80.0, 180.0, n_resource)
    # The processed resource schema stores actual minus forecast.  Occasional
    # weather ramps make this distribution heavier-tailed than the short-horizon
    # system forecast error.
    actual_minus_forecast = stats.t.rvs(
        df=5.0, loc=-0.006, scale=0.065, size=n_resource, random_state=rng
    )
    forecast = rng.uniform(0.2, 0.85, n_resource) * nameplate
    available = forecast + actual_minus_forecast * nameplate
    resource_frame = pd.DataFrame(
        {
            "Interval Start": pd.date_range(
                "2025-03-01", periods=n_resource, freq="h", tz="US/Central"
            ),
            "resource": resource,
            "What_cop": forecast,
            "W_avail": available,
            "err_norm": actual_minus_forecast,
        }
    )
    return {"system": system, "resource": resource_frame}


def _finite_sample(values: pd.Series | np.ndarray) -> np.ndarray:
    sample = np.asarray(values, dtype=float).reshape(-1)
    return sample[np.isfinite(sample)]


def _regime_summary(regime: str, source: str, sample: np.ndarray) -> dict[str, object]:
    if sample.size < 3:
        raise ValueError(f"Regime {regime!r} needs at least three finite observations")

    sigma = float(np.std(sample, ddof=1))
    median = float(np.median(sample))
    robust_sigma = float(1.4826 * np.median(np.abs(sample - median)))
    gaussian_loc, gaussian_scale = stats.norm.fit(sample)
    if sigma > 0.0:
        t_df, t_loc, t_scale = stats.t.fit(sample)
        skew = float(stats.skew(sample, bias=False))
        kurtosis = float(stats.kurtosis(sample, fisher=True, bias=False))
    else:
        t_df, t_loc, t_scale = np.inf, median, 0.0
        skew = 0.0
        kurtosis = 0.0

    quantiles = np.quantile(sample, [0.01, 0.05, 0.25, 0.50, 0.75, 0.95, 0.99])
    return {
        "regime": regime,
        "sample_source": source,
        "n": int(sample.size),
        "mean": float(np.mean(sample)),
        "sigma": sigma,
        "robust_sigma": robust_sigma,
        "skew": skew,
        "kurtosis": kurtosis,
        "q01": float(quantiles[0]),
        "q05": float(quantiles[1]),
        "q25": float(quantiles[2]),
        "q50": float(quantiles[3]),
        "q75": float(quantiles[4]),
        "q95": float(quantiles[5]),
        "q99": float(quantiles[6]),
        "gaussian_loc": float(gaussian_loc),
        "gaussian_scale": float(gaussian_scale),
        "student_t_df": float(t_df),
        "student_t_loc": float(t_loc),
        "student_t_scale": float(t_scale),
        "eps_sample": sample.copy(),
    }


def define_regimes(
    samples: Mapping[str, pd.DataFrame], cfg: Mapping[str, object]
) -> pd.DataFrame:
    """Define the low, medium, and high monitoring-noise regimes.

    All returned samples use the monitor convention that positive error means a
    delivery shortfall.  Thus resource ``err_norm`` is negated because the
    processed-data contract stores it as actual minus COP forecast.
    """
    try:
        system = samples["system"]
        resource = samples["resource"]
    except KeyError as exc:
        raise KeyError("samples must contain 'system' and 'resource' tables") from exc
    _require_columns(system, SYSTEM_COLUMNS, "system samples")
    _require_columns(resource, RESOURCE_COLUMNS, "resource samples")

    monitor_cfg = cfg.get("monitor", {})
    if not isinstance(monitor_cfg, Mapping):
        raise TypeError("cfg['monitor'] must be a mapping")
    low_horizon = float(monitor_cfg.get("low_horizon_h", 6.0))
    high_horizon = float(monitor_cfg.get("high_horizon_h", 24.0))
    worst_quantile = float(monitor_cfg.get("high_error_quantile", 0.75))
    if not 0.0 < worst_quantile < 1.0:
        raise ValueError("monitor.high_error_quantile must lie strictly between 0 and 1")

    horizon = pd.to_numeric(system["horizon_h"], errors="coerce")
    system_error = pd.to_numeric(system["err_stwpf_norm"], errors="coerce")
    normalized_region = (
        system["region"].astype(str).str.upper().str.replace(r"[^A-Z]", "", regex=True)
    )
    system_wide = normalized_region.isin({"SYSTEM", "SYSTEMWIDE"})
    if not system_wide.any():
        raise ValueError("system samples contain no system-wide region observations")
    resource_shortfall = -pd.to_numeric(resource["err_norm"], errors="coerce")

    low = _finite_sample(system_error[system_wide & (horizon <= low_horizon)])
    medium = _finite_sample(resource_shortfall)
    cutoff = float(np.quantile(np.abs(medium), worst_quantile))
    resource_worst = medium[np.abs(medium) >= cutoff]
    system_long = _finite_sample(system_error[system_wide & (horizon >= high_horizon)])
    high = np.concatenate((resource_worst, system_long))

    rows = [
        _regime_summary("low", f"system STWPF, horizon <= {low_horizon:g} h", low),
        _regime_summary("medium", "resource COP, all hours", medium),
        _regime_summary(
            "high",
            (
                f"resource COP |error| >= q{worst_quantile:g} "
                f"or system STWPF horizon >= {high_horizon:g} h"
            ),
            high,
        ),
    ]
    regimes = pd.DataFrame(rows)
    observed_order = regimes.set_index("regime")["sigma"]
    if not (observed_order["low"] <= observed_order["medium"] <= observed_order["high"]):
        LOGGER.warning(
            "Empirical regime standard deviations are not ordered low <= medium <= high: %s",
            observed_order.to_dict(),
        )
    return regimes

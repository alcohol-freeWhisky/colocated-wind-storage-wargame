"""Detection probabilities and deterrence calculations for the monitor."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import pandas as pd
from scipy import stats


def _error_sample(eps_sample: Sequence[float] | np.ndarray) -> np.ndarray:
    sample = np.asarray(eps_sample, dtype=float).reshape(-1)
    sample = sample[np.isfinite(sample)]
    if sample.size == 0:
        raise ValueError("eps_sample must contain at least one finite observation")
    return sample


def q0(tau: float, eps_sample: Sequence[float] | np.ndarray) -> float:
    """Empirical false-positive probability ``P(eps > tau)``."""
    sample = _error_sample(eps_sample)
    return float(np.mean(sample > tau))


def q1(tau: float, m: float, eps_sample: Sequence[float] | np.ndarray) -> float:
    """Empirical detection probability ``P(m + eps > tau)``."""
    sample = _error_sample(eps_sample)
    return float(np.mean(m + sample > tau))


def q0_gaussian(tau: float, sigma: float, mu: float = 0.0) -> float:
    """Gaussian false-positive probability in closed form."""
    if sigma <= 0.0:
        raise ValueError("sigma must be positive")
    return float(stats.norm.sf(tau, loc=mu, scale=sigma))


def q1_gaussian(tau: float, m: float, sigma: float, mu: float = 0.0) -> float:
    """Gaussian detection probability in closed form."""
    if sigma <= 0.0:
        raise ValueError("sigma must be positive")
    return float(stats.norm.sf(tau - m, loc=mu, scale=sigma))


# Readable aliases for callers that prefer the distribution name first.
gaussian_q0 = q0_gaussian
gaussian_q1 = q1_gaussian


def roc_curve(
    eps_sample: Sequence[float] | np.ndarray,
    m: float,
    taus: Sequence[float] | np.ndarray,
) -> pd.DataFrame:
    """Return empirical and fitted-Gaussian ROC points over thresholds."""
    sample = _error_sample(eps_sample)
    mu = float(np.mean(sample))
    sigma = float(np.std(sample, ddof=1)) if sample.size > 1 else 0.0
    rows: list[dict[str, float]] = []
    for tau in np.asarray(taus, dtype=float).reshape(-1):
        false_positive = q0(float(tau), sample)
        detection = q1(float(tau), m, sample)
        row = {
            "tau": float(tau),
            "q0": false_positive,
            "q1": detection,
            "delta_q": detection - false_positive,
        }
        if sigma > 0.0:
            gaussian_false_positive = q0_gaussian(float(tau), sigma, mu)
            gaussian_detection = q1_gaussian(float(tau), m, sigma, mu)
        else:
            gaussian_false_positive = float(mu > tau)
            gaussian_detection = float(m + mu > tau)
        row.update(
            {
                "q0_gaussian": gaussian_false_positive,
                "q1_gaussian": gaussian_detection,
                "delta_q_gaussian": gaussian_detection - gaussian_false_positive,
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def F_star(g: float, delta: float, d: int, q1: float, q0: float) -> float:
    """Minimum fine implied by one-shot incentive compatibility."""
    if g < 0.0:
        raise ValueError("g must be non-negative")
    if not 0.0 < delta <= 1.0:
        raise ValueError("delta must lie in (0, 1]")
    if d < 0:
        raise ValueError("d must be non-negative")
    if g == 0.0:
        return 0.0
    delta_q = q1 - q0
    if delta_q <= 0.0:
        return float(np.inf)
    return float(g * (delta ** (-d) - q1) / delta_q)


def T_star(
    g: float,
    delta: float,
    d: int,
    q1: float,
    q0: float,
    ell: float,
    T_max: int = 10_000,
) -> int | float:
    """Return the shortest positive correction window satisfying deterrence."""
    if g < 0.0 or ell < 0.0:
        raise ValueError("g and ell must be non-negative")
    if not 0.0 < delta <= 1.0:
        raise ValueError("delta must lie in (0, 1]")
    if d < 0 or T_max < 1:
        raise ValueError("d must be non-negative and T_max must be positive")

    delta_q = q1 - q0
    discounted_sum = 0.0
    discount = 1.0
    for duration in range(1, T_max + 1):
        discounted_sum += discount
        deterrence_value = delta**d * (q1 * g + delta_q * ell * discounted_sum)
        if g <= deterrence_value:
            return duration
        discount *= delta
    return float(np.inf)


def enforceability(sigma: float | np.ndarray, a: float) -> float | np.ndarray:
    """Return the evidentiary enforceability factor ``exp(-a * sigma)``."""
    if a < 0.0 or np.any(np.asarray(sigma) < 0.0):
        raise ValueError("sigma and a must be non-negative")
    value = np.exp(-a * np.asarray(sigma, dtype=float))
    return float(value) if value.ndim == 0 else value


def effective_fine(F: float | np.ndarray, kappa: float | np.ndarray) -> float | np.ndarray:
    """Apply enforceability ``kappa`` to a nominal fine ``F``."""
    value = np.asarray(kappa, dtype=float) * np.asarray(F, dtype=float)
    return float(value) if value.ndim == 0 else value


def _monitor_config(cfg: Mapping[str, object]) -> Mapping[str, object]:
    monitor_cfg = cfg.get("monitor", cfg)
    if not isinstance(monitor_cfg, Mapping):
        raise TypeError("monitor configuration must be a mapping")
    return monitor_cfg


def _as_float_list(value: object, name: str) -> list[float]:
    if isinstance(value, (str, bytes)):
        raise TypeError(f"{name} must be numeric or a numeric sequence")
    if np.isscalar(value):
        return [float(value)]
    return [float(item) for item in value]  # type: ignore[union-attr]


def deterrence_grid(
    cfg: Mapping[str, object], regimes: pd.DataFrame
) -> pd.DataFrame:
    """Evaluate deterrence at fixed physical thresholds and withholding levels."""
    required = {"regime", "sigma", "eps_sample"}
    missing = sorted(required.difference(regimes.columns))
    if missing:
        raise ValueError(f"regimes is missing required columns: {', '.join(missing)}")

    monitor_cfg = _monitor_config(cfg)
    thresholds_frac = _as_float_list(
        monitor_cfg.get("thresholds_frac", [0.02, 0.05, 0.10, 0.15]),
        "thresholds_frac",
    )
    withholding_frac = _as_float_list(
        monitor_cfg.get("withholding_grid_frac", [0.02, 0.05, 0.10, 0.20]),
        "withholding_grid_frac",
    )
    deltas = _as_float_list(monitor_cfg.get("delta", 0.98), "delta")
    delays = [
        int(value)
        for value in _as_float_list(
            monitor_cfg.get("delay_grid", [1, 4, 12]), "delay_grid"
        )
    ]
    cap_multiple = float(monitor_cfg.get("fine_cap_multiple_of_gain", 3.0))
    ell_fraction = float(monitor_cfg.get("ell_fraction_of_gain", 0.25))
    enforceability_a = float(monitor_cfg.get("enforceability_a", 2.0))
    gain = 1.0
    ell = ell_fraction * gain

    rows: list[dict[str, object]] = []
    for regime_row in regimes.itertuples(index=False):
        regime = str(regime_row.regime)
        sigma = float(regime_row.sigma)
        if sigma <= 0.0:
            raise ValueError(f"Regime {regime!r} has non-positive sigma")
        sample = _error_sample(regime_row.eps_sample)
        kappa = float(enforceability(sigma, enforceability_a))
        for tau_frac in thresholds_frac:
            for m_frac in withholding_frac:
                false_positive = q0(tau_frac, sample)
                detection = q1(tau_frac, m_frac, sample)
                delta_q = detection - false_positive
                for delta in deltas:
                    for delay in delays:
                        fine = F_star(gain, delta, delay, detection, false_positive)
                        effective = float(effective_fine(fine, kappa))
                        duration = T_star(
                            gain,
                            delta,
                            delay,
                            detection,
                            false_positive,
                            ell,
                        )
                        rows.append(
                            {
                                "regime": regime,
                                "sigma": sigma,
                                "tau_frac": tau_frac,
                                "m_frac": m_frac,
                                "delta": delta,
                                "d": delay,
                                "q0": false_positive,
                                "q1": detection,
                                "delta_q": delta_q,
                                "F_star_over_g": fine / gain,
                                "kappa": kappa,
                                "F_star_kappa_over_g": effective / gain,
                                "feasible": bool(
                                    np.isfinite(fine) and fine <= cap_multiple * gain
                                ),
                                "T_star": duration,
                            }
                        )
    return pd.DataFrame(rows)

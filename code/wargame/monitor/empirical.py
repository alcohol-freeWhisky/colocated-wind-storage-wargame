"""Array-based empirical checks using solved operating trajectories."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np


def _trajectory_arrays(
    b: np.ndarray, q: np.ndarray, prices: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    baselines = np.asarray(b, dtype=float)
    injections = np.asarray(q, dtype=float)
    price_vector = np.asarray(prices, dtype=float).reshape(-1)
    if baselines.ndim != 2 or injections.ndim != 2:
        raise ValueError("b and q must be two-dimensional N x T arrays")
    if baselines.shape != injections.shape:
        raise ValueError("b and q must have the same shape")
    if baselines.shape[0] < 1 or baselines.shape[1] != price_vector.size:
        raise ValueError("prices must have one entry for every time period")
    return baselines, injections, price_vector


def inject_withholding(
    q_plan: np.ndarray,
    prices: np.ndarray,
    m_mw: float,
    top_quantile: float = 0.75,
) -> np.ndarray:
    """Reduce agent 1's injection in hours at or above a price quantile."""
    q = np.asarray(q_plan, dtype=float)
    price_vector = np.asarray(prices, dtype=float).reshape(-1)
    if q.ndim != 2 or q.shape[0] < 1:
        raise ValueError("q_plan must be a non-empty N x T array")
    if q.shape[1] != price_vector.size:
        raise ValueError("prices must have one entry for every time period")
    if m_mw < 0.0:
        raise ValueError("m_mw must be non-negative")
    if not 0.0 <= top_quantile <= 1.0:
        raise ValueError("top_quantile must lie in [0, 1]")

    attacked = q.copy()
    finite_prices = price_vector[np.isfinite(price_vector)]
    if finite_prices.size == 0:
        raise ValueError("prices must contain at least one finite value")
    cutoff = float(np.quantile(finite_prices, top_quantile))
    attacked[0, np.isfinite(price_vector) & (price_vector >= cutoff)] -= m_mw
    return attacked


def shortfall_signal(
    b: np.ndarray,
    q: np.ndarray,
    eps_sample: Sequence[float] | np.ndarray,
    rng: np.random.Generator,
) -> np.ndarray:
    """Return ``z = b - q + eps`` using iid empirical-noise draws."""
    baselines = np.asarray(b, dtype=float)
    injections = np.asarray(q, dtype=float)
    if baselines.shape != injections.shape or baselines.ndim != 2:
        raise ValueError("b and q must be same-shaped N x T arrays")
    errors = np.asarray(eps_sample, dtype=float).reshape(-1)
    errors = errors[np.isfinite(errors)]
    if errors.size == 0:
        raise ValueError("eps_sample must contain at least one finite observation")
    noise = rng.choice(errors, size=baselines.shape, replace=True)
    return baselines - injections + noise


def detection_rates(
    b: np.ndarray,
    q: np.ndarray,
    prices: np.ndarray,
    m_mw: float,
    tau: float,
    eps_sample: Sequence[float] | np.ndarray,
    rng: np.random.Generator,
    top_quantile: float = 0.75,
) -> dict[str, float | int]:
    """Compare sanction rates for injected agent 1 and untouched agents.

    Rates are evaluated only in the high-price hours in which withholding is
    injected.  The non-injected rate is ``NaN`` for a one-agent trajectory.
    """
    baselines, injections, price_vector = _trajectory_arrays(b, q, prices)
    attacked = inject_withholding(injections, price_vector, m_mw, top_quantile)
    signals = shortfall_signal(baselines, attacked, eps_sample, rng)
    cutoff = float(np.quantile(price_vector[np.isfinite(price_vector)], top_quantile))
    attacked_hours = np.isfinite(price_vector) & (price_vector >= cutoff)
    injected_flags = signals[0, attacked_hours] > tau
    other_flags = signals[1:, attacked_hours] > tau
    return {
        "injected_agent_rate": float(np.mean(injected_flags)),
        "non_injected_agents_rate": (
            float(np.mean(other_flags)) if other_flags.size else float("nan")
        ),
        "n_injected_observations": int(injected_flags.size),
        "n_non_injected_observations": int(other_flags.size),
        "n_attack_hours": int(np.sum(attacked_hours)),
    }


compute_detection_rates = detection_rates

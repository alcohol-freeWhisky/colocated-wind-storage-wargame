"""Closed-form and smoke tests for monitor calibration and detection."""

from __future__ import annotations

import numpy as np
from scipy import stats

from wargame.monitor.calibration import define_regimes, synthetic_error_samples
from wargame.monitor.detection import (
    F_star,
    T_star,
    deterrence_grid,
    q0_gaussian,
    q1_gaussian,
)
from wargame.monitor.empirical import inject_withholding


def test_gaussian_detection_closed_forms() -> None:
    sigma = 0.12
    tau = 0.18
    m = 0.07
    assert q0_gaussian(tau, sigma) == stats.norm.sf(tau / sigma)
    assert q1_gaussian(tau, m, sigma) == stats.norm.sf((tau - m) / sigma)


def test_f_star_hand_computed_case() -> None:
    expected = 10.0 * (0.9**-2 - 0.8) / (0.8 - 0.2)
    assert np.isclose(F_star(10.0, 0.9, 2, 0.8, 0.2), expected)


def test_t_star_is_one_when_one_period_suffices() -> None:
    assert T_star(g=1.0, delta=1.0, d=0, q1=0.9, q0=0.1, ell=0.2) == 1


def test_t_star_weakly_increases_with_gaussian_noise() -> None:
    durations = []
    for sigma in (0.05, 0.10, 0.20):
        false_positive = q0_gaussian(tau=0.1, sigma=sigma)
        detection = q1_gaussian(tau=0.1, m=0.1, sigma=sigma)
        durations.append(
            T_star(
                g=1.0,
                delta=0.98,
                d=1,
                q1=detection,
                q0=false_positive,
                ell=0.25,
            )
        )
    assert durations == sorted(durations)


def test_deterrence_grid_runs_on_synthetic_samples() -> None:
    cfg = {
        "monitor": {
            "thresholds_sigma": [1.0, 2.0],
            "thresholds_frac": [0.05, 0.10],
            "withholding_grid_frac": [0.05, 0.10],
            "delta": 0.98,
            "delay_grid": [1, 4],
            "fine_cap_multiple_of_gain": 3.0,
            "ell_fraction_of_gain": 0.25,
            "enforceability_a": 2.0,
        }
    }
    regimes = define_regimes(synthetic_error_samples(seed=17), cfg)
    grid = deterrence_grid(cfg, regimes)

    assert len(grid) == 3 * 2 * 2 * 1 * 2
    assert set(grid["regime"]) == {"low", "medium", "high"}
    assert list(grid.columns) == [
        "regime",
        "sigma",
        "tau_frac",
        "m_frac",
        "delta",
        "d",
        "q0",
        "q1",
        "delta_q",
        "F_star_over_g",
        "kappa",
        "F_star_kappa_over_g",
        "feasible",
        "T_star",
    ]
    assert set(grid["tau_frac"]) == {0.05, 0.10}
    assert set(grid["m_frac"]) == {0.05, 0.10}
    assert (grid["q1"] >= grid["q0"]).all()
    assert grid["feasible"].dtype == bool


def test_inject_withholding_changes_only_agent_one_high_price_hours() -> None:
    q = np.full((3, 4), 10.0)
    prices = np.array([1.0, 2.0, 3.0, 4.0])
    attacked = inject_withholding(q, prices, m_mw=2.0, top_quantile=0.75)

    np.testing.assert_array_equal(attacked[0], [10.0, 10.0, 10.0, 8.0])
    np.testing.assert_array_equal(attacked[1:], q[1:])
    np.testing.assert_array_equal(q, np.full((3, 4), 10.0))

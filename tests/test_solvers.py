"""Planner, owner-game, and receding-horizon solver tests."""

from __future__ import annotations

import itertools

import numpy as np

from wargame.model.env import Episode
from wargame.model.physics import Agent, Battery
from wargame.solvers.central import CentralLP, solve_central
from wargame.solvers.design_matrix import solve_cell
from wargame.solvers.game import solve_game
from wargame.solvers.receding import (
    forecast_subhorizon,
    reachable_terminal_soc,
    solve_receding_central,
)
from wargame.solvers.realize import realize


def _config() -> dict:
    return {
        "battery": {
            "terminal_soc": "return",
            "allow_grid_charging": False,
            "eps_tiebreak_usd_per_mwh": 1e-3,
        },
        "poi": {"lambda_plus": 100.0},
        "game": {
            "max_sweeps": 100, "tol_rel": 1e-6,
            "max_gain_tol": 1.0, "damping": 0.5, "deviation_check": True,
        },
        "design_matrix": {"game_warm_start": True},
        "solver": "HIGHS",
    }


def test_central_matches_tiny_wind_charging_brute_force() -> None:
    battery = Battery(E=1, P=1, eta_c=1, eta_d=1, c_deg=0, soc0=0)
    agent = Agent("a", 1, battery)
    cfg = _config()
    cfg["battery"]["terminal_soc"] = "free"
    episode = Episode.from_arrays(
        [[1.0, 0.0]], agents=[agent], pi_DA=[0, 10], pi_RT=[0, 10], K=2, cfg=cfg,
    )
    solution = solve_central(episode, cfg)
    best = -np.inf
    for c0, c1, d0, d1 in itertools.product([0.0, 1.0], repeat=4):
        if c0 > 1.0 or c1 > 0.0:
            continue
        soc1, soc2 = c0 - d0, c0 - d0 + c1 - d1
        if 0 <= soc1 <= 1 and 0 <= soc2 <= 1:
            q = np.array([1 - c0 + d0, -c1 + d1])
            best = max(best, float(np.array([0, 10]) @ q))
    assert solution.objective == best == 10.0
    np.testing.assert_allclose(solution.q, [[0.0, 1.0]], atol=1e-7)


def test_central_model_is_dpp_and_reusable() -> None:
    episode = Episode.from_arrays(
        np.ones((2, 6)), nameplates=[2, 2], pi_DA=np.ones(6),
        pi_RT=np.arange(6), K=3, cfg=_config(),
    )
    model = CentralLP(episode)
    assert model.problem.is_dpp()
    assert model.solve().status.startswith("optimal")
    assert model.solve(pi=np.arange(6)[::-1]).status.startswith("optimal")


def test_full_game_passes_unilateral_deviation_check() -> None:
    agents = [Agent(f"a{i}", 4, Battery(0, 0, 1, 1, 0, 0)) for i in range(2)]
    episode = Episode.from_arrays(
        np.full((2, 6), 3.0), agents=agents,
        pi_DA=np.full(6, 20.0), pi_RT=np.full(6, 20.0),
        K=4.0, cfg=_config(),
    )
    solution = solve_game(episode, _config(), share_rule="equal", information="full")
    assert solution.converged
    assert solution.max_gain <= 1.0


def test_forecast_view_uses_current_truth_and_future_forecast() -> None:
    W = np.array([[1.0, 8.0], [2.0, 9.0]])
    What = np.array([[7.0, 3.0], [6.0, 4.0]])
    episode = Episode.from_arrays(
        W, What=What, pi_DA=[11.0, 12.0], pi_RT=[50.0, 60.0],
        nameplates=[10.0, 10.0], K=20.0, cfg=_config(),
    )
    view = forecast_subhorizon(episode, 0)
    np.testing.assert_allclose(view.W[:, 0], W[:, 0])
    np.testing.assert_allclose(view.W[:, 1], What[:, 1])
    np.testing.assert_allclose(view.pi_RT, [50.0, 12.0])
    result = solve_receding_central(episode, foresight="forecast")
    np.testing.assert_allclose(
        result.soc[:, -1], [agent.battery.soc0 for agent in episode.agents], atol=1e-6
    )


def test_wind_only_terminal_target_is_capped_at_reachable_soc() -> None:
    battery = Battery(E=2, P=1, eta_c=0.5, eta_d=1, c_deg=0, soc0=0)
    episode = Episode.from_arrays(
        [[0.2, 0.0]], agents=[Agent("a", 1, battery)],
        pi_DA=[0, 0], pi_RT=[0, 0], K=1, cfg=_config(),
    )
    target = reachable_terminal_soc(
        episode,
        initial_soc=np.array([0.0]),
        requested=np.array([1.0]),
    )
    np.testing.assert_allclose(target, [0.1])


def test_perfect_receding_central_equals_one_shot() -> None:
    rng = np.random.default_rng(6974)
    W = rng.uniform(2, 9, (3, 8))
    episode = Episode.from_arrays(
        W, What=W, pi_DA=np.arange(8), pi_RT=np.arange(8) * 5,
        nameplates=[10, 11, 12], K=20, cfg=_config(),
    )
    one_shot = realize(episode, solve_central(episode, _config()))
    receding = solve_receding_central(episode, _config(), foresight="perfect")
    assert receding.objective == one_shot.objective


def test_representative_cells_have_no_simultaneous_operation() -> None:
    rng = np.random.default_rng(6974)
    W = rng.uniform(2, 9, (3, 8))
    episode = Episode.from_arrays(
        W, What=np.maximum(W - 0.5, 0), pi_DA=np.arange(8),
        pi_RT=np.array([-10, -5, 0, 5, 20, 50, 30, 10]),
        nameplates=[10, 11, 12], K=20, cfg=_config(),
    )
    for cell in ("C_P", "C_F", "D_F_EQ_FULL", "D_F_INJ_NONE", "D_P_INJ_PRICE"):
        result = solve_cell(episode, cell, _config())
        assert not np.any((result.c > 1e-6) & (result.d > 1e-6))
        assert result.q.sum(axis=0).max() <= episode.K + 1e-6

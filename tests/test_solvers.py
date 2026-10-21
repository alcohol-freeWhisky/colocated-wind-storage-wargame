"""LP optimality, Nash, and all-regime smoke tests."""

import itertools
import time

import numpy as np
import pandas as pd

from wargame.experiments.metrics import gaps
from wargame.experiments.run_episode import run_all_regimes
from wargame.model.env import Episode
from wargame.model.physics import Agent, Battery
from wargame.solvers.central import CentralLP, solve_central
from wargame.solvers.game import solve_r2
from wargame.solvers.agent_lp import POIBudget, solve_agent
from wargame.solvers.mpc import solve_r4a
from wargame.solvers.receding import forecast_subhorizon, solve_r1_f, solve_r2_f


def test_central_matches_tiny_discrete_brute_force() -> None:
    battery = Battery(E=1, P=1, eta_c=1, eta_d=1, c_deg=0, soc0=0)
    agent = Agent("a", 1, battery)
    cfg = {
        "battery": {"terminal_soc": "free", "allow_grid_charging": True},
        "poi": {"lambda_minus": 0.0, "lambda_plus": 100.0},
        "solver": "HIGHS",
    }
    episode = Episode.from_arrays(
        np.zeros((1, 2)),
        agents=[agent],
        pi_DA=[0, 10],
        pi_RT=[0, 10],
        K=2,
        D=[0, 0],
        cfg=cfg,
    )
    solution = solve_central(episode)

    best = -np.inf
    grid = [0.0, 1.0]
    for c0, c1, d0, d1 in itertools.product(grid, repeat=4):
        soc1 = c0 - d0
        soc2 = soc1 + c1 - d1
        if 0 <= soc1 <= 1 and 0 <= soc2 <= 1:
            q = np.array([-c0 + d0, -c1 + d1])
            best = max(best, float(np.array([0, 10]) @ q))
    assert solution.objective == best == 10.0
    np.testing.assert_allclose(solution.q, [[-1.0, 1.0]], atol=1e-7)


def test_central_model_is_dpp_and_reusable() -> None:
    episode = Episode.from_arrays(
        np.ones((2, 6)), nameplates=[2, 2], pi_DA=np.ones(6), pi_RT=np.arange(6), K=3
    )
    model = CentralLP(episode)
    assert model.problem.is_dpp()
    first = model.solve()
    second = model.solve(pi=np.arange(6)[::-1])
    assert first.status.startswith("optimal")
    assert second.status.startswith("optimal")


def test_best_response_profile_passes_unilateral_deviation_check() -> None:
    batteries = [Battery(0, 0, 1, 1, 0, 0), Battery(0, 0, 1, 1, 0, 0)]
    agents = [Agent("a", 4, batteries[0]), Agent("b", 4, batteries[1])]
    cfg = {
        "battery": {"terminal_soc": "return", "allow_grid_charging": True},
        "poi": {"lambda_minus": 250.0, "lambda_plus": 100.0},
        "game": {"max_sweeps": 100, "tol_rel": 1e-8, "damping": 0.5, "deviation_check": True},
        "solver": "HIGHS",
    }
    episode = Episode.from_arrays(
        np.full((2, 6), 3.0),
        agents=agents,
        pi_DA=np.full(6, 20.0),
        pi_RT=np.full(6, 20.0),
        K=4.0,
        D=np.zeros(6),
        cfg=cfg,
    )
    solution = solve_r2(episode)
    assert solution.converged
    assert solution.max_gain <= 1e-4


def test_tiebreak_selects_curtailment_over_free_cycling() -> None:
    battery = Battery(E=1, P=1, eta_c=0.9, eta_d=0.9, c_deg=0, soc0=1)
    agent = Agent("a", 1, battery)
    cfg = {
        "battery": {
            "terminal_soc": "return",
            "allow_grid_charging": True,
            "eps_tiebreak_usd_per_mwh": 1e-3,
        },
        "poi": {"lambda_minus": 0.0, "lambda_plus": 0.0},
        "solver": "HIGHS",
    }
    episode = Episode.from_arrays(
        [[1.0]], agents=[agent], pi_DA=[0.0], pi_RT=[0.0], K=0.0, D=[0.0], cfg=cfg
    )

    central = solve_central(episode, cfg)
    private = solve_agent(
        agent,
        W=[1.0],
        prices=[0.0],
        K=0.0,
        D=[0.0],
        cfg=cfg,
        poi_budget=POIBudget(0.0),
    )

    for solution in (central, private):
        np.testing.assert_allclose(solution.c, 0.0, atol=1e-8)
        np.testing.assert_allclose(solution.d, 0.0, atol=1e-8)
        np.testing.assert_allclose(solution.r, 1.0, atol=1e-8)


def test_mpc_price_information_switches_future_view() -> None:
    battery = Battery(E=1, P=1, eta_c=1, eta_d=1, c_deg=0, soc0=0)
    agent = Agent("a", 1, battery)
    base_cfg = {
        "battery": {
            "terminal_soc": "free",
            "allow_grid_charging": True,
            "eps_tiebreak_usd_per_mwh": 1e-3,
        },
        "poi": {"delta_D": 0.0, "lambda_minus": 0.0, "lambda_plus": 0.0},
        "mpc": {"price_info": "perfect", "wind_info": "perfect"},
        "solver": "HIGHS",
    }
    episode = Episode.from_arrays(
        np.zeros((1, 2)),
        What=np.zeros((1, 2)),
        agents=[agent],
        pi_DA=[0.0, 0.0],
        pi_RT=[0.0, 100.0],
        K=2.0,
        D=[0.0, 0.0],
        cfg=base_cfg,
    )
    perfect = solve_r4a(episode, base_cfg)
    forecast_cfg = {**base_cfg, "mpc": {"price_info": "forecast", "wind_info": "forecast"}}
    forecast = solve_r4a(episode, forecast_cfg)

    assert perfect.profit.sum() > 99.0
    assert abs(forecast.profit.sum()) < 1e-8


def test_gaps_include_decomposed_information_gaps() -> None:
    frame = pd.DataFrame(
        {
            "regime": ["R1", "R1_f", "R2", "R2_f", "R4a", "R4a_f", "R4b", "R4b_f"],
            "system_profit": [100.0, 90.0, 80.0, 72.0, 70.0, 50.0, 60.0, 45.0],
        }
    )
    result = gaps(frame).iloc[0]
    assert result.to_dict() == {
        "strategic_gap": 20.0,
        "info_gap_aggregate": 10.0,
        "info_gap_local": 20.0,
        "signal_value": 10.0,
        "forecast_gap_central": 10.0,
        "forecast_gap_game": 8.0,
        "forecast_gap_mpc": 20.0,
        "PoA": 1.25,
        "PoA_f": 1.25,
    }


def test_forecast_receding_regimes_use_realized_current_hour() -> None:
    W = np.array([[1.0, 8.0], [2.0, 9.0]])
    What = np.array([[7.0, 3.0], [6.0, 4.0]])
    episode = Episode.from_arrays(
        W,
        What=What,
        b=What,
        pi_DA=[11.0, 12.0],
        pi_RT=[50.0, 60.0],
        nameplates=[10.0, 10.0],
        K=20.0,
        D=[0.0, 0.0],
    )
    view = forecast_subhorizon(episode, 0)
    np.testing.assert_allclose(view.W[:, 0], W[:, 0])
    np.testing.assert_allclose(view.W[:, 1], What[:, 1])
    np.testing.assert_allclose(view.pi_RT, [50.0, 12.0])
    for result in (solve_r1_f(episode), solve_r2_f(episode)):
        np.testing.assert_allclose(result.soc[:, -1], [agent.battery.soc0 for agent in episode.agents], atol=1e-6)


def test_all_regimes_smoke_under_30_seconds() -> None:
    rng = np.random.default_rng(6974)
    W = rng.uniform(2, 9, (3, 24))
    What = np.maximum(W + rng.normal(0, 0.8, W.shape), 0)
    prices = np.array(
        [12, 10, 8, 5, 3, 2, 6, 15, 28, 40, 32, 25, 20, 18, 16, 22, 38, 65, 80, 58, 42, 30, 22, 16]
    )
    episode = Episode.from_arrays(
        W,
        What=What,
        b=What,
        pi_DA=0.9 * prices,
        pi_RT=prices,
        nameplates=[10, 11, 12],
        K=20,
        D=0.4 * What.sum(axis=0),
    )
    started = time.perf_counter()
    results = run_all_regimes(episode, episode.cfg)
    elapsed = time.perf_counter() - started
    assert list(results) == [
        "R1", "R1_f", "R2", "R2_f", "R3a", "R3b", "R4a", "R4a_f", "R4b", "R4b_f"
    ]
    assert elapsed < 30
    for result in results.values():
        assert result.realization.q.sum(axis=0).max() <= episode.K + 1e-6
        assert result.metrics["simultaneous_charge_discharge_hours"] == 0
    assert len(results["R2_f"].metrics["sweeps_by_hour"]) == 24


def _negative_budget_episode(shortfall: str = "full") -> tuple[Episode, dict]:
    """Two agents; agent 0 grid-charges while agent 1 exports above K."""

    cfg = {
        "battery": {
            "terminal_soc": "free",
            "allow_grid_charging": True,
            "eps_tiebreak_usd_per_mwh": 1e-3,
        },
        "poi": {"delta_D": 0.5, "lambda_minus": 250.0, "lambda_plus": 100.0},
        "mpc": {"price_info": "perfect", "wind_info": "perfect", "private_shortfall_beta": shortfall},
        "solver": "HIGHS",
    }
    batteries = [
        Battery(E=10, P=5, eta_c=1, eta_d=1, c_deg=0, soc0=0),
        Battery(E=1, P=1, eta_c=1, eta_d=1, c_deg=0, soc0=0),
    ]
    agents = [Agent("a0", 10, batteries[0]), Agent("a1", 10, batteries[1])]
    W = np.array([[0.0] * 4, [15.0] * 4])
    b = np.array([[0.0] * 4, [30.0] * 4])
    episode = Episode.from_arrays(
        W,
        What=W,
        b=b,
        agents=agents,
        pi_DA=[0.0, 0.0, 1000.0, 1000.0],
        pi_RT=[0.0, 0.0, 1000.0, 1000.0],
        K=10.0,
        D=[15.0] * 4,
        cfg=cfg,
    )
    return episode, cfg


def test_r4a_negative_poi_budget_is_floored_and_feasible() -> None:
    import wargame.solvers.agent_lp as agent_lp

    episode, cfg = _negative_budget_episode()
    seen: list[float] = []
    original = agent_lp.AgentLP.solve

    def spy(self, **kwargs):  # records the budget handed to the LP
        budget = kwargs.get("poi_budget")
        if budget is not None:
            seen.append(float(np.min(budget.limit)))
        return original(self, **kwargs)

    agent_lp.AgentLP.solve = spy
    try:
        result = solve_r4a(episode, cfg)
    finally:
        agent_lp.AgentLP.solve = original
    assert min(seen) >= -5.0 - 1e-9  # floored at -P_i
    assert result.q.sum(axis=0).max() <= episode.K + 1e-6


def test_mpc_private_shortfall_beta_option() -> None:
    import pytest

    episode, cfg = _negative_budget_episode("game")
    assert solve_r4a(episode, cfg).q.shape == (2, 4)
    bad = {**cfg, "mpc": {**cfg["mpc"], "private_shortfall_beta": "nope"}}
    with pytest.raises(ValueError):
        solve_r4a(episode, bad)


def test_game_objective_excludes_plus_penalty_and_converges_on_undamped_residual() -> None:
    episode, cfg = _negative_budget_episode()
    sol = solve_r2(episode, {**cfg, "game": {"max_sweeps": 200, "tol_rel": 1e-5, "max_gain_tol": 1.0}})
    agg = sol.q.sum(axis=0)
    expected = (
        episode.pi_RT @ agg
        - sum(a.battery.c_deg * sol.d[i].sum() for i, a in enumerate(episode.agents))
        - 250.0 * sol.Vminus.sum()
    )
    assert abs(sol.objective - expected) < 1e-6
    assert sol.objective_with_plus_penalty <= sol.objective + 1e-9
    assert sol.converged == (sol.max_delta < 1e-5 * episode.nameplates.sum() and sol.max_gain <= 1.0)

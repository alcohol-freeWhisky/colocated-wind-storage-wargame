"""LP optimality, Nash, receding-horizon and cell smoke tests."""

import itertools
import time

import numpy as np

from wargame.model.env import Episode
from wargame.model.physics import Agent, Battery
from wargame.solvers.central import CentralLP, solve_central
from wargame.solvers.agent_lp import POIBudget, solve_agent
from wargame.solvers.design_matrix import solve_cell
from wargame.solvers.game import solve_game
from wargame.solvers.realize import realize
from wargame.solvers.receding import forecast_subhorizon, solve_receding_central


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
    solution = solve_game(episode, cfg, share_rule="equal")
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


def test_forecast_receding_central_uses_realized_current_hour() -> None:
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
    result = solve_receding_central(episode, foresight="forecast")
    np.testing.assert_allclose(
        result.soc[:, -1], [agent.battery.soc0 for agent in episode.agents], atol=1e-6
    )


def test_perfect_foresight_receding_central_equals_one_shot_central() -> None:
    episode = _smoke_episode()
    cfg = episode.cfg
    one_shot = realize(episode, solve_central(episode, cfg))
    receding = solve_receding_central(episode, cfg, foresight="perfect")
    lambda_minus = float(cfg["poi"]["lambda_minus"])
    j_one_shot = one_shot.profit.sum() - lambda_minus * one_shot.Vminus.sum()
    j_receding = receding.profit.sum() - lambda_minus * receding.Vminus.sum()
    assert abs(j_receding - j_one_shot) <= 1e-6 * max(abs(j_one_shot), 1.0)


def _smoke_episode() -> Episode:
    rng = np.random.default_rng(6974)
    W = rng.uniform(2, 9, (3, 24))
    What = np.maximum(W + rng.normal(0, 0.8, W.shape), 0)
    prices = np.array(
        [12, 10, 8, 5, 3, 2, 6, 15, 28, 40, 32, 25, 20, 18, 16, 22, 38, 65, 80, 58, 42, 30, 22, 16]
    )
    return Episode.from_arrays(
        W,
        What=What,
        b=What,
        pi_DA=0.9 * prices,
        pi_RT=prices,
        nameplates=[10, 11, 12],
        K=20,
        D=0.4 * What.sum(axis=0),
    )


def test_realization_never_exceeds_poi_limit_in_representative_cells() -> None:
    episode = _smoke_episode()
    started = time.perf_counter()
    for cell in ("C_P", "C_F", "D_F_EQ_FULL", "D_F_INJ_NONE", "D_P_INJ_PRICE"):
        result = solve_cell(episode, cell, episode.cfg)
        assert result.q.sum(axis=0).max() <= episode.K + 1e-6
        assert not np.any((result.c > 1e-6) & (result.d > 1e-6))
    assert time.perf_counter() - started < 60


def _negative_budget_episode() -> tuple[Episode, dict]:
    """Two agents; agent 0 grid-charges while agent 1 exports above K."""

    cfg = {
        "battery": {
            "terminal_soc": "free",
            "allow_grid_charging": True,
            "eps_tiebreak_usd_per_mwh": 1e-3,
        },
        "poi": {"delta_D": 0.5, "lambda_minus": 250.0, "lambda_plus": 100.0},
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


def test_negative_poi_budget_is_floored_and_feasible() -> None:
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
        result = solve_cell(episode, "D_F_INJ_NONE", cfg)
    finally:
        agent_lp.AgentLP.solve = original
    assert min(seen) >= -5.0 - 1e-9  # floored at -P_i
    assert result.q.sum(axis=0).max() <= episode.K + 1e-6


def test_game_objective_excludes_plus_penalty_and_converges_on_undamped_residual() -> None:
    episode, cfg = _negative_budget_episode()
    sol = solve_game(
        episode,
        {**cfg, "game": {"max_sweeps": 200, "tol_rel": 1e-5, "max_gain_tol": 1.0}},
        share_rule="equal",
    )
    agg = sol.q.sum(axis=0)
    expected = (
        episode.pi_RT @ agg
        - sum(a.battery.c_deg * sol.d[i].sum() for i, a in enumerate(episode.agents))
        - 250.0 * sol.Vminus.sum()
    )
    assert abs(sol.objective - expected) < 1e-6
    assert sol.objective_with_plus_penalty <= sol.objective + 1e-9
    assert sol.converged == (sol.max_delta < 1e-5 * episode.nameplates.sum() and sol.max_gain <= 1.0)

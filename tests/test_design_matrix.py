"""Offline tests for the four-factor design matrix."""

from __future__ import annotations

import numpy as np
import pytest

from wargame.experiments.design import CELL_ORDER, parse_cell
from wargame.model.env import Episode
from wargame.model.physics import Agent, Battery
from wargame.solvers.agent_lp import AgentLP, solve_agent
from wargame.solvers.central import solve_central
from wargame.solvers.design_matrix import solve_cell
from wargame.solvers.game import penalty_share_weights, solve_game
from wargame.solvers.realize import realize


def _config() -> dict:
    return {
        "battery": {
            "terminal_soc": "return",
            "allow_grid_charging": True,
            "eps_tiebreak_usd_per_mwh": 1e-3,
        },
        "poi": {"delta_D": 0.5, "lambda_minus": 250.0, "lambda_plus": 100.0},
        "game": {
            "max_sweeps": 40,
            "tol_rel": 1e-5,
            "max_gain_tol": 1.0,
            "damping": 0.5,
            "deviation_check": True,
            "injection_shortfall": "own",
        },
        "design_matrix": {
            "game_warm_start": True,
            "price_coordination": {
                "proximal_tau": 2.0,
                "step_usd_per_mwh_per_mw": 0.5,
                "step_decay": "none",
                "max_iterations": 30,
                "overflow_tol_rel": 1e-3,
                "cs_tol_usd": 100.0,
                "warm_start": True,
            },
        },
        "solver": "HIGHS",
    }


def test_share_weights_are_budget_balanced_with_equal_fallback() -> None:
    episode = Episode.from_arrays(
        [[0.0, 3.0], [0.0, 1.0]],
        b=[[0.0, 4.0], [0.0, 4.0]],
        nameplates=[4.0, 4.0],
        K=10.0,
        D=[0.0, 4.0],
        cfg=_config(),
    )
    q = np.array([[0.0, 3.0], [0.0, 1.0]])
    w_minus, w_plus = penalty_share_weights(episode, q, "injection")
    np.testing.assert_allclose(w_minus.sum(axis=0), 1.0)
    np.testing.assert_allclose(w_plus.sum(axis=0), 1.0)
    np.testing.assert_allclose(w_minus[:, 0], 0.5)
    np.testing.assert_allclose(w_plus[:, 0], 0.5)
    equal_minus, equal_plus = penalty_share_weights(episode, q, "equal")
    np.testing.assert_allclose(equal_minus, 0.5)
    np.testing.assert_allclose(equal_plus, 0.5)


def test_agent_lp_constant_vector_betas_equal_scalars() -> None:
    battery = Battery(E=2, P=1, eta_c=1, eta_d=1, c_deg=0, soc0=1)
    agent = Agent("a", 4, battery)
    kwargs = {
        "W": [3.0, 1.0, 2.0],
        "prices": [20.0, -5.0, 30.0],
        "K": 2.0,
        "D": [1.0, 1.0, 1.0],
        "q_other": [1.0, 0.0, 1.0],
        "cfg": _config(),
        "beta_minus": 0.4,
        "beta_plus": 0.7,
    }
    scalar = solve_agent(agent, **kwargs)
    vector = solve_agent(
        agent,
        **{
            **kwargs,
            "beta_minus": np.full(3, 0.4),
            "beta_plus": np.full(3, 0.7),
        },
    )
    np.testing.assert_allclose(vector.q, scalar.q, atol=1e-6)


def test_price_coordination_clears_only_congested_hour() -> None:
    cfg = _config()
    batteries = [Battery(0, 0, 1, 1, 0, 0) for _ in range(2)]
    agents = [Agent(f"a{i}", 4, battery) for i, battery in enumerate(batteries)]
    episode = Episode.from_arrays(
        [[1.0, 4.0, 1.0], [1.0, 4.0, 1.0]],
        agents=agents,
        b=np.zeros((2, 3)),
        pi_DA=[5.0, 5.0, 5.0],
        pi_RT=[5.0, 5.0, 5.0],
        K=5.0,
        D=[0.0, 0.0, 0.0],
        cfg=cfg,
    )
    result = solve_cell(episode, "D_P_INJ_PRICE", cfg)
    assert result.converged
    assert result.price_iterations_by_hour is not None
    assert max(result.price_iterations_by_hour) <= 30
    assert max(result.price_max_overflow_by_hour or [np.inf]) <= 1e-3 * sum(
        agent.nameplate for agent in agents
    )
    assert result.mu_by_hour is not None
    assert result.mu_by_hour[0, 1] > 0.0
    assert result.mu_by_hour[0, 0] == 0.0
    assert result.mu_by_hour[0, 2] == 0.0


def test_injection_full_own_shortfalls_cover_system_shortfall() -> None:
    cfg = _config()
    batteries = [Battery(0, 0, 1, 1, 0, 0) for _ in range(2)]
    agents = [Agent(f"a{i}", 4, battery) for i, battery in enumerate(batteries)]
    episode = Episode.from_arrays(
        [[1.0, 0.5, 1.5], [0.5, 1.0, 0.0]],
        agents=agents,
        b=[[4.0, 4.0, 4.0], [4.0, 4.0, 4.0]],
        pi_RT=[5.0, 5.0, 5.0],
        K=10.0,
        D=[4.0, 4.0, 4.0],
        cfg=cfg,
    )
    solution = solve_game(episode, cfg, share_rule="injection")
    assert solution.converged
    private_delivery = cfg["poi"]["delta_D"] * episode.b
    own_shortfall = np.maximum(private_delivery - solution.q, 0.0).sum(axis=0)
    system_shortfall = np.maximum(episode.D - solution.q.sum(axis=0), 0.0)
    assert np.all(own_shortfall >= system_shortfall - 1e-8)


@pytest.mark.parametrize(
    ("price", "overshoots"),
    [(120.0, True), (20.0, False)],
)
def test_causal_agent_objective_matches_exact_charge(
    price: float, overshoots: bool
) -> None:
    cfg = _config()
    cfg["battery"]["eps_tiebreak_usd_per_mwh"] = 0.0
    agent = Agent("a", 10.0, Battery(0, 0, 1, 1, 0, 0))
    model = AgentLP(
        agent,
        1,
        cfg,
        shortfall_mode="private",
        overflow_mode="causal",
    )
    q_other = 2.0
    solution = model.solve(
        W=[8.0],
        prices=[price],
        q_other=[q_other],
        K=5.0,
        D=[0.0],
        beta_minus=1.0,
        others_positive=[q_other],
        others_sum=[q_other],
    )
    q = float(solution.q[0])
    hand_charge = 100.0 * max(q, 0.0) * max(q + q_other - 5.0, 0.0) / (
        max(q, 0.0) + q_other
    )
    assert solution.objective == pytest.approx(price * q - hand_charge, abs=1e-6)
    assert (q + q_other > 5.0 + 1e-5) is overshoots


def test_causal_agent_problem_is_dpp() -> None:
    cfg = _config()
    agent = Agent("a", 10.0, Battery(0, 0, 1, 1, 0, 0))
    model = AgentLP(agent, 2, cfg, overflow_mode="causal")
    assert model.problem.is_dpp()


def test_injection_full_exact_game_converges_with_small_deviation_gain() -> None:
    cfg = _config()
    cfg["game"]["max_sweeps"] = 100
    batteries = [Battery(0, 0, 1, 1, 0, 0) for _ in range(2)]
    agents = [Agent(f"a{i}", 4.0, battery) for i, battery in enumerate(batteries)]
    episode = Episode.from_arrays(
        [[4.0, 4.0, 4.0], [4.0, 4.0, 4.0]],
        agents=agents,
        b=np.zeros((2, 3)),
        pi_RT=[120.0, 20.0, 140.0],
        K=5.0,
        D=[0.0, 0.0, 0.0],
        cfg=cfg,
    )
    solution = solve_game(episode, cfg, share_rule="injection")
    assert solution.converged
    assert solution.max_gain <= 1.0


def test_c_p_matches_one_shot_central_realized_objective() -> None:
    cfg = _config()
    episode = Episode.from_arrays(
        [[2.0, 5.0, 1.0, 4.0], [3.0, 1.0, 4.0, 2.0]],
        What=[[1.0, 2.0, 3.0, 4.0], [2.0, 2.0, 2.0, 2.0]],
        b=[[2.0] * 4, [2.0] * 4],
        pi_DA=[8.0, 8.0, 8.0, 8.0],
        pi_RT=[-5.0, 20.0, 10.0, 40.0],
        nameplates=[6.0, 6.0],
        K=7.0,
        D=[2.0, 2.0, 2.0, 2.0],
        cfg=cfg,
    )
    one_shot = realize(episode, solve_central(episode, cfg))
    receding = solve_cell(episode, "C_P", cfg)
    lambda_minus = cfg["poi"]["lambda_minus"]
    j_one_shot = one_shot.profit.sum() - lambda_minus * one_shot.Vminus.sum()
    j_receding = receding.profit.sum() - lambda_minus * receding.Vminus.sum()
    assert abs(j_receding - j_one_shot) <= 1e-6 * max(abs(j_one_shot), 1.0)


def test_parse_cell_round_trips_all_fourteen_ids() -> None:
    assert len(CELL_ORDER) == 14
    assert len(set(CELL_ORDER)) == 14
    for cell in CELL_ORDER:
        factors = parse_cell(cell)
        rebuilt = (
            f"{factors['control']}_{factors['foresight']}"
            if factors["control"] == "C"
            else f"D_{factors['foresight']}_{factors['share']}_{factors['info']}"
        )
        assert rebuilt == cell


def test_every_cell_runs_and_realization_respects_poi() -> None:
    cfg = _config()
    episode = Episode.from_arrays(
        [[2.0, 4.0, 1.0, 3.0], [3.0, 2.0, 4.0, 1.0]],
        What=[[1.0, 3.0, 2.0, 2.0], [2.0, 1.0, 3.0, 2.0]],
        b=[[2.0] * 4, [2.0] * 4],
        pi_DA=[5.0, 10.0, 15.0, 20.0],
        pi_RT=[6.0, 12.0, 8.0, 25.0],
        nameplates=[5.0, 5.0],
        K=6.0,
        D=[2.0, 2.0, 2.0, 2.0],
        cfg=cfg,
    )
    for cell in CELL_ORDER:
        result = solve_cell(episode, cell, cfg)
        assert result.q.shape == (2, 4)
        assert result.q.sum(axis=0).max() <= episode.K + 1e-6

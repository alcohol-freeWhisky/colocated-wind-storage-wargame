"""Offline tests for the matched four-factor design."""

from __future__ import annotations

import numpy as np
import pytest

from wargame.experiments.design import CELL_ORDER, parse_cell
from wargame.model.env import Episode
from wargame.model.physics import Agent, Battery
from wargame.solvers.agent_lp import AgentLP
from wargame.solvers.design_matrix import solve_cell
from wargame.solvers.game import penalty_share_weights, solve_game
from wargame.solvers.realize import realize
from wargame.solvers.central import solve_central


def _config() -> dict:
    return {
        "battery": {
            "terminal_soc": "return",
            "allow_grid_charging": False,
            "eps_tiebreak_usd_per_mwh": 1e-3,
        },
        "poi": {"lambda_plus": 100.0},
        "game": {
            "max_sweeps": 100,
            "tol_rel": 1e-5,
            "max_gain_tol": 1.0,
            "damping": 0.5,
            "deviation_check": True,
        },
        "design_matrix": {"game_warm_start": True},
        "solver": "HIGHS",
    }


def test_overflow_share_weights_are_budget_balanced() -> None:
    episode = Episode.from_arrays(
        [[0.0, 3.0], [0.0, 1.0]], nameplates=[4.0, 4.0], K=10.0, cfg=_config()
    )
    q = np.array([[0.0, 3.0], [0.0, 1.0]])
    causal = penalty_share_weights(episode, q, "injection")
    equal = penalty_share_weights(episode, q, "equal")
    np.testing.assert_allclose(causal.sum(axis=0), 1.0)
    np.testing.assert_allclose(causal[:, 0], 0.5)
    np.testing.assert_allclose(causal[:, 1], [0.75, 0.25])
    np.testing.assert_allclose(equal, 0.5)


@pytest.mark.parametrize(("price", "overshoots"), [(120.0, True), (20.0, False)])
def test_causal_agent_uses_exact_overflow_charge(price: float, overshoots: bool) -> None:
    cfg = _config()
    cfg["battery"]["eps_tiebreak_usd_per_mwh"] = 0.0
    agent = Agent("a", 10.0, Battery(0, 0, 1, 1, 0, 0))
    model = AgentLP(agent, 1, cfg, overflow_mode="causal")
    q_other = 2.0
    solution = model.solve(
        W=[8.0], prices=[price], q_other=[q_other], K=5.0,
        others_positive=[q_other], others_sum=[q_other],
    )
    q = float(solution.q[0])
    charge = 100.0 * max(q, 0.0) * max(q + q_other - 5.0, 0.0) / (
        max(q, 0.0) + q_other
    )
    assert solution.objective == pytest.approx(price * q - charge, abs=1e-6)
    assert (q + q_other > 5.0 + 1e-5) is overshoots


def test_full_and_aggregate_use_same_payoff_and_constraints() -> None:
    cfg = _config()
    agents = [Agent(f"a{i}", 4, Battery(0, 0, 1, 1, 0, 0)) for i in range(2)]
    episode = Episode.from_arrays(
        [[4.0, 4.0], [4.0, 4.0]], agents=agents,
        pi_RT=[20.0, 20.0], K=5.0, cfg=cfg,
    )
    full = solve_game(episode, cfg, share_rule="equal", information="full")
    aggregate = solve_game(episode, cfg, share_rule="equal", information="aggregate")
    assert full.converged
    assert aggregate.converged
    np.testing.assert_allclose(full.objective, aggregate.objective, atol=1e-3)


def test_no_signal_changes_only_rival_information() -> None:
    cfg = _config()
    agents = [Agent(f"a{i}", 4, Battery(0, 0, 1, 1, 0, 0)) for i in range(2)]
    episode = Episode.from_arrays(
        [[4.0], [4.0]], agents=agents, pi_RT=[20.0], K=5.0, cfg=cfg,
    )
    full = solve_game(episode, cfg, share_rule="equal", information="full")
    none = solve_game(episode, cfg, share_rule="equal", information="nothing")
    assert none.q.sum() >= full.q.sum() - 1e-6
    assert np.all(none.q >= -1e-8)


def test_perfect_receding_planner_matches_one_shot() -> None:
    cfg = _config()
    episode = Episode.from_arrays(
        [[2.0, 5.0, 1.0, 4.0], [3.0, 1.0, 4.0, 2.0]],
        What=[[1.0, 2.0, 3.0, 4.0], [2.0, 2.0, 2.0, 2.0]],
        pi_DA=[8.0] * 4, pi_RT=[-5.0, 20.0, 10.0, 40.0],
        nameplates=[6.0, 6.0], K=7.0, cfg=cfg,
    )
    one_shot = realize(episode, solve_central(episode, cfg))
    receding = solve_cell(episode, "C_P", cfg)
    assert receding.objective == pytest.approx(one_shot.objective, rel=1e-6, abs=1e-6)


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


def test_every_cell_runs_with_same_physics() -> None:
    cfg = _config()
    episode = Episode.from_arrays(
        [[2.0, 4.0, 1.0, 3.0], [3.0, 2.0, 4.0, 1.0]],
        What=[[1.0, 3.0, 2.0, 2.0], [2.0, 1.0, 3.0, 2.0]],
        pi_DA=[5.0, 10.0, 15.0, 20.0], pi_RT=[6.0, 12.0, 8.0, 25.0],
        nameplates=[5.0, 5.0], K=6.0, cfg=cfg,
    )
    for cell in CELL_ORDER:
        result = solve_cell(episode, cell, cfg)
        assert result.q.shape == (2, 4)
        assert result.q.sum(axis=0).max() <= episode.K + 1e-6
        assert not np.any((result.c > 1e-6) & (result.d > 1e-6))

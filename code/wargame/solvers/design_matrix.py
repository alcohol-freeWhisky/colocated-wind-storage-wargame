"""Matched hourly solvers for the 14-cell operating design."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np
from numpy.typing import NDArray

from wargame.experiments.design import parse_cell
from wargame.model.env import Episode
from wargame.solvers.agent_lp import AgentSolution
from wargame.solvers.game import penalty_share_weights, solve_game
from wargame.solvers.receding import (
    _empty_trajectories,
    _realization,
    forecast_subhorizon,
    perfect_subhorizon,
    reachable_terminal_soc,
    solve_receding_central,
)
from wargame.solvers.realize import Realization, realize_hour

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class _WarmPlan:
    c: NDArray[np.float64]
    d: NDArray[np.float64]
    r: NDArray[np.float64]


def _view(episode: Episode, t: int, foresight: str) -> Episode:
    return perfect_subhorizon(episode, t) if foresight == "P" else forecast_subhorizon(episode, t)


def _attach_shares(episode: Episode, result: Realization, share: str) -> Realization:
    result.w_plus = penalty_share_weights(
        episode, result.q_planned, "injection" if share == "INJ" else "equal"
    )
    return result


def _solve_decentralized(
    episode: Episode,
    cell_id: str,
    config: Mapping[str, Any],
    foresight: str,
    share: str,
    info: str,
) -> Realization:
    q, c, d, r, q_plan, c_plan, d_plan, r_plan, spill = _empty_trajectories(episode)
    soc = np.zeros((episode.N, episode.T + 1), dtype=float)
    terminal = np.asarray([agent.battery.soc0 for agent in episode.agents], dtype=float)
    soc[:, 0] = terminal
    warm: _WarmPlan | None = None
    warm_enabled = bool(config.get("design_matrix", {}).get("game_warm_start", True))
    information = {"FULL": "full", "PRICE": "aggregate", "NONE": "nothing"}[info]

    sweeps_by_hour: list[int] = []
    converged_by_hour: list[bool] = []
    sweep_log: list[dict[str, float]] = []
    aggregate_signal = np.full((episode.T, episode.T), np.nan)
    max_delta = 0.0
    max_gain = 0.0

    for t in range(episode.T):
        view = _view(episode, t, foresight)
        game = solve_game(
            view,
            config,
            initial_soc=soc[:, t],
            terminal_soc=reachable_terminal_soc(view, soc[:, t], terminal),
            initial_plan=warm if warm_enabled and info != "NONE" else None,
            share_rule="injection" if share == "INJ" else "equal",
            information=information,
        )
        plans = [
            AgentSolution(
                q=game.q[i], c=game.c[i], d=game.d[i], r=game.r[i],
                soc=game.soc[i], Vplus=game.Vplus,
                objective=float("nan"), base_profit=float("nan"), status=game.status,
            )
            for i in range(episode.N)
        ]
        sweeps_by_hour.append(game.sweeps)
        converged_by_hour.append(game.converged)
        sweep_log.extend({"hour": float(t), **entry} for entry in game.sweep_log)
        max_delta = max(max_delta, game.max_delta)
        max_gain = max(max_gain, game.max_gain)
        if info == "PRICE":
            aggregate_signal[t, t:] = game.q.sum(axis=0)
        if info != "NONE":
            warm = _WarmPlan(game.c[:, 1:].copy(), game.d[:, 1:].copy(), game.r[:, 1:].copy())

        for i, plan in enumerate(plans):
            q_plan[i, t] = plan.q[0]
            c_plan[i, t] = plan.c[0]
            d_plan[i, t] = plan.d[0]
            r_plan[i, t] = plan.r[0]
        q[:, t], c[:, t], d[:, t], r[:, t], soc[:, t + 1], spill[:, t] = realize_hour(
            episode.W[:, t], c_plan[:, t], d_plan[:, t], r_plan[:, t],
            episode.agents, soc[:, t], episode.K,
        )
        LOGGER.debug("cell=%s day=%s hour=%d", cell_id, episode.day, t)

    result = _realization(
        episode,
        q=q, c=c, d=d, r=r, soc=soc,
        q_plan=q_plan, c_plan=c_plan, d_plan=d_plan, r_plan=r_plan,
        spill=spill, status=cell_id,
        converged=bool(all(converged_by_hour)),
        sweeps_by_hour=sweeps_by_hour,
        game_converged_by_hour=converged_by_hour,
        max_delta=max_delta, max_gain=max_gain, sweep_log=sweep_log,
        information_iterations_by_hour=sweeps_by_hour,
        information_converged_by_hour=converged_by_hour,
        aggregate_signal_by_hour=aggregate_signal if info == "PRICE" else None,
    )
    return _attach_shares(episode, result, share)


def solve_cell(
    episode: Episode,
    cell_id: str,
    cfg: Mapping[str, Any] | None = None,
) -> Realization:
    """Solve and physically realize one canonical design-matrix cell."""

    factors = parse_cell(cell_id)
    config = episode.cfg if cfg is None else cfg
    if factors["control"] == "C":
        result = solve_receding_central(
            episode,
            config,
            foresight="perfect" if factors["foresight"] == "P" else "forecast",
        )
        result.status = cell_id
        return _attach_shares(episode, result, "INJ")
    return _solve_decentralized(
        episode, cell_id, config, factors["foresight"],
        str(factors["share"]), str(factors["info"]),
    )

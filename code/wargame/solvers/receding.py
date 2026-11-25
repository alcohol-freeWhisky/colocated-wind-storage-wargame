"""Receding-horizon central policy and shared information views."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np
from numpy.typing import NDArray

from wargame.model.env import Episode
from wargame.solvers.central import solve_central
from wargame.solvers.realize import Realization, realize_hour


@dataclass(slots=True)
class _WarmPlan:
    """Previous-hour plan tail used to initialize a forecast game."""

    c: NDArray[np.float64]
    d: NDArray[np.float64]
    r: NDArray[np.float64]


def forecast_subhorizon(episode: Episode, horizon_start: int) -> Episode:
    """Build the forecast information view from ``horizon_start`` to episode end."""

    if not 0 <= horizon_start < episode.T:
        raise ValueError("horizon_start must identify an hour in the episode")
    wind = episode.What[:, horizon_start:].copy()
    wind[:, 0] = episode.W[:, horizon_start]
    prices = episode.pi_DA[horizon_start:].copy()
    prices[0] = episode.pi_RT[horizon_start]
    return Episode(
        agents=episode.agents,
        W=wind,
        What=episode.What[:, horizon_start:],
        pi_DA=episode.pi_DA[horizon_start:],
        pi_RT=prices,
        K=episode.K,
        cfg=episode.cfg,
        day=episode.day,
    )


def perfect_subhorizon(episode: Episode, horizon_start: int) -> Episode:
    """Build the true-data information view from ``horizon_start`` onward."""

    if not 0 <= horizon_start < episode.T:
        raise ValueError("horizon_start must identify an hour in the episode")
    return Episode(
        agents=episode.agents,
        W=episode.W[:, horizon_start:].copy(),
        What=episode.What[:, horizon_start:].copy(),
        pi_DA=episode.pi_DA[horizon_start:].copy(),
        pi_RT=episode.pi_RT[horizon_start:].copy(),
        K=episode.K,
        cfg=episode.cfg,
        day=episode.day,
    )


def reachable_terminal_soc(
    episode: Episode,
    initial_soc: NDArray[np.float64],
    requested: NDArray[np.float64],
) -> NDArray[np.float64]:
    """Cap a return target at the SOC reachable in the current information view."""

    if episode.cfg.get("battery", {}).get("terminal_soc", "return") != "return":
        return requested.copy()
    if episode.cfg.get("battery", {}).get("allow_grid_charging", False):
        return requested.copy()
    power = np.asarray([agent.battery.P for agent in episode.agents], dtype=float)[:, None]
    eta = np.asarray([agent.battery.eta_c for agent in episode.agents], dtype=float)
    maximum_charge = np.minimum(episode.W, power).sum(axis=1)
    reachable = initial_soc + eta * maximum_charge
    return np.minimum(requested, reachable)


def _empty_trajectories(episode: Episode) -> tuple[NDArray[np.float64], ...]:
    shape = (episode.N, episode.T)
    return tuple(np.zeros(shape, dtype=float) for _ in range(9))


def _realization(
    episode: Episode,
    *,
    q: NDArray[np.float64],
    c: NDArray[np.float64],
    d: NDArray[np.float64],
    r: NDArray[np.float64],
    soc: NDArray[np.float64],
    q_plan: NDArray[np.float64],
    c_plan: NDArray[np.float64],
    d_plan: NDArray[np.float64],
    r_plan: NDArray[np.float64],
    spill: NDArray[np.float64],
    status: str,
    converged: bool | None = None,
    sweeps_by_hour: list[int] | None = None,
    game_converged_by_hour: list[bool] | None = None,
    max_delta: float | None = None,
    max_gain: float | None = None,
    sweep_log: list[dict[str, float]] | None = None,
    information_iterations_by_hour: list[int] | None = None,
    information_converged_by_hour: list[bool] | None = None,
    aggregate_signal_by_hour: NDArray[np.float64] | None = None,
    w_plus: NDArray[np.float64] | None = None,
) -> Realization:
    aggregate = q.sum(axis=0)
    aggregate_plan = q_plan.sum(axis=0)
    costs = np.asarray([agent.battery.c_deg for agent in episode.agents])[:, None]
    return Realization(
        q=q,
        c=c,
        d=d,
        r=r,
        soc=soc,
        q_planned=q_plan,
        c_planned=c_plan,
        d_planned=d_plan,
        r_planned=r_plan,
        Vplus=np.maximum(aggregate - episode.K, 0.0),
        Vplus_attempted=np.maximum(aggregate_plan - episode.K, 0.0),
        profit=(episode.pi_RT[None, :] * q - costs * d).sum(axis=1),
        profit_planned=(episode.pi_RT[None, :] * q_plan - costs * d_plan).sum(axis=1),
        spill=spill,
        status=status,
        converged=converged,
        sweeps=None if sweeps_by_hour is None else int(sum(sweeps_by_hour)),
        max_delta=max_delta,
        max_gain=max_gain,
        sweeps_by_hour=sweeps_by_hour,
        game_converged_by_hour=game_converged_by_hour,
        sweep_log=sweep_log,
        information_iterations_by_hour=information_iterations_by_hour,
        information_converged_by_hour=information_converged_by_hour,
        aggregate_signal_by_hour=aggregate_signal_by_hour,
        w_plus=w_plus,
    )


def solve_receding_central(
    episode: Episode,
    cfg: Mapping[str, Any] | None = None,
    *,
    foresight: str = "forecast",
) -> Realization:
    """Execute a central LP hourly with perfect or forecast information."""

    config = episode.cfg if cfg is None else cfg
    if foresight not in {"perfect", "forecast"}:
        raise ValueError("foresight must be 'perfect' or 'forecast'")
    q, c, d, r, q_plan, c_plan, d_plan, r_plan, spill = _empty_trajectories(episode)
    soc = np.zeros((episode.N, episode.T + 1), dtype=float)
    terminal = np.asarray([agent.battery.soc0 for agent in episode.agents], dtype=float)
    soc[:, 0] = terminal

    for t in range(episode.T):
        view = (
            perfect_subhorizon(episode, t)
            if foresight == "perfect"
            else forecast_subhorizon(episode, t)
        )
        plan = solve_central(
            view,
            config,
            initial_soc=soc[:, t],
            terminal_soc=reachable_terminal_soc(view, soc[:, t], terminal),
        )
        q_plan[:, t] = plan.q[:, 0]
        c_plan[:, t] = plan.c[:, 0]
        d_plan[:, t] = plan.d[:, 0]
        r_plan[:, t] = plan.r[:, 0]
        q[:, t], c[:, t], d[:, t], r[:, t], soc[:, t + 1], spill[:, t] = realize_hour(
            episode.W[:, t],
            c_plan[:, t],
            d_plan[:, t],
            r_plan[:, t],
            episode.agents,
            soc[:, t],
            episode.K,
        )
    return _realization(
        episode,
        q=q,
        c=c,
        d=d,
        r=r,
        soc=soc,
        q_plan=q_plan,
        c_plan=c_plan,
        d_plan=d_plan,
        r_plan=r_plan,
        spill=spill,
        status="C_P" if foresight == "perfect" else "C_F",
    )

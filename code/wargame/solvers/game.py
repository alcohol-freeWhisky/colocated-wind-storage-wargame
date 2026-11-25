"""Best-response games under three matched information structures."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Literal, Mapping

import numpy as np
from numpy.typing import ArrayLike, NDArray

from wargame.model.env import Episode
from wargame.model.physics import battery_is_feasible, simulate_soc
from wargame.solvers.agent_lp import AgentLP

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class GameSolution:
    """A planned owner profile and fixed-point diagnostics."""

    q: NDArray[np.float64]
    c: NDArray[np.float64]
    d: NDArray[np.float64]
    r: NDArray[np.float64]
    soc: NDArray[np.float64]
    Vplus: NDArray[np.float64]
    objective: float
    status: str
    converged: bool
    sweeps: int
    max_delta: float
    max_gain: float
    w_plus: NDArray[np.float64] | None = None
    sweep_log: list[dict[str, float]] = field(default_factory=list)


def penalty_share_weights(
    episode: Episode,
    q: ArrayLike,
    rule: str,
) -> NDArray[np.float64]:
    """Allocate each hour's total overflow charge without changing its size."""

    profile = np.asarray(q, dtype=float)
    if profile.shape != (episode.N, episode.T):
        raise ValueError(f"q must have shape {(episode.N, episode.T)}")
    if rule == "equal":
        return np.full_like(profile, 1.0 / episode.N)
    if rule != "injection":
        raise ValueError("share_rule must be 'injection' or 'equal'")
    positive = np.maximum(profile, 0.0)
    denominator = positive.sum(axis=0)
    weights = np.full_like(profile, 1.0 / episode.N)
    active = denominator > 1e-12
    weights[:, active] = positive[:, active] / denominator[active]
    return weights


def _remove_damped_cycles(
    c: NDArray[np.float64],
    d: NDArray[np.float64],
    r: NDArray[np.float64],
    W: NDArray[np.float64],
    eta_c: float,
    eta_d: float,
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """Remove simultaneous charge/discharge while preserving injection and SOC."""

    round_trip = eta_c * eta_d
    reduction = np.minimum(c, d / round_trip)
    loss = 1.0 - round_trip
    if loss > 1e-12:
        reduction = np.minimum(reduction, np.maximum(W - r, 0.0) / loss)
    return (
        np.maximum(c - reduction, 0.0),
        np.maximum(d - round_trip * reduction, 0.0),
        np.minimum(r + loss * reduction, W),
    )


def _perceived_rivals(
    profile: NDArray[np.float64],
    i: int,
    information: str,
    snapshot: NDArray[np.float64] | None,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Return only the aggregate rival signals visible to owner i."""

    if information == "nothing":
        zeros = np.zeros(profile.shape[1])
        return zeros, zeros
    source = snapshot
    if source is None:
        raise RuntimeError("informed best responses require a sweep snapshot")
    rival_sum = source.sum(axis=0) - source[i]
    rival_positive = np.maximum(source, 0.0).sum(axis=0) - np.maximum(source[i], 0.0)
    return rival_sum, rival_positive


def _agent_payoff(
    episode: Episode,
    i: int,
    own_q: NDArray[np.float64],
    own_c: NDArray[np.float64],
    own_d: NDArray[np.float64],
    own_r: NDArray[np.float64],
    rival_sum: NDArray[np.float64],
    rival_positive: NDArray[np.float64],
    share_rule: str,
    cfg: Mapping[str, Any],
) -> float:
    overflow = np.maximum(own_q + rival_sum - episode.K, 0.0)
    if share_rule == "equal":
        share = np.full(episode.T, 1.0 / episode.N)
    else:
        denominator = np.maximum(own_q, 0.0) + rival_positive
        share = np.zeros(episode.T)
        active = denominator > 1e-12
        share[active] = np.maximum(own_q[active], 0.0) / denominator[active]
    penalty = float(cfg.get("poi", {}).get("lambda_plus", 100.0)) * float(share @ overflow)
    tie = float(cfg.get("battery", {}).get("eps_tiebreak_usd_per_mwh", 1e-3))
    return float(
        episode.pi_RT @ own_q
        - episode.agents[i].battery.c_deg * own_d.sum()
        - penalty
        - tie * (own_c + own_d + own_r).sum()
    )


def _maximum_deviation_gain(
    episode: Episode,
    models: list[AgentLP],
    q: NDArray[np.float64],
    c: NDArray[np.float64],
    d: NDArray[np.float64],
    r: NDArray[np.float64],
    start_soc: NDArray[np.float64],
    target_soc: NDArray[np.float64],
    information: str,
    share_rule: str,
    config: Mapping[str, Any],
) -> float:
    """Return the largest payoff improvement under the cell's information."""

    maximum = 0.0
    snapshot = q.copy() if information in {"full", "aggregate"} else None
    for i, model in enumerate(models):
        rival_sum, rival_positive = _perceived_rivals(q, i, information, snapshot)
        current = _agent_payoff(
            episode, i, q[i], c[i], d[i], r[i], rival_sum,
            rival_positive, share_rule, config,
        )
        kwargs: dict[str, Any] = {
            "W": episode.W[i],
            "prices": episode.pi_RT,
            "q_other": rival_sum,
            "K": episode.K,
            "beta_plus": 1.0 / episode.N if share_rule == "equal" else 0.0,
            "initial_soc": float(start_soc[i]),
            "terminal_soc": float(target_soc[i]),
        }
        if share_rule == "injection":
            kwargs.update(others_positive=rival_positive, others_sum=rival_sum)
        deviation = model.solve(**kwargs)
        maximum = max(maximum, deviation.objective - current)
    return float(max(maximum, 0.0))


def solve_game(
    episode: Episode,
    cfg: Mapping[str, Any] | None = None,
    *,
    share_rule: str,
    information: Literal["full", "aggregate", "nothing"] = "full",
    initial_soc: ArrayLike | None = None,
    terminal_soc: ArrayLike | None = None,
    initial_plan: Any | None = None,
) -> GameSolution:
    """Solve one owner game while changing only the available rival signal.

    ``full`` observes owner-level plans, while ``aggregate`` receives only net
    and positive aggregate injections. Both use the same sequential update
    protocol, with the visible signal refreshed after each response. ``nothing``
    supplies no current rival signal, so each owner solves against a zero-rival
    benchmark. Payoffs, penalties, constraints, and realization are identical.
    """

    if information not in {"full", "aggregate", "nothing"}:
        raise ValueError("information must be 'full', 'aggregate', or 'nothing'")
    if share_rule not in {"injection", "equal"}:
        raise ValueError("share_rule must be 'injection' or 'equal'")
    config = episode.cfg if cfg is None else cfg
    game_cfg = config.get("game", {})
    max_sweeps = 1 if information == "nothing" else int(game_cfg.get("max_sweeps", 200))
    damping = 1.0 if information == "nothing" else float(game_cfg.get("damping", 0.5))
    tolerance = float(game_cfg.get("tol_rel", 1e-5)) * float(episode.nameplates.sum())

    default_soc = np.asarray([agent.battery.soc0 for agent in episode.agents], dtype=float)
    start_soc = default_soc if initial_soc is None else np.asarray(initial_soc, dtype=float)
    target_soc = default_soc if terminal_soc is None else np.asarray(terminal_soc, dtype=float)
    expected = episode.W.shape
    if initial_plan is None:
        c = np.zeros(expected)
        d = np.zeros(expected)
        r = np.zeros(expected)
    else:
        c, d, r = (
            np.asarray(getattr(initial_plan, name), dtype=float).copy()
            for name in ("c", "d", "r")
        )
        if any(array.shape != expected for array in (c, d, r)):
            raise ValueError(f"initial plan must have shape {expected}")
    q = episode.W - r - c + d
    mode = "causal" if share_rule == "injection" else "shared"
    models = [AgentLP(agent, episode.T, config, overflow_mode=mode) for agent in episode.agents]
    terminal_rule = str(config.get("battery", {}).get("terminal_soc", "return"))
    profile_feasible = np.asarray(
        [
            battery_is_feasible(
                c[i], d[i], agent.battery,
                initial_soc=float(start_soc[i]), terminal=terminal_rule,
                terminal_soc=float(target_soc[i]),
            )
            and np.all(r[i] >= -1e-8)
            and np.all(r[i] <= episode.W[i] + 1e-8)
            and np.all(c[i] <= episode.W[i] - r[i] + 1e-8)
            for i, agent in enumerate(episode.agents)
        ],
        dtype=bool,
    )

    history: list[dict[str, float]] = []
    max_delta = np.inf
    max_gain = np.inf
    gain_tolerance = float(game_cfg.get("max_gain_tol", 1.0))
    gain_interval = max(1, int(game_cfg.get("gain_check_interval", 5)))
    sweeps_done = 0
    for sweep in range(1, max_sweeps + 1):
        residual = 0.0
        for i, model in enumerate(models):
            snapshot = q.copy() if information in {"full", "aggregate"} else None
            rival_sum, rival_positive = _perceived_rivals(q, i, information, snapshot)
            kwargs: dict[str, Any] = {
                "W": episode.W[i],
                "prices": episode.pi_RT,
                "q_other": rival_sum,
                "K": episode.K,
                "beta_plus": 1.0 / episode.N if share_rule == "equal" else 0.0,
                "initial_soc": float(start_soc[i]),
                "terminal_soc": float(target_soc[i]),
            }
            if share_rule == "injection":
                kwargs.update(others_positive=rival_positive, others_sum=rival_sum)
            best = model.solve(**kwargs)
            residual = max(residual, float(np.max(np.abs(best.q - q[i]))))
            step = damping if profile_feasible[i] else 1.0
            c[i] = (1 - step) * c[i] + step * best.c
            d[i] = (1 - step) * d[i] + step * best.d
            r[i] = (1 - step) * r[i] + step * best.r
            profile_feasible[i] = True
            c[i], d[i], r[i] = _remove_damped_cycles(
                c[i], d[i], r[i], episode.W[i],
                episode.agents[i].battery.eta_c, episode.agents[i].battery.eta_d,
            )
            q[i] = episode.W[i] - r[i] - c[i] + d[i]
        max_delta = residual
        sweeps_done = sweep
        history.append({"sweep": float(sweep), "max_delta": max_delta})
        check_gain = bool(game_cfg.get("deviation_check", True)) and (
            max_delta < tolerance or sweep % gain_interval == 0
        )
        if check_gain:
            max_gain = _maximum_deviation_gain(
                episode, models, q, c, d, r, start_soc, target_soc,
                information, share_rule, config,
            )
            history[-1]["max_gain"] = max_gain
            if max_gain <= gain_tolerance:
                break

    aggregate = q.sum(axis=0)
    vplus = np.maximum(aggregate - episode.K, 0.0)
    soc = np.vstack(
        [
            simulate_soc(c[i], d[i], agent.battery, initial_soc=float(start_soc[i]))
            for i, agent in enumerate(episode.agents)
        ]
    )
    weights = penalty_share_weights(episode, q, share_rule)

    if bool(game_cfg.get("deviation_check", True)):
        max_gain = _maximum_deviation_gain(
            episode, models, q, c, d, r, start_soc, target_soc,
            information, share_rule, config,
        )
    else:
        max_gain = 0.0
    converged = bool(max_gain <= gain_tolerance)
    objective = float(
        episode.pi_RT @ aggregate
        - sum(agent.battery.c_deg * d[i].sum() for i, agent in enumerate(episode.agents))
    )
    return GameSolution(
        q=q, c=c, d=d, r=r, soc=soc, Vplus=vplus,
        objective=objective,
        status="converged" if converged else "max_sweeps",
        converged=converged, sweeps=sweeps_done,
        max_delta=0.0 if information == "nothing" else max_delta,
        max_gain=max_gain, w_plus=weights, sweep_log=history,
    )

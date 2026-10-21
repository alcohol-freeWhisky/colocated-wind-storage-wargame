"""Gauss--Seidel best-response games for regimes R2 and R3."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Mapping

import numpy as np
from numpy.typing import ArrayLike, NDArray

from wargame.model.env import Episode
from wargame.model.physics import battery_is_feasible, simulate_soc
from wargame.solvers.agent_lp import AgentLP

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class GameSolution:
    """A decentralized dispatch profile and fixed-point diagnostics."""

    q: NDArray[np.float64]
    c: NDArray[np.float64]
    d: NDArray[np.float64]
    r: NDArray[np.float64]
    soc: NDArray[np.float64]
    Vminus: NDArray[np.float64]
    Vplus: NDArray[np.float64]
    objective: float  # central definition: sum pi*q - c_deg*d - lambda_minus*sum V^- (no lambda_plus)
    status: str
    converged: bool
    sweeps: int
    max_delta: float
    max_gain: float
    beta_minus: NDArray[np.float64]
    beta_plus: NDArray[np.float64]
    mu: NDArray[np.float64]
    sweep_log: list[dict[str, float]] = field(default_factory=list)
    objective_with_plus_penalty: float = float("nan")  # objective - lambda_plus*sum V^+


def beta_weights(episode: Episode, rule: str | ArrayLike) -> NDArray[np.float64]:
    """Return agent penalty shares for a named or explicit beta rule."""

    if not isinstance(rule, str):
        weights = np.asarray(rule, dtype=float)
        if weights.shape != (episode.N,) or np.any(weights < 0):
            raise ValueError("Explicit beta weights must be a non-negative length-N vector")
        return weights
    if rule == "capacity_share":
        return episode.nameplates / episode.nameplates.sum()
    if rule == "equal":
        return np.full(episode.N, 1.0 / episode.N)
    if rule == "full":
        return np.ones(episode.N)
    raise ValueError("beta rule must be 'capacity_share', 'equal', or 'full'")


def _remove_damped_cycles(
    c: NDArray[np.float64],
    d: NDArray[np.float64],
    r: NDArray[np.float64],
    W: NDArray[np.float64],
    eta_c: float,
    eta_d: float,
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """Canonicalize a damped plan without changing injection or SoC."""

    round_trip = eta_c * eta_d
    loss = 1.0 - round_trip
    reduction = np.minimum(c, d / round_trip)
    if loss > 1e-12:
        reduction = np.minimum(reduction, np.maximum(W - r, 0.0) / loss)
    charge = np.maximum(c - reduction, 0.0)
    discharge = np.maximum(d - round_trip * reduction, 0.0)
    curtailment = np.minimum(r + loss * reduction, W)
    return charge, discharge, curtailment


def _agent_payoff(
    episode: Episode,
    i: int,
    q: NDArray[np.float64],
    c: NDArray[np.float64],
    d: NDArray[np.float64],
    r: NDArray[np.float64],
    beta_minus: float,
    beta_plus: float,
    mu: NDArray[np.float64],
    cfg: Mapping[str, Any],
) -> float:
    aggregate = q.sum(axis=0)
    vminus = np.maximum(episode.D - aggregate, 0.0)
    vplus = np.maximum(aggregate - episode.K, 0.0)
    poi = cfg.get("poi", {})
    eps_tiebreak = float(cfg.get("battery", {}).get("eps_tiebreak_usd_per_mwh", 1e-3))
    return float(
        (episode.pi_RT - mu) @ q[i]
        - episode.agents[i].battery.c_deg * d[i].sum()
        - beta_minus * float(poi.get("lambda_minus", 250.0)) * vminus.sum()
        - beta_plus * float(poi.get("lambda_plus", 100.0)) * vplus.sum()
        - eps_tiebreak * (c[i] + d[i] + r[i]).sum()
    )


def solve_game(
    episode: Episode,
    cfg: Mapping[str, Any] | None = None,
    *,
    beta: str | ArrayLike = "capacity_share",
    beta_minus: str | ArrayLike | None = None,
    beta_plus: str | ArrayLike | None = None,
    mu: ArrayLike | None = None,
    initial_soc: ArrayLike | None = None,
    terminal_soc: ArrayLike | None = None,
    initial_plan: Any | None = None,
) -> GameSolution:
    """Compute a damped Gauss--Seidel best-response fixed point.

    Convergence is tested on the *undamped* best-response residual
    ``max |BR_q - q|`` (evaluated against the profile at the moment each agent
    best-responds) relative to total nameplate, not on the damped step, so that
    the tolerance is not halved by damping.  The solution is flagged converged
    only if the residual is below ``game.tol_rel * sum(N)`` and the final
    unilateral-deviation gain is at most ``game.max_gain_tol`` dollars.
    ``max_delta`` reports the undamped residual of the last sweep.
    """

    config = episode.cfg if cfg is None else cfg
    game_cfg = config.get("game", {})
    max_sweeps = int(game_cfg.get("max_sweeps", 200))
    damping = float(game_cfg.get("damping", 0.5))
    if not (0 < damping <= 1):
        raise ValueError("game.damping must lie in (0, 1]")
    tolerance = float(game_cfg.get("tol_rel", 1e-5)) * float(episode.nameplates.sum())
    eps_tiebreak = float(config.get("battery", {}).get("eps_tiebreak_usd_per_mwh", 1e-3))
    bminus = beta_weights(episode, beta if beta_minus is None else beta_minus)
    bplus = beta_weights(episode, beta if beta_plus is None else beta_plus)
    dual_price = np.zeros(episode.T) if mu is None else np.asarray(mu, dtype=float)
    if dual_price.shape != (episode.T,) or np.any(dual_price < -1e-8):
        raise ValueError("mu must be a non-negative length-T vector")
    dual_price = np.maximum(dual_price, 0.0)

    default_soc = np.asarray([agent.battery.soc0 for agent in episode.agents], dtype=float)
    start_soc = default_soc if initial_soc is None else np.asarray(initial_soc, dtype=float)
    target_soc = default_soc if terminal_soc is None else np.asarray(terminal_soc, dtype=float)
    if start_soc.shape != (episode.N,) or target_soc.shape != (episode.N,):
        raise ValueError("initial_soc and terminal_soc must be length-N vectors")

    expected = episode.W.shape
    if initial_plan is None:
        c = np.zeros_like(episode.W)
        d = np.zeros_like(episode.W)
        r = np.zeros_like(episode.W)
    else:
        arrays = [np.asarray(getattr(initial_plan, name), dtype=float) for name in ("c", "d", "r")]
        if any(array.shape != expected for array in arrays):
            raise ValueError(f"initial_plan c, d, r must have shape {expected}")
        c, d, r = (array.copy() for array in arrays)
        r = np.minimum(np.maximum(r, 0.0), episode.W)
    q = episode.W - r - c + d
    models = [AgentLP(agent, episode.T, config) for agent in episode.agents]
    terminal_rule = str(config.get("battery", {}).get("terminal_soc", "return"))
    allow_grid = bool(config.get("battery", {}).get("allow_grid_charging", True))
    profile_feasible = np.asarray(
        [
            battery_is_feasible(
                c[i],
                d[i],
                agent.battery,
                initial_soc=float(start_soc[i]),
                terminal=terminal_rule,
                terminal_soc=float(target_soc[i]),
            )
            and np.all(r[i] >= -1e-8)
            and np.all(r[i] <= episode.W[i] + 1e-8)
            and (allow_grid or np.all(c[i] <= episode.W[i] - r[i] + 1e-8))
            for i, agent in enumerate(episode.agents)
        ],
        dtype=bool,
    )
    history: list[dict[str, float]] = []
    residual_ok = False
    max_delta = np.inf
    sweeps_done = 0

    for sweep in range(1, max_sweeps + 1):
        residual = 0.0
        for i, model in enumerate(models):
            q_other = q.sum(axis=0) - q[i]
            best = model.solve(
                W=episode.W[i],
                prices=episode.pi_RT,
                q_other=q_other,
                K=episode.K,
                D=episode.D,
                beta_minus=float(bminus[i]),
                beta_plus=float(bplus[i]),
                mu=dual_price,
                initial_soc=float(start_soc[i]),
                terminal_soc=float(target_soc[i]),
            )
            residual = max(residual, float(np.max(np.abs(best.q - q[i]))))
            step = damping if profile_feasible[i] else 1.0
            c[i] = (1 - step) * c[i] + step * best.c
            d[i] = (1 - step) * d[i] + step * best.d
            r[i] = (1 - step) * r[i] + step * best.r
            profile_feasible[i] = True
            if eps_tiebreak > 0:
                battery = episode.agents[i].battery
                c[i], d[i], r[i] = _remove_damped_cycles(
                    c[i], d[i], r[i], episode.W[i], battery.eta_c, battery.eta_d
                )
            q[i] = episode.W[i] - r[i] - c[i] + d[i]
        max_delta = residual
        sweeps_done = sweep
        history.append({"sweep": float(sweep), "max_delta": max_delta})
        LOGGER.debug("best-response sweep=%d max_delta=%.6g", sweep, max_delta)
        if max_delta < tolerance:
            residual_ok = True
            break

    aggregate = q.sum(axis=0)
    vminus = np.maximum(episode.D - aggregate, 0.0)
    vplus = np.maximum(aggregate - episode.K, 0.0)
    soc = np.vstack(
        [
            simulate_soc(c[i], d[i], agent.battery, initial_soc=float(start_soc[i]))
            for i, agent in enumerate(episode.agents)
        ]
    )

    max_gain = 0.0
    if bool(game_cfg.get("deviation_check", True)):
        for i, model in enumerate(models):
            current = _agent_payoff(
                episode, i, q, c, d, r, float(bminus[i]), float(bplus[i]), dual_price, config
            )
            deviation = model.solve(
                W=episode.W[i],
                prices=episode.pi_RT,
                q_other=aggregate - q[i],
                K=episode.K,
                D=episode.D,
                beta_minus=float(bminus[i]),
                beta_plus=float(bplus[i]),
                mu=dual_price,
                initial_soc=float(start_soc[i]),
                terminal_soc=float(target_soc[i]),
            )
            max_gain = max(max_gain, deviation.objective - current)
    max_gain = float(max(max_gain, 0.0))
    converged = bool(residual_ok and max_gain <= float(game_cfg.get("max_gain_tol", 1.0)))
    lambda_minus = float(config.get("poi", {}).get("lambda_minus", 250.0))
    lambda_plus = float(config.get("poi", {}).get("lambda_plus", 100.0))
    system_objective = float(
        episode.pi_RT @ aggregate
        - sum(agent.battery.c_deg * d[i].sum() for i, agent in enumerate(episode.agents))
        - lambda_minus * vminus.sum()
    )
    return GameSolution(
        q=q,
        c=c,
        d=d,
        r=r,
        soc=soc,
        Vminus=vminus,
        Vplus=vplus,
        objective=system_objective,
        objective_with_plus_penalty=system_objective - lambda_plus * float(vplus.sum()),
        status="converged" if converged else "max_sweeps",
        converged=converged,
        sweeps=sweeps_done,
        max_delta=max_delta,
        max_gain=max_gain,
        beta_minus=bminus,
        beta_plus=bplus,
        mu=dual_price,
        sweep_log=history,
    )


def solve_r2(
    episode: Episode,
    cfg: Mapping[str, Any] | None = None,
    **solve_kwargs: Any,
) -> GameSolution:
    """Solve the capacity-share selfish game (R2)."""

    return solve_game(episode, cfg, beta="capacity_share", **solve_kwargs)


def solve_r3a(episode: Episode, cfg: Mapping[str, Any] | None = None) -> GameSolution:
    """Solve full-penalty coordination without a dual price (R3a)."""

    return solve_game(episode, cfg, beta="full")


def solve_r3b(
    episode: Episode,
    mu: ArrayLike,
    cfg: Mapping[str, Any] | None = None,
) -> GameSolution:
    """Solve full-penalty coordination with the R1 headroom dual (R3b)."""

    return solve_game(episode, cfg, beta="full", mu=mu)

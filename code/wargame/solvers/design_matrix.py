"""Hourly solvers for the revised four-factor Part I design matrix.

FULL/INJ agents pay their own private shortfall and optimize the exact causal
overflow-share charge, while FULL/EQ retains exact equal-weight system terms.
PRICE and NONE agents cannot observe system shortfall, so they optimize against
private shortfall ``D_i = delta_D * b_i``.  INJ therefore has private shortfall
weight 1 (the agent pays what it causes), while EQ has weight 1/N (the
anticipated equal split); these weights follow the allocation rules rather
than being tuning parameters.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np
from numpy.typing import NDArray

from wargame.experiments.design import parse_cell
from wargame.model.env import Episode
from wargame.solvers.agent_lp import AgentLP, AgentSolution, POIBudget
from wargame.solvers.game import penalty_share_weights, solve_game
from wargame.solvers.receding import (
    _empty_trajectories,
    _realization,
    forecast_subhorizon,
    perfect_subhorizon,
    solve_receding_central,
)
from wargame.solvers.realize import Realization, realize_hour

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class _WarmPlan:
    """A previous FULL solution tail used for the next hourly game."""

    c: NDArray[np.float64]
    d: NDArray[np.float64]
    r: NDArray[np.float64]


@dataclass(slots=True)
class _PriceResult:
    """Executed iterate and diagnostics from one coordinator run."""

    plans: list[AgentSolution]
    mu: NDArray[np.float64]
    iterations: int
    max_overflow: float
    max_mu: float
    converged: bool


def _budget_vector(budget: float, battery: Any, soc: float, remaining: int) -> np.ndarray:
    """Feasible per-hour POI budget: floor hour 0 at max charging, later hours at 0."""

    max_charge = min(battery.P, max(battery.E - soc, 0.0) / battery.eta_c)
    vector = np.full(remaining, max(budget, 0.0))
    vector[0] = max(budget, -max_charge)
    return vector


def _view(episode: Episode, t: int, foresight: str) -> Episode:
    return (
        perfect_subhorizon(episode, t)
        if foresight == "P"
        else forecast_subhorizon(episode, t)
    )


def _private_shortfall_weight(share: str, n_agents: int) -> float:
    return 1.0 if share == "INJ" else 1.0 / n_agents


def _coordinate_price(
    view: Episode,
    config: Mapping[str, Any],
    initial_soc: NDArray[np.float64],
    terminal_soc: NDArray[np.float64],
    share: str,
    mu0: NDArray[np.float64],
) -> _PriceResult:
    """Coordinate price-taking responses by proximal dual ascent.

    The quadratic proximal term stabilizes the fixed-point computation; it is
    a numerical device, not an economic cost, and is omitted from reported
    objectives.
    """

    coordination = config.get("design_matrix", {}).get("price_coordination", {})
    rho0 = float(coordination.get("step_usd_per_mwh_per_mw", 0.5))
    proximal_tau = float(coordination.get("proximal_tau", 0.5))
    step_decay = str(coordination.get("step_decay", "none")).lower()
    max_iterations = int(coordination.get("max_iterations", 60))
    overflow_tolerance = float(coordination.get("overflow_tol_rel", 1e-3)) * float(
        view.nameplates.sum()
    )
    cs_tolerance = float(coordination.get("cs_tol_usd", 1.0))
    if rho0 <= 0 or proximal_tau <= 0 or max_iterations < 1:
        raise ValueError(
            "Price coordination requires positive step, proximal_tau, and max_iterations"
        )
    if step_decay not in {"none", "sqrt"}:
        raise ValueError("price_coordination.step_decay must be 'none' or 'sqrt'")

    mu = np.asarray(mu0, dtype=float).copy()
    if mu.shape != (view.T,):
        raise ValueError(f"mu0 must have shape {(view.T,)}")
    warm_models = [AgentLP(agent, view.T, config) for agent in view.agents]
    models = [
        AgentLP(agent, view.T, config, proximal_tau=proximal_tau)
        for agent in view.agents
    ]
    delta_delivery = float(config.get("poi", {}).get("delta_D", 0.5))
    beta_minus = _private_shortfall_weight(share, view.N)
    best_plans: list[AgentSolution] | None = None
    best_mu = mu.copy()
    best_overflow = np.inf
    best_objective = -np.inf
    converged = False
    iterations = 0

    previous_plans = [
        model.solve(
            W=view.W[i],
            prices=view.pi_RT,
            q_other=np.zeros(view.T),
            K=view.K,
            D=delta_delivery * view.b[i],
            beta_minus=beta_minus,
            beta_plus=0.0,
            mu=mu,
            initial_soc=float(initial_soc[i]),
            terminal_soc=float(terminal_soc[i]),
        )
        for i, model in enumerate(warm_models)
    ]
    previous_aggregate = np.sum([plan.q for plan in previous_plans], axis=0)

    def proximal_responses(price: NDArray[np.float64]) -> list[AgentSolution]:
        return [
            model.solve(
                W=view.W[i],
                prices=view.pi_RT,
                q_other=np.zeros(view.T),
                K=view.K,
                D=delta_delivery * view.b[i],
                beta_minus=beta_minus,
                beta_plus=0.0,
                mu=price,
                initial_soc=float(initial_soc[i]),
                terminal_soc=float(terminal_soc[i]),
                q_reference=previous_plans[i].q,
            )
            for i, model in enumerate(models)
        ]

    for iteration in range(1, max_iterations + 1):
        # A predictor-corrector step supplies the damping missing from the
        # simultaneous primal/dual update on a nonsmooth dispatch problem.
        predictor = proximal_responses(mu)
        predictor_aggregate = np.sum([plan.q for plan in predictor], axis=0)
        step = rho0 if step_decay == "none" else rho0 / np.sqrt(iteration)
        predictor_mu = np.maximum(0.0, mu + step * (predictor_aggregate - view.K))
        plans = proximal_responses(predictor_mu)
        aggregate = np.sum([plan.q for plan in plans], axis=0)
        max_overflow = float(np.max(np.maximum(aggregate - view.K, 0.0)))
        objective = float(sum(plan.objective for plan in plans))
        mu_new = np.maximum(0.0, mu + step * (aggregate - view.K))
        complementarity = float(np.max(mu_new * np.maximum(view.K - aggregate, 0.0)))
        stable = bool(
            np.max(np.abs(mu_new - mu)) <= 0.01
            or np.max(np.abs(aggregate - previous_aggregate)) <= overflow_tolerance
        )
        is_converged = (
            max_overflow <= overflow_tolerance
            and complementarity <= cs_tolerance
            and stable
        )
        if (
            max_overflow < best_overflow - 1e-12
            or (abs(max_overflow - best_overflow) <= 1e-12 and objective > best_objective)
        ):
            best_plans = plans
            best_mu = mu_new.copy()
            best_overflow = max_overflow
            best_objective = objective
        iterations = iteration
        mu = mu_new
        if is_converged:
            converged = True
            best_plans = plans
            best_mu = mu_new.copy()
            best_overflow = max_overflow
            break
        previous_plans = plans
        previous_aggregate = aggregate

    if best_plans is None:  # guarded by max_iterations validation
        raise RuntimeError("Price coordinator produced no iterate")
    return _PriceResult(
        best_plans,
        best_mu,
        iterations,
        best_overflow,
        float(np.max(best_mu)),
        converged,
    )


def _attach_ex_post_shares(
    episode: Episode,
    result: Realization,
    share: str,
) -> Realization:
    rule = "injection" if share == "INJ" else "equal"
    result.w_minus, result.w_plus = penalty_share_weights(episode, result.q, rule)
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
    capacity_shares = episode.nameplates / episode.nameplates.sum()
    delta_delivery = float(config.get("poi", {}).get("delta_D", 0.5))
    private_beta = _private_shortfall_weight(share, episode.N)

    warm_game: _WarmPlan | None = None
    warm_mu: NDArray[np.float64] | None = None
    game_warm_start = bool(config.get("design_matrix", {}).get("game_warm_start", True))
    price_cfg = config.get("design_matrix", {}).get("price_coordination", {})
    price_warm_start = bool(price_cfg.get("warm_start", True))
    sweeps_by_hour: list[int] = []
    game_converged: list[bool] = []
    sweep_log: list[dict[str, float]] = []
    price_iterations: list[int] = []
    price_converged: list[bool] = []
    price_overflow: list[float] = []
    price_max_mu: list[float] = []
    mu_by_hour = np.full((episode.T, episode.T), np.nan)
    all_converged = True
    max_delta = 0.0
    max_gain = 0.0

    for t in range(episode.T):
        view = _view(episode, t, foresight)
        remaining = view.T
        if info == "FULL":
            game = solve_game(
                view,
                config,
                initial_soc=soc[:, t],
                terminal_soc=terminal,
                initial_plan=warm_game if game_warm_start else None,
                share_rule="injection" if share == "INJ" else "equal",
            )
            plans = [
                AgentSolution(
                    q=game.q[i],
                    c=game.c[i],
                    d=game.d[i],
                    r=game.r[i],
                    soc=game.soc[i],
                    Vminus=game.Vminus,
                    Vplus=game.Vplus,
                    objective=float("nan"),
                    base_profit=float("nan"),
                    status=game.status,
                )
                for i in range(episode.N)
            ]
            sweeps_by_hour.append(game.sweeps)
            game_converged.append(game.converged)
            sweep_log.extend({"hour": float(t), **entry} for entry in game.sweep_log)
            all_converged = all_converged and game.converged
            max_delta = max(max_delta, game.max_delta)
            max_gain = max(max_gain, game.max_gain)
            warm_game = _WarmPlan(
                game.c[:, 1:].copy(), game.d[:, 1:].copy(), game.r[:, 1:].copy()
            )
        elif info == "PRICE":
            start_mu = (
                warm_mu
                if price_warm_start and warm_mu is not None
                else np.zeros(remaining, dtype=float)
            )
            price = _coordinate_price(view, config, soc[:, t], terminal, share, start_mu)
            plans = price.plans
            price_iterations.append(price.iterations)
            price_converged.append(price.converged)
            price_overflow.append(price.max_overflow)
            price_max_mu.append(price.max_mu)
            mu_by_hour[t, t:] = price.mu
            warm_mu = price.mu[1:].copy()
            all_converged = all_converged and price.converged
        else:
            plans = []
            for i, agent in enumerate(episode.agents):
                model = AgentLP(agent, remaining, config, enforce_budget=True)
                budget = _budget_vector(
                    float(episode.K * capacity_shares[i]),
                    agent.battery,
                    float(soc[i, t]),
                    remaining,
                )
                plans.append(
                    model.solve(
                        W=view.W[i],
                        prices=view.pi_RT,
                        q_other=np.zeros(remaining),
                        K=episode.K,
                        D=delta_delivery * view.b[i],
                        beta_minus=private_beta,
                        beta_plus=0.0,
                        poi_budget=POIBudget(budget),
                        initial_soc=float(soc[i, t]),
                        terminal_soc=float(terminal[i]),
                    )
                )

        for i, plan in enumerate(plans):
            q_plan[i, t] = plan.q[0]
            c_plan[i, t] = plan.c[0]
            d_plan[i, t] = plan.d[0]
            r_plan[i, t] = plan.r[0]
        q[:, t], c[:, t], d[:, t], r[:, t], soc[:, t + 1], spill[:, t] = realize_hour(
            episode.W[:, t],
            c_plan[:, t],
            d_plan[:, t],
            r_plan[:, t],
            episode.agents,
            soc[:, t],
            episode.K,
        )
        LOGGER.debug("cell=%s day=%s hour=%d", cell_id, episode.day, t)

    result = _realization(
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
        status=cell_id,
        converged=all_converged if info in {"FULL", "PRICE"} else None,
        sweeps_by_hour=sweeps_by_hour if info == "FULL" else None,
        game_converged_by_hour=game_converged if info == "FULL" else None,
        max_delta=max_delta if info == "FULL" else None,
        max_gain=max_gain if info == "FULL" else None,
        sweep_log=sweep_log if info == "FULL" else None,
        price_iterations_by_hour=price_iterations if info == "PRICE" else None,
        price_converged_by_hour=price_converged if info == "PRICE" else None,
        price_max_overflow_by_hour=price_overflow if info == "PRICE" else None,
        price_max_mu_by_hour=price_max_mu if info == "PRICE" else None,
        mu_by_hour=mu_by_hour if info == "PRICE" else None,
    )
    return _attach_ex_post_shares(episode, result, share)


def solve_cell(
    episode: Episode,
    cell_id: str,
    cfg: Mapping[str, Any] | None = None,
) -> Realization:
    """Solve and physically realize one canonical design-matrix cell hourly."""

    factors = parse_cell(cell_id)
    config = episode.cfg if cfg is None else cfg
    if factors["control"] == "C":
        result = solve_receding_central(
            episode,
            config,
            foresight="perfect" if factors["foresight"] == "P" else "forecast",
        )
        result.status = cell_id
        return _attach_ex_post_shares(episode, result, "INJ")
    return _solve_decentralized(
        episode,
        cell_id,
        config,
        factors["foresight"],
        str(factors["share"]),
        str(factors["info"]),
    )

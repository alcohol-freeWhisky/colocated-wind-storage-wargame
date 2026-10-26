"""Episode-level operating metrics for design-matrix cells."""

from __future__ import annotations

from typing import Any

import numpy as np

from wargame.model.env import Episode
from wargame.solvers.game import penalty_share_weights
from wargame.solvers.realize import Realization


def episode_metrics(episode: Episode, solution_or_realisation: Any, regime: str) -> dict[str, Any]:
    """Compute DESIGN.md section 4 operating and penalty-allocation metrics.

    INJ design cells (and central cells, whose primary allocation is INJ) pay
    ``lambda_minus * (D_i-q_i)^+`` per agent.  EQ cells continue to
    allocate the system shortfall through their ex-post weights.  Overflow is
    allocated by the stored ex-post weights in every cell.
    """

    result = solution_or_realisation
    is_realized = isinstance(result, Realization) or hasattr(result, "q_planned")
    q = np.asarray(result.q, dtype=float)
    c = np.asarray(result.c, dtype=float)
    d = np.asarray(result.d, dtype=float)
    r = np.asarray(result.r, dtype=float)
    if is_realized:
        q_plan = np.asarray(result.q_planned, dtype=float)
        c_plan = np.asarray(result.c_planned, dtype=float)
        d_plan = np.asarray(result.d_planned, dtype=float)
        r_plan = np.asarray(result.r_planned, dtype=float)
        vminus_plan = np.asarray(result.Vminus_planned, dtype=float)
        vplus_attempted = np.asarray(result.Vplus_attempted, dtype=float)
    else:
        q_plan, c_plan, d_plan, r_plan = q, c, d, r
        vminus_plan = np.maximum(episode.D - q_plan.sum(axis=0), 0.0)
        vplus_attempted = np.maximum(q_plan.sum(axis=0) - episode.K, 0.0)
    vminus = np.maximum(episode.D - q.sum(axis=0), 0.0)
    vplus = np.maximum(q.sum(axis=0) - episode.K, 0.0)
    costs = np.asarray([agent.battery.c_deg for agent in episode.agents])[:, None]
    individual = (episode.pi_RT[None, :] * q - costs * d).sum(axis=1)
    individual_plan = (episode.pi_RT[None, :] * q_plan - costs * d_plan).sum(axis=1)
    poi = episode.cfg.get("poi", {})
    lambda_minus = float(poi.get("lambda_minus", 250.0))
    lambda_plus = float(poi.get("lambda_plus", 100.0))
    system_profit_realized = float(individual.sum())
    system_profit_planned = float(individual_plan.sum())
    system_objective = float(system_profit_realized - lambda_minus * vminus.sum())
    system_objective_planned = float(
        system_profit_planned
        - lambda_minus * vminus_plan.sum()
        - lambda_plus * vplus_attempted.sum()
    )
    simultaneous = (c > 1e-6) & (d > 1e-6)
    simultaneous_plan = (c_plan > 1e-6) & (d_plan > 1e-6)
    w_minus = getattr(result, "w_minus", None)
    w_plus = getattr(result, "w_plus", None)
    if w_minus is None or w_plus is None:
        w_minus, w_plus = penalty_share_weights(episode, q, "injection")
    else:
        w_minus = np.asarray(w_minus, dtype=float)
        w_plus = np.asarray(w_plus, dtype=float)
    is_injection_cell = str(regime).startswith("C_") or "_INJ_" in str(regime)
    if is_injection_cell:
        private_delivery = float(poi.get("delta_D", 0.5)) * episode.b
        penalty_minus = lambda_minus * np.maximum(private_delivery - q, 0.0).sum(
            axis=1
        )
    else:
        penalty_minus = (w_minus * (lambda_minus * vminus)[None, :]).sum(axis=1)
    penalty_plus = (w_plus * (lambda_plus * vplus_attempted)[None, :]).sum(axis=1)
    total_penalty_minus = float(penalty_minus.sum())
    penalty_concentration = (
        float(penalty_minus.max() / total_penalty_minus)
        if total_penalty_minus > 1e-12
        else 1.0 / episode.N
    )
    metrics = {
        "day": episode.day,
        "regime": regime,
        "system_profit_realized": system_profit_realized,
        "system_profit_planned": system_profit_planned,
        "system_objective": system_objective,
        "system_objective_planned": system_objective_planned,
        "profit_realized": system_profit_realized,
        "profit_planned": system_profit_planned,
        "system_profit": system_profit_realized,
        "per_agent_profit": individual.tolist(),
        "per_agent_profit_planned": individual_plan.tolist(),
        "per_agent_penalty_minus": penalty_minus.tolist(),
        "per_agent_penalty_plus": penalty_plus.tolist(),
        "per_agent_net_profit": (individual - penalty_minus).tolist(),
        "penalty_concentration": penalty_concentration,
        "curtailment_planned_mwh": float(r_plan.sum()),
        "curtailment_realized_mwh": float(r.sum()),
        "throughput_mwh": float((c + d).sum()),
        "under_delivery_mwh": float(vminus.sum()),
        "under_delivery_planned_mwh": float(vminus_plan.sum()),
        "attempted_overflow_mwh": float(vplus_attempted.sum()),
        "attempted_overflow_hours": int(np.count_nonzero(vplus_attempted > 1e-6)),
        "poi_violation_attempted_mwh": float(vplus_attempted.sum()),
        "poi_violation_attempted_hours": int(np.count_nonzero(vplus_attempted > 1e-6)),
        "realized_overflow_mwh": float(vplus.sum()),
        "simultaneous_charge_discharge_hours": int(simultaneous.sum()),
        "simultaneous_charge_discharge_planned_hours": int(simultaneous_plan.sum()),
        "converged": getattr(result, "converged", None),
        "sweeps": getattr(result, "sweeps", None),
        "max_delta": getattr(result, "max_delta", None),
        "max_gain": getattr(result, "max_gain", None),
        "sweeps_by_hour": getattr(result, "sweeps_by_hour", None),
    }
    price_converged = getattr(result, "price_converged_by_hour", None)
    metrics["price_converged_hours_frac"] = (
        float(np.mean(price_converged)) if price_converged else None
    )
    game_converged = getattr(result, "game_converged_by_hour", None)
    metrics["game_converged_hours_frac"] = (
        float(np.mean(game_converged)) if game_converged else None
    )
    if str(regime).startswith("C_"):
        equal_minus, equal_plus = penalty_share_weights(episode, q, "equal")
        metrics["per_agent_penalty_minus_eq"] = (
            equal_minus * (lambda_minus * vminus)[None, :]
        ).sum(axis=1).tolist()
        metrics["per_agent_penalty_plus_eq"] = (
            equal_plus * (lambda_plus * vplus_attempted)[None, :]
        ).sum(axis=1).tolist()
    return metrics

"""Episode metrics for the matched 14-cell operating design."""

from __future__ import annotations

from typing import Any

import numpy as np

from wargame.model.env import Episode
from wargame.solvers.game import penalty_share_weights


def episode_metrics(episode: Episode, result: Any, regime: str) -> dict[str, Any]:
    """Evaluate every cell with the same realized system-value metric."""

    q = np.asarray(result.q, dtype=float)
    c = np.asarray(result.c, dtype=float)
    d = np.asarray(result.d, dtype=float)
    r = np.asarray(result.r, dtype=float)
    q_plan = np.asarray(result.q_planned, dtype=float)
    c_plan = np.asarray(result.c_planned, dtype=float)
    d_plan = np.asarray(result.d_planned, dtype=float)
    r_plan = np.asarray(result.r_planned, dtype=float)
    vplus_attempted = np.maximum(q_plan.sum(axis=0) - episode.K, 0.0)
    vplus_realized = np.maximum(q.sum(axis=0) - episode.K, 0.0)
    costs = np.asarray([agent.battery.c_deg for agent in episode.agents])[:, None]
    individual = (episode.pi_RT[None, :] * q - costs * d).sum(axis=1)
    individual_plan = (episode.pi_RT[None, :] * q_plan - costs * d_plan).sum(axis=1)
    lambda_plus = float(episode.cfg.get("poi", {}).get("lambda_plus", 100.0))
    w_plus = getattr(result, "w_plus", None)
    if w_plus is None:
        rule = "equal" if "_EQ_" in str(regime) else "injection"
        w_plus = penalty_share_weights(episode, q_plan, rule)
    w_plus = np.asarray(w_plus, dtype=float)
    penalty_plus = (w_plus * (lambda_plus * vplus_attempted)[None, :]).sum(axis=1)
    total_penalty = float(penalty_plus.sum())
    simultaneous = (c > 1e-6) & (d > 1e-6)
    simultaneous_plan = (c_plan > 1e-6) & (d_plan > 1e-6)
    info_converged = getattr(result, "information_converged_by_hour", None)
    game_converged = getattr(result, "game_converged_by_hour", None)

    return {
        "day": episode.day,
        "regime": regime,
        "system_objective": float(individual.sum()),
        "system_profit_realized": float(individual.sum()),
        "system_profit_planned": float(individual_plan.sum()),
        "system_objective_planned": float(individual_plan.sum() - lambda_plus * vplus_attempted.sum()),
        "per_agent_profit": individual.tolist(),
        "per_agent_profit_planned": individual_plan.tolist(),
        "per_agent_penalty_plus": penalty_plus.tolist(),
        "per_agent_net_profit": (individual - penalty_plus).tolist(),
        "penalty_concentration": (
            float(penalty_plus.max() / total_penalty)
            if total_penalty > 1e-12 else 1.0 / episode.N
        ),
        "curtailment_planned_mwh": float(r_plan.sum()),
        "curtailment_realized_mwh": float(r.sum()),
        "throughput_mwh": float((c + d).sum()),
        "attempted_overflow_mwh": float(vplus_attempted.sum()),
        "attempted_overflow_hours": int(np.count_nonzero(vplus_attempted > 1e-6)),
        "realized_overflow_mwh": float(vplus_realized.sum()),
        "simultaneous_charge_discharge_hours": int(simultaneous.sum()),
        "simultaneous_charge_discharge_planned_hours": int(simultaneous_plan.sum()),
        "converged": getattr(result, "converged", None),
        "sweeps": getattr(result, "sweeps", None),
        "max_delta": getattr(result, "max_delta", None),
        "max_gain": getattr(result, "max_gain", None),
        "sweeps_by_hour": getattr(result, "sweeps_by_hour", None),
        "information_converged_hours_frac": (
            float(np.mean(info_converged)) if info_converged else None
        ),
        "game_converged_hours_frac": (
            float(np.mean(game_converged)) if game_converged else None
        ),
    }

"""Limited-information receding-horizon policies (R4a and R4b)."""

from __future__ import annotations

from typing import Any, Literal, Mapping

import numpy as np

from wargame.model.env import Episode
from wargame.solvers.agent_lp import AgentLP, POIBudget
from wargame.solvers.game import beta_weights
from wargame.solvers.realize import Realization, realize_hour


def _information_view(
    realized: np.ndarray,
    forecast: np.ndarray,
    t: int,
    option: str,
    name: str,
) -> np.ndarray:
    """Return the remaining-horizon perfect or forecast information view."""

    if option == "perfect":
        return realized[t:].copy()
    if option == "forecast":
        view = forecast[t:].copy()
        view[0] = realized[t]
        return view
    raise ValueError(f"mpc.{name}_info must be 'perfect' or 'forecast'")


def _budget_vector(budget: float, battery: Any, soc: float, remaining: int) -> np.ndarray:
    """Feasible per-hour POI budget: floor hour 0 at max charging, later hours at 0."""

    max_charge = min(battery.P, max(battery.E - soc, 0.0) / battery.eta_c)
    vector = np.full(remaining, max(budget, 0.0))
    vector[0] = max(budget, -max_charge)
    return vector


def solve_mpc(
    episode: Episode,
    cfg: Mapping[str, Any] | None = None,
    *,
    mode: Literal["aggregate", "local"] = "aggregate",
) -> Realization:
    """Execute an R4 policy one hour at a time and realize each joint action.

    Each agent penalises a *private* shortfall against ``D_i = delta_D * b_i``.
    ``mpc.private_shortfall_beta`` selects the weight on that penalty:
    ``game`` (default) uses the same share ``beta_i`` as the R2 game
    (``poi.beta_rule``, capacity share by default) so that marginal shortage
    incentives are comparable across regimes; ``full`` uses ``beta_i = 1``,
    which makes each MPC agent N times more shortage-averse than an R2 agent.

    The R4a POI budget ``max(K - Q_{t-1}, 0) + q_{i,t-1}`` can be negative when
    the agent charged from the grid in t-1.  A bare ``q_i <= negative`` is
    infeasible if the battery cannot charge that much, so the current-hour
    budget is floored at ``-min(P_i, (E_i - soc)/eta_c)`` (grid charging stays
    allowed up to the power and energy headroom, i.e. at least ``-P_i`` is never
    demanded), and the persistence of the budget over later planned hours is
    floored at zero so the plan is never forced to charge every hour.
    """

    if mode not in {"aggregate", "local"}:
        raise ValueError("mode must be 'aggregate' (R4a) or 'local' (R4b)")
    config = episode.cfg if cfg is None else cfg
    n_agents, horizon = episode.N, episode.T
    shares = episode.nameplates / episode.nameplates.sum()
    delta_delivery = float(config.get("poi", {}).get("delta_D", 0.5))
    mpc_cfg = config.get("mpc", {})
    shortfall_rule = str(mpc_cfg.get("private_shortfall_beta", "game"))
    if shortfall_rule == "game":
        shortfall_beta = beta_weights(
            episode, str(config.get("poi", {}).get("beta_rule", "capacity_share"))
        )
    elif shortfall_rule == "full":
        shortfall_beta = np.ones(n_agents)
    else:
        raise ValueError("mpc.private_shortfall_beta must be 'game' or 'full'")
    price_info = str(mpc_cfg.get("price_info", "perfect"))
    wind_info = str(mpc_cfg.get("wind_info", "perfect"))

    q_plan = np.zeros((n_agents, horizon))
    c_plan = np.zeros((n_agents, horizon))
    d_plan = np.zeros((n_agents, horizon))
    r_plan = np.zeros((n_agents, horizon))
    q = np.zeros((n_agents, horizon))
    c = np.zeros((n_agents, horizon))
    d = np.zeros((n_agents, horizon))
    r = np.zeros((n_agents, horizon))
    spill = np.zeros((n_agents, horizon))
    soc = np.zeros((n_agents, horizon + 1))
    soc[:, 0] = [agent.battery.soc0 for agent in episode.agents]

    for t in range(horizon):
        remaining = horizon - t
        if t == 0 or mode == "local":
            budgets = episode.K * shares
        else:
            prior_total = float(q[:, t - 1].sum())
            budgets = np.maximum(episode.K - prior_total, 0.0) + q[:, t - 1]

        for i, agent in enumerate(episode.agents):
            wind_view = _information_view(
                episode.W[i], episode.What[i], t, wind_info, "wind"
            )
            price_view = _information_view(
                episode.pi_RT, episode.pi_DA, t, price_info, "price"
            )
            private_delivery = delta_delivery * episode.b[i, t:]
            model = AgentLP(agent, remaining, config, enforce_budget=True)
            plan = model.solve(
                W=wind_view,
                prices=price_view,
                q_other=np.zeros(remaining),
                K=episode.K,
                D=private_delivery,
                beta_minus=float(shortfall_beta[i]),
                beta_plus=1.0,
                poi_budget=POIBudget(_budget_vector(float(budgets[i]), agent.battery, soc[i, t], remaining)),
                initial_soc=float(soc[i, t]),
                terminal_soc=agent.battery.soc0,
            )
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

    aggregate_plan = q_plan.sum(axis=0)
    aggregate = q.sum(axis=0)
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
        Vminus=np.maximum(episode.D - aggregate, 0.0),
        Vminus_planned=np.maximum(episode.D - aggregate_plan, 0.0),
        Vplus=np.maximum(aggregate - episode.K, 0.0),
        Vplus_attempted=np.maximum(aggregate_plan - episode.K, 0.0),
        profit=(episode.pi_RT[None, :] * q - costs * d).sum(axis=1),
        profit_planned=(episode.pi_RT[None, :] * q_plan - costs * d_plan).sum(axis=1),
        spill=spill,
        status="R4a" if mode == "aggregate" else "R4b",
    )


def solve_r4a(episode: Episode, cfg: Mapping[str, Any] | None = None) -> Realization:
    """Run aggregate-headroom MPC (R4a)."""

    return solve_mpc(episode, cfg, mode="aggregate")


def solve_r4b(episode: Episode, cfg: Mapping[str, Any] | None = None) -> Realization:
    """Run fixed local-budget MPC (R4b)."""

    return solve_mpc(episode, cfg, mode="local")

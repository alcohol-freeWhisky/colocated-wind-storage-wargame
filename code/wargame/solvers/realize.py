"""Physical POI realization of planned decentralized dispatches."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from wargame.model.env import Episode
from wargame.model.physics import Agent


@dataclass(slots=True)
class Realization:
    """Planned-versus-realized trajectories and economic outcomes."""

    q: NDArray[np.float64]
    c: NDArray[np.float64]
    d: NDArray[np.float64]
    r: NDArray[np.float64]
    soc: NDArray[np.float64]
    q_planned: NDArray[np.float64]
    c_planned: NDArray[np.float64]
    d_planned: NDArray[np.float64]
    r_planned: NDArray[np.float64]
    Vminus: NDArray[np.float64]
    Vminus_planned: NDArray[np.float64]
    Vplus: NDArray[np.float64]
    Vplus_attempted: NDArray[np.float64]
    profit: NDArray[np.float64]
    profit_planned: NDArray[np.float64]
    spill: NDArray[np.float64]
    status: str = "realized"
    converged: bool | None = None
    sweeps: int | None = None
    max_delta: float | None = None
    max_gain: float | None = None
    sweeps_by_hour: list[int] | None = None
    game_converged_by_hour: list[bool] | None = None
    sweep_log: list[dict[str, float]] | None = None
    price_iterations_by_hour: list[int] | None = None
    price_converged_by_hour: list[bool] | None = None
    price_max_overflow_by_hour: list[float] | None = None
    price_max_mu_by_hour: list[float] | None = None
    mu_by_hour: NDArray[np.float64] | None = None
    w_minus: NDArray[np.float64] | None = None
    w_plus: NDArray[np.float64] | None = None

    @property
    def objective(self) -> float:
        """Realized agent energy profit before shared penalties."""

        return float(self.profit.sum())


def realize_hour(
    W: ArrayLike,
    c_plan: ArrayLike,
    d_plan: ArrayLike,
    r_plan: ArrayLike,
    agents: list[Agent],
    soc_start: ArrayLike,
    K: float,
    *,
    tol: float = 1e-9,
) -> tuple[
    NDArray[np.float64],
    NDArray[np.float64],
    NDArray[np.float64],
    NDArray[np.float64],
    NDArray[np.float64],
    NDArray[np.float64],
]:
    """Realize one hour, enforcing battery bounds and the aggregate POI cap."""

    wind = np.asarray(W, dtype=float)
    charge = np.maximum(np.asarray(c_plan, dtype=float), 0.0).copy()
    discharge = np.maximum(np.asarray(d_plan, dtype=float), 0.0).copy()
    curtail = np.maximum(np.asarray(r_plan, dtype=float), 0.0).copy()
    start = np.asarray(soc_start, dtype=float)
    n_agents = len(agents)
    if any(array.shape != (n_agents,) for array in (wind, charge, discharge, curtail, start)):
        raise ValueError("Hourly realization inputs must be length-N vectors")

    soc_next = np.empty(n_agents)
    for i, agent in enumerate(agents):
        battery = agent.battery
        charge[i] = min(charge[i], battery.P)
        discharge[i] = min(discharge[i], battery.P)
        curtail[i] = min(curtail[i], wind[i])
        trial = start[i] + battery.eta_c * charge[i] - discharge[i] / battery.eta_d
        if trial < 0:
            discharge[i] = battery.eta_d * (start[i] + battery.eta_c * charge[i])
        trial = start[i] + battery.eta_c * charge[i] - discharge[i] / battery.eta_d
        if trial > battery.E:
            charge[i] = max((battery.E - start[i] + discharge[i] / battery.eta_d) / battery.eta_c, 0.0)
        soc_next[i] = start[i] + battery.eta_c * charge[i] - discharge[i] / battery.eta_d

    q = wind - curtail - charge + discharge
    overflow = max(float(q.sum()) - float(K), 0.0)
    spill = np.zeros(n_agents)
    if overflow > tol:
        positive = np.maximum(q, 0.0)
        if positive.sum() <= tol:
            raise RuntimeError("Positive POI overflow has no positive exporter")
        # The controller's required reduction is exactly pro-rata in positive q.
        cuts = overflow * positive / positive.sum()
        for i, cut in enumerate(cuts):
            wind_cut = min(float(cut), max(wind[i] - curtail[i], 0.0))
            curtail[i] += wind_cut
            remaining = float(cut) - wind_cut
            if remaining <= tol:
                continue
            battery = agents[i].battery
            headroom_reduction = max(battery.eta_d * (battery.E - soc_next[i]), 0.0)
            discharge_cut = min(remaining, discharge[i], headroom_reduction)
            discharge[i] -= discharge_cut
            soc_next[i] += discharge_cut / battery.eta_d
            # This rare fallback represents inverter-side dissipation when an
            # already-full battery cannot retain all curtailed discharge.
            spill[i] = max(remaining - discharge_cut, 0.0)
        q = wind - curtail - charge + discharge - spill

    q[np.abs(q) < tol] = 0.0
    soc_next = np.asarray(
        [np.clip(soc_next[i], 0.0, agent.battery.E) for i, agent in enumerate(agents)]
    )
    if q.sum() > K + 1e-6:
        raise RuntimeError(f"POI realization failed: export {q.sum()} exceeds K={K}")
    return q, charge, discharge, curtail, soc_next, spill


def realize(episode: Episode, plan: Any) -> Realization:
    """Apply the physical realization layer to a complete planned profile."""

    q_plan = np.asarray(plan.q, dtype=float)
    c_plan = np.asarray(plan.c, dtype=float)
    d_plan = np.asarray(plan.d, dtype=float)
    r_plan = np.asarray(plan.r, dtype=float)
    expected = (episode.N, episode.T)
    if any(array.shape != expected for array in (q_plan, c_plan, d_plan, r_plan)):
        raise ValueError(f"Planned q, c, d, r must all have shape {expected}")

    q = np.zeros(expected)
    c = np.zeros(expected)
    d = np.zeros(expected)
    r = np.zeros(expected)
    spill = np.zeros(expected)
    soc = np.zeros((episode.N, episode.T + 1))
    soc[:, 0] = [agent.battery.soc0 for agent in episode.agents]
    for t in range(episode.T):
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
    degradation = np.asarray([agent.battery.c_deg for agent in episode.agents])[:, None]
    profit = episode.pi_RT[None, :] * q - degradation * d
    profit_plan = episode.pi_RT[None, :] * q_plan - degradation * d_plan
    return Realization(
        q=q,
        c=c,
        d=d,
        r=r,
        soc=soc,
        q_planned=q_plan.copy(),
        c_planned=c_plan.copy(),
        d_planned=d_plan.copy(),
        r_planned=r_plan.copy(),
        Vminus=np.maximum(episode.D - aggregate, 0.0),
        Vminus_planned=np.maximum(episode.D - aggregate_plan, 0.0),
        Vplus=np.maximum(aggregate - episode.K, 0.0),
        Vplus_attempted=np.maximum(aggregate_plan - episode.K, 0.0),
        profit=profit.sum(axis=1),
        profit_planned=profit_plan.sum(axis=1),
        spill=spill,
        converged=getattr(plan, "converged", None),
        sweeps=getattr(plan, "sweeps", None),
        max_delta=getattr(plan, "max_delta", None),
        max_gain=getattr(plan, "max_gain", None),
    )


realize_solution = realize

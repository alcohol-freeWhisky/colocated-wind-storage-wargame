"""Centralized perfect-foresight dispatch (regime R1)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import cvxpy as cp
import numpy as np
from numpy.typing import NDArray

from wargame.model.env import Episode


OPTIMAL_STATUSES = {cp.OPTIMAL, cp.OPTIMAL_INACCURATE}


@dataclass(slots=True)
class Solution:
    """Dispatch and diagnostics returned by the centralized LP."""

    q: NDArray[np.float64]
    c: NDArray[np.float64]
    d: NDArray[np.float64]
    r: NDArray[np.float64]
    soc: NDArray[np.float64]
    Vminus: NDArray[np.float64]
    Vplus: NDArray[np.float64]
    objective: float
    status: str
    duals: NDArray[np.float64]
    solve_time: float | None = None

    @property
    def mu(self) -> NDArray[np.float64]:
        """POI shadow price, exposed under the notation used in the proposal."""

        return self.duals


def solver_name(cfg: Mapping[str, Any]) -> str:
    """Resolve the configured cvxpy LP solver."""

    setting = cfg.get("solver", "HIGHS")
    if isinstance(setting, Mapping):
        setting = setting.get("name", "HIGHS")
    name = str(setting).upper()
    installed = set(cp.installed_solvers())
    if name not in installed:
        for fallback in ("HIGHS", "CLARABEL"):
            if fallback in installed:
                return fallback
        raise RuntimeError("Neither configured solver nor HiGHS/CLARABEL is installed")
    return name


class CentralLP:
    """Reusable DPP-parametrized centralized LP for fixed agents and horizon."""

    def __init__(self, episode: Episode, cfg: Mapping[str, Any] | None = None) -> None:
        self.episode = episode
        self.cfg = dict(episode.cfg if cfg is None else cfg)
        n_agents, horizon = episode.N, episode.T
        self.pi = cp.Parameter(horizon, name="pi")
        self.W = cp.Parameter((n_agents, horizon), nonneg=True, name="W")
        self.K = cp.Parameter(nonneg=True, name="K")
        self.D = cp.Parameter(horizon, nonneg=True, name="D")
        self.initial_soc = [
            cp.Parameter(nonneg=True, name=f"initial_soc_{i}") for i in range(n_agents)
        ]
        self.terminal_soc = [
            cp.Parameter(nonneg=True, name=f"terminal_soc_{i}") for i in range(n_agents)
        ]

        self.c_var = cp.Variable((n_agents, horizon), nonneg=True, name="c")
        self.d_var = cp.Variable((n_agents, horizon), nonneg=True, name="d")
        self.r_var = cp.Variable((n_agents, horizon), nonneg=True, name="r")
        self.soc_var = cp.Variable((n_agents, horizon + 1), name="soc")
        self.vminus_var = cp.Variable(horizon, nonneg=True, name="Vminus")
        self.q_expr = self.W - self.r_var - self.c_var + self.d_var
        total_q = cp.sum(self.q_expr, axis=0)

        constraints: list[cp.Constraint] = [
            self.r_var <= self.W,
            self.soc_var >= 0,
        ]
        for i, agent in enumerate(episode.agents):
            battery = agent.battery
            constraints.extend(
                [
                    self.c_var[i] <= battery.P,
                    self.d_var[i] <= battery.P,
                    self.soc_var[i] <= battery.E,
                    self.soc_var[i, 0] == self.initial_soc[i],
                    self.soc_var[i, 1:]
                    == self.soc_var[i, :-1]
                    + battery.eta_c * self.c_var[i]
                    - self.d_var[i] / battery.eta_d,
                ]
            )
            if not self.cfg.get("battery", {}).get("allow_grid_charging", True):
                constraints.append(self.c_var[i] <= self.W[i] - self.r_var[i])
            if self.cfg.get("battery", {}).get("terminal_soc", "return") == "return":
                constraints.append(self.soc_var[i, -1] >= self.terminal_soc[i])
        self.poi_constraint = total_q <= self.K
        constraints.extend([self.poi_constraint, self.vminus_var >= self.D - total_q])

        degradation = sum(
            (agent.battery.c_deg * cp.sum(self.d_var[i]) for i, agent in enumerate(episode.agents)),
            cp.Constant(0.0),
        )
        eps_tiebreak = float(
            self.cfg.get("battery", {}).get("eps_tiebreak_usd_per_mwh", 1e-3)
        )
        if eps_tiebreak < 0:
            raise ValueError("battery.eps_tiebreak_usd_per_mwh must be non-negative")
        activity = cp.sum(self.c_var + self.d_var + self.r_var)
        lambda_minus = float(self.cfg.get("poi", {}).get("lambda_minus", 250.0))
        # pi * W is constant in the decisions. Omitting that parameter-times-
        # parameter term keeps the model DPP; solve() adds it back to welfare.
        dispatch_delta = -self.r_var - self.c_var + self.d_var
        objective = cp.Maximize(
            cp.sum(cp.multiply(self.pi, dispatch_delta))
            - degradation
            - lambda_minus * cp.sum(self.vminus_var)
            - eps_tiebreak * activity
        )
        self.problem = cp.Problem(objective, constraints)
        if not self.problem.is_dpp():
            raise RuntimeError("Central LP construction is not DPP")

    def solve(
        self,
        *,
        pi: NDArray[np.float64] | None = None,
        W: NDArray[np.float64] | None = None,
        K: float | None = None,
        D: NDArray[np.float64] | None = None,
        initial_soc: NDArray[np.float64] | None = None,
        terminal_soc: NDArray[np.float64] | None = None,
        warm_start: bool = True,
    ) -> Solution:
        """Solve for supplied parameter values or the constructor episode values."""

        episode = self.episode
        self.pi.value = episode.pi_RT if pi is None else np.asarray(pi, dtype=float)
        self.W.value = episode.W if W is None else np.asarray(W, dtype=float)
        self.K.value = episode.K if K is None else float(K)
        self.D.value = episode.D if D is None else np.asarray(D, dtype=float)
        default_soc = np.asarray([agent.battery.soc0 for agent in episode.agents], dtype=float)
        start = default_soc if initial_soc is None else np.asarray(initial_soc, dtype=float)
        target = default_soc if terminal_soc is None else np.asarray(terminal_soc, dtype=float)
        if start.shape != (episode.N,) or target.shape != (episode.N,):
            raise ValueError("initial_soc and terminal_soc must be length-N vectors")
        capacities = np.asarray([agent.battery.E for agent in episode.agents], dtype=float)
        if np.any(start < 0) or np.any(start > capacities):
            raise ValueError("initial_soc must lie within each battery's bounds")
        if np.any(target < 0) or np.any(target > capacities):
            raise ValueError("terminal_soc must lie within each battery's bounds")
        for i in range(episode.N):
            self.initial_soc[i].value = float(start[i])
            self.terminal_soc[i].value = float(target[i])
        self.problem.solve(solver=solver_name(self.cfg), warm_start=warm_start)
        if self.problem.status not in OPTIMAL_STATUSES:
            raise RuntimeError(f"Central LP failed with status {self.problem.status}")
        q = np.asarray(self.q_expr.value, dtype=float)
        vminus = np.maximum(np.asarray(self.vminus_var.value, dtype=float), 0.0)
        charge = np.maximum(np.asarray(self.c_var.value, dtype=float), 0.0)
        discharge = np.maximum(np.asarray(self.d_var.value, dtype=float), 0.0)
        curtailment = np.maximum(np.asarray(self.r_var.value, dtype=float), 0.0)
        lambda_minus = float(self.cfg.get("poi", {}).get("lambda_minus", 250.0))
        objective = float(
            np.asarray(self.pi.value) @ q.sum(axis=0)
            - sum(
                agent.battery.c_deg * discharge[i].sum()
                for i, agent in enumerate(episode.agents)
            )
            - lambda_minus * vminus.sum()
        )
        return Solution(
            q=q,
            c=charge,
            d=discharge,
            r=curtailment,
            soc=np.clip(
                np.asarray(self.soc_var.value, dtype=float),
                0.0,
                np.asarray([agent.battery.E for agent in episode.agents])[:, None],
            ),
            Vminus=vminus,
            Vplus=np.maximum(q.sum(axis=0) - float(self.K.value), 0.0),
            objective=objective,
            status=str(self.problem.status),
            duals=np.maximum(np.asarray(self.poi_constraint.dual_value, dtype=float), 0.0),
            solve_time=self.problem.solver_stats.solve_time,
        )


def solve_central(
    episode: Episode,
    cfg: Mapping[str, Any] | None = None,
    **solve_kwargs: Any,
) -> Solution:
    """Build and solve regime R1."""

    return CentralLP(episode, cfg).solve(**solve_kwargs)


# A short alias is convenient in notebooks and preserves a conventional API.
solve = solve_central

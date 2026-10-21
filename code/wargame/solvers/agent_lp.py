"""Reusable single-agent LP for games and receding-horizon control."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import cvxpy as cp
import numpy as np
from numpy.typing import ArrayLike, NDArray

from wargame.model.physics import Agent
from wargame.solvers.central import OPTIMAL_STATUSES, solver_name


@dataclass(frozen=True, slots=True)
class POIBudget:
    """Per-hour private export limit used by limited-information regimes."""

    limit: float | ArrayLike


@dataclass(slots=True)
class AgentSolution:
    """Single-agent physical plan and optimization diagnostics."""

    q: NDArray[np.float64]
    c: NDArray[np.float64]
    d: NDArray[np.float64]
    r: NDArray[np.float64]
    soc: NDArray[np.float64]
    Vminus: NDArray[np.float64]
    Vplus: NDArray[np.float64]
    objective: float
    base_profit: float
    status: str


def _vector(value: float | ArrayLike, horizon: int, name: str) -> NDArray[np.float64]:
    array = np.asarray(value, dtype=float)
    if array.ndim == 0:
        return np.full(horizon, float(array))
    if array.shape != (horizon,):
        raise ValueError(f"{name} must be scalar or length {horizon}")
    return array


class AgentLP:
    """DPP-parametrized best-response LP for one fixed battery and horizon."""

    def __init__(
        self,
        agent: Agent,
        horizon: int,
        cfg: Mapping[str, Any],
        *,
        enforce_budget: bool = False,
    ) -> None:
        self.agent = agent
        self.horizon = int(horizon)
        self.cfg = dict(cfg)
        self.enforce_budget = enforce_budget
        battery = agent.battery

        self.pi = cp.Parameter(horizon, name="pi")
        self.W = cp.Parameter(horizon, nonneg=True, name="W")
        self.q_other = cp.Parameter(horizon, name="q_other")
        self.K = cp.Parameter(nonneg=True, name="K")
        self.D = cp.Parameter(horizon, nonneg=True, name="D")
        self.beta_minus = cp.Parameter(nonneg=True, name="beta_minus")
        self.beta_plus = cp.Parameter(nonneg=True, name="beta_plus")
        self.mu = cp.Parameter(horizon, nonneg=True, name="mu")
        self.initial_soc = cp.Parameter(nonneg=True, name="initial_soc")
        self.terminal_min = cp.Parameter(nonneg=True, name="terminal_min")
        if enforce_budget:
            self.budget = cp.Parameter(horizon, name="budget")

        self.c_var = cp.Variable(horizon, nonneg=True, name="c")
        self.d_var = cp.Variable(horizon, nonneg=True, name="d")
        self.r_var = cp.Variable(horizon, nonneg=True, name="r")
        self.soc_var = cp.Variable(horizon + 1, name="soc")
        self.vminus_var = cp.Variable(horizon, nonneg=True, name="Vminus")
        self.vplus_var = cp.Variable(horizon, nonneg=True, name="Vplus")
        self.q_expr = self.W - self.r_var - self.c_var + self.d_var
        aggregate = self.q_expr + self.q_other

        constraints: list[cp.Constraint] = [
            self.r_var <= self.W,
            self.c_var <= battery.P,
            self.d_var <= battery.P,
            self.soc_var >= 0,
            self.soc_var <= battery.E,
            self.soc_var[0] == self.initial_soc,
            self.soc_var[1:]
            == self.soc_var[:-1] + battery.eta_c * self.c_var - self.d_var / battery.eta_d,
            self.vminus_var >= self.D - aggregate,
            self.vplus_var >= aggregate - self.K,
        ]
        if self.cfg.get("battery", {}).get("terminal_soc", "return") == "return":
            constraints.append(self.soc_var[-1] >= self.terminal_min)
        if not self.cfg.get("battery", {}).get("allow_grid_charging", True):
            constraints.append(self.c_var <= self.W - self.r_var)
        if enforce_budget:
            constraints.append(self.q_expr <= self.budget)

        poi = self.cfg.get("poi", {})
        lambda_minus = float(poi.get("lambda_minus", 250.0))
        lambda_plus = float(poi.get("lambda_plus", 100.0))
        self.eps_tiebreak = float(
            self.cfg.get("battery", {}).get("eps_tiebreak_usd_per_mwh", 1e-3)
        )
        if self.eps_tiebreak < 0:
            raise ValueError("battery.eps_tiebreak_usd_per_mwh must be non-negative")
        # The W component of q is constant in the decisions. Removing it from
        # the objective avoids a parameter-times-parameter term and preserves DPP.
        dispatch_delta = -self.r_var - self.c_var + self.d_var
        activity = cp.sum(self.c_var + self.d_var + self.r_var)
        objective = cp.Maximize(
            cp.sum(cp.multiply(self.pi - self.mu, dispatch_delta))
            - battery.c_deg * cp.sum(self.d_var)
            - lambda_minus * self.beta_minus * cp.sum(self.vminus_var)
            - lambda_plus * self.beta_plus * cp.sum(self.vplus_var)
            - self.eps_tiebreak * activity
        )
        self.problem = cp.Problem(objective, constraints)
        if not self.problem.is_dpp():
            raise RuntimeError("Agent LP construction is not DPP")

    def solve(
        self,
        *,
        W: ArrayLike,
        prices: ArrayLike,
        q_other: ArrayLike | None = None,
        K: float,
        D: ArrayLike,
        beta_minus: float = 0.0,
        beta_plus: float = 0.0,
        mu: ArrayLike | None = None,
        poi_budget: POIBudget | float | ArrayLike | None = None,
        initial_soc: float | None = None,
        terminal_soc: float | None = None,
        warm_start: bool = True,
    ) -> AgentSolution:
        """Solve one best response for the supplied horizon data."""

        horizon = self.horizon
        wind = _vector(W, horizon, "W")
        price = _vector(prices, horizon, "prices")
        others = np.zeros(horizon) if q_other is None else _vector(q_other, horizon, "q_other")
        delivery = _vector(D, horizon, "D")
        dual_price = np.zeros(horizon) if mu is None else _vector(mu, horizon, "mu")
        start = self.agent.battery.soc0 if initial_soc is None else float(initial_soc)
        target = start if terminal_soc is None else float(terminal_soc)

        self.W.value = wind
        self.pi.value = price
        self.q_other.value = others
        self.K.value = float(K)
        self.D.value = delivery
        self.beta_minus.value = float(beta_minus)
        self.beta_plus.value = float(beta_plus)
        self.mu.value = dual_price
        self.initial_soc.value = start
        self.terminal_min.value = target
        if self.enforce_budget:
            if poi_budget is None:
                budget_value = wind + self.agent.battery.P
            else:
                raw = poi_budget.limit if isinstance(poi_budget, POIBudget) else poi_budget
                budget_value = _vector(raw, horizon, "poi_budget")
            self.budget.value = budget_value
        elif poi_budget is not None:
            raise ValueError("This AgentLP was constructed without a POI budget constraint")

        self.problem.solve(solver=solver_name(self.cfg), warm_start=warm_start)
        if self.problem.status not in OPTIMAL_STATUSES:
            raise RuntimeError(f"Agent LP failed with status {self.problem.status}")
        q = np.asarray(self.q_expr.value, dtype=float)
        discharge = np.maximum(np.asarray(self.d_var.value, dtype=float), 0.0)
        vminus = np.maximum(np.asarray(self.vminus_var.value, dtype=float), 0.0)
        vplus = np.maximum(np.asarray(self.vplus_var.value, dtype=float), 0.0)
        poi = self.cfg.get("poi", {})
        economic_objective = float(
            (price - dual_price) @ q
            - self.agent.battery.c_deg * discharge.sum()
            - float(poi.get("lambda_minus", 250.0)) * beta_minus * vminus.sum()
            - float(poi.get("lambda_plus", 100.0)) * beta_plus * vplus.sum()
        )
        charge = np.maximum(np.asarray(self.c_var.value, dtype=float), 0.0)
        curtailment = np.maximum(np.asarray(self.r_var.value, dtype=float), 0.0)
        return AgentSolution(
            q=q,
            c=charge,
            d=discharge,
            r=curtailment,
            soc=np.clip(np.asarray(self.soc_var.value, dtype=float), 0.0, self.agent.battery.E),
            Vminus=vminus,
            Vplus=vplus,
            objective=economic_objective
            - self.eps_tiebreak * float((charge + discharge + curtailment).sum()),
            base_profit=float(price @ q - self.agent.battery.c_deg * discharge.sum()),
            status=str(self.problem.status),
        )


def solve_agent(
    agent: Agent,
    *,
    W: ArrayLike,
    prices: ArrayLike,
    K: float,
    D: ArrayLike,
    cfg: Mapping[str, Any],
    q_other: ArrayLike | None = None,
    beta_minus: float = 0.0,
    beta_plus: float = 0.0,
    mu: ArrayLike | None = None,
    poi_budget: POIBudget | float | ArrayLike | None = None,
    initial_soc: float | None = None,
    terminal_soc: float | None = None,
) -> AgentSolution:
    """Convenience wrapper for a one-off single-agent solve."""

    horizon = np.asarray(W).size
    model = AgentLP(agent, horizon, cfg, enforce_budget=poi_budget is not None)
    return model.solve(
        W=W,
        prices=prices,
        q_other=q_other,
        K=K,
        D=D,
        beta_minus=beta_minus,
        beta_plus=beta_plus,
        mu=mu,
        poi_budget=poi_budget,
        initial_soc=initial_soc,
        terminal_soc=terminal_soc,
    )


solve = solve_agent

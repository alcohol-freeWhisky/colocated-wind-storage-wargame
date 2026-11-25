"""Reusable single-owner best response for the operating game."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping

import cvxpy as cp
import numpy as np
from numpy.typing import ArrayLike, NDArray

from wargame.model.physics import Agent
from wargame.solvers.central import OPTIMAL_STATUSES, solver_name


@dataclass(slots=True)
class AgentSolution:
    """One owner's planned dispatch and economic payoff."""

    q: NDArray[np.float64]
    c: NDArray[np.float64]
    d: NDArray[np.float64]
    r: NDArray[np.float64]
    soc: NDArray[np.float64]
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
    """DPP-parametrized owner best response.

    Equal sharing charges one fixed fraction of aggregate attempted overflow.
    Causal sharing charges the exact positive-injection share. Both use the
    same physical constraints, prices, and total overflow rate.
    """

    def __init__(
        self,
        agent: Agent,
        horizon: int,
        cfg: Mapping[str, Any],
        *,
        overflow_mode: Literal["shared", "causal"] = "shared",
    ) -> None:
        if overflow_mode not in {"shared", "causal"}:
            raise ValueError("overflow_mode must be 'shared' or 'causal'")
        self.agent = agent
        self.horizon = int(horizon)
        self.cfg = dict(cfg)
        self.overflow_mode = overflow_mode
        self.overflow_scale = max(float(agent.nameplate), 1.0)
        battery = agent.battery

        self.pi = cp.Parameter(horizon, name="pi")
        self.W = cp.Parameter(horizon, nonneg=True, name="W")
        self.q_other = cp.Parameter(horizon, name="q_other")
        self.K = cp.Parameter(nonneg=True, name="K")
        self.beta_plus = cp.Parameter(horizon, nonneg=True, name="beta_plus")
        self.initial_soc = cp.Parameter(nonneg=True, name="initial_soc")
        self.terminal_min = cp.Parameter(nonneg=True, name="terminal_min")
        if overflow_mode == "causal":
            self.others_positive = cp.Parameter(horizon, nonneg=True, name="P_other")
            self.overflow_c = cp.Parameter(horizon, nonneg=True, name="overflow_c")
            self.overflow_m = cp.Parameter(horizon, nonneg=True, name="overflow_m")

        self.c_var = cp.Variable(horizon, nonneg=True, name="c")
        self.d_var = cp.Variable(horizon, nonneg=True, name="d")
        self.r_var = cp.Variable(horizon, nonneg=True, name="r")
        self.soc_var = cp.Variable(horizon + 1, name="soc")
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
            self.vplus_var >= aggregate - self.K,
        ]
        if not self.cfg.get("battery", {}).get("allow_grid_charging", False):
            constraints.append(self.c_var <= self.W - self.r_var)
        if self.cfg.get("battery", {}).get("terminal_soc", "return") == "return":
            constraints.append(self.soc_var[-1] >= self.terminal_min)

        if overflow_mode == "causal":
            self.positive_q_var = cp.Variable(horizon, nonneg=True, name="positive_q")
            self.positive_total_var = cp.Variable(horizon, nonneg=True, name="positive_total")
            constraints.extend(
                [
                    self.positive_q_var >= self.q_expr,
                    self.positive_total_var == self.positive_q_var + self.others_positive,
                ]
            )

        lambda_plus = float(self.cfg.get("poi", {}).get("lambda_plus", 100.0))
        self.eps_tiebreak = float(
            self.cfg.get("battery", {}).get("eps_tiebreak_usd_per_mwh", 1e-3)
        )
        dispatch_delta = -self.r_var - self.c_var + self.d_var
        if overflow_mode == "causal":
            overflow_charge = lambda_plus * cp.sum(
                cp.pos(
                    self.positive_q_var
                    - self.overflow_c
                    + cp.multiply(
                        self.overflow_m,
                        cp.inv_pos(self.positive_total_var / self.overflow_scale),
                    )
                )
            )
        else:
            overflow_charge = lambda_plus * cp.sum(
                cp.multiply(self.beta_plus, self.vplus_var)
            )
        activity = cp.sum(self.c_var + self.d_var + self.r_var)
        self.problem = cp.Problem(
            cp.Maximize(
                cp.sum(cp.multiply(self.pi, dispatch_delta))
                - battery.c_deg * cp.sum(self.d_var)
                - overflow_charge
                - self.eps_tiebreak * activity
            ),
            constraints,
        )
        if not self.problem.is_dpp():
            raise RuntimeError("Agent problem is not DPP")

    def solve(
        self,
        *,
        W: ArrayLike,
        prices: ArrayLike,
        K: float,
        q_other: ArrayLike | None = None,
        beta_plus: float | ArrayLike = 0.0,
        initial_soc: float | None = None,
        terminal_soc: float | None = None,
        others_positive: ArrayLike | None = None,
        others_sum: ArrayLike | None = None,
        warm_start: bool = True,
    ) -> AgentSolution:
        horizon = self.horizon
        wind = _vector(W, horizon, "W")
        price = _vector(prices, horizon, "prices")
        others = np.zeros(horizon) if q_other is None else _vector(q_other, horizon, "q_other")
        plus_weight = _vector(beta_plus, horizon, "beta_plus")
        if np.any(plus_weight < 0):
            raise ValueError("beta_plus must be non-negative")
        start = self.agent.battery.soc0 if initial_soc is None else float(initial_soc)
        target = start if terminal_soc is None else float(terminal_soc)

        self.W.value = wind
        self.pi.value = price
        self.q_other.value = others
        self.K.value = float(K)
        self.beta_plus.value = plus_weight
        self.initial_soc.value = start
        self.terminal_min.value = target

        positive_others: NDArray[np.float64] | None = None
        if self.overflow_mode == "causal":
            if others_positive is None or others_sum is None:
                raise ValueError("causal sharing requires aggregate rival signals")
            positive_others = _vector(others_positive, horizon, "others_positive")
            summed_others = _vector(others_sum, horizon, "others_sum")
            if not np.allclose(others, summed_others, atol=1e-8, rtol=1e-10):
                raise ValueError("q_other and others_sum must agree")
            overflow_c = np.maximum(positive_others - summed_others + float(K), 0.0)
            self.others_positive.value = positive_others
            self.overflow_c.value = overflow_c
            self.overflow_m.value = overflow_c * positive_others / self.overflow_scale

        solver = "CLARABEL" if self.overflow_mode == "causal" else solver_name(self.cfg)
        self.problem.solve(solver=solver, warm_start=warm_start)
        if self.problem.status not in OPTIMAL_STATUSES:
            raise RuntimeError(f"Agent solve failed with status {self.problem.status}")

        q = np.asarray(self.q_expr.value, dtype=float)
        charge = np.maximum(np.asarray(self.c_var.value, dtype=float), 0.0)
        discharge = np.maximum(np.asarray(self.d_var.value, dtype=float), 0.0)
        curtailment = np.maximum(np.asarray(self.r_var.value, dtype=float), 0.0)
        vplus = np.maximum(q + others - float(K), 0.0)
        lambda_plus = float(self.cfg.get("poi", {}).get("lambda_plus", 100.0))
        if self.overflow_mode == "causal":
            assert positive_others is not None
            positive_q = np.maximum(q, 0.0)
            denominator = positive_q + positive_others
            share = np.zeros(horizon)
            active = denominator > 1e-12
            share[active] = positive_q[active] / denominator[active]
            overflow_penalty = lambda_plus * float(share @ vplus)
        else:
            overflow_penalty = lambda_plus * float(plus_weight @ vplus)
        base_profit = float(price @ q - self.agent.battery.c_deg * discharge.sum())
        objective = (
            base_profit
            - overflow_penalty
            - self.eps_tiebreak * float((charge + discharge + curtailment).sum())
        )
        return AgentSolution(
            q=q,
            c=charge,
            d=discharge,
            r=curtailment,
            soc=np.clip(np.asarray(self.soc_var.value, dtype=float), 0.0, self.agent.battery.E),
            Vplus=vplus,
            objective=objective,
            base_profit=base_profit,
            status=str(self.problem.status),
        )


def solve_agent(
    agent: Agent,
    *,
    W: ArrayLike,
    prices: ArrayLike,
    K: float,
    cfg: Mapping[str, Any],
    q_other: ArrayLike | None = None,
    beta_plus: float | ArrayLike = 0.0,
    initial_soc: float | None = None,
    terminal_soc: float | None = None,
) -> AgentSolution:
    """Convenience wrapper for a one-off equal-share owner solve."""

    model = AgentLP(agent, np.asarray(W).size, cfg)
    return model.solve(
        W=W,
        prices=prices,
        q_other=q_other,
        K=K,
        beta_plus=beta_plus,
        initial_soc=initial_soc,
        terminal_soc=terminal_soc,
    )


solve = solve_agent

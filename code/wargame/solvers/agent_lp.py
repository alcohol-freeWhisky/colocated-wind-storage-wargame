"""Reusable single-agent LP for games and receding-horizon control."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping

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
    """DPP-parametrized best response for one fixed battery and horizon.

    ``overflow_mode="causal"`` uses the exact injection-share overflow
    charge.  It is a conic DPP model rather than an LP and is solved with
    Clarabel.  The default ``"shared"`` mode retains the linear weighted
    system-overflow term used by every other regime.

    ``proximal_tau`` enables the quadratic regularizer used only as a numerical
    fixed-point device by PRICE coordination.  It is deliberately excluded
    from the returned economic objective and is not an economic cost.
    """

    def __init__(
        self,
        agent: Agent,
        horizon: int,
        cfg: Mapping[str, Any],
        *,
        enforce_budget: bool = False,
        shortfall_mode: Literal["system", "private"] = "system",
        overflow_mode: Literal["shared", "causal"] = "shared",
        proximal_tau: float = 0.0,
    ) -> None:
        self.agent = agent
        self.horizon = int(horizon)
        self.cfg = dict(cfg)
        self.enforce_budget = enforce_budget
        if shortfall_mode not in {"system", "private"}:
            raise ValueError("shortfall_mode must be 'system' or 'private'")
        if overflow_mode not in {"shared", "causal"}:
            raise ValueError("overflow_mode must be 'shared' or 'causal'")
        if proximal_tau < 0:
            raise ValueError("proximal_tau must be non-negative")
        self.shortfall_mode = shortfall_mode
        self.overflow_mode = overflow_mode
        self.overflow_scale = max(float(agent.nameplate), 1.0)
        self.proximal_tau = float(proximal_tau)
        battery = agent.battery

        self.pi = cp.Parameter(horizon, name="pi")
        self.W = cp.Parameter(horizon, nonneg=True, name="W")
        self.q_other = cp.Parameter(horizon, name="q_other")
        self.K = cp.Parameter(nonneg=True, name="K")
        self.D = cp.Parameter(horizon, nonneg=True, name="D")
        self.beta_minus = cp.Parameter(horizon, nonneg=True, name="beta_minus")
        self.beta_plus = cp.Parameter(horizon, nonneg=True, name="beta_plus")
        self.mu = cp.Parameter(horizon, nonneg=True, name="mu")
        self.initial_soc = cp.Parameter(nonneg=True, name="initial_soc")
        self.terminal_min = cp.Parameter(nonneg=True, name="terminal_min")
        if enforce_budget:
            self.budget = cp.Parameter(horizon, name="budget")
        if self.proximal_tau > 0:
            self.q_reference = cp.Parameter(horizon, name="q_reference")
        if self.overflow_mode == "causal":
            self.others_positive = cp.Parameter(horizon, nonneg=True, name="P_other")
            self.overflow_c = cp.Parameter(horizon, nonneg=True, name="overflow_c")
            self.overflow_m = cp.Parameter(horizon, nonneg=True, name="overflow_m")

        self.c_var = cp.Variable(horizon, nonneg=True, name="c")
        self.d_var = cp.Variable(horizon, nonneg=True, name="d")
        self.r_var = cp.Variable(horizon, nonneg=True, name="r")
        self.soc_var = cp.Variable(horizon + 1, name="soc")
        self.vminus_var = cp.Variable(horizon, nonneg=True, name="Vminus")
        self.vplus_var = cp.Variable(horizon, nonneg=True, name="Vplus")
        self.q_expr = self.W - self.r_var - self.c_var + self.d_var
        aggregate = self.q_expr + self.q_other
        if self.overflow_mode == "causal":
            self.positive_q_var = cp.Variable(horizon, nonneg=True, name="positive_q")
            self.positive_total_var = cp.Variable(
                horizon, nonneg=True, name="positive_total"
            )

        constraints: list[cp.Constraint] = [
            self.r_var <= self.W,
            self.c_var <= battery.P,
            self.d_var <= battery.P,
            self.soc_var >= 0,
            self.soc_var <= battery.E,
            self.soc_var[0] == self.initial_soc,
            self.soc_var[1:]
            == self.soc_var[:-1] + battery.eta_c * self.c_var - self.d_var / battery.eta_d,
            self.vminus_var
            >= self.D - (self.q_expr if self.shortfall_mode == "private" else aggregate),
            self.vplus_var >= aggregate - self.K,
        ]
        if self.overflow_mode == "causal":
            constraints.extend(
                [
                    self.positive_q_var >= self.q_expr,
                    self.positive_total_var
                    == self.positive_q_var + self.others_positive,
                ]
            )
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
        if self.overflow_mode == "causal":
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
        payoff = (
            cp.sum(cp.multiply(self.pi - self.mu, dispatch_delta))
            - battery.c_deg * cp.sum(self.d_var)
            - lambda_minus * cp.sum(cp.multiply(self.beta_minus, self.vminus_var))
            - overflow_charge
            - self.eps_tiebreak * activity
        )
        if self.proximal_tau > 0:
            payoff -= 0.5 * self.proximal_tau * cp.sum_squares(
                self.q_expr - self.q_reference
            )
        objective = cp.Maximize(payoff)
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
        beta_minus: float | ArrayLike = 0.0,
        beta_plus: float | ArrayLike = 0.0,
        mu: ArrayLike | None = None,
        poi_budget: POIBudget | float | ArrayLike | None = None,
        initial_soc: float | None = None,
        terminal_soc: float | None = None,
        q_reference: ArrayLike | None = None,
        others_positive: ArrayLike | None = None,
        others_sum: ArrayLike | None = None,
        warm_start: bool = True,
    ) -> AgentSolution:
        """Solve one best response for the supplied horizon data."""

        horizon = self.horizon
        wind = _vector(W, horizon, "W")
        price = _vector(prices, horizon, "prices")
        if self.overflow_mode == "causal":
            if others_positive is None or others_sum is None:
                raise ValueError(
                    "others_positive and others_sum are required for causal overflow"
                )
            positive_others = _vector(others_positive, horizon, "others_positive")
            summed_others = _vector(others_sum, horizon, "others_sum")
            if np.any(positive_others < 0):
                raise ValueError("others_positive must be non-negative")
            others = (
                summed_others
                if q_other is None
                else _vector(q_other, horizon, "q_other")
            )
            if not np.allclose(others, summed_others, atol=1e-8, rtol=1e-10):
                raise ValueError("q_other and others_sum must agree in causal mode")
        else:
            if others_positive is not None or others_sum is not None:
                raise ValueError(
                    "others_positive and others_sum require overflow_mode='causal'"
                )
            positive_others = None
            summed_others = None
            others = (
                np.zeros(horizon)
                if q_other is None
                else _vector(q_other, horizon, "q_other")
            )
        delivery = _vector(D, horizon, "D")
        dual_price = np.zeros(horizon) if mu is None else _vector(mu, horizon, "mu")
        minus_weight = _vector(beta_minus, horizon, "beta_minus")
        plus_weight = _vector(beta_plus, horizon, "beta_plus")
        if np.any(minus_weight < 0) or np.any(plus_weight < 0):
            raise ValueError("beta_minus and beta_plus must be non-negative")
        start = self.agent.battery.soc0 if initial_soc is None else float(initial_soc)
        target = start if terminal_soc is None else float(terminal_soc)

        self.W.value = wind
        self.pi.value = price
        self.q_other.value = others
        self.K.value = float(K)
        self.D.value = delivery
        self.beta_minus.value = minus_weight
        self.beta_plus.value = plus_weight
        self.mu.value = dual_price
        self.initial_soc.value = start
        self.terminal_min.value = target
        if self.overflow_mode == "causal":
            assert positive_others is not None and summed_others is not None
            overflow_c = positive_others - summed_others + float(K)
            if np.any(overflow_c < -1e-8):
                raise ValueError("causal overflow parameter c must be non-negative")
            overflow_c = np.maximum(overflow_c, 0.0)
            self.others_positive.value = positive_others
            self.overflow_c.value = overflow_c
            # Algebraically this remains c*P/y. Scaling the reciprocal cone to
            # roughly nameplate units avoids ill-conditioned c*P coefficients.
            self.overflow_m.value = (
                overflow_c * positive_others / self.overflow_scale
            )
        if self.proximal_tau > 0:
            if q_reference is None:
                raise ValueError("q_reference is required for a proximal AgentLP")
            self.q_reference.value = _vector(q_reference, horizon, "q_reference")
        elif q_reference is not None:
            raise ValueError("q_reference requires a positive proximal_tau")
        if self.enforce_budget:
            if poi_budget is None:
                budget_value = wind + self.agent.battery.P
            else:
                raw = poi_budget.limit if isinstance(poi_budget, POIBudget) else poi_budget
                budget_value = _vector(raw, horizon, "poi_budget")
            self.budget.value = budget_value
        elif poi_budget is not None:
            raise ValueError("This AgentLP was constructed without a POI budget constraint")

        if self.overflow_mode == "causal":
            if "CLARABEL" not in set(cp.installed_solvers()):
                raise RuntimeError("Causal overflow best responses require CLARABEL")
            self.problem.solve(solver="CLARABEL", warm_start=warm_start)
        elif self.proximal_tau > 0:
            installed = set(cp.installed_solvers())
            qp_solver = next(
                (candidate for candidate in ("CLARABEL", "OSQP") if candidate in installed),
                None,
            )
            if qp_solver is None:
                raise RuntimeError("PRICE coordination requires CLARABEL or OSQP")
            self.problem.solve(solver=qp_solver, warm_start=warm_start)
        else:
            self.problem.solve(solver=solver_name(self.cfg), warm_start=warm_start)
        if self.problem.status not in OPTIMAL_STATUSES:
            raise RuntimeError(f"Agent LP failed with status {self.problem.status}")
        q = np.asarray(self.q_expr.value, dtype=float)
        discharge = np.maximum(np.asarray(self.d_var.value, dtype=float), 0.0)
        vminus = np.maximum(np.asarray(self.vminus_var.value, dtype=float), 0.0)
        vplus = (
            np.maximum(q + others - float(K), 0.0)
            if self.overflow_mode == "causal"
            else np.maximum(np.asarray(self.vplus_var.value, dtype=float), 0.0)
        )
        poi = self.cfg.get("poi", {})
        if self.overflow_mode == "causal":
            assert positive_others is not None and summed_others is not None
            positive_q = np.maximum(q, 0.0)
            denominator = positive_q + positive_others
            overflow = np.maximum(q + summed_others - float(K), 0.0)
            causal_share = np.zeros(horizon, dtype=float)
            active = denominator > 1e-12
            causal_share[active] = positive_q[active] / denominator[active]
            overflow_penalty = float(poi.get("lambda_plus", 100.0)) * float(
                causal_share @ overflow
            )
        else:
            overflow_penalty = float(poi.get("lambda_plus", 100.0)) * float(
                plus_weight @ vplus
            )
        economic_objective = float(
            (price - dual_price) @ q
            - self.agent.battery.c_deg * discharge.sum()
            - float(poi.get("lambda_minus", 250.0)) * float(minus_weight @ vminus)
            - overflow_penalty
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
    beta_minus: float | ArrayLike = 0.0,
    beta_plus: float | ArrayLike = 0.0,
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

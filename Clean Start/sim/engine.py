"""Hour-by-hour engine of the curtailment-compensation game (spec rev. 2, Sections 2, 4, 6, 7).

All arrays are batched over days: inputs have shape (D, T, N), with D days, T hours and N owners.
Days are independent (SOC resets daily), so a batch of days runs in parallel.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .params import Params

TOL = 1e-9


@dataclass
class DayInputs:
    W: np.ndarray        # true available wind (D,T,N)
    mu: np.ndarray       # owner's honest forecast (D,T,N)
    What: np.ndarray     # monitor's ex-post estimate of available wind (D,T,N)
    Wex: np.ndarray      # operator's ex-ante forecast, used only by Variant I (D,T,N)
    p: np.ndarray        # real-time price (D,T)
    dis_ok: np.ndarray   # discharge allowed by the day-ahead price rule (D,T) bool
    pbar: np.ndarray     # mean positive day-ahead price of each day (D,)


def simulate(inp: DayInputs, ell: np.ndarray, declare: np.ndarray, prm: Params) -> dict:
    """Run the fixed battery rule and settlement for given reports.

    ell: reports (D,T,N). declare: storage declaration (D,N) bool (True = declare).
    Returns a dict of (D,T,N) arrays plus daily payoffs before audits.
    """
    D, T, N = inp.W.shape
    w = prm.nameplate / prm.nameplate.sum()
    kappa = prm.kappa
    s = np.broadcast_to(prm.s0_frac * prm.E, (D, N)).copy()

    names = ["k", "v", "c", "r", "g", "d", "x", "e_true", "e_est", "T", "cong", "soc", "lost_phys"]
    out = {n: np.zeros((D, T, N)) for n in names}
    for t in range(T):
        W, l = inp.W[:, t], ell[:, t]
        if prm.variant_I:                       # report-independent benchmark
            Wex = inp.Wex[:, t]
            cong = Wex.sum(-1) > prm.K + TOL
            k_cong = np.broadcast_to(kappa, (D, N))
            k_unc = Wex + (prm.K - Wex.sum(-1, keepdims=True)) * w
            v_cong = np.maximum(Wex - kappa, 0.0)
        else:
            L = l.sum(-1)
            cong = L > prm.K + TOL
            if prm.rule == "R":
                k_cong = l * prm.K / np.maximum(L, TOL)[:, None]
            elif prm.rule == "C":
                k_cong = np.minimum(l, kappa)
            else:
                raise ValueError(prm.rule)
            k_unc = l + (prm.K - L)[:, None] * w
            v_cong = np.maximum(l - k_cong, 0.0)
        cg = cong[:, None]
        k = np.where(cg, k_cong, k_unc)
        v = np.where(cg, v_cong, 0.0)
        instructed = v > TOL

        # Battery rule (spec 2): charge only surplus above the share in instructed hours.
        u = np.maximum(W - k, 0.0)
        room = (prm.E - s) / prm.eta_c
        c = np.where(instructed, np.minimum.reduce([u, np.broadcast_to(prm.P, u.shape), room]), 0.0)
        r = u - c                                   # curtailed (lost) generation
        g = W - r
        head = np.maximum(k - (g - c), 0.0)          # unused share
        free = ~instructed if prm.discharge_rule == "strict" else (~instructed | (r <= TOL))
        d_ok = free & inp.dis_ok[:, t][:, None]
        d = np.where(d_ok, np.minimum.reduce([np.broadcast_to(prm.P, u.shape), prm.eta_d * s, head]), 0.0)
        x = g - c + d
        s = s + prm.eta_c * c - d / prm.eta_d

        # Settlement (spec 6).
        if prm.subsidy is None:
            gcf_true, gcf_est = W, inp.What[:, t]
        else:
            volunt = (inp.p[:, t] < -prm.subsidy)[:, None]
            gcf_true = np.where(volunt, 0.0, W)
            gcf_est = np.where(volunt, 0.0, inp.What[:, t])
        e_true = np.minimum(v, np.maximum(gcf_true - g, 0.0))
        e_est = np.minimum(v, np.maximum(gcf_est - g, 0.0))
        if prm.settlement in ("S0", "S1"):
            Tpay = prm.lam * np.where(declare, np.maximum(v - c, 0.0), v)
        elif prm.settlement == "S2":
            Tpay = prm.lam * e_est
        elif prm.settlement == "S2c":                # cap at the estimate: v_est = (What - k)^+ (rev. 2.4)
            v_est = np.where(cg, np.maximum(inp.What[:, t] - k, 0.0), 0.0)
            Tpay = prm.lam * np.minimum(v_est, np.maximum(gcf_est - g, 0.0))
        else:
            raise ValueError(prm.settlement)

        lost_phys = np.where(cg, np.maximum(gcf_true - g, 0.0), 0.0)   # physical lost generation, report-free
        for n, a in zip(names, [k, v, c, r, g, d, x, e_true, e_est, Tpay, np.broadcast_to(cg, k.shape), s, lost_phys]):
            out[n][:, t] = a

    out["energy_rev"] = (inp.p[:, :, None] * out["x"]).sum(1)                 # (D,N)
    out["wear_cost"] = prm.wear * out["d"].sum(1)
    out["comp"] = out["T"].sum(1)
    tv = np.maximum(inp.pbar - prm.wear, 0.0)[:, None] * prm.eta_d * s if prm.terminal_value else 0.0 * s
    out["terminal"] = tv
    out["payoff_pre"] = out["energy_rev"] + out["comp"] - out["wear_cost"] + out["terminal"]
    # Violation volumes for audits (spec 7).
    out["omega"] = np.maximum(out["T"] / prm.lam - out["e_true"], 0.0).sum(1) if prm.lam > 0 else np.zeros((D, N))
    # Fine base (rev. 2.2): bias against the owner's own forecast records, not against realized wind,
    # so honest forecast error is never fined (GB "best estimate" standard for notifications).
    out["infl_vol"] = np.maximum(ell - inp.mu - prm.tau * prm.nameplate, 0.0).sum(1)
    out["hidden_vol"] = (out["c"] * (~declare)[:, None, :]).sum(1)
    # Estimate-based assessment, used for false findings (monitor relies on What instead of records).
    out["omega_est"] = np.maximum(out["T"] / prm.lam - out["e_est"], 0.0).sum(1) if prm.lam > 0 else np.zeros((D, N))
    out["infl_vol_est"] = np.maximum(ell - inp.What - prm.tau * prm.nameplate, 0.0).sum(1)
    out["ell"] = ell
    return out


def penalty(out: dict, prm: Params, alpha=None, rng: np.random.Generator | None = None) -> np.ndarray:
    """Audit repayment + fines per owner-day (D,N), S1 only; zero otherwise.

    alpha: (D,N) audit probabilities (default prm.alpha). With rng=None the expectation is returned.
    Violation = any invalid payment, inflation beyond tolerance, or hidden storage.
    A finding on a violation (prob z) charges records-based repayment + fines.
    A false finding on a compliant owner-day (prob z0) charges the estimate-based assessment.
    """
    if prm.settlement != "S1":
        return np.zeros_like(out["omega"])
    a = prm.alpha if alpha is None else alpha
    true_pen = prm.lam * out["omega"] + prm.f * (out["infl_vol"] + out["hidden_vol"])
    est_pen = prm.lam * out["omega_est"] + prm.f * out["infl_vol_est"]
    violates = true_pen > TOL
    if rng is None:
        return a * np.where(violates, prm.z * true_pen, prm.z0 * est_pen)
    audited = rng.random(true_pen.shape) < a
    found = rng.random(true_pen.shape) < np.where(violates, prm.z, prm.z0)
    return np.where(audited & found, np.where(violates, true_pen, est_pen), 0.0)


def payoff(inp, ell, declare, prm, alpha=None):
    """Expected daily payoff per owner (D,N) and the simulation output."""
    out = simulate(inp, ell, declare, prm)
    return out["payoff_pre"] - penalty(out, prm, alpha), out


def decompose_overpayment(inp, ell, declare, prm, i: int) -> dict:
    """Telescoping split of owner i's overpayment O = T_act - lam*e_true (spec 10), per day.

    storage   = T_act - T(declare, ell)
    inflation = T(declare, ell) - T(declare, mu_i)   [rivals' reports fixed]
    error     = T(declare, mu_i) - lam * e_true(actual)
    Also returns self-induced payments: hours congested given ell but not given (mu_i, ell_-i).
    """
    act = simulate(inp, ell, declare, prm)
    dec = declare.copy(); dec[:, i] = True
    a1 = simulate(inp, ell, dec, prm)
    ell_h = ell.copy(); ell_h[:, :, i] = inp.mu[:, :, i]
    a2 = simulate(inp, ell_h, dec, prm)
    T_act, T1, T2 = (o["T"][:, :, i].sum(1) for o in (act, a1, a2))
    paid_true = prm.lam * act["e_true"][:, :, i].sum(1)
    self_ind = (act["cong"][:, :, i] > 0) & ~(a2["cong"][:, :, i] > 0)
    return {"O": T_act - paid_true, "storage": T_act - T1, "inflation": T1 - T2,
            "error": T2 - paid_true, "self_induced": (act["T"][:, :, i] * self_ind).sum(1)}

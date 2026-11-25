"""Pure-strategy equilibria over the spec's strategy grid (spec Sections 5 and 8).

Strategy of owner i = (beta_low, beta_mid, beta_high, declare): a bias option for each ex-ante congestion bin
plus a daily storage declaration. 7^3 x 2 = 686 strategies per owner.
Payoff = mean expected daily payoff over the evaluation days (common random numbers across strategies).
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass

import numpy as np

from .engine import DayInputs, payoff, simulate

BETAS = (0.0, -0.1, 0.05, 0.1, 0.25, 0.5, "cap")   # 0.05 = tau (rev. 2.3); -0.1 under-report (rev. 2.4)
STRATS = [(b0, b1, b2, dec) for b0, b1, b2 in itertools.product(range(len(BETAS)), repeat=3) for dec in (True, False)]
TRUTH = (0, 0, 0, True)


def option_reports(inp: DayInputs, prm) -> np.ndarray:
    """Reports for each bias option: (5, D, T, N). ell = min(mu + beta N, N + P); cap = N + P."""
    capv = prm.nameplate + prm.P
    out = []
    for b in BETAS:
        out.append(np.broadcast_to(capv, inp.mu.shape).copy() if b == "cap"
                   else np.clip(inp.mu + b * prm.nameplate, 0.0, capv))
    return np.stack(out)


def build(profile, opts, bins):
    """Reports (D,T,N) and declaration (D,N) from a profile of strategies."""
    D, T, N = opts.shape[1:]
    ell = np.empty((D, T, N))
    dec = np.empty((D, N), bool)
    for i, (b0, b1, b2, de) in enumerate(profile):
        choice = np.choose(bins, [b0, b1, b2])                  # (D,T) option index
        ell[:, :, i] = np.take_along_axis(opts[:, :, :, i], choice[None], 0)[0]
        dec[:, i] = de
    return ell, dec


def value(profile, inp, opts, bins, prm) -> np.ndarray:
    ell, dec = build(profile, opts, bins)
    u, _ = payoff(inp, ell, dec, prm)
    return u.mean(0)                                            # (N,) mean daily payoff


def best_response(i, profile, inp, opts, bins, prm):
    vals = np.empty(len(STRATS))
    for k, s in enumerate(STRATS):
        prof = list(profile); prof[i] = s
        vals[k] = value(prof, inp, opts, bins, prm)[i]
    return vals


@dataclass
class EqResult:
    profile: list
    converged: bool
    sweeps: int
    max_dev_gain: float          # max over owners of (best grid payoff - current payoff), $/day
    cycle: bool
    history: list


def solve(inp, bins, prm, start=None, max_sweeps=30, tol=1e-6) -> EqResult:
    """Sequential best-response iteration. An owner switches only if it gains more than tol
    (ties keep the current strategy). Stops at a pure Nash equilibrium of the grid, a detected cycle,
    or max_sweeps. Reports the maximum unilateral deviation gain at the final profile."""
    opts = option_reports(inp, prm)
    N = prm.N
    profile = list(start) if start else [TRUTH] * N
    seen, history = {tuple(profile)}, [tuple(profile)]
    cycle = False
    for sweep in range(1, max_sweeps + 1):
        changed = False
        for i in range(N):
            vals = best_response(i, profile, inp, opts, bins, prm)
            cur = vals[STRATS.index(profile[i])]
            k = int(np.argmax(vals))
            if vals[k] > cur + tol:
                profile[i] = STRATS[k]; changed = True
        history.append(tuple(profile))
        if not changed:
            break
        if tuple(profile) in seen:
            cycle = True
            break
        seen.add(tuple(profile))
    gains = []
    for i in range(N):
        vals = best_response(i, profile, inp, opts, bins, prm)
        gains.append(vals.max() - vals[STRATS.index(profile[i])])
    return EqResult(profile, not changed, sweep, float(max(gains)), cycle, history)


def metrics(profile, inp, bins, prm) -> dict:
    """Outcome metrics at a profile ($/day and MWh/day are means over evaluation days)."""
    from .engine import decompose_overpayment, penalty
    opts = option_reports(inp, prm)
    ell, dec = build(profile, opts, bins)
    o = simulate(inp, ell, dec, prm)
    pen = penalty(o, prm)
    N = prm.N
    bias = (ell - inp.mu) / prm.nameplate                     # (D,T,N) as a share of nameplate
    m = {
        "energy_MWh": o["x"].sum((1, 2)).mean(),
        "curtailed_MWh": o["r"].sum((1, 2)).mean(),
        "stored_MWh": o["c"].sum((1, 2)).mean(),
        "comp_paid": o["T"].sum((1, 2)).mean(),
        "comp_eligible": prm.lam * o["e_true"].sum((1, 2)).mean(),
        "penalty_exp": pen.sum(1).mean(),
        "cong_hours": o["cong"][:, :, 0].sum(1).mean(),
        "discharge_MWh": o["d"].sum((1, 2)).mean(),
        "profit_per_owner": (o["payoff_pre"] - pen).mean(0),
    }
    for b, name in enumerate(["low", "mid", "high"]):
        m[f"bias_{name}"] = bias[bins == b].mean()
    dcm = {k: 0.0 for k in ["O", "storage", "inflation", "error", "self_induced"]}
    for i in range(N):
        d = decompose_overpayment(inp, ell, dec, prm, i)
        for k in dcm:
            dcm[k] += d[k].mean()
    m.update({f"over_{k}": v for k, v in dcm.items()})
    # Jointly induced congestion: congested at this profile but not under all-honest reports.
    l0, d0 = build([TRUTH] * N, opts, bins)
    o0 = simulate(inp, l0, d0, prm)
    ind = (o["cong"][:, :, 0] > 0) & ~(o0["cong"][:, :, 0] > 0)
    m["induced_cong_hours"] = ind.sum(1).mean()
    m["induced_curtailed_MWh"] = o["r"][ind].sum() / len(ind)
    m["induced_paid"] = o["T"][ind].sum() / len(ind)
    # Settlement accuracy against physical lost generation (report-free benchmark).
    diff = o["T"] - prm.lam * o["lost_phys"]
    m["pay_over_gross"] = np.maximum(diff, 0).sum((1, 2)).mean()
    m["pay_under_gross"] = np.maximum(-diff, 0).sum((1, 2)).mean()
    m["pay_net_error"] = m["pay_over_gross"] - m["pay_under_gross"]
    m["audit_recovery_exp"] = (prm.alpha * prm.z * prm.lam * o["omega"]).sum(1).mean() if prm.settlement == "S1" else 0.0
    phys = inp.W.sum(-1) > prm.K
    rep_c = o["cong"][:, :, 0] > 0
    m["phys_cong_hours"] = phys.sum(1).mean()
    m["reported_not_phys_hours"] = (rep_c & ~phys).sum(1).mean()
    return m


def fmt_profile(profile) -> str:
    lab = lambda b: "cap" if BETAS[b] == "cap" else f"{BETAS[b]:g}"
    return " | ".join(f"({lab(a)},{lab(b)},{lab(c)},{'D' if d else 'H'})" for a, b, c, d in profile)

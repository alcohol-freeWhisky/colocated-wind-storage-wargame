"""Contextual EXP3 learning (Step 4; design pre-registered in EXPERIMENT_LOG.md).

Each owner has 3 bin learners (bias option per ex-ante congestion bin) and 1 declaration learner.
Bandit feedback: an owner sees only its realized payoff (sampled audits under S1).
Seeds run in parallel as a batch; for exact regret every round also simulates, for each learner and each
alternative arm, the day with only that learner's action changed (all other draws fixed).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import equilibrium as eqm
from .engine import DayInputs, simulate

TOL = 1e-9


@dataclass
class LearnResult:
    snaps: dict            # round -> (pb (S,N,3,K), pd (S,N,2))
    regret: dict           # round -> (S,N,4) cumulative external regret ($), learner 3 = declaration
    rounds_seen: dict      # round -> (S,N,4) number of updates per learner
    invariance_max: float  # max |u_cf - u_act| over all counterfactuals (0 under Variant I)
    mean_reward: np.ndarray  # (S,N) mean realized daily payoff


def _hourly(out, inp, ell, dec, prm, audited):
    """Hourly reward (B,24,N) excluding terminal value, plus terminal (B,N) and charge (B,24,N)."""
    rev = inp.p[:, :, None] * out["x"] - prm.wear * out["d"] + out["T"]
    if prm.settlement == "S1":
        assert prm.z == 1.0 and prm.z0 == 0.0, "hourly fine attribution assumes z=1, z0=0"
        pen = (prm.lam * np.maximum(out["T"] / prm.lam - out["e_true"], 0.0)
               + prm.f * np.maximum(ell - inp.mu - prm.tau * prm.nameplate, 0.0)
               + prm.f * out["c"] * (~dec)[:, None, :])
        rev = rev - audited[:, None, :] * pen
    return rev, out["terminal"], out["c"]


def run(prm, inp: DayInputs, bins: np.ndarray, T: int, seeds=range(10), attribution="daily",
        snap_at=None, verbose=False, clip=True) -> LearnResult:
    D, H, N = inp.W.shape
    K = len(eqm.BETAS)
    S = len(seeds)
    opts = eqm.option_reports(inp, prm)                              # (K,D,H,N)
    gamma = min(1.0, np.sqrt(K * np.log(K) / ((np.e - 1) * T)))
    gamma_d = min(1.0, np.sqrt(2 * np.log(2) / ((np.e - 1) * T)))
    eta, eta_d = gamma / K, gamma_d / 2
    snap_at = set(snap_at or [T // 16, T // 8, T // 4, T // 2, T])

    # Paired random streams per seed (identical across treatments).
    r_day = [np.random.default_rng(1000 + s) for s in seeds]
    r_act = [np.random.default_rng(2000 + s) for s in seeds]
    r_aud = [np.random.default_rng(3000 + s) for s in seeds]

    Sb = np.zeros((S, N, 3, K)); Sd = np.zeros((S, N, 2))
    absb = np.zeros((S, N, 3)); absd = np.zeros((S, N)); nb = np.zeros((S, N, 4))
    cum_act = np.zeros((S, N, 4)); cum_cf_b = np.zeros((S, N, 3, K)); cum_cf_d = np.zeros((S, N, 2))
    tot_reward = np.zeros((S, N))
    inv_max = 0.0
    snaps, regrets, seen = {}, {}, {}

    # Variant layout: 0 = actual; then for each owner i: 3*K bin variants, then 2 declaration variants.
    per = 3 * K + 2
    V = 1 + N * per
    tt = np.arange(H)[None, None, :, None]
    ii = np.arange(N)[None, None, None, :]

    def probs(Sx, eta_, gamma_, k):
        z = eta_ * (Sx - Sx.max(-1, keepdims=True))
        w = np.exp(z); w /= w.sum(-1, keepdims=True)
        return (1 - gamma_) * w + gamma_ / k

    for t in range(1, T + 1):
        d = np.array([g.integers(D) for g in r_day])                 # (S,)
        pb, pd = probs(Sb, eta, gamma, K), probs(Sd, eta_d, gamma_d, 2)
        u = np.stack([g.random((N, 4)) for g in r_act])              # (S,N,4)
        A = (pb.cumsum(-1) < u[:, :, :3, None]).sum(-1).clip(max=K - 1)   # (S,N,3)
        dec_act = u[:, :, 3] < pd[:, :, 0]                           # arm 0 = declare
        audited = np.stack([g.random(N) < prm.alpha for g in r_aud]) # (S,N)

        Av = np.broadcast_to(A[:, None], (S, V, N, 3)).copy()
        Dv = np.broadcast_to(dec_act[:, None], (S, V, N)).copy()
        for i in range(N):
            o = 1 + i * per
            for j in range(3):
                Av[:, o + j * K:o + (j + 1) * K, i, j] = np.arange(K)[None]
            Dv[:, o + 3 * K, i] = True
            Dv[:, o + 3 * K + 1, i] = False
        bd = bins[d]                                                 # (S,H)
        idx = np.take_along_axis(Av, np.broadcast_to(bd[:, None, None, :], (S, V, N, H)), axis=3)
        idx = idx.transpose(0, 1, 3, 2)                              # (S,V,H,N)
        ell = opts[idx, d[:, None, None, None], tt, ii].reshape(S * V, H, N)
        dec = Dv.reshape(S * V, N)
        rep = lambda a: np.repeat(a[d], V, axis=0)
        binp = DayInputs(W=rep(inp.W), mu=rep(inp.mu), What=rep(inp.What), Wex=rep(inp.Wex), p=rep(inp.p),
                         dis_ok=rep(inp.dis_ok), pbar=rep(inp.pbar))
        out = simulate(binp, ell, dec, prm)
        aud = np.repeat(audited, V, axis=0)
        hr, tv, ch = _hourly(out, binp, ell, dec, prm, aud)
        hr, tv, ch = hr.reshape(S, V, H, N), tv.reshape(S, V, N), ch.reshape(S, V, H, N)
        U = hr.sum(2) + tv                                           # (S,V,N) daily payoff
        base_h = (inp.p[d][:, :, None] * inp.mu[d])                  # (S,H,N) observable baseline
        present = np.stack([(bd == j).any(1) for j in range(3)], -1) # (S,3)
        if attribution == "daily":
            Rb = np.broadcast_to(U[:, :, :, None], (S, V, N, 3))
            base_b = np.broadcast_to(base_h.sum(1)[:, :, None], (S, N, 3))
        else:
            mask = np.stack([bd == j for j in range(3)], -1)         # (S,H,3)
            hb = np.einsum("svhn,shj->svnj", hr, mask)
            cb = np.einsum("svhn,shj->svnj", ch, mask)
            share = np.where(ch.sum(2)[..., None] > TOL, cb / np.maximum(ch.sum(2)[..., None], TOL), 0.0)
            Rb = hb + tv[..., None] * share
            base_b = np.einsum("shn,shj->snj", base_h, mask)
        base_d = base_h.sum(1)                                       # (S,N)

        # Realized and counterfactual rewards per learner.
        r_act_b = Rb[:, 0]                                           # (S,N,3)
        r_act_d = U[:, 0]                                            # (S,N)
        cf_b = np.empty((S, N, 3, K)); cf_d = np.empty((S, N, 2))
        for i in range(N):
            o = 1 + i * per
            for j in range(3):
                cf_b[:, i, j] = Rb[:, o + j * K:o + (j + 1) * K, i, j]
            cf_d[:, i] = U[:, o + 3 * K:o + 3 * K + 2, i]
        # Internal consistency checks: the counterfactual of the played arm equals the realized reward,
        # and the realized daily payoff equals the engine's payoff with the same audit draws.
        assert np.allclose(np.take_along_axis(cf_b, A[..., None], -1)[..., 0], r_act_b, atol=1e-6)
        assert np.allclose(np.take_along_axis(cf_d, (~dec_act).astype(int)[..., None], -1)[..., 0], r_act_d, atol=1e-6)
        if t == 1:
            o0 = {k: v.reshape(S, V, *v.shape[1:])[:, 0] for k, v in out.items() if k != "ell"}
            pen0 = 0.0
            if prm.settlement == "S1":
                pen0 = audited * (prm.lam * o0["omega"] + prm.f * (o0["infl_vol"] + o0["hidden_vol"]))
            assert np.allclose(U[:, 0], o0["payoff_pre"] - pen0, atol=1e-6), "reward != engine payoff"
        if prm.variant_I:
            inv_max = max(inv_max, float(np.abs(cf_b - r_act_b[..., None]).max()),
                          float(np.abs(cf_d - r_act_d[..., None]).max()))
        pres = present[:, None, :]                                   # (S,1,3)
        cum_act[:, :, :3] += np.where(pres, r_act_b, 0.0)
        cum_cf_b += np.where(pres[..., None], cf_b, 0.0)
        cum_act[:, :, 3] += r_act_d
        cum_cf_d += cf_d
        nb[:, :, :3] += pres; nb[:, :, 3] += 1
        tot_reward += r_act_d

        # EXP3 updates (bandit: only the realized reward of the chosen arm is used).
        xb = r_act_b - base_b
        absb += np.where(pres, np.abs(xb), 0.0)
        scale_b = 4 * absb / np.maximum(nb[:, :, :3], 1) + TOL
        lim = 1.0 if clip else np.inf   # v1 clipped to [-1,1]; v2 (clip=False) keeps rare large fines
        rb = np.clip(xb / scale_b, -lim, lim)
        pa = np.take_along_axis(pb, A[..., None], -1)[..., 0]
        upd = np.where(pres, rb / pa, 0.0)
        np.put_along_axis(Sb, A[..., None], np.take_along_axis(Sb, A[..., None], -1) + upd[..., None], -1)
        xd = r_act_d - base_d
        absd += np.abs(xd)
        rd = np.clip(xd / (4 * absd / nb[:, :, 3] + TOL), -lim, lim)
        ad = (~dec_act).astype(int)
        pda = np.take_along_axis(pd, ad[..., None], -1)[..., 0]
        np.put_along_axis(Sd, ad[..., None], np.take_along_axis(Sd, ad[..., None], -1) + (rd / pda)[..., None], -1)

        if t in snap_at:
            snaps[t] = (probs(Sb, eta, gamma, K), probs(Sd, eta_d, gamma_d, 2))
            reg = np.concatenate([cum_cf_b.max(-1) - cum_act[:, :, :3],
                                  (cum_cf_d.max(-1) - cum_act[:, :, 3])[..., None]], -1)
            regrets[t] = reg
            seen[t] = nb.copy()
            if verbose:
                print(f"  t={t} regret/round per learner (mean over seeds/owners): "
                      f"{(reg / np.maximum(nb, 1)).mean((0, 1)).round(1)}", flush=True)
    return LearnResult(snaps, regrets, seen, inv_max, tot_reward / T)

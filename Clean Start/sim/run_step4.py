"""Step 4: contextual EXP3 learning vs grid equilibria (design pre-registered in EXPERIMENT_LOG.md).

Learn one treatment:   ../.venv/bin/python -m sim.run_step4 learn "<treatment>" daily|bin [T]
Analyze all results:   ../.venv/bin/python -m sim.run_step4 analyze
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from . import equilibrium as eqm
from . import learning
from .data import congestion_model, day_inputs, load
from .engine import simulate
from .params import anchor_params
from .run_step3 import LAM, TREATMENTS
from .run_step3c import accounting

import os
VERSION = os.environ.get("STEP4_VERSION", "v1")   # v1: clipped rewards (pre-registered); v2: unclipped
OUT = Path(__file__).resolve().parents[1] / "results" / ("step4" if VERSION == "v1" else "step4_v2")
OUT.mkdir(parents=True, exist_ok=True)
STEP4 = ["T1 R/S0", "T2 R/S1 f=5l", "T5 C/S1 f=3l", "T3 R/S2", "T6 C/S2", "T3c R/S2c", "T6c C/S2c", "T6 C/S2 VariantI"]
fname = lambda name, att: OUT / f"{name.replace(' ', '_').replace('/', '-')}__{att}.npz"


def setup():
    ds = load()
    base = anchor_params(ds.nameplate, lam=LAM)
    _, bins, _ = congestion_model(ds, slice(0, 30), base.K)
    trn = day_inputs(ds, slice(0, 30), seed=1)
    te = day_inputs(ds, slice(30, 60), seed=0)
    return base, bins[:30], trn, bins[30:], te


def learn(name, att, T):
    base, btr, trn, _, _ = setup()
    prm = base.with_(**TREATMENTS[name])
    t0 = time.time()
    r = learning.run(prm, trn, btr, T=T, attribution=att, verbose=True, clip=(VERSION == "v1"))
    rounds = sorted(r.snaps)
    np.savez(fname(name, att), rounds=rounds,
             pb=np.stack([r.snaps[t][0] for t in rounds]), pd=np.stack([r.snaps[t][1] for t in rounds]),
             regret=np.stack([r.regret[t] for t in rounds]), seen=np.stack([r.rounds_seen[t] for t in rounds]),
             invariance_max=r.invariance_max, mean_reward=r.mean_reward, secs=time.time() - t0)
    print(f"{name} {att}: done in {time.time()-t0:.0f}s, invariance_max={r.invariance_max:.2e}", flush=True)


def ci(x):
    """mean and 95% half-width across seeds (axis 0)."""
    x = np.asarray(x, float)
    return x.mean(0), 1.96 * x.std(0, ddof=1) / np.sqrt(x.shape[0])


def bias_table(opts, mu, bins, nameplate):
    """m[a,i,j] = mean over hours in bin j of (option a report - mu)/N_i; also |.|."""
    K, _, _, N = opts.shape
    dev = (opts - mu[None]) / nameplate
    m = np.full((K, N, 3), np.nan); ma = np.full((K, N, 3), np.nan)
    for j in range(3):
        sel = bins == j
        m[:, :, j] = dev[:, sel, :].mean(1)
        ma[:, :, j] = np.abs(dev[:, sel, :]).mean(1)
    return m, ma


def outcomes(profile, inp, bins, prm):
    a = accounting(profile, inp, bins, prm)
    opts = eqm.option_reports(inp, prm)
    ell, dec = eqm.build(profile, opts, bins)
    o = simulate(inp, ell, dec, prm)
    diff = o["T"] - prm.lam * np.where(o["cong"] > 0, o["r"], 0.0)
    phys = inp.W.sum(-1) > prm.K
    rep = o["cong"][:, :, 0] > 0
    return {"paid": a["paid"], "over": np.maximum(diff, 0).sum((1, 2)).mean(),
            "under": np.maximum(-diff, 0).sum((1, 2)).mean(), "unpaid_uninstructed": a["phys_lost_uninstructed"],
            "energy": a["energy_MWh"], "market_value": a["market_value"],
            "rep_cong_h": rep.sum(1).mean(), "rep_not_phys_h": (rep & ~phys).sum(1).mean()}


def analyze():
    base, btr, trn, bte, te = setup()
    prof3 = json.loads((OUT.parent / "step3_profiles.json").read_text())
    lab = lambda a: "cap" if eqm.BETAS[a] == "cap" else f"{eqm.BETAS[a]:g}"
    rows, eqrows, regrows, outrows = [], [], [], []
    rng = np.random.default_rng(7)
    for att in ["daily", "bin"]:
        for name in STEP4:
            f = fname(name, att)
            if not f.exists():
                continue
            z = np.load(f)
            prm = base.with_(**TREATMENTS[name])
            opts_te = eqm.option_reports(te, prm)
            m, ma = bias_table(opts_te, te.mu, bte, prm.nameplate)
            rounds = list(z["rounds"])
            for k, t in enumerate(rounds):
                pb, pdc = z["pb"][k], z["pd"][k]                         # (S,N,3,K), (S,N,2)
                sb = np.einsum("snja,anj->snj", pb, m).mean(1)            # (S,3) mean over owners
                ab = np.einsum("snja,anj->snj", pb, ma).mean(1)
                row = {"attribution": att, "treatment": name, "round": t}
                for j, bn in enumerate(["low", "mid", "high"]):
                    mu_, hw = ci(sb[:, j]); row[f"bias_{bn}"] = mu_; row[f"bias_{bn}_ci"] = hw
                    row[f"absbias_{bn}"] = ab[:, j].mean()
                    for a in range(len(eqm.BETAS)):
                        row[f"p_{bn}_{lab(a)}"] = pb[:, :, j, a].mean()
                for nm, x in [("high-low", sb[:, 2] - sb[:, 0]), ("mid-high", sb[:, 1] - sb[:, 2]),
                              ("mid-low", sb[:, 1] - sb[:, 0])]:
                    mu_, hw = ci(x); row[f"d_{nm}"] = mu_; row[f"d_{nm}_ci"] = hw
                row["p_declare"] = pdc[:, :, 0].mean()
                rows.append(row)
                reg = z["regret"][k] / np.maximum(z["seen"][k], 1)        # (S,N,4) $/round
                regrows.append({"attribution": att, "treatment": name, "round": t,
                                **{f"regret_{n}": reg[:, :, q].mean() for q, n in enumerate(["low", "mid", "high", "decl"])},
                                "regret_max_learner": reg.max()})
            # Final policy vs every equilibrium found on test days (Step 3b) and on training days.
            pbF, pdF = z["pb"][-1], z["pd"][-1]
            eqs = {"test/" + tag: [tuple(s) for s in prof3[name + tag]["profile"]] for tag in ["", " [start=cap]"]}
            for tag, st in [("", None), (" [start=cap]", [(eqm.BETAS.index("cap"),) * 3 + (False,)] * prm.N)]:
                eqs["train/" + tag] = eqm.solve(trn, btr, prm, start=st).profile
            seen_p = {}
            for key, prof in eqs.items():
                if tuple(prof) in seen_p:
                    continue
                seen_p[tuple(prof)] = key
                mass = np.mean([pbF[:, i, j, prof[i][j]].mean() for i in range(prm.N) for j in range(3)])
                mdec = np.mean([pdF[:, i, 0 if prof[i][3] else 1].mean() for i in range(prm.N)])
                eqrows.append({"attribution": att, "treatment": name, "equilibrium": key,
                               "profile": eqm.fmt_profile(prof), "mass_on_eq_bias": mass, "mass_on_eq_decl": mdec})
            # Modal profile deviation gain (test days) and sampled-profile outcomes, per seed.
            S = pbF.shape[0]
            for s in range(S):
                modal = [tuple(int(np.argmax(pbF[s, i, j])) for j in range(3)) + (bool(pdF[s, i, 0] >= 0.5),)
                         for i in range(prm.N)]
                gains = []
                for i in range(prm.N):
                    vals = eqm.best_response(i, modal, te, opts_te, bte, prm)
                    gains.append(vals.max() - vals[eqm.STRATS.index(modal[i])])
                samp = []
                for _ in range(20):
                    prof = [tuple(int(rng.choice(len(eqm.BETAS), p=pbF[s, i, j] / pbF[s, i, j].sum())) for j in range(3))
                            + (bool(rng.random() < pdF[s, i, 0]),) for i in range(prm.N)]
                    samp.append(outcomes(prof, te, bte, prm))
                outrows.append({"attribution": att, "treatment": name, "seed": s, "modal": eqm.fmt_profile(modal),
                                "modal_dev_gain_max": max(gains), "modal_dev_gain_mean": np.mean(gains),
                                **{k: np.mean([o[k] for o in samp]) for k in samp[0]}})
            print(f"analyzed {name} {att}; invariance_max={float(z['invariance_max']):.2e}", flush=True)
    honest = {name: outcomes([eqm.TRUTH] * base.N, te, bte, base.with_(**TREATMENTS[name])) for name in STEP4}
    pd.DataFrame(rows).to_csv(OUT / "policy_bias.csv", index=False)
    pd.DataFrame(eqrows).to_csv(OUT / "mass_on_equilibria.csv", index=False)
    pd.DataFrame(regrows).to_csv(OUT / "regret.csv", index=False)
    pd.DataFrame(outrows).to_csv(OUT / "outcomes_by_seed.csv", index=False)
    pd.DataFrame(honest).T.to_csv(OUT / "outcomes_honest.csv")
    print("written", flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "learn":
        learn(sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 20000)
    else:
        analyze()

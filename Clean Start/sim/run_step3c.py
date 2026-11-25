"""Step 3c: final-review checks before Step 4.

(1) P0 accounting: reconcile the contract-eligible benchmark with the physical-lost-generation benchmark.
(2) Market value of exports (sum p*x - wear), so energy is not read as welfare.
(3) Under-reporting boundary: re-solve the S2c treatments (and S2 controls) with beta = -0.25 added.

Run from "Clean Start":  ../.venv/bin/python -m sim.run_step3c
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from . import equilibrium as eqm
from .data import congestion_model, day_inputs, load
from .engine import simulate
from .params import anchor_params
from .run_step3 import LAM, TREATMENTS

OUT = Path(__file__).resolve().parents[1] / "results"


def accounting(profile, inp, bins, prm) -> dict:
    """All benchmarks in $/day (means over days). lost = W - g = r (curtailed generation)."""
    opts = eqm.option_reports(inp, prm)
    ell, dec = eqm.build(profile, opts, bins)
    o = simulate(inp, ell, dec, prm)
    cg = o["cong"] > 0
    lam = prm.lam
    day = lambda a: a.sum((1, 2)).mean()
    lost = o["r"]
    return {
        "paid": day(o["T"]),
        "contract_eligible": lam * day(o["e_true"]),                     # lam*min(v, lost): cap = reported shortfall v
        "phys_lost_instructed": lam * day(np.where(cg, lost, 0.0)),        # lam*lost in reported-congested hours
        "gap_report_cap": lam * day(np.where(cg, np.maximum(lost - o["v"], 0.0), 0.0)),
        "phys_lost_uninstructed": lam * day(np.where(cg, 0.0, lost)),      # curtailment with no instruction (unpaid)
        "curtailed_uninstructed_MWh": day(np.where(cg, 0.0, lost)),
        "market_value": (inp.p[:, :, None] * o["x"]).sum((1, 2)).mean() - prm.wear * day(o["d"]),
        "energy_MWh": day(o["x"]),
    }


def main():
    ds = load()
    base = anchor_params(ds.nameplate, lam=LAM)
    _, bins, _ = congestion_model(ds, slice(0, 30), base.K)
    te = slice(30, 60)
    inp, b = day_inputs(ds, te, seed=0), bins[te]
    prof = json.loads((OUT / "step3_profiles.json").read_text())

    # (1)+(2) accounting at the Step 3b equilibria (relaxed battery) and at all-honest reports.
    rows = []
    for name, kw in TREATMENTS.items():
        prm = base.with_(**kw)
        p_eq = [tuple(s) for s in prof[name]["profile"]]
        a, h = accounting(p_eq, inp, b, prm), accounting([eqm.TRUTH] * prm.N, inp, b, prm)
        rows.append({"treatment": name, **a, "d_market_value": a["market_value"] - h["market_value"],
                     "d_energy": a["energy_MWh"] - h["energy_MWh"]})
    acc = pd.DataFrame(rows)
    acc["check_identity"] = acc.contract_eligible + acc.gap_report_cap - acc.phys_lost_instructed  # must be 0
    acc.to_csv(OUT / "step3c_accounting.csv", index=False)
    pd.set_option("display.width", 250, "display.max_columns", 30)
    print((acc.set_index("treatment") / 1).round(1).to_string(), flush=True)

    # (3) Boundary check: add beta = -0.25 (appended so existing option indices are unchanged).
    eqm.BETAS = eqm.BETAS + (-0.25,)
    eqm.STRATS = [(x, y, z, d) for x in range(len(eqm.BETAS)) for y in range(len(eqm.BETAS))
                  for z in range(len(eqm.BETAS)) for d in (True, False)]
    ic = eqm.BETAS.index("cap")
    srows = []
    for name in ["T3c R/S2c", "T6c C/S2c", "T3 R/S2", "T6 C/S2"]:
        prm = base.with_(**TREATMENTS[name])
        for tag, start in [("", None), (" [start=cap]", [(ic, ic, ic, False)] * prm.N)]:
            t0 = time.time()
            eq = eqm.solve(inp, b, prm, start=start)
            m = eqm.metrics(eq.profile, inp, b, prm)
            a = accounting(eq.profile, inp, b, prm)
            h = accounting([eqm.TRUTH] * prm.N, inp, b, prm)
            srows.append({"treatment": name + tag, "converged": eq.converged, "max_dev_gain": eq.max_dev_gain,
                          "profile": eqm.fmt_profile(eq.profile), "bias_high": m["bias_high"],
                          "d_energy": a["energy_MWh"] - h["energy_MWh"],
                          "d_market_value": a["market_value"] - h["market_value"],
                          "paid": a["paid"], "phys_lost_instructed": a["phys_lost_instructed"],
                          "profit_total": m["profit_per_owner"].sum(), "secs": time.time() - t0})
            print(srows[-1], flush=True)
    pd.DataFrame(srows).to_csv(OUT / "step3c_beta_minus025.csv", index=False)


if __name__ == "__main__":
    main()

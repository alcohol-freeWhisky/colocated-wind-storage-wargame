"""Step 3: core experiments T1-T6, enforcement levels, Variant I, controls.

Run from "Clean Start":  ../.venv/bin/python -m sim.run_step3
Writes results/step3_summary.csv and results/step3_profiles.json.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from .data import congestion_model, day_inputs, load
from .equilibrium import BETAS, STRATS, TRUTH, fmt_profile, metrics, solve
from .params import anchor_params

OUT = Path(__file__).resolve().parents[1] / "results"
OUT.mkdir(exist_ok=True)
LAM = 30.0

TREATMENTS = {
    "T1 R/S0": dict(rule="R", settlement="S0"),
    "T2 R/S1 f=3l": dict(rule="R", settlement="S1", f=3 * LAM),
    "T2 R/S1 f=5l": dict(rule="R", settlement="S1", f=5 * LAM),
    "T3 R/S2": dict(rule="R", settlement="S2"),
    "T4 C/S0": dict(rule="C", settlement="S0"),
    "T5 C/S1 f=3l": dict(rule="C", settlement="S1", f=3 * LAM),
    "T5 C/S1 f=5l": dict(rule="C", settlement="S1", f=5 * LAM),
    "T6 C/S2": dict(rule="C", settlement="S2"),
    "T3c R/S2c": dict(rule="R", settlement="S2c"),
    "T6c C/S2c": dict(rule="C", settlement="S2c"),
    "T6 C/S2 VariantI": dict(rule="C", settlement="S2", variant_I=True),
}
NO_BATTERY = ["T1 R/S0", "T4 C/S0", "T6 C/S2"]


def main():
    ds = load()
    base = anchor_params(ds.nameplate, lam=LAM)
    _, bins, _ = congestion_model(ds, slice(0, 30), base.K)
    te = slice(30, 60)
    inp, b = day_inputs(ds, te, seed=0), bins[te]
    rows, profiles = [], {}

    def run(name, prm, start=None, tag=""):
        t0 = time.time()
        eq = solve(inp, b, prm, start=start)
        m = metrics(eq.profile, inp, b, prm)
        truth = metrics([TRUTH] * prm.N, inp, b, prm)
        row = {"treatment": name + tag, "converged": eq.converged, "cycle": eq.cycle, "sweeps": eq.sweeps,
               "max_dev_gain": eq.max_dev_gain, "profile": fmt_profile(eq.profile),
               **{k: v for k, v in m.items() if k != "profit_per_owner"},
               "profit_total": m["profit_per_owner"].sum(),
               "truth_energy_MWh": truth["energy_MWh"], "truth_comp_paid": truth["comp_paid"],
               "truth_profit_total": truth["profit_per_owner"].sum(), "secs": time.time() - t0}
        rows.append(row)
        profiles[name + tag] = {"profile": eq.profile, "history": eq.history,
                                "profit_per_owner": m["profit_per_owner"].tolist()}
        print(f"{name+tag:28s} conv={eq.converged} cyc={eq.cycle} sweeps={eq.sweeps} "
              f"maxdev={eq.max_dev_gain:.2e}  {row['profile']}", flush=True)

    ic = BETAS.index("cap")
    allcap = [(ic, ic, ic, False)] * base.N
    for name, kw in TREATMENTS.items():
        prm = base.with_(**kw)
        run(name, prm)
        run(name, prm, start=allcap, tag=" [start=cap]")
    for name in NO_BATTERY:
        prm = base.with_(**TREATMENTS[name], P=0 * base.P, E=0 * base.E)
        run(name, prm, tag=" [no battery]")
    for name in ["T1 R/S0", "T2 R/S1 f=5l", "T3 R/S2", "T5 C/S1 f=5l", "T6 C/S2", "T3c R/S2c", "T6c C/S2c"]:
        run(name, base.with_(**TREATMENTS[name], discharge_rule="strict"), tag=" [strict battery]")

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "step3_summary.csv", index=False)
    (OUT / "step3_profiles.json").write_text(json.dumps(profiles, indent=1, default=str))
    pd.set_option("display.width", 250, "display.max_columns", 40)
    cols = ["treatment", "converged", "max_dev_gain", "bias_low", "bias_mid", "bias_high", "energy_MWh",
            "truth_energy_MWh", "curtailed_MWh", "stored_MWh", "discharge_MWh", "induced_cong_hours", "induced_curtailed_MWh",
            "induced_paid", "phys_cong_hours", "reported_not_phys_hours", "pay_over_gross", "pay_under_gross",
            "pay_net_error", "audit_recovery_exp", "comp_paid", "comp_eligible", "penalty_exp",
            "over_O", "over_storage", "over_inflation", "over_error", "over_self_induced", "profit_total",
            "truth_profit_total"]
    print(df[cols].round(3).to_string(index=False))


if __name__ == "__main__":
    main()

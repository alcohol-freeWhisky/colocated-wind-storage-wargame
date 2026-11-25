"""TOY 3: compare sharing rules on synthetic wind, with a correlation knob.

Question (Q4): how much energy does each rule lose compared with truthful
reports, and how does this depend on how similar the owners' wind is?

Rules (same names as the proposal):
  R0  truthful pro-rata (benchmark): shares in proportion to true available power
  R1  fixed shares by installed capacity (= what happens when everyone
      over-reports to the cap)
  R6  meter feedback, no reports: start from fixed shares; an owner that sent
      less than its share last hour is capped at (what it sent + margin);
      the leftover goes to the others

Wind comes from the Andoni et al. (2017) recipe (sources/04, p. 7), see
toy_common.synthetic_wind. No real data is needed.

Run:  python toy03_rules_synthetic_wind.py
"""
import numpy as np
from toy_common import pro_rata_rows, water_fill, synthetic_wind

# ---- numbers you can change ---------------------------------------------
L = np.array([100.0, 60.0, 30.0, 10.0])   # installed capacity of 4 owners (MW)
KAPPA = 0.6                               # K = KAPPA * sum(L)
HOURS = 24 * 365                          # one synthetic year
MARGIN = 0.10                             # meter-feedback margin (share of L)
PERSISTENCE = 0.95                        # hidden AR(1) persistence of wind (try 0.0)
# -------------------------------------------------------------------------
K = KAPPA * L.sum()


def run_rules(A):
    T, N = A.shape
    x_truth = np.minimum(A, pro_rata_rows(A, K))
    x_fixed = np.minimum(A, K * L / L.sum())
    x_fb = np.zeros_like(A)
    x_prev = k_prev = None
    for t in range(T):
        if x_prev is None:
            caps = L.copy()
        else:
            limited = x_prev < k_prev - 1e-9          # left part of its share unused
            caps = np.where(limited, x_prev + MARGIN * L, L)
        k = water_fill(caps, L, K)
        x_fb[t] = np.minimum(A[t], k)
        x_prev, k_prev = x_fb[t], k
    return x_truth, x_fixed, x_fb


print(f"4 owners, installed {L.tolist()} MW, connection K = {K:.0f} MW, one year of hours, "
      f"wind persistence {PERSISTENCE}")
print(f"{'wind corr. (r)':>14} {'power corr.':>11} {'hour-to-hour':>12} {'hours congested':>15} "
      f"{'R1 fixed loses':>15} {'R6 feedback loses':>18}")
rows = []
for r in [0.0, 0.25, 0.5, 0.75, 0.9, 1.0]:
    A = synthetic_wind(len(L), HOURS, r, L, seed=7, persistence=PERSISTENCE)
    pc = np.corrcoef(A.T)[np.triu_indices(len(L), 1)].mean()
    xt, xf, xb = run_rules(A)
    lf = 1 - xf.sum() / xt.sum(); lb = 1 - xb.sum() / xt.sum()
    cong = (A.sum(1) > K).mean()
    lag1 = np.mean([np.corrcoef(A[:-1, i], A[1:, i])[0, 1] for i in range(len(L))])
    rows.append((r, pc, lf, lb))
    print(f"{r:14.2f} {pc:11.2f} {lag1:12.2f} {cong:15.0%} {lf:15.1%} {lb:18.1%}")

print("""
Read the table:
 - R0 (truthful reports) loses nothing by construction.
 - R1 (fixed shares, = everyone lies to the cap) loses most when owners' wind
   is NOT similar: one owner's share sits unused while another is curtailed.
 - When wind is identical (r = 1), fixed shares lose nothing: everyone is
   curtailed by the same percentage anyway.
 - R6 (meter feedback) needs no reports but reacts one hour late. In this
   simulation it depends strongly on wind persisting from one hour to the
   next ('hour-to-hour' column = measured lag-1 correlation of power). Set
   PERSISTENCE = 0.0 above and run again: R6 then loses MORE than fixed shares.
 - Not tested here: owners gaming R6 (for example, discharging a battery just
   to keep a large share), as in turn-and-earn allocation (sources/09).
Compare with the real-data result in the proposal (Figure 6).""")

# one liar, others truthful, medium correlation
A = synthetic_wind(len(L), HOURS, 0.5, L, seed=7, persistence=PERSISTENCE)
base = np.minimum(A, pro_rata_rows(A, K))
print("\nOne owner reports its cap every hour, others truthful (r = 0.5):")
for i in range(len(L)):
    R = A.copy(); R[:, i] = L[i]
    X = np.minimum(A, pro_rata_rows(R, K))
    gain = (X[:, i] - base[:, i]).sum(); others = (np.delete(X - base, i, 1)).sum()
    print(f"  owner {i+1} ({L[i]:5.0f} MW): gains {gain / base[:, i].sum():+6.1%} of its energy; "
          f"others lose {-others:8.0f} MWh; wasted {base.sum() - X.sum():7.0f} MWh")

try:
    import matplotlib.pyplot as plt
    rr = np.array(rows)
    plt.figure(figsize=(6, 3.5))
    plt.plot(rr[:, 1], 100 * rr[:, 2], "o-", label="R1 fixed shares (= everyone lies)")
    plt.plot(rr[:, 1], 100 * rr[:, 3], "s-", label="R6 meter feedback")
    plt.xlabel("correlation of owners' power"); plt.ylabel("energy lost vs. truthful (%)")
    plt.legend(); plt.tight_layout(); plt.savefig("toy03_rules.png", dpi=120)
    print("Figure saved: toy03_rules.png")
except ImportError:
    print("(matplotlib not installed: no figure)")

"""TOY 2: the "lying does not pay" rule, checked by brute force.

Claim (proposal, Section 5.3). One hour, connection congested (Q = sum of true
available power > K), the other owners report the truth, the inspection
probability alpha does not depend on the report, the fine is f per MWh
over-reported. Then NO over-report pays if and only if

        alpha * f  >=  v * K * (Q - a_i) / Q**2 .

This script:
  1. checks the claim on 3,000 random cases;
  2. shows, for Example B, the smallest inspection probability for several fines
     (this is the checker's "commit first" (Stackelberg) choice).

Run:  python toy02_lying_rule.py
"""
import numpy as np
from toy_common import pro_rata, sends

rng = np.random.default_rng(1)


def best_net_gain(a, i, K, v, alpha, f, cap):
    """Largest expected extra profit owner i can get by over-reporting by d,
    others truthful. Searched on a fine grid of d (vectorized)."""
    S = a.sum() - a[i]                        # sum of the others' (true) reports
    base = sends(a, pro_rata(a, K))[i]
    d = np.linspace(1e-4, cap - a[i], 4000)
    l_i = a[i] + d
    share = np.where(S + l_i > K, l_i * K / (S + l_i), l_i)
    gain = np.minimum(a[i], share) - base
    return float(np.max(v * gain - alpha * f * d))


print("STEP 1. Random test of the rule")
agree = cases = 0
while cases < 3000:
    N = rng.integers(2, 6)
    a = rng.uniform(1, 10, N)
    Q = a.sum(); K = rng.uniform(0.3, 0.95) * Q          # congested hour
    i = 0; v = 1.0; cap = a[i] + rng.uniform(1, 10)
    threshold = v * K * (Q - a[i]) / Q**2
    alpha = rng.uniform(0, 1); f = rng.uniform(0, 3)
    if abs(alpha * f - threshold) < 0.01:              # too close to call on a grid
        continue
    rule_says_honest = alpha * f >= threshold
    brute_says_honest = best_net_gain(a, i, K, v, alpha, f, cap) <= 1e-9
    agree += rule_says_honest == brute_says_honest
    cases += 1
print(f"  rule and brute force agree in {agree} of {cases} random cases")
print("  (a numerical check on a finite grid, away from the exact threshold;")
print("   the proof is the concavity argument in the proposal, Section 5.3)")

print("\nSTEP 2. Example B: a = (8, 4), K = 9, v = $100/MWh, owner 2 is the liar")
a = np.array([8.0, 4.0]); K = 9.0; v = 100.0
Q = a.sum(); thr = v * K * (Q - a[1]) / Q**2
print(f"  value of the first small step of lying: ${thr:.0f} per MW")
print(f"  {'fine per MW ($)':>16} {'smallest inspection prob.':>27}")
for f in [50, 100, 200, 500, 1000]:
    need = thr / f
    print(f"  {f:16.0f} {(f'{need:.0%}' if need <= 1 else 'infeasible (>100%)'):>27}")
print("""
Lesson: the checker can trade inspections for fines. A fine twice as large
needs half the inspections. In real life fines are capped (by contracts or law),
so the inspection budget still matters.

Warning: an owner can choose WHEN to lie. Over a day, the rule must hold in the
hour where lying pays most (largest K*(Q - a_i)/Q^2). Try other numbers above.""")

"""TOY 1: two owners, one hour (Example B of the proposal).

Question: if the connection is split in proportion to reports, does owner 2
want to over-report? What happens when both owners can choose?

Run:  python toy01_two_owners.py
Change the numbers in the block below and run again.
"""
import numpy as np
from toy_common import pro_rata, sends

# ---- numbers you can change ---------------------------------------------
a = np.array([8.0, 4.0])    # true available power of owner 1 and owner 2 (MW)
K = 9.0                     # connection limit (MW)
CAP = 10.0                  # largest report allowed (installed capacity, MW)
V = 100.0                   # value of one MWh ($)
STEP = 0.1                  # report grid for the equilibrium search (MW)
# -------------------------------------------------------------------------


def outcome(l1, l2):
    k = pro_rata([l1, l2], K)
    x = sends(a, k)
    return k, x


print("=" * 70)
print("STEP 1. Owner 1 tells the truth. Owner 2 tries different reports.")
print("=" * 70)
print(f"{'owner 2 report':>15} {'share 1':>8} {'share 2':>8} {'sent 1':>7} {'sent 2':>7} {'unused':>7}")
for l2 in [a[1], 5.0, 6.0, 6.4, 7.0, 8.0, CAP]:
    k, x = outcome(a[0], l2)
    print(f"{l2:15.1f} {k[0]:8.2f} {k[1]:8.2f} {x[0]:7.2f} {x[1]:7.2f} {K - x.sum():7.2f}")
print("""
Read the table:
 - From 4 to 6.4 MW, owner 2 gains exactly what owner 1 loses (a TRANSFER).
 - Above 6.4 MW, owner 2's share is larger than what it has, so part of
   the connection is unused (WASTE).
 - At 6.4 MW, owner 2 sends exactly its share: the meter sees nothing odd.""")

# exact point where owner 2's share reaches its true power, others truthful:
# l2 * K / (a1 + l2) = a2  ->  l2 = a2 * a1 / (K - a2)
l2_star = a[1] * a[0] / (K - a[1])
print(f"Smallest report that gives owner 2 all its power: {l2_star:.2f} MW")

print()
print("=" * 70)
print("STEP 2. Both owners choose. Search all report pairs on a grid.")
print("=" * 70)
grid = np.round(np.arange(STEP, CAP + 1e-9, STEP), 6)
n = len(grid)
U = np.zeros((n, n, 2))
for i, l1 in enumerate(grid):
    for j, l2 in enumerate(grid):
        U[i, j] = V * outcome(l1, l2)[1]
best1 = U[:, :, 0].max(axis=0)          # best payoff of owner 1 for each l2
best2 = U[:, :, 1].max(axis=1)          # best payoff of owner 2 for each l1
ne = [(float(grid[i]), float(grid[j])) for i in range(n) for j in range(n)
      if U[i, j, 0] >= best1[j] - 1e-9 and U[i, j, 1] >= best2[i] - 1e-9]
print(f"Number of Nash equilibria on the grid: {len(ne)}")
l1s = sorted({e[0] for e in ne}); l2s = sorted({e[1] for e in ne})
print(f"Owner 1 reports in equilibrium: {l1s[0]} to {l1s[-1]}")
print(f"Owner 2 reports in equilibrium: {l2s[0]} to {l2s[-1]}")
for e in [ne[0], ne[-1]]:
    k, x = outcome(*e)
    print(f"  example equilibrium {e}: sent = {x.round(2)}, unused = {K - x.sum():.2f}")
truth_is_ne = any(abs(e[0] - a[0]) < 1e-9 and abs(e[1] - a[1]) < 1e-9 for e in ne)
print(f"Is 'both tell the truth' an equilibrium? {truth_is_ne}")
print("""
Lesson: reporting the cap is never worse than any other report (a bigger report
never lowers your own share): it is WEAKLY DOMINANT. So 'everyone at the cap'
is always an equilibrium, and then the rule behaves like fixed shares by
capacity. It is not the only equilibrium: an owner that already gets all its
power is indifferent among several reports (see the range above).""")

try:
    import matplotlib.pyplot as plt
    l2s_plot = np.linspace(2, CAP, 400)
    X = np.array([outcome(a[0], l)[1] for l in l2s_plot])
    plt.figure(figsize=(6, 3.5))
    plt.plot(l2s_plot, X[:, 0], label="owner 1 sends (honest)")
    plt.plot(l2s_plot, X[:, 1], label="owner 2 sends")
    plt.fill_between(l2s_plot, 0, K - X.sum(1), alpha=0.3, label="unused connection")
    plt.axvline(a[1], ls=":", c="k"); plt.axvline(l2_star, ls=":", c="k")
    plt.xlabel("owner 2's report (MW)"); plt.ylabel("MWh in the hour"); plt.legend()
    plt.tight_layout(); plt.savefig("toy01_two_owners.png", dpi=120)
    print("Figure saved: toy01_two_owners.png")
except ImportError:
    print("(matplotlib not installed: no figure)")

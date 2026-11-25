"""TOY 4: do learning owners find the equilibrium? (Q1, Q2, Q3)

Three owners share a connection. Each day, each owner picks ONE report option
for the whole day:
    0 truth       report = available power
    1 x1.25       report = min(1.25 * available, cap)
    2 x1.5        report = min(1.5 * available, cap)
    3 cap         report = cap (installed capacity) every hour
A checker inspects ONE owner per day, at random (probability 1/3 each), and
fines PHI x (value of one MWh) per MWh over-reported that day.

The script does two things for each fine level:
  A. Game theory: it computes all pure Nash equilibria of this 4 x 4 x 4 game
     (expected payoffs over a set of synthetic days).
  B. Learning: each owner runs EXP3 (sources/12): it sees only its own profit.
Then it compares A and B.

Run:  python toy04_learning_vs_equilibrium.py      (about 20-40 seconds)
"""
import itertools
import numpy as np
from toy_common import pro_rata_rows, synthetic_wind

# ---- numbers you can change ---------------------------------------------
L = np.array([60.0, 30.0, 10.0])   # installed capacity (MW)
KAPPA = 0.6                        # K = KAPPA * sum(L)
N_DAYS = 200                       # synthetic days used as the "world"
R_CORR = 0.75                      # wind correlation between owners
FINES = [0.0, 1.0, 4.0]            # fine per MWh over-reported, in MWh-values
T_LEARN = 60000                    # days of repeated play for learning
GAMMA = 0.07                       # EXP3 exploration rate
SEED = 3
# -------------------------------------------------------------------------
K = KAPPA * L.sum()
N, NA = len(L), 4
NAMES = ["truth", "x1.25", "x1.5", "cap"]
ALPHA = 1.0 / N                     # random checker: 1 inspection per day

A = synthetic_wind(N, 24 * N_DAYS, R_CORR, L, seed=SEED).reshape(N_DAYS, 24, N)


def reports(arms, a):
    """Reports for one day, given each owner's option."""
    R = a.copy()
    for i, k in enumerate(arms):
        if k == 1: R[:, i] = np.minimum(1.25 * a[:, i], L[i])
        if k == 2: R[:, i] = np.minimum(1.5 * a[:, i], L[i])
        if k == 3: R[:, i] = L[i]
    return R


def day_result(arms, a):
    R = reports(arms, a)
    x = np.minimum(a, pro_rata_rows(R, K))
    return x.sum(0), (R - a).clip(0).sum(0)          # energy, over-reported MWh


# precompute energy and over-reporting for every profile and day
profiles = list(itertools.product(range(NA), repeat=N))
E = np.zeros((len(profiles), N_DAYS, N)); O = np.zeros_like(E)
for p, prof in enumerate(profiles):
    for d in range(N_DAYS):
        E[p, d], O[p, d] = day_result(prof, A[d])
index = {prof: p for p, prof in enumerate(profiles)}


def equilibria(phi):
    U = (E - ALPHA * phi * O).mean(1)                 # expected payoff per profile
    out = []
    for p, prof in enumerate(profiles):
        stable = True
        for i in range(N):
            for k in range(NA):
                q = list(prof); q[i] = k
                if U[index[tuple(q)], i] > U[p, i] + 1e-9:
                    stable = False
        if stable:
            out.append(prof)
    return out


def learn(phi, seed=0):
    """EXP3 for each owner. Reward scaled to [0, 1] with fixed bounds:
    energy <= 24*L and over-reported MWh <= 24*L, so
    payoff/(24 L) is in [-phi, 1]."""
    rng = np.random.default_rng(seed)
    logw = np.zeros((N, NA))
    for t in range(T_LEARN):
        w = np.exp(logw - logw.max(1, keepdims=True))
        prob = (1 - GAMMA) * w / w.sum(1, keepdims=True) + GAMMA / NA
        arms = tuple(rng.choice(NA, p=prob[i]) for i in range(N))
        d = rng.integers(N_DAYS)
        energy, over = E[index[arms], d], O[index[arms], d]
        fine = np.zeros(N)
        j = rng.integers(N)                           # the inspected owner today
        fine[j] = phi * over[j]
        r = ((energy - fine) / (24 * L) + phi) / (1 + phi)
        for i in range(N):
            logw[i, arms[i]] += GAMMA / NA * r[i] / prob[i, arms[i]]
    w = np.exp(logw - logw.max(1, keepdims=True))
    return (1 - GAMMA) * w / w.sum(1, keepdims=True) + GAMMA / NA   # what is actually played


print(f"Owners {L.tolist()} MW, K = {K:.0f} MW, wind correlation {R_CORR}, "
      f"inspection prob. {ALPHA:.0%} per owner per day")
for phi in FINES:
    print("\n" + "=" * 70)
    print(f"Fine = {phi} x value of one MWh, per MWh over-reported")
    ne = equilibria(phi)
    print("  A. Pure Nash equilibria:")
    for prof in ne:
        print("     " + ", ".join(NAMES[k] for k in prof))
    if not ne:
        print("     none in pure strategies")
    P = np.mean([learn(phi, seed=s) for s in range(3)], axis=0)
    print("  B. What EXP3 learners play at the end (average of 3 runs):")
    for i in range(N):
        print(f"     owner {i+1} ({L[i]:3.0f} MW): " +
              "  ".join(f"{NAMES[k]} {P[i, k]:.2f}" for k in range(NA)))

print("""
How to read (with the default numbers): with no fine, the only pure
equilibrium is 'cap' for everyone. With a fine of 1x or 4x, it is 'truth' for
everyone. The learners move toward these equilibria, but slowly and with
mixing (exploration, noise, finite runs). Other numbers can give other
results: try FINES = [0.3] (a 'small lie' equilibrium), more days
(T_LEARN), or another wind correlation.""")

"""Small simulations for 'Wargame Project - Simplified Proposal.md'.

Run from anywhere:
    python "Clean Start/Our References/update_20261120/sims/simplified_sims.py"

Uses only numpy, pandas, matplotlib and the processed ERCOT data already in the
repository (data/processed). Writes PNG figures to ../figures and prints every
number quoted in the proposal.

Units: power in MW, energy in MWh, one period = one hour.
Payoffs in the learning experiment are in "MWh-equivalents": one delivered MWh
is worth v = 1, and a fine of phi means phi x v per MWh over-reported.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
FIG = HERE.parent / "figures"
REPO = HERE.parents[3]
FIG.mkdir(exist_ok=True)

UNITS = ["ANCHOR_WIND1", "ANCHOR_WIND2", "ANCHOR_WIND3", "ANCHOR_WIND4", "ANCHOR_WIND5"]
SHORT = ["W1 (16 MW)", "W2 (99 MW)", "W3 (89 MW)", "W4 (39 MW)", "W5 (19 MW)"]
KAPPA = 0.6            # K = KAPPA * total wind nameplate (designed stress level)
P_RATIO, DUR = 0.29, 1.5   # battery power / wind nameplate, hours (Anchor-like)
ETA = 0.922            # one-way battery efficiency

C = {"blue": "#2E6FBA", "orange": "#E07B24", "green": "#3A9A5B", "red": "#C8423B",
     "grey": "#7F7F7F", "purple": "#7A5AA6"}
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                     "figure.dpi": 150, "savefig.bbox": "tight"})


# ----------------------------------------------------------------------------
# Allocation rules
# ----------------------------------------------------------------------------
def pro_rata(reports, K):
    """Share proportional to reports: k_i = l_i * min(1, K / sum l)."""
    s = reports.sum()
    return reports.copy() if s <= K else reports * K / s


def pro_rata_rows(R, K):
    """Row-wise pro_rata for a (T, N) array of reports."""
    tot = R.sum(1, keepdims=True)
    return R * np.minimum(1.0, K / np.maximum(tot, 1e-12))


def water_fill(caps, weights, K):
    """k_i = min(cap_i, lam * w_i) with sum k = K (weighted max-min fill).
    If the caps do not use K, the leftover is spread by weights."""
    if caps.sum() <= K:
        return caps + (K - caps.sum()) * weights / weights.sum()
    lo, hi = 0.0, float((caps / weights).max())
    for _ in range(60):
        lam = 0.5 * (lo + hi)
        if np.minimum(caps, lam * weights).sum() > K:
            hi = lam
        else:
            lo = lam
    return np.minimum(caps, lo * weights)


# ----------------------------------------------------------------------------
# Data
# ----------------------------------------------------------------------------
def load_data(units=UNITS):
    UNITS_ = units
    w = pd.read_parquet(REPO / "data/processed/wind_hourly.parquet")
    w = w[w.resource.isin(UNITS_)]
    A = w.pivot_table(index="Interval Start", columns="resource", values="W_avail")[UNITS_]
    f = pd.read_parquet(REPO / "data/processed/forecast_error_resource.parquet")
    f = f[f.resource.isin(UNITS_)]
    E = f.pivot_table(index="Interval Start", columns="resource", values="What_cop")
    E = E.reindex(index=A.index, columns=UNITS_)
    n_missing = int(E.isna().sum().sum())
    E = E.fillna(A.shift(1)).fillna(0.0)    # observable fallback: last hour's availability
    res = pd.read_csv(REPO / "data/processed/resources.csv").set_index("resource")
    L = res.loc[UNITS_, "nameplate_mw"].to_numpy(float)
    A = A.clip(lower=0)
    A = np.minimum(A.to_numpy(float), L)
    T = (A.shape[0] // 24) * 24                     # keep full days only
    E = np.clip(E.to_numpy(float), 0, L)[:T]
    if units == UNITS:
        err = (E - A[:T]) / L
        print(f"[data] checker estimate (COP) missing cells: {n_missing}; "
              f"error std = {err.std():.3f} x nameplate")
    return A[:T], E, L


# ----------------------------------------------------------------------------
# Example B: two owners, one hour
# ----------------------------------------------------------------------------
def example_b():
    a1, a2, K, v, cap = 8.0, 4.0, 9.0, 100.0, 10.0
    r2 = np.linspace(2.0, cap, 1000)
    x1, x2, unused = [], [], []
    for r in r2:
        k = pro_rata(np.array([a1, r]), K)
        x = np.minimum([a1, a2], k)
        x1.append(x[0]); x2.append(x[1]); unused.append(K - x.sum())
    x1, x2, unused = map(np.array, (x1, x2, unused))

    print("\n=== Example B ===")
    for r in (4.0, 6.4, 8.0, 10.0):
        k = pro_rata(np.array([a1, r]), K); x = np.minimum([a1, a2], k)
        print(f"owner2 reports {r:4.1f}: x1={x[0]:.2f} x2={x[1]:.2f} unused={K-x.sum():.2f}")
    Q = a1 + a2
    mg = v * K * (Q - a2) / Q**2
    print(f"marginal gain at truth = ${mg:.0f} per MW over-reported")

    # Nash equilibria on a grid (reports capped at 10 MW = installed capacity)
    grid = np.round(np.arange(0.1, cap + 1e-9, 0.1), 1)
    def pay(l1, l2):
        k = pro_rata(np.array([l1, l2]), K); return np.minimum([a1, a2], k)
    P = np.array([[pay(l1, l2) for l2 in grid] for l1 in grid])  # (n,n,2)
    br1 = P[:, :, 0].max(axis=0); br2 = P[:, :, 1].max(axis=1)
    ne = [(grid[i], grid[j]) for i in range(len(grid)) for j in range(len(grid))
          if P[i, j, 0] >= br1[j] - 1e-9 and P[i, j, 1] >= br2[i] - 1e-9]
    l1s = sorted({e[0] for e in ne}); l2s = sorted({e[1] for e in ne})
    outs = [pay(*e) for e in ne]
    print(f"NE count={len(ne)}; l1 in [{min(l1s)},{max(l1s)}], l2 in [{min(l2s)},{max(l2s)}]")
    print(f"NE x1 range [{min(o[0] for o in outs):.2f},{max(o[0] for o in outs):.2f}], "
          f"x2 range [{min(o[1] for o in outs):.2f},{max(o[1] for o in outs):.2f}], "
          f"unused range [{min(K-o.sum() for o in outs):.2f},{max(K-o.sum() for o in outs):.2f}]")
    print("truthful (8,4) is NE:", (8.0, 4.0) in ne)

    fig, ax = plt.subplots(1, 2, figsize=(10, 3.6))
    ax[0].plot(r2, x1, color=C["blue"], lw=2, label="Owner 1 sends (honest, has 8)")
    ax[0].plot(r2, x2, color=C["orange"], lw=2, label="Owner 2 sends (has 4)")
    ax[0].fill_between(r2, 0, unused, color=C["red"], alpha=0.25, label="Unused connection")
    ax[0].axvline(4, color="k", ls=":", lw=1); ax[0].text(3.25, 9.6, "truth", fontsize=9)
    ax[0].axvline(6.4, color="k", ls=":", lw=1); ax[0].text(6.5, 9.6, "6.4", fontsize=9)
    ax[0].axvspan(4, 6.4, color=C["orange"], alpha=0.08)
    ax[0].axvspan(6.4, cap, color=C["red"], alpha=0.06)
    ax[0].text(4.3, 1.0, "transfer\nzone", fontsize=8.5, color=C["orange"])
    ax[0].text(7.6, 1.0, "transfer +\nwaste zone", fontsize=8.5, color=C["red"])
    ax[0].set_xlabel("Owner 2's report (MW)"); ax[0].set_ylabel("Energy sent in the hour (MWh)")
    ax[0].set_title("(a) Who sends what, as owner 2 over-reports")
    ax[0].set_ylim(0, 10.5); ax[0].legend(fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.17), frameon=False, ncol=3)

    fine = 100.0  # $ per MW over-reported, = value of 1 MWh
    for alpha, col in [(0.0, C["red"]), (0.25, C["orange"]), (0.5, C["green"]), (0.75, C["blue"])]:
        net = v * (x2 - 3.0) - alpha * fine * np.clip(r2 - a2, 0, None)
        ax[1].plot(r2[r2 >= 4], net[r2 >= 4], lw=2, color=col, label=f"inspection prob. {alpha:.0%}")
    ax[1].axhline(0, color="k", lw=0.8)
    ax[1].set_xlabel("Owner 2's report (MW)"); ax[1].set_ylabel("Owner 2's expected extra profit ($)")
    ax[1].set_title("(b) Fine = $100 per MW over-reported")
    ax[1].legend(fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.17), frameon=False, ncol=2)
    fig.savefig(FIG / "fig2_example_b.png"); plt.close(fig)


# ----------------------------------------------------------------------------
# Real data: compare sharing rules (truthful owners)
# ----------------------------------------------------------------------------
def simulate_rule(A, L, K, rule, battery, lag_margin=0.10):
    """Return delivered energy per hour (T,N) for a sharing rule.
    rule in {'truthful', 'fixed', 'feedback'}. Batteries follow a simple greedy plan:
    send as much as the share allows (wind first, then battery); store wind that
    cannot be sent."""
    T, N = A.shape
    P = P_RATIO * L if battery else np.zeros(N)
    Emax = DUR * P
    soc = 0.5 * Emax
    X = np.zeros((T, N))
    x_prev = k_prev = None
    for t in range(T):
        dis_max = np.minimum(P, soc * ETA)
        a = A[t] + dis_max                       # power the owner could send now
        if rule == "truthful":
            k = pro_rata(a, K)
        elif rule == "fixed":
            k = K * L / L.sum()
        elif rule == "feedback":
            if x_prev is None:
                caps = L + P
            else:
                limited = x_prev < k_prev - 1e-6        # sent less than its share
                caps = np.where(limited, x_prev + lag_margin * L, L + P)
            k = water_fill(caps, L, K)
        x = np.minimum(a, k)
        wind_used = np.minimum(A[t], x)
        dis = x - wind_used
        spill = A[t] - wind_used
        ch = np.minimum(np.minimum(P, spill), (Emax - soc) / ETA) if battery else 0 * spill
        soc = soc - dis / ETA + ch * ETA
        X[t] = x
        x_prev, k_prev = x, k
    return X


def rules_on_real_data(A, L):
    K = KAPPA * L.sum()
    days = A.shape[0] / 24
    print(f"\n=== Real data: Anchor Wind, {A.shape[0]} h ({days:.0f} full days), K = {K:.1f} MW ===")
    print(f"hours with total available wind > K: {(A.sum(1) > K).mean():.0%}")
    out = {}
    for battery in (False, True):
        for rule in ("truthful", "fixed", "feedback"):
            X = simulate_rule(A, L, K, rule, battery)
            out[(battery, rule)] = X.sum() / days
    for battery in (False, True):
        ideal = out[(battery, "truthful")]
        for rule in ("truthful", "fixed", "feedback"):
            v = out[(battery, rule)]
            print(f"battery={battery!s:5}  {rule:9s}: {v:8.1f} MWh/day   lost vs truthful: "
                  f"{ideal - v:6.1f} MWh/day ({(ideal - v) / ideal:5.1%})")

    # one owner over-reports, others truthful (wind only)
    print("\n-- one owner over-reports to its installed capacity in every hour; others truthful --")
    base = np.minimum(A, pro_rata_rows(A, K))
    rows = []
    for i in range(len(L)):
        R = A.copy(); R[:, i] = L[i]
        X = np.minimum(A, pro_rata_rows(R, K))
        gain = (X[:, i] - base[:, i]).sum() / days
        others = (np.delete(X, i, 1) - np.delete(base, i, 1)).sum() / days
        waste = (base.sum() - X.sum()) / days
        rows.append((SHORT[i], gain, gain / (base[:, i].sum() / days), others, waste))
        print(f"{SHORT[i]:11s}: liar +{gain:6.1f} MWh/day ({gain / (base[:, i].sum() / days):+.1%}), "
              f"others {others:7.1f}, wasted {waste:5.1f}")

    # everybody at cap (= fixed shares) by unit: who wins, who loses
    Xf = simulate_rule(A, L, K, "fixed", False)
    print("\n-- everybody reports installed capacity (= fixed shares) vs truthful, per unit --")
    for i in range(len(L)):
        d = (Xf[:, i].sum() - base[:, i].sum()) / days
        print(f"{SHORT[i]:11s}: {d:+7.1f} MWh/day ({d / (base[:, i].sum() / days):+.1%})")

    labels = ["Truthful reports\n(benchmark)", "Everyone over-reports\n(= fixed shares)",
              "Meter feedback\n(1-hour lag, no reports)"]
    fig, ax = plt.subplots(figsize=(7.5, 3.4))
    xs = np.arange(3); wdt = 0.36
    for j, battery in enumerate((False, True)):
        ideal = out[(battery, "truthful")]
        vals = [ideal - out[(battery, r)] for r in ("truthful", "fixed", "feedback")]
        b = ax.bar(xs + (j - 0.5) * wdt, vals, wdt, color=[C["grey"], C["blue"]][j],
                   label=["Wind only", "Wind + battery"][j])
        for rect, v in zip(b, vals):
            ax.text(rect.get_x() + rect.get_width() / 2, v + 0.4, f"{v:.0f}", ha="center", fontsize=8.5)
    ax.set_xticks(xs); ax.set_xticklabels(labels)
    ax.set_ylabel("Energy lost vs. truthful\n(MWh per day)")
    ax.set_title(f"Anchor Wind, 60 days, K = {K:.0f} MW (60% of nameplate)")
    ax.set_ylim(0, 26)
    ax.legend(frameon=False)
    fig.savefig(FIG / "fig3_rules_real_data.png"); plt.close(fig)
    return out


# ----------------------------------------------------------------------------
# Stress: incentive to lie and needed inspection rate vs. connection size
# ----------------------------------------------------------------------------
def stress_curve(A, L):
    kappas = np.round(np.arange(0.4, 1.01, 0.05), 2)
    phi = 3.0                     # fine per MWh over-reported, in units of v
    mults = [1.1, 1.25, 1.5, 2.0, None]   # None = report installed capacity
    print("\n=== Stress: gain from lying and needed inspection probability vs K ===")
    gains, alphas = [], []
    for kap in kappas:
        K = kap * L.sum()
        base = np.minimum(A, pro_rata_rows(A, K))
        g_row, a_row = [], []
        for i in range(len(L)):
            best_ratio, best_gain = 0.0, 0.0
            for m in mults:
                for windy_only in (False, True):
                    R = A.copy()
                    lie = L[i] if m is None else np.minimum(m * A[:, i], L[i])
                    mask = (A[:, i] > 0.5 * L[i]) if windy_only else np.ones(len(A), bool)
                    R[:, i] = np.where(mask, lie, A[:, i])
                    X = np.minimum(A, pro_rata_rows(R, K))
                    g = (X[:, i] - base[:, i]).sum()
                    over = (R[:, i] - A[:, i]).clip(0).sum()
                    if over > 0:
                        best_ratio = max(best_ratio, g / over)
                        best_gain = max(best_gain, g / base[:, i].sum())
            g_row.append(best_gain); a_row.append(min(1.0, best_ratio / phi))
        gains.append(g_row); alphas.append(a_row)
        print(f"kappa={kap:.2f}: best % gain by unit {np.round(100*np.array(g_row),1)}; "
              f"needed inspection prob (fine={phi:g}) {np.round(a_row,2)}")
    gains, alphas = np.array(gains), np.array(alphas)

    fig, ax = plt.subplots(1, 2, figsize=(10, 3.5))
    cols = [C["red"], C["blue"], C["green"], C["orange"], C["purple"]]
    for i in range(len(L)):
        ax[0].plot(kappas, 100 * gains[:, i], color=cols[i], lw=2, label=SHORT[i])
        ax[1].plot(kappas, alphas[:, i], color=cols[i], lw=2)
    for a_ in ax:
        a_.axvline(0.6, color="k", ls=":", lw=1)
        a_.axvspan(0.4, 0.5, color=C["red"], alpha=0.07)
        a_.set_xlabel("Connection size K / wind nameplate")
    ax[0].text(0.405, ax[0].get_ylim()[1] * 0.92, "stress\n(derate)", fontsize=8, color=C["red"])
    ax[0].text(0.61, ax[0].get_ylim()[1] * 0.92, "base case", fontsize=8)
    ax[0].set_ylabel("Best gain from lying\n(% of honest energy)")
    ax[0].set_title("(a) Lying pays more when K is smaller")
    ax[0].legend(fontsize=8, frameon=False)
    ax[1].set_ylabel("Inspection probability needed")
    ax[1].set_title(f"(b) Inspection rate so that no lie pays\n(fine = {phi:g} x value of 1 MWh)")
    ax[1].axhline(0.2, color=C["grey"], ls="--", lw=1)
    ax[1].text(0.82, 0.205, "1 inspection/day, 5 owners", fontsize=8, color=C["grey"])
    ax[1].set_ylim(0, 0.25)
    fig.savefig(FIG / "fig4_stress.png"); plt.close(fig)
    return kappas, gains, alphas


# ----------------------------------------------------------------------------
# Learning: owners learn what to report (EXP3), checker with 1 inspection/day
# ----------------------------------------------------------------------------
ARMS = [("truth", 1.0, False), ("x1.25", 1.25, False), ("x1.5", 1.5, False),
        ("cap", None, False), ("cap when windy", None, True)]


def build_reports(arm_idx, a, L):
    R = a.copy()
    for i, k in enumerate(arm_idx):
        _, m, windy = ARMS[k]
        lie = np.full(a.shape[0], L[i]) if m is None else np.minimum(m * a[:, i], L[i])
        mask = (a[:, i] > 0.5 * L[i]) if windy else np.ones(a.shape[0], bool)
        R[:, i] = np.where(mask, np.maximum(lie, a[:, i]), a[:, i])
    return R


def learning_run(Ad, Ed, L, K, policy, phi, T, seed, gamma=0.07):
    rng = np.random.default_rng(seed)
    N, n = len(L), len(ARMS)
    logw = np.zeros((N, n))
    over_hist = np.zeros(T); truth_hist = np.zeros(T); caught = 0; lies = 0
    # payoff per owner-day lies in [-phi*24*L_i, 24*L_i] because energy and
    # over-reported MWh are both at most 24*L_i; rescale to [0,1]
    scale = 24.0 * L
    for day in range(T):
        d = rng.integers(len(Ad)); a, est = Ad[d], Ed[d]
        w = np.exp(logw - logw.max(1, keepdims=True)); p = (1 - gamma) * w / w.sum(1, keepdims=True) + gamma / n
        arms = np.array([rng.choice(n, p=p[i]) for i in range(N)])
        R = build_reports(arms, a, L)
        X = np.minimum(a, pro_rata_rows(R, K))
        energy = X.sum(0); over = (R - a).clip(0).sum(0)
        fine = np.zeros(N)
        if policy == "random":
            j = rng.integers(N)
        elif policy == "targeted":
            score = (R - est).sum(0) / L          # report above independent estimate
            j = int(np.argmax(score))
        else:
            j = None
        if j is not None:
            fine[j] = phi * over[j]
            caught += over[j] > 1e-9
        lies += (over > 1e-9).sum()
        avail = a.sum(0)
        r = ((energy - fine) / scale + phi) / (1.0 + phi)       # in [0,1]
        assert r.min() >= -1e-9 and r.max() <= 1 + 1e-9
        for i in range(N):
            logw[i, arms[i]] += gamma / n * r[i] / p[i, arms[i]]
        over_hist[day] = over.sum() / max(avail.sum(), 1e-9)
        truth_hist[day] = (arms == 0).mean()
    final_p = np.exp(logw - logw.max(1, keepdims=True))
    final_p = (1 - gamma) * final_p / final_p.sum(1, keepdims=True) + gamma / n   # includes exploration
    return over_hist, truth_hist, final_p, caught / max(lies, 1)


def learning(A, E, L, T=50000, seeds=6, ne_levels=None):
    K = KAPPA * L.sum()
    nd = A.shape[0] // 24
    Ad = A[: nd * 24].reshape(nd, 24, -1); Ed = E[: nd * 24].reshape(nd, 24, -1)
    configs = [("No checks", "none", 0.0, C["red"]),
               ("Random checks, small fine (1x)", "random", 1.0, C["orange"]),
               ("Random checks, large fine (5x)", "random", 5.0, C["green"]),
               ("Targeted checks, small fine (1x)", "targeted", 1.0, C["blue"])]
    print(f"\n=== Learning (EXP3, {T} days, {seeds} seeds, 1 inspection/day) ===")
    res = {}
    for name, pol, phi, col in configs:
        H = []; Tr = []; Fp = []; cr = []
        for s in range(seeds):
            h, tr, fp, c = learning_run(Ad, Ed, L, K, pol, phi, T, 1000 + s)
            H.append(h); Tr.append(tr); Fp.append(fp); cr.append(c)
        H = np.array(H); Tr = np.array(Tr); Fp = np.mean(Fp, 0)
        res[name] = (H, Tr, Fp, col)
        last = slice(T - 5000, T)
        print(f"{name:34s}: over-report first 200 d {100*H[:, :200].mean():5.1f}%")
        print(f"{name:34s}: over-report (last 5000 d) {100*H[:, last].mean():5.1f}% of available, "
              f"truthful share {Tr[:, last].mean():.0%}, P(lie caught) {np.mean(cr):.0%}")
        print("   final mixed strategy per owner (truth, x1.25, x1.5, cap, cap-when-windy):")
        for i in range(len(L)):
            print(f"   {SHORT[i]:11s} " + " ".join(f"{q:.2f}" for q in Fp[i]))

    fig, ax = plt.subplots(1, 2, figsize=(10, 3.5))
    k = 200
    days_axis = np.arange(1, T + 1)
    for name, (H, Tr, Fp, col) in res.items():
        m = pd.Series(H.mean(0)).rolling(k, min_periods=1).mean() * 100
        ax[0].plot(days_axis, m, color=col, lw=2, label=name)
        mt = pd.Series(Tr.mean(0)).rolling(k, min_periods=1).mean()
        ax[1].plot(days_axis, mt, color=col, lw=2)
        if ne_levels and name in ne_levels:
            for lev in sorted(set(ne_levels[name])):
                ax[0].axhline(100 * lev, color=col, ls="--", lw=1)
    for a_ in ax:
        a_.set_xscale("log")
    ax[0].set_xlabel("Day of repeated play"); ax[0].set_ylabel("Over-reported energy\n(% of available)")
    ax[0].set_title("(a) How much owners over-report\n(dashed = equilibrium levels)")
    ax[0].legend(fontsize=8, frameon=False)
    ax[1].set_xlabel("Day of repeated play"); ax[1].set_ylabel("Share of owners reporting the truth")
    ax[1].set_title("(b) How often owners tell the truth"); ax[1].set_ylim(0, 1)
    fig.savefig(FIG / "fig5_learning.png"); plt.close(fig)
    return res


# ----------------------------------------------------------------------------
# Schematic of the setting
# ----------------------------------------------------------------------------
def schematic():
    fig, ax = plt.subplots(figsize=(9, 3.6)); ax.axis("off")
    ax.set_xlim(0, 10); ax.set_ylim(0, 4)
    for j, (y, name) in enumerate([(3.2, "Owner 1"), (2.0, "Owner 2"), (0.8, "Owner 3")]):
        ax.add_patch(plt.Rectangle((0.2, y - 0.4), 2.2, 0.8, fc="#EAF1FA", ec=C["blue"]))
        ax.text(1.3, y + 0.12, name, ha="center", fontsize=10, weight="bold")
        ax.text(1.3, y - 0.2, "wind + battery", ha="center", fontsize=8.5)
        ax.annotate("", xy=(4.6, 2.0), xytext=(2.45, y), arrowprops=dict(arrowstyle="->", color=C["blue"], lw=1.5))
        ax.text(3.0, y + (0.18 if y > 2 else -0.3) if y != 2.0 else y + 0.1,
                ["report $\\ell_1$", "report $\\ell_2$", "report $\\ell_3$"][j], fontsize=8.5, color=C["grey"])
    ax.add_patch(plt.Circle((5.1, 2.0), 0.5, fc="#FFF3E6", ec=C["orange"], lw=2))
    ax.text(5.1, 2.08, "shared\nconnection", ha="center", va="center", fontsize=8)
    ax.text(5.1, 1.25, "limit K MW", ha="center", fontsize=8.5, color=C["orange"])
    ax.annotate("", xy=(7.3, 2.0), xytext=(5.62, 2.0), arrowprops=dict(arrowstyle="->", lw=2))
    ax.add_patch(plt.Rectangle((7.35, 1.6), 1.4, 0.8, fc="#F2F2F2", ec="k"))
    ax.text(8.05, 2.0, "Grid\n(ERCOT price)", ha="center", va="center", fontsize=8.5)
    ax.add_patch(plt.Rectangle((4.1, 3.2), 2.0, 0.6, fc="#EFF7F1", ec=C["green"]))
    ax.text(5.1, 3.5, "Coordinator: splits K\nin proportion to reports", ha="center", va="center", fontsize=8)
    ax.add_patch(plt.Rectangle((4.1, 0.05), 2.0, 0.6, fc="#FBEDEC", ec=C["red"]))
    ax.text(5.1, 0.35, "Checker: B inspections/day,\nfines over-reporting", ha="center", va="center", fontsize=8)
    fig.savefig(FIG / "fig1_setting.png"); plt.close(fig)


def example_a_check():
    """Two owners, two hours, K=1, prices 20 then 100, wear 5 per MWh discharged."""
    K, p1, p2, wear = 1.0, 20.0, 100.0, 5.0
    def payoff(s1, s2):  # s = 'C' (store) or 'S' (sell now)
        sell_now = [s == "S" for s in (s1, s2)]
        n_now = sum(sell_now); n_later = 2 - n_now
        out = []
        for s in sell_now:
            if s:
                out.append(p1 * min(1, K / n_now))
            else:
                q = min(1, K / n_later)
                out.append((p2 - wear) * q)
        return out
    print("\n=== Example A check ===")
    for s1 in "CS":
        print(s1, [tuple(payoff(s1, s2)) for s2 in "CS"])


def correlation_sensitivity():
    sets = pd.read_csv(REPO / "results/tables/agent_sets.csv")
    print("\n=== Does the value of honest reports depend on how similar the owners' wind is? ===")
    rows = []
    cases = [("Anchor (5 units, same site)", UNITS)] + [
        (f"{r.correlation_set} correlation set", [r.member_1, r.member_2, r.member_3, r.member_4])
        for r in sets.itertuples()]
    for name, units in cases:
        A, _, L = load_data(units)
        corr = np.corrcoef(A.T)[np.triu_indices(len(units), 1)].mean()
        K = KAPPA * L.sum(); days = A.shape[0] / 24
        res = {r: simulate_rule(A, L, K, r, False).sum() / days for r in ("truthful", "fixed", "feedback")}
        lf = (res["truthful"] - res["fixed"]) / res["truthful"]
        lb = (res["truthful"] - res["feedback"]) / res["truthful"]
        rows.append((name, corr, lf, lb))
        print(f"{name:30s} mean corr {corr:.2f}: everyone-lies/fixed loses {lf:5.1%}, "
              f"meter feedback loses {lb:5.1%}")
    return rows


def corr_figure(rows):
    fig, ax = plt.subplots(figsize=(6.5, 3.2))
    rows = sorted(rows, key=lambda r: r[1])
    xs = np.arange(len(rows)); wdt = 0.36
    ax.bar(xs - wdt / 2, [100 * r[2] for r in rows], wdt, color=C["blue"], label="Everyone over-reports (= fixed shares)")
    ax.bar(xs + wdt / 2, [100 * r[3] for r in rows], wdt, color=C["green"], label="Meter feedback, 1-hour lag")
    ax.set_xticks(xs)
    ax.set_xticklabels([f"{r[0].split(' (')[0].replace(' correlation set','')}\ncorr {r[1]:.2f}" for r in rows])
    ax.set_ylabel("Energy lost vs. truthful (%)")
    ax.set_title("Honest reports are worth more when owners' wind is less similar")
    ax.legend(frameon=False, fontsize=8)
    fig.savefig(FIG / "fig6_correlation.png"); plt.close(fig)


def equilibrium_enumeration(A, E, L):
    """Pure Nash equilibria of the 5-owner game where each owner picks one report
    option (ARMS) for the whole 60-day window. Payoff = mean daily energy minus
    expected fine. Checker: 1 inspection/day."""
    import itertools
    K = KAPPA * L.sum()
    nd = A.shape[0] // 24
    Ad = A[: nd * 24].reshape(nd, 24, -1); Ed = E[: nd * 24].reshape(nd, 24, -1)
    N, n = len(L), len(ARMS)
    # precompute each owner's report series for each arm
    Rarm = np.zeros((n, nd, 24, N))
    for k in range(n):
        for d in range(nd):
            Rarm[k, d] = build_reports(np.full(N, k), Ad[d], L)
    profiles = list(itertools.product(range(n), repeat=N))
    configs = [("No checks", "none", 0.0), ("Random, fine 1x", "random", 1.0),
               ("Random, fine 5x", "random", 5.0), ("Targeted, fine 1x", "targeted", 1.0),
               ("Unused-share charge 1x (meter only)", "unused", 1.0)]
    print("\n=== Pure Nash equilibria, 5 owners x 5 report options, 60 real days ===")
    out = {}
    for name, pol, phi in configs:
        U = np.zeros((len(profiles), N)); OV = np.zeros(len(profiles)); EN = np.zeros(len(profiles))
        for pi, prof in enumerate(profiles):
            R = np.stack([Rarm[prof[i], :, :, i] for i in range(N)], axis=-1)  # nd,24,N
            tot = R.sum(-1, keepdims=True)
            Kshare = R * np.minimum(1.0, K / np.maximum(tot, 1e-12))
            X = np.minimum(Ad, Kshare)
            energy = X.sum(1); over = (R - Ad).clip(0).sum(1)          # nd,N
            if pol == "unused":
                fine = phi * (Kshare - X).sum(1)
            elif pol == "random":
                fine = phi * over / N
            elif pol == "targeted":
                score = (R - Ed).sum(1) / L
                j = score.argmax(1)
                fine = np.zeros_like(over); fine[np.arange(nd), j] = phi * over[np.arange(nd), j]
            else:
                fine = np.zeros_like(over)
            U[pi] = (energy - fine).mean(0)
            OV[pi] = over.sum() / (Ad.sum()); EN[pi] = energy.sum(1).mean()
        idx = {p: i for i, p in enumerate(profiles)}
        ne = []
        for pi, prof in enumerate(profiles):
            ok = True
            for i in range(N):
                for k in range(n):
                    if k == prof[i]:
                        continue
                    q = list(prof); q[i] = k
                    if U[idx[tuple(q)], i] > U[pi, i] + 1e-6:
                        ok = False; break
                if not ok:
                    break
            if ok:
                ne.append(pi)
        truth = idx[tuple([0] * N)]
        print(f"{name:18s}: {len(ne)} pure NE")
        for pi in ne[:6]:
            print("   " + ", ".join(ARMS[k][0] for k in profiles[pi]) +
                  f" | over-report {OV[pi]:.1%} of available | energy {EN[pi]:.0f} MWh/day "
                  f"(truthful: {EN[truth]:.0f})")
        out[name] = (min(OV[pi] for pi in ne), max(OV[pi] for pi in ne))
    return out


if __name__ == "__main__":
    example_a_check()
    schematic()
    example_b()
    A, E, L = load_data()
    rules_on_real_data(A, L)
    stress_curve(A, L)
    ne = equilibrium_enumeration(A, E, L)
    names = {"No checks": "No checks", "Random, fine 1x": "Random checks, small fine (1x)",
             "Random, fine 5x": "Random checks, large fine (5x)",
             "Targeted, fine 1x": "Targeted checks, small fine (1x)"}
    learning(A, E, L, ne_levels={names[k]: v for k, v in ne.items() if k in names})
    rows = correlation_sensitivity()
    corr_figure(rows)
    print("\nFigures written to", FIG)

"""Unit tests U1-U13 (spec Section 10) and theory checks P1-P4 (spec Section 9).

Run from the repository root:
    .venv/bin/python -m pytest "Clean Start/sim/tests" -q
"""
import itertools

import numpy as np
import pytest

from sim.engine import DayInputs, decompose_overpayment, payoff, penalty, simulate
from sim.params import Params
from sim import theory as th


def inputs(W, mu=None, What=None, Wex=None, p=40.0, dis_ok=False, pbar=0.0):
    """Build a one-day batch from (T,N) arrays."""
    W = np.atleast_2d(np.asarray(W, float))[None]
    T = W.shape[1]
    mu = W if mu is None else np.atleast_2d(np.asarray(mu, float))[None]
    What = W if What is None else np.atleast_2d(np.asarray(What, float))[None]
    Wex = mu if Wex is None else np.atleast_2d(np.asarray(Wex, float))[None]
    p = np.broadcast_to(np.asarray(p, float), (1, T)).copy()
    dis = np.broadcast_to(np.asarray(dis_ok, bool), (1, T)).copy()
    return DayInputs(W=W, mu=mu, What=What, Wex=Wex, p=p, dis_ok=dis, pbar=np.array([pbar]))


def rep(ell):
    return np.atleast_2d(np.asarray(ell, float))[None]


HIDE = np.array([[False, False]])
DECL = np.array([[True, True]])

# Hand example of spec Section 9: N=(10,5), K=9, W=mu=(8,4), p=40, lam=30.
# Owner 1 has no battery; owner 2 has room (P=2, E=4, empty). No terminal value (V_s = 0).
HAND = Params(nameplate=np.array([10.0, 5.0]), K=9.0, P=np.array([0.0, 2.0]), E=np.array([0.0, 4.0]),
              s0_frac=0.0, lam=30.0, terminal_value=False, tau=0.0)


def owner2_payoff(rule, settlement, l2):
    prm = HAND.with_(rule=rule, settlement=settlement)
    u, _ = payoff(inputs([[8, 4]]), rep([[8, l2]]), HIDE, prm)
    return u[0, 1]


# ---------------------------------------------------------------- U9 hand example
@pytest.mark.parametrize("rule,settlement,gain", [("R", "S0", 82.0), ("C", "S0", 72.0),
                                                   ("R", "S2", 40.0), ("C", "S2", 0.0)])
def test_U9_hand_example(rule, settlement, gain):
    assert owner2_payoff(rule, settlement, 6.4) - owner2_payoff(rule, settlement, 4.0) == pytest.approx(gain)


def test_U9_hand_example_quantities():
    o = simulate(inputs([[8, 4]]), rep([[8, 6.4]]), HIDE, HAND.with_(rule="R"))
    assert o["k"][0, 0] == pytest.approx([5, 4]) and o["v"][0, 0, 1] == pytest.approx(2.4)
    o = simulate(inputs([[8, 4]]), rep([[8, 4]]), HIDE, HAND.with_(rule="R"))
    assert o["k"][0, 0] == pytest.approx([6, 3]) and o["c"][0, 0, 1] == pytest.approx(1.0)


# ---------------------------------------------------------------- U1-U8, U10-U13
def test_U1_honest_curtailment_paid_exactly_under_S2():
    o = simulate(inputs([[8, 4]]), rep([[8, 4]]), HIDE, HAND.with_(settlement="S2"))
    assert o["r"][0, 0, 0] == pytest.approx(2.0)                    # owner 1 curtails 2 MWh
    assert o["T"][0, 0, 0] == pytest.approx(30.0 * 2.0)


def test_U2_honest_forecast_error_never_fined():
    prm = HAND.with_(settlement="S1", tau=0.05, alpha=1.0, z=1.0, f=90.0)
    inp = inputs([[8, 4]], mu=[[9.5, 5.0]])                          # mu - W = 0.15-0.2 N > tau N, but honest
    o = simulate(inp, inp.mu, HIDE, prm)
    assert o["infl_vol"].sum() == 0.0
    # Only repayment of invalid payment (no fine): penalty = lam * omega.
    assert penalty(o, prm) == pytest.approx(prm.lam * o["omega"] + prm.f * o["hidden_vol"])


def test_U3_stored_energy_not_eligible_under_S2():
    o = simulate(inputs([[8, 4]]), rep([[8, 4]]), HIDE, HAND.with_(settlement="S2"))
    assert o["c"][0, 0, 1] == pytest.approx(1.0) and o["T"][0, 0, 1] == pytest.approx(0.0)


def random_case(rng, T=24, N=3):
    nameplate = rng.uniform(5, 50, N)
    prm = Params(nameplate=nameplate, K=0.6 * nameplate.sum(), P=0.29 * nameplate,
                 E=0.435 * nameplate, s0_frac=rng.uniform(0, 1))
    W = rng.uniform(0, 1, (T, N)) * nameplate
    mu = np.clip(W + rng.normal(0, 0.15, (T, N)) * nameplate, 0, nameplate)
    inp = inputs(W, mu=mu, What=np.clip(W + rng.normal(0, 0.04, (T, N)) * nameplate, 0, None),
                 p=rng.normal(30, 40, T), dis_ok=rng.random(T) < 0.5, pbar=35.0)
    ell = np.minimum(mu * rng.uniform(1, 1.6, (T, N)), nameplate + prm.P)[None]
    return inp, ell, prm


@pytest.mark.parametrize("seed", range(20))
def test_U4_U8_feasibility_and_balance(seed):
    rng = np.random.default_rng(seed)
    inp, ell, prm = random_case(rng)
    for rule, st, var, dr in itertools.product("RC", ["S0", "S1", "S2", "S2c"], [False, True], ["strict", "uncurtailed"]):
        p = prm.with_(rule=rule, settlement=st, variant_I=var, discharge_rule=dr)
        dec = rng.random((1, prm.N)) < 0.5
        o = simulate(inp, ell, dec, p)
        assert np.all(o["soc"] >= -1e-9) and np.all(o["soc"] <= p.E + 1e-9)          # U4
        assert np.all(o["c"] * o["d"] <= 1e-12)                                       # U4
        assert np.all(o["r"] >= -1e-12) and np.all(o["g"] <= inp.W + 1e-9)
        assert np.allclose(o["x"], o["g"] - o["c"] + o["d"])                         # U8 balance
        assert np.all(o["x"] <= o["k"] + 1e-9)
        assert np.all(o["x"].sum(-1) <= p.K + 1e-9)                                  # U8 limit
        assert np.all(o["c"] <= np.maximum(inp.W - o["k"], 0) + 1e-9)                # charge from own surplus
        # SOC accounting: s_T = s_0 + eta_c sum c - sum d / eta_d
        sT = p.s0_frac * p.E + p.eta_c * o["c"].sum(1) - o["d"].sum(1) / p.eta_d
        assert np.allclose(o["soc"][:, -1], sT)
        assert np.allclose(o["payoff_pre"], o["energy_rev"] + o["comp"] - o["wear_cost"] + o["terminal"])


def test_U5_no_congestion_no_payment():
    o = simulate(inputs([[4, 2]]), rep([[4, 2]]), HIDE, HAND)
    assert o["v"].sum() == 0 and o["T"].sum() == 0


def test_U6_report_induced_instruction():
    # Honest totals fit (6 + 2 = 8 <= 9); owner 2 inflates to 4, which triggers congestion.
    inp = inputs([[6, 2]])
    ell = rep([[6, 4]])
    o = simulate(inp, ell, HIDE, HAND)
    assert o["cong"][0, 0, 0] == 1
    dcm = decompose_overpayment(inp, ell, HIDE, HAND, i=1)
    assert dcm["self_induced"][0] > 0


def test_U7_T6_deviations_gain_only_through_channels():
    prm = HAND.with_(rule="C", settlement="S2")
    inp = inputs([[8, 4]])                                   # congested already, honest cap non-binding
    base = payoff(inp, rep([[8, 4]]), HIDE, prm)[0][0, 1]
    for l2 in np.linspace(4, 7, 13):                         # trigger fixed (already congested)
        assert payoff(inp, rep([[8, l2]]), HIDE, prm)[0][0, 1] == pytest.approx(base)
    # Trigger channel: honest totals fit, inflation creates congestion; with lam > p it pays.
    inp2 = inputs([[5, 4]], p=10.0)
    prm2 = prm.with_(P=np.array([0.0, 0.0]), E=np.array([0.0, 0.0]))
    gain = payoff(inp2, rep([[5, 4.5]]), HIDE, prm2)[0][0, 1] - payoff(inp2, rep([[5, 4]]), HIDE, prm2)[0][0, 1]
    # Honest 5 + 4 = 9 (not congested): owner 2 sells 4. Report 4.5 -> congested, k2 = kappa2 = 3:
    # owner 2 sells 3 and is paid lam for 1 MWh of (self-induced) lost generation: gain = lam - p.
    assert gain == pytest.approx(30.0 - 10.0)
    # Cap channel: honest under-forecast (mu < W) makes the cap bind; raising ell raises e.
    inp3 = inputs([[8, 5]], mu=[[8, 3.5]])
    lo = simulate(inp3, rep([[8, 3.5]]), HIDE, prm2)["T"][0, 0, 1]
    hi = simulate(inp3, rep([[8, 5.0]]), HIDE, prm2)["T"][0, 0, 1]
    assert hi > lo


def test_U10_variant_I_reports_irrelevant():
    rng = np.random.default_rng(1)
    inp, ell, prm = random_case(rng)
    for rule, st in itertools.product("RC", ["S0", "S2"]):
        p = prm.with_(rule=rule, settlement=st, variant_I=True)
        dec = np.ones((1, prm.N), bool)
        base = payoff(inp, ell, dec, p)[0]
        for _ in range(5):
            ell2 = ell.copy(); ell2[..., 0] *= rng.uniform(0.5, 2)
            assert np.allclose(payoff(inp, ell2, dec, p)[0], base)


def test_U11_declared_storage_not_fined():
    prm = HAND.with_(settlement="S1", alpha=1.0, f=90.0)
    o = simulate(inputs([[8, 4]]), rep([[8, 4]]), DECL, prm)
    assert o["hidden_vol"][0, 1] == 0 and o["c"][0, 0, 1] > 0
    oh = simulate(inputs([[8, 4]]), rep([[8, 4]]), HIDE, prm)
    assert oh["hidden_vol"][0, 1] == pytest.approx(1.0)


def test_U12_imperfect_verification_expectation_matches_sampling():
    rng = np.random.default_rng(0)
    inp, ell, prm = random_case(rng)
    p = prm.with_(settlement="S1", alpha=0.3, z=0.7, z0=0.1)
    o = simulate(inp, ell, rng.random((1, prm.N)) < 0.5, p)
    exp = penalty(o, p)
    draws = np.mean([penalty(o, p, rng=np.random.default_rng(s)) for s in range(20000)], axis=0)
    assert np.allclose(draws, exp, rtol=0.05, atol=1e-6)


@pytest.mark.parametrize("seed", range(10))
def test_U13_decomposition_adds_up(seed):
    rng = np.random.default_rng(seed)
    inp, ell, prm = random_case(rng)
    for rule, st in itertools.product("RC", ["S0", "S2"]):
        p = prm.with_(rule=rule, settlement=st)
        d = decompose_overpayment(inp, ell, rng.random((1, prm.N)) < 0.5, p, i=int(rng.integers(prm.N)))
        assert d["storage"] + d["inflation"] + d["error"] == pytest.approx(d["O"])


# ---------------------------------------------------------------- Theory checks (math vs engine)
def fd_gain(inp, ell, i, prm, declare=HIDE, h=1e-4):
    """Finite-difference dU_i/dl_i at the given reports (expected payoff incl. audits)."""
    up = ell.copy(); up[..., i] += h
    return (payoff(inp, up, declare, prm)[0][0, i] - payoff(inp, ell, declare, prm)[0][0, i]) / h


TWO = Params(nameplate=np.array([10.0, 10.0]), K=9.0, P=np.array([0.0, 0.0]), E=np.array([0.0, 0.0]),
             lam=30.0, tau=0.0, terminal_value=False)


@pytest.mark.parametrize("p", [40.0, 10.0, -20.0, -200.0])
@pytest.mark.parametrize("rule", ["R", "C"])
def test_P1_marginal_matches_formula_curtailment(rule, p):
    inp = inputs([[8, 8]], p=p)                      # W=8 each, honest L=16 > K=9, both can fill shares
    ell = rep([[8, 8]])
    a = th.a_coef(9.0, 8.0, 16.0)
    assert fd_gain(inp, ell, 1, TWO.with_(rule=rule)) == pytest.approx(th.P1_marginal(rule, 30.0, p, a), rel=1e-3, abs=1e-3)


def test_P1_can_fail_at_very_negative_price():
    a = th.a_coef(9.0, 8.0, 16.0)
    assert th.P1_marginal("R", 30.0, -200.0, a) < 0
    assert fd_gain(inputs([[8, 8]], p=-200.0), rep([[8, 8]]), 1, TWO) < 0


def test_P1_P2_marginal_displacing_charging():
    # Owner 2 has battery room: its surplus is charged, so one more exported MWh displaces charging.
    pbar = 60.0
    prm = TWO.with_(P=np.array([0.0, 10.0]), E=np.array([0.0, 20.0]), s0_frac=0.0, terminal_value=True)
    inp = inputs([[8, 8]], p=40.0, pbar=pbar)
    a = th.a_coef(9.0, 8.0, 16.0)
    Vs = th.V_s(prm.eta_c, prm.eta_d, pbar, prm.wear)
    assert fd_gain(inp, rep([[8, 8]]), 1, prm) == pytest.approx(th.P1_marginal("R", 30.0, 40.0 - Vs, a), rel=1e-3)
    assert fd_gain(inp, rep([[8, 8]]), 1, prm.with_(settlement="S2")) == pytest.approx(
        th.P2_marginal("R", 30.0, 40.0, a, "charging", Vs), rel=1e-3, abs=1e-6)


@pytest.mark.parametrize("p", [40.0, 10.0])
@pytest.mark.parametrize("rule", ["R", "C"])
def test_P2_marginal_curtailment(rule, p):
    a = th.a_coef(9.0, 8.0, 16.0)
    g = fd_gain(inputs([[8, 8]], p=p), rep([[8, 8]]), 1, TWO.with_(rule=rule, settlement="S2"))
    assert g == pytest.approx(th.P2_marginal(rule, 30.0, p, a, "curtailment"), rel=1e-3, abs=1e-6)


@pytest.mark.parametrize("rule", ["R", "C"])
def test_P3_deterrence_threshold(rule):
    """Sign of the marginal expected gain flips at alpha* (S1, random audits, z=1, tau=0)."""
    p, lam, f, z = 40.0, 30.0, 90.0, 1.0
    a = th.a_coef(9.0, 8.0, 16.0)
    astar = th.P3_alpha_star(rule, lam, f, z, p, a)
    inp, ell = inputs([[8, 8]], p=p), rep([[8, 8]])
    prm = TWO.with_(rule=rule, settlement="S1", f=f, z=z)
    below = fd_gain(inp, ell, 1, prm.with_(alpha=astar - 0.02))
    above = fd_gain(inp, ell, 1, prm.with_(alpha=astar + 0.02))
    assert below > 0 > above


def test_P4_relabel_gain():
    assert th.P4_relabel_gain(30.0, 30.0) == 0.0 and th.P4_relabel_gain(30.0, 10.0) == 20.0


# ---------------------------------------------------------------- rev. 2.4 additions
def test_S2c_pays_true_lost_generation_despite_under_forecast():
    """Honest under-forecast (mu < W): S2 caps payment at the report; S2c pays the true lost generation."""
    prm = HAND.with_(rule="C", settlement="S2", P=np.array([0.0, 0.0]), E=np.array([0.0, 0.0]))
    inp = inputs([[8, 5]], mu=[[8, 3.5]])
    o2 = simulate(inp, rep([[8, 3.5]]), HIDE, prm)
    oc = simulate(inp, rep([[8, 3.5]]), HIDE, prm.with_(settlement="S2c"))
    assert o2["T"][0, 0, 1] == pytest.approx(30 * 0.5)          # capped at v = 3.5 - 3
    assert oc["T"][0, 0, 1] == pytest.approx(30 * 2.0)          # true lost generation 5 - 3
    assert oc["lost_phys"][0, 0, 1] == pytest.approx(2.0)


def test_S2c_removes_cap_channel_under_C():
    prm = HAND.with_(rule="C", settlement="S2c", P=np.array([0.0, 0.0]), E=np.array([0.0, 0.0]))
    inp = inputs([[8, 5]], mu=[[8, 3.5]])
    base = payoff(inp, rep([[8, 3.5]]), HIDE, prm)[0][0, 1]
    for l2 in [4.0, 5.0, 6.0, 8.0]:
        assert payoff(inp, rep([[8, l2]]), HIDE, prm)[0][0, 1] == pytest.approx(base)


@pytest.mark.parametrize("p", [10.0, 50.0])
def test_P2c_marginal_R(p):
    """S2c (cap at estimate), rule R, curtailment case: dU/dl = (p - lam) a. Negative when p < lam,
    so the owner gains by UNDER-reporting (smaller share, more paid curtailment)."""
    a = th.a_coef(9.0, 8.0, 16.0)
    g = fd_gain(inputs([[8, 8]], p=p), rep([[8, 8]]), 1, TWO.with_(rule="R", settlement="S2c"))
    assert g == pytest.approx((p - 30.0) * a, rel=1e-3)


@pytest.mark.parametrize("p", [10.0, 50.0])
def test_P2c_marginal_C_below_share(p):
    """S2c, rule C, report below the share (l < kappa): k = l, so dU/dl = p - lam."""
    g = fd_gain(inputs([[8, 8]], p=p), rep([[8, 4.0]]), 1, TWO.with_(rule="C", settlement="S2c"))
    assert g == pytest.approx(p - 30.0, rel=1e-3)

# Experiment Log

Every step, test, run and conclusion, in order. Spec: `game_spec_v1.md`. Code: `sim/`.
Environment: repository `.venv` (Python 3.15, numpy 2.5, pandas 3.1). Tests: `cd "Clean Start" && ../.venv/bin/python -m pytest sim/tests -q`.

---

## Step 1: Engine, unit tests, theory checks (2026-11-25)

**Built:**
- `sim/params.py`: parameters.
- `sim/engine.py`: hour-by-hour physics, allocation (R, C, Variant I), fixed battery rule, settlement (S0, S1, S2), expected and sampled audits, overpayment decomposition.
- `sim/theory.py`: closed forms of P1–P4.
- `sim/tests/test_engine.py`.

**Result: 61/61 tests pass.**

| Check | What it compares | Outcome |
|---|---|---|
| U9 hand example | Engine vs the spec §9 table | Owner 2's payoff, honest → lie: R/S0 150→232 (+82), C/S0 150→222 (+72), R/S2 120→160 (+40), C/S2 120→120 (0). **Exact match.** |
| U1–U8, U10–U13 | Accounting, feasibility, channels, decomposition | All pass. U4/U8 run on 20 random 24-h cases × 12 rule/settlement/variant combinations. |
| P1 | Finite-difference $\partial U/\partial\ell$ vs $\lambda(1-a)+\hat p a$ (R), $\lambda$ (C) | Match at p = 40, 10, −20, −200. P1 **fails at p = −200** under R, as the formula predicts. |
| P1/P2, storage case | FD vs formula with $\hat p=p-V_s$, $V_s=\eta_c\eta_d(\bar p-10)$ | Match |
| P2 | FD under S2 vs $(p-\lambda)a$ (R), 0 (C) | Match |
| P3 | Sign of the expected marginal gain at $\alpha^*\pm0.02$ | Simulated marginal = ±0.02·(λ+f) = ±2.4: the threshold is reproduced **exactly**. Example: $\alpha^*_R=0.273$, $\alpha^*_C=0.250$ at p=40, λ=30, f=90, a=0.281. |
| U7 channels | T6 deviations | Trigger fixed: gain 0. Trigger channel: gain = λ − p = 20 (exact). Cap channel: payment rises with the report. |

**Math ↔ code finding #1.** The spec's terminal value $\bar p\eta_d s$ omitted wear, while $V_s$ in P1/P2 subtracts it. Fixed the spec (rev. 2.1): terminal value $(\bar p-10)^+\eta_d s$. The P1/P2 storage-case tests pass only with the fix.

**Interpretation for later steps.** With random audits of one owner per day ($\alpha=0.2$, z=1), P3 predicts deterrence under C iff $f\ge 4\lambda$ (curtailment case). Under R, the threshold is higher in hours with $p>\lambda$. This is a sharp, testable prediction for Step 3 (f = 3λ vs 5λ).

---

## Step 2: Data and calibration (2026-11-25)

**Built:** `sim/data.py`: ERCOT Anchor loader, forecast-based congestion probability, monitor estimate noise.

| Item | Value |
|---|---|
| Days | 60 full days, 2025-03-01 to 2025-04-30 (DST day absent: not 24 h) |
| Split | Train days 1–30 (π model); test days 31–60 (experiments) |
| Nameplate | 16.0, 98.8, 88.8, 38.7, 19.3 MW; K = 157.0 MW |
| Battery P / E | 4.6/7.0, 28.7/43.0, 25.8/38.6, 11.2/16.8, 5.6/8.4 MW/MWh |
| Congestion (ΣW > K) | Train 54.3%, test 44.6% of hours |
| Bin sizes (train / test hours) | Low 273/323, mid 82/111, high 365/286 |
| Bin calibration (realized rate vs mean π) | Train: 0.05/0.03, 0.49/0.55, 0.93/0.94. Test: 0.07/0.03, **0.36/0.53**, 0.91/0.93 |
| Honest forecast error (COP − W)/N | Mean +0.014, sd 0.163 (per unit 0.15–0.17); P(μ > W) = 0.48 |
| RT price | Mean 25.3 $/MWh; negative in 20% of hours, 38% of congested hours |
| Mean positive DA price ($\bar p$, test) | 31.0 $/MWh |

**Conclusions:**
- The bins separate congestion well (5% / 40–50% / 90%+). The mid bin is over-predicted out of sample (0.36 realized vs 0.53 predicted); keep in mind when reading the headline test.
- **Finding #2 (blocks Step 3).** The honest forecast μ = COP is mostly a **day-ahead** forecast (sd 16% of N). With the spec's fine base $(\ell-W-\tau N)^+$ and τ = 5%, an honest report exceeds the tolerance in 31% of owner-hours and **97% of owner-days**. Honest owners would be fined almost every day. This conflicts with the spec's timing (reports just before the hour, as GB notifications are made about 1 h ahead).

| τ | Owner-hours exceeding | Owner-days with ≥1 |
|---|---|---|
| 0.05 | 0.313 | 0.973 |
| 0.10 | 0.207 | 0.917 |
| 0.16 | 0.123 | 0.777 |
| 0.25 | 0.063 | 0.547 |
| 0.32 | 0.035 | 0.330 |

**Decision needed before Step 3** (see the options in the session).

**Decision (user, 2026-11-25):** the fine base is the bias against the owner's own forecast records, $(\ell-\mu-\tau N)^+$ (spec rev. 2.2). The engine and test U2 were updated; 61/61 pass.

---

## Step 3: Core experiments, pre-registered predictions (written before any run)

**Setup:**
- Test days 31–60 (30 days); congestion bins from the training-day model.
- λ = 30; random audits α = 0.2 (one owner per day), z = 1, τ = 0.05.
- Strategy grid: β ∈ {0, 0.1, 0.25, 0.5, cap} per bin, × declare/hide.
- Equilibrium: sequential best response from the truthful profile (also from all-cap, to check multiplicity).

| ID | Prediction | Basis |
|---|---|---|
| D1 | Declaration: hide under S0; hide under S1 with f = 3λ; **declare** under S1 with f = 5λ; no effect under S2 (stays at the start). | Hiding gains λ per stored MWh and costs α(λ+f): 0.2·120 = 24 < 30 (hide), 0.2·180 = 36 > 30 (declare). Exact threshold f* = 4λ. |
| I1 | T1 (R/S0), T4 (C/S0): inflation in the congested bins (high, mid), likely cap. | P1: marginal gain λ > 0 (C) and λ(1−a)+p̂a (R), positive unless p̂ is very negative. There is no cost under S0. |
| I2 | T5 (C/S1): inflation with f = 3λ; **none** beyond τ with f = 5λ. | P3: α*_C = λ/(λ+f) = 0.25 (f = 3λ) > 0.2; 0.167 (f = 5λ) < 0.2. |
| I3 | T2 (R/S1), f = 5λ: deterred in most congested hours, but inflation is possible where p > λ. | P3: deterred iff (p−λ)a ≤ 0.2(λ+f) − λ = 6; for small owners a ≈ K/L ≈ 0.7–0.9. |
| I4 | T3 (R/S2): little or no inflation, because congested-hour prices are mostly below λ = 30. | P2: (p−λ)a in curtailment hours; (p − V_s)a with V_s ≈ 0.85(31−10) ≈ 18 in charging hours. |
| I5 | T6 (C/S2): no inflation through compensation. Any inflation found comes from the trigger, cap or charging channels; most likely in the mid bin (trigger) when λ > p. | P2 channels; U7. |
| I6 | T6 Variant I: reports have no effect; the equilibrium stays at the start profile. | Weak incentive compatibility. |

**Known limitation of the grid:** β ≥ 0 only, so incentives to **under**-report (possible under R/S2 when p < λ) cannot appear. Checked separately if needed.

## Step 3: Core experiments, results (2026-11-25)

**Code:** `sim/equilibrium.py` (strategy grid, best response, metrics), `sim/run_step3.py`.
**Outputs:** `results/step3_summary.csv`, `results/step3_profiles.json`, `results/step3_stdout.txt`. Runtime 2 min.

**Changes made during Step 3 (each forced by a check; all tests re-run, 61/61 pass):**
1. **Grid artifact.** Without β = τ in the grid, the predicted "inflate exactly to τ" showed up as β = 0.1. Diagnostic run: once β = 0.05 is available, every owner picks exactly 0.05 under f = 5λ. Spec rev. 2.3 adds β = τ; grid {0, 0.05, 0.1, 0.25, 0.5, cap}, 432 strategies per owner.
2. **Joint induced-congestion metric.** The unilateral "self-induced" metric reads 0 when all owners inflate together, which is misleading. Added hours congested at equilibrium but not under all-honest reports, with the curtailment and payments in those hours.
3. **Battery-rule robustness switch** (`discharge_rule="uncurtailed"`): discharge is also allowed in instructed hours with r = 0. Needed because of finding F5.

**Equilibrium quality:** all 24 runs converged (2–4 sweeps); maximum unilateral deviation gain = 0 on the grid; no cycles. Runs started from all-cap reach the same equilibrium, **except T2 R/S1 f=3λ**, which has a second equilibrium with mid-bin inflation (0.25–cap). **Multiple equilibria.**

### Main table (test days, means per day; bias as a share of nameplate; Δ relative to all-honest reports under the same rule)

| Treatment | Bias low / mid / high | ΔEnergy (MWh) | Comp. paid vs eligible (k$) | Overpayment (k$): storage / inflation / error | Exp. penalty (k$) | ΔOwner profit (k$) |
|---|---|---|---|---|---|---|
| T1 R/S0 | cap / cap / cap | −78.9 | 130.0 vs 17.4 | 1.6 / 83.1 / 27.8 | 0 | +113.2 |
| T2 R/S1 f=3λ | τ / τ / τ (second eq.: τ / 0.25–cap / τ) | +2.6 | 21.9 vs 14.6 | 1.7 / 2.1 / 3.4 | 2.7 | +4.0 |
| T2 R/S1 f=5λ | τ / τ / τ, declare | +2.6 | 20.2 vs 14.6 | 0 / 2.1 / 3.4 | 1.2 | +3.8 |
| T3 R/S2 | cap / cap (one 0.5) / 0–τ | −73.0 | 17.6 vs 16.2 | 0 / −7.6 / 9.1 | 0 | +3.6 |
| T4 C/S0 | cap / cap / cap | −69.3 | 130.0 vs 17.4 | 1.6 / 112.0 / −1.0 | 0 | +113.3 |
| T5 C/S1 f=3λ | τ / cap / cap | +0.6 | 71.7 vs 15.9 | 2.3 / 53.1 / 0.3 | 42.4 | +13.9 |
| T5 C/S1 f=5λ | τ / τ / τ, declare | +0.05 | 20.4 vs 14.9 | 0 / 4.3 / 1.3 | 1.1 | +3.9 |
| T6 C/S2 | 0.5 / 0.5 / 0.25–0.5 | −51.8 | 18.6 vs 17.3 | 0 / 4.9 / −3.6 | 0 | +5.4 |
| T6 Variant I | = start profile (truth or cap) | 0.0 | 13.38 vs 13.37 | 0 / 0 / 0.009 | 0 | 0 |
| T1 no battery | cap / 0.5–cap / 0.5–cap | −14.5 | 75.3 vs 19.0 | 0 / 41.0 / 15.4 | 0 | +57.5 |
| T6 no battery | cap / 0.5 / 0.25–0.5 | −4.7 | 20.4 vs 19.0 | 0 / 5.6 / −4.1 | 0 | +5.6 |
| T3, discharge if r=0 | 0.1–cap / 0.5–cap / 0–τ | −3.2 | 16.7 vs 15.2 | 0 / −4.1 / 5.6 | 0 | +3.9 |
| T6, discharge if r=0 | cap / 0.5–cap / 0.25–0.5 | +8.5 | 17.8 vs 16.1 | 0 / 4.2 / −2.5 | 0 | +4.8 |

### Predictions vs outcomes

| ID | Prediction | Outcome | Verdict |
|---|---|---|---|
| D1 | Hide under S0 and S1 f=3λ; declare under S1 f=5λ; no effect under S2 | Exactly so. One owner in T2 f=3λ stays "declare": it stores nothing at that profile, so it is indifferent. | ✅ Exact (threshold f* = 4λ) |
| I1 | Inflation in congested bins under S0 | Cap in **all** bins, including low. With no cost, inflation is weakly dominant, and it also triggers congestion. At all-cap, R and C give identical outcomes, because shares ∝ N + P ∝ N: "everyone lies → fixed shares". | ✅ (stronger than predicted) |
| I2 | C/S1: inflate with f=3λ; none beyond τ with f=5λ | f=3λ: τ in low, cap in mid/high. f=5λ: exactly τ everywhere. | ✅ Exact: owners use the tolerance in full and stop there (P3) |
| I3 | R/S1: deterred except where p > λ | Deterred beyond τ **even at f=3λ** (unlike C), because R's marginal gain λ(1−a)+p̂a is below 24 at the low congested-hour prices. A second equilibrium with mid-bin inflation exists. | ✅ Consistent with the P3 formula; multiplicity is new |
| I4 | R/S2: little or no inflation | **Wrong for low/mid bins** (cap). Right for the high bin (0–τ, as P2's (p−λ)a < 0 predicts). | ❌ Pre-registration missed that P2's trigger channel applies to R too |
| I5 | C/S2: no inflation via compensation; some via channels, mostly mid bin | Inflation 0.25–0.5 in **all** bins, through the trigger channel (11 induced congested h/day) and the **cap** channel (honest owners underpaid, F6). | ⚠️ Channels confirmed; size underestimated |
| I6 | Variant I: reports irrelevant, the equilibrium stays at the start | Truth and all-cap give identical outcomes; overpayment = estimation error only ($9/day). | ✅ Exact (weak incentive compatibility) |

### Findings

- **F1. Unchecked self-reported settlement (S0) is fully exploited.** Owners report the cap in every hour, under both rules. Compensation paid is **7.5× eligible** (130k vs 17k $/day); owner profit rises 150%. P1 is confirmed.
- **F2. Audits deter beyond the tolerance, and the theory threshold holds exactly.** Under random audits (α = 0.2), f = 5λ stops inflation at exactly τ and makes owners declare storage. f = 3λ fails under C (cap in congested bins) but mostly works under R. The residual overpayment under S1 f=5λ is about 5.6k $/day: inflation inside the tolerance plus forecast-error payments.
- **F3. Verified settlement (S2) does not stop inflation when the trigger and cap use reports.** Owners inflate to induce congestion (11–13 extra congested h/day). They are paid for real but self-induced lost generation, and for real lost generation the report-based cap would otherwise withhold. Overpayment is small (1.3–1.4k $/day), but the incentive is not removed.
- **F4. Only Variant I (report-independent trigger, allocation and cap) removes all reporting incentives,** with no energy loss and overpayment equal to estimation error only. It is weakly incentive compatible: reports are irrelevant, so truth is not uniquely selected. This is a strong design result: **verification must also take the report out of the trigger and the cap.**
- **F5. A large share of the energy loss is a battery-rule interaction, not curtailment.** With "no discharge while instructed", induced instructions in all 24 h switch batteries off (discharge 64 → 0 MWh/day). With discharge allowed when r = 0:
  - T3's energy loss falls from −73 to −3 MWh/day;
  - T6 goes from −52 to +8 MWh/day.

  Inflation persists in both cases. **Report energy-loss results only with this caveat. The strict rule exaggerates the efficiency cost.**
- **F6. The report-based cap underpays honest owners under S2.** At truthful reports, the cap binds in 43–44% of instructed owner-hours, because the day-ahead forecast often under-predicts. Honest owners are paid about 87% of their true lost generation (13.2k vs 15.2k $/day), which explains why inflation under C/S2 partly "corrects" underpayment. Design implication: cap at the verified estimate, not at the report.
- **F7. Storage is not needed for the inflation incentive, but it raises the stakes.** No-battery controls show the same inflation pattern. Storage adds A2 (1.6–2.3k $/day hidden under S0 and S1 f=3λ) and, through F5, the energy loss.

### Math ↔ simulation status after Step 3

| Result | Status |
|---|---|
| P1 (S0 rewards inflation) | Confirmed in equilibrium (cap everywhere) and by finite differences (Step 1) |
| P2 (S2 removes A2; the R marginal is (p−λ)a; three channels remain) | A2 removal confirmed. High-bin behaviour matches (p−λ)a < 0. Trigger and cap channels **dominate** in low/mid bins: a quantitative surprise, not a contradiction |
| P3 (local deterrence; inflate to τ) | Confirmed exactly: thresholds f* = 4λ (C, and storage declaration) and "inflate exactly to τ" |
| P4 (two-rate) | Not yet run |
| Variant I weak IC | Confirmed exactly |

**Open items before Step 4:**
- (i) Decide the battery rule for the headline runs (F5). Recommendation: keep "strict" as the spec, and report "uncurtailed" as a robustness check in every table.
- (ii) Consider a capped-at-estimate design (F6) as one extra treatment.
- (iii) The β ≥ 0 grid cannot show under-reporting incentives (possible under R/S2 with p < λ). Not tested.

---

## Step 3b: Audit adjustments and rerun (2026-11-25)

**Reviewer audit of Steps 1–3:** approved, with three changes. All adopted:
1. **Relaxed battery rule as primary:** discharge allowed in instructed hours with r = 0. The strict rule is now robustness.
2. **S2c treatment:** verified settlement with the cap at the monitor's estimate, $(\widehat W-k)^+$; the trigger and allocation are unchanged.
3. **β = −0.1** (under-reporting), with ℓ ≥ 0.

**Also added:**
- Settlement accuracy against **physical** lost generation (report-free): gross over, gross under, net, expected audit recovery.
- Reported vs physical congestion hours.
- Reporting conventions in the spec: equilibria hold on the grid only; thresholds are conditional; record access is a strong assumption; one site, 30 days.

Spec rev. 2.4 (P2c added). Tests 67/67 (new: S2c pays true lost generation; S2c removes the cap channel; P2c marginals R and C). Grid: 7 options → 686 strategies/owner. 32 runs, all converged, maximum deviation gain 0, no cycles. Runtime 5.3 min.

**Physical congestion:** 10.7 h/day (ΣW > K) on the test days.

### Main table (relaxed battery; k$/day unless stated; Δ vs all-honest reports, same mechanism)

| Treatment | Bias low / mid / high | ΔEnergy MWh | Instructed h/day without physical congestion | Paid vs contract-eligible | Over / under vs physical lost gen. | ΔProfit |
|---|---|---|---|---|---|---|
| T1 R/S0 | cap / cap / cap | −1.7 | 13.3 | 130.0 vs 16.1 | 113.9 / 0 | +114.4 |
| T2 R/S1 f=5λ | τ / τ / τ, declare | +6.1 | 2.6 | 20.0 vs 14.5 | 5.8 / 1.0 (recovery 1.2) | +3.9 |
| T3 R/S2 | 0.1–cap / 0.5–cap / 0–τ | −3.2 | 13.3 | 16.7 vs 15.2 | 2.4 / 1.8 | +3.9 |
| T4 C/S0 | cap / cap / cap | +8.5 | 13.3 | 130.0 vs 16.1 | 113.9 / 0 | +114.5 |
| T5 C/S1 f=3λ | τ / cap / cap | +6.0 | 3.3 | 71.7 vs 15.6 | 56.1 / 0 (recovery 11.2) | +13.9 |
| T5 C/S1 f=5λ | τ / τ / τ, declare | +3.0 | 2.6 | 20.2 vs 14.7 | 5.7 / 1.2 (recovery 1.2) | +3.9 |
| T6 C/S2 | 0.5–cap / 0–cap / 0.25–0.5 | +8.5 | 13.3 | 17.8 vs 16.1 | 2.8 / 1.1 | +4.8 |
| **T3c R/S2c** | 0–0.5 / 0–0.1 / **−0.1** | −3.8 | 6.2 | 15.5 vs 9.0 | 1.3 / 1.0 | +0.7 |
| **T6c C/S2c** | 0.05–cap / 0–cap / **−0.1 to 0.05** | **−31.9** | 13.3 | 17.6 vs 11.7 | 1.5 / 1.2 | +1.6 |
| T6 Variant I | = start | 0.0 | 1.6 | 13.3 vs 13.3 | **0.6 / 2.5** | 0 |

Strict-battery robustness: ΔEnergy T1 −78.9, T3 −73.0, T6 −51.8, T3c −45.7, T6c −40.9; T2/T5 f=5λ +2.6/+0.05. The equilibrium reports are similar to the relaxed rule (T3 and T6 inflate somewhat more under strict).

**Multiple grid equilibria:**
- T2 R/S1 f=3λ: the all-τ equilibrium, and one with mid-bin inflation.
- T5 C/S1 f=3λ: two owners also cap the low bin when starting from all-cap.
- **T6 C/S2 (new):** from honest, a cap/0.5 mix; from all-cap, cap everywhere.

### Do the Step 3 findings survive?

| Finding | Status after rev. 2.4 |
|---|---|
| F1 S0 fully exploited | **Survives.** Cap everywhere, both rules. With the relaxed battery rule the harm is almost entirely financial (overpayment 114k $/day), not physical (ΔE −1.7 / +8.5). |
| F2 thresholds | **Survives exactly.** f = 5λ: τ everywhere and declare; f = 3λ: C fails in congested bins, R holds (plus a second equilibrium). |
| F3 S2 does not stop inflation | **Survives.** Low/mid-bin inflation; 13.3 instructed h/day without physical congestion (more than the 10.7 physically congested hours). The physical damage is small under the relaxed rule. |
| F4 Variant I | **Survives as an incentive result.** Correction to the "$9/day": against physical lost generation, Variant I **underpays** gross 2.5k and **overpays** gross 0.6k $/day (net −1.9k). The earlier figure hid offsetting errors, as the reviewer suspected. The cause is the operator's ex-ante forecast cap (under-forecasts) plus estimate noise. |
| F5 battery rule drives energy loss | **Confirmed** across 7 treatments. The incentives are robust; the physical damage depends on the battery rule. |
| F6 report cap underpays honest owners | **Confirmed by its fix.** S2c pays true lost generation and closes the cap channel: mid-bin inflation drops from 0.5–cap to 0–0.1, and the owner gain drops from 3.9–4.8k to 0.7–1.6k $/day. |
| F7 storage amplifies, does not cause | **Survives** (no-battery controls unchanged). |

### New findings

- **F8. S2c opens a deflation channel (P2c, confirmed both ways).** With the report out of the cap, owners **under-report** in the high-congestion bin (β = −0.1). A smaller share means more paid curtailment when λ > p. The math gives $(p-\lambda)a$ (R) and $p-\lambda$ (C, ℓ < κ), and finite differences match. Under C this destroys energy (−31.9 MWh/day): owners cut their own share and are paid to curtail. Reports still enter the **allocation**, so each fix closes one channel and opens its mirror image.
- **F9. The under-reporting option never appears outside S2c.** Under S0 and S1, payment rises with the report. Under S2 the report cap makes deflation costly. Adding β < 0 did not change any S0, S1 or S2 conclusion.
- **F10. Paper congestion.** Under S0 and S2, owners create about 13 instructed hours/day with no physical congestion. Under S1 f=5λ, 2.6 h/day (from tolerance-level inflation). Under Variant I, 1.6 h/day (forecast false positives).

### Central result (as framed by the reviewer, confirmed by the runs)

**Verifying compensation claims is not enough while strategic reports still decide when compensation becomes available.**
- Report-based trigger → inflation to create instructions (S2).
- Report-based cap → honest owners underpaid and inflation to lift the cap (S2).
- Report-based allocation → deflation to be paid for curtailment (S2c).
- Only the fully report-independent mechanism (Variant I) removes the reporting incentive, at the cost of forecast-driven settlement errors (net −1.9k $/day underpayment).

### Step 4 framing (from the audit)

The headline test is **not** "bias rises with congestion probability". The question is whether the relationship between bias and congestion probability **emerges, disappears or reverses** across mechanisms. The equilibria already predict:
- saturation (S0);
- flat at τ (S1 f=5λ);
- larger in low/mid than high (S2);
- reversal in the high bin (S2c);
- none (Variant I).

EXP3 runs will use multiple seeds, report uncertainty and regret, and evaluate on days not used for the π model.

---

## Step 3c: Final-review checks before Step 4 (2026-11-25)

**Reviewer final review of Step 3b:** approved to proceed to Step 4, with one accounting check (P0) and interpretation corrections. Code: `sim/run_step3c.py`; outputs: `results/step3c_accounting.csv`, `results/step3c_beta_minus025.csv`, `results/step3c_beta_minus050_stdout.txt`.

### P0. Accounting: the two eligibility benchmarks reconciled

Definitions ($/day, means over test days; lost generation $=W-g=r$):
- **Contract-eligible** $=\lambda\sum\min(v,\,W-g)$. The cap is the *reported* shortfall $v=(\ell-k)^+$.
- **Physical, instructed hours** $=\lambda\sum(W-g)$ over hours with reported congestion. No report cap.
- **Report-cap gap** $=\lambda\sum(W-g-v)^+$ over the same hours.
- **Identity:** contract-eligible + report-cap gap = physical (instructed hours). It holds exactly in all 11 treatments (residual 0.0).

| Treatment | Paid | Contract-eligible | Report-cap gap | Physical (instructed h) | Curtailment outside reported congestion (unpaid) |
|---|---|---|---|---|---|
| T1 R/S0 | 130.0 | 16.1 | 0 | 16.1 | 0 |
| T3 R/S2 | 16.7 | 15.2 | 0.9 | 16.0 | 0 |
| T6 C/S2 | 17.8 | 16.1 | 0 | 16.1 | 0 |
| **T3c R/S2c** | 15.5 | **9.0** | **6.3** | 15.3 | 0.8 |
| **T6c C/S2c** | 17.6 | **11.7** | **5.6** | 17.4 | 0 |
| T6 Variant I | 13.3 | 13.3 | 1.9 | 15.2 | **1.2 (40 MWh)** |

(k$/day.)

**Explanation.** Under S2c, owners deflate in the high bin, so the reported shortfall $v$ shrinks. The contract-eligible benchmark is capped by $v$, so it drops ($9.0k). Physical lost generation does not drop. S2c pays from the estimate, not from $v$, so it pays close to physical lost generation: over 1.3k / under 1.0k is estimate noise. **The discrepancy is a benchmark artifact, not missing money.**

**Rule from now on:**
- Settlement accuracy is measured against **physical** lost generation.
- The contract-eligible figure is reported only as "what a report-capped contract would owe".
- The earlier over/under metric counts only hours with reported congestion. Curtailment outside them is unpaid and now reported separately. It is non-zero under Variant I (1.2k $/day, 40 MWh: forecast says no congestion, but the owner is physically curtailed). So Variant I's total underpayment against all physical lost generation is 2.5 + 1.2 = 3.7k gross.

**Correction to F6.** S2c does **not** pay true lost generation exactly. It removes the report-dependent cap and pays the noisy estimate.

### Market value, not just energy

Market value of exports = Σ p·x − wear, Δ vs all-honest reports (relaxed battery), $/day:

| Treatment | ΔMarket value |
|---|---|
| T1 R/S0 | −9 |
| T2 R/S1 f=5λ | +168 |
| T3 R/S2 | +232 |
| T6 C/S2 | +235 |
| T3c R/S2c | +115 |
| T6c C/S2c | −722 |

These are small against ~59.6k $/day. **Market value is still not welfare.** It omits:
- the system cost of replacing curtailed energy;
- the cost to the payer of overpayment (a transfer, but a real cost to the scheme);
- effects on other grid users of false instructions.

**Wording rule:** "physical damage is small" becomes "**exports and their market value change little; the damage measured here is financial (transfers)**".

### Battery rule: absolute differences (replaces "10–20× larger")

ΔEnergy vs all-honest, MWh/day:

| Treatment | Relaxed | Strict |
|---|---|---|
| T1 R/S0 | −1.7 | −78.9 |
| T2 R/S1 f=5λ | +6.1 | +2.6 |
| T3 R/S2 | −3.2 | −73.0 |
| T5 C/S1 f=5λ | +3.0 | +0.1 |
| T6 C/S2 | **+8.5** | **−51.8** |
| T3c R/S2c | −3.8 | −45.7 |
| T6c C/S2c | −31.9 | −40.9 |

**What the comparison shows:**
- The strict rule turns inflation into large energy losses where inflation is large: T1, T3, T6 (sign flips), T3c.
- It changes little where reports stay near τ (T2, T5), or where the loss already comes from deflation (T6c).
- Payments and profit gains barely move (ΔProfit within 0.8k $/day).

**Corrected claim:** the incentives are robust to the battery rule. The energy effect depends on it, by 0 to 77 MWh/day.

### Under-reporting boundary (β = −0.25, then −0.5)

The S2c equilibria used the floor option β = −0.1, so I widened the grid. S2 controls are unchanged with −0.25.

| Grid floor | T3c R/S2c bias_high | T3c ΔE | T6c C/S2c bias_high | T6c ΔE | T6c ΔMarket value | T6c paid |
|---|---|---|---|---|---|---|
| −0.1 | −0.10 | −3.8 | −0.10 to +0.05 | −31.9 | −0.7k | 17.6k |
| −0.25 | −0.22 | −9.5 | −0.09 / +0.04 (2 equilibria) | −99 / −125 | −1.8k / −2.6k | 19.8k / 20.6k |
| −0.5 | −0.32 | −14.9 | −0.16 / −0.30 (2 equilibria) | **−426 / −454** | **−6.8k / −7.3k** | **29.9k / 27.2k** |

**F8 revised.** The deflation incentive is **not local**, and the grid floor was binding.
- **R/S2c:** partly bounded. The two small owners go to the floor (−0.5). The larger owners stop at −0.1/−0.25: by P2c the gain is $(p-\lambda)a$, and a large deflation lowers $L$ enough to end the congestion that pays them.
- **C/S2c:** unbounded within the grid, as P2c predicts ($p-\lambda$ per MWh, with no damping from $a$). Owners **split roles**:
  - some report cap in a bin, which keeps the trigger on: congestion rises to 22–24 h/day;
  - others deflate to collect paid curtailment.
- At the −0.5 floor, T6c loses ~16% of exports, and market value falls by 6.8–7.3k $/day.

**Implication.** Under C, the true optimum is the report floor ($\ell\to0$) in hours with $\lambda>p$, as long as rivals keep congestion on. S2c with a report-based trigger is the most physically damaging mechanism tested, not a mild fix.

**Step 4 consequence:** the learning runs keep the spec grid (floor −0.1) for comparability with Step 3b. S2c deflation magnitudes from learning are therefore **lower bounds**.

### Multiple equilibria (reporting rule)

**Grid equilibria found** (two starting points, honest and all-cap):

| Treatment | Equilibria found |
|---|---|
| T2 R/S1 f=3λ | 2 (all-τ; mid-bin inflation) |
| T5 C/S1 f=3λ | 2 (two owners also cap the low bin) |
| T6 C/S2 | 2 profiles, **payoff-identical** (same payments, energy and profit) |
| T6c C/S2c with floor −0.25 or −0.5 | 2 |

Elsewhere, both starts gave the same equilibrium. That is not proof of uniqueness.

**Reporting rule:**
- Results are stated as "the equilibria found", never "the predicted equilibrium".
- Step 4 compares learned play against **every** equilibrium found.

### Central result, corrected wording

Verified settlement is insufficient when strategic reports still influence other payoff-relevant parts of the mechanism (trigger, cap, allocation). **Among the mechanisms tested,** only Variant I removes the reporting incentive. That is not a claim that it is the only possible design. Variant I trades that robustness for settlement accuracy: 2.5k gross underpayment in instructed hours, plus 1.2k of uninstructed curtailment. **Strategic robustness and settlement accuracy are distinct objectives.**

---

## Step 4: Contextual EXP3, design and pre-registered predictions (written before any learning run)

**Question.** Do learning owners independently discover the reporting incentive of each mechanism? A positive, flat or reversed relationship between bias and congestion bin can all count as results.

### Design

- **Learners.** Each owner has four EXP3 learners: one per ex-ante congestion bin (7 bias options, the spec grid with floor −0.1) and one for the daily storage declaration (2 options). Each day, every learner samples an action, and the owner reports by its bin learners.
- **Feedback: bandit.** An owner observes only its own realized daily payoff, with sampled audits under S1.
- **Reward (primary): the owner's full daily payoff,** given to all four of its learners. This is exact and absorbs the battery-state interactions across hours (reviewer checklist item). A learner is not updated on days when its bin does not occur.
  - **Robustness: bin attribution.** Each bin learner gets the payoff in its bin's hours, plus the terminal value split by that bin's share of charged energy.
- **Variance control.** Rewards are reduced by an action-independent baseline the owner observes ex post: Σ p·μ, the market value of its own honest forecast. EXP3 stays unbiased. Rewards are scaled by 4 × the running mean |reward − baseline| and clipped to [−1, 1].
  - γ = min(1, √(K ln K/((e−1)T))); η = γ/K.
- **Environment.**
  - Learning on training days 1–30, sampled uniformly with replacement. These are the days used for the π model, so learning is in-sample with respect to π.
  - Evaluation of the frozen policies on test days 31–60, which are unseen.
  - Monitor-estimate noise is fixed per day (seed 1 on training days, seed 0 on test days, as in Step 3).
- **Seeds and pairing.** 10 seeds. Seed s uses the same day sequence, audit draws and action uniforms in every treatment (paired).
- **Horizon.** T = 20,000 days per seed. Policy snapshots at T/16, T/8, T/4, T/2 and T.
- **Treatments (8):** T1 R/S0, T2 R/S1 f=5λ, T5 C/S1 f=3λ, T3 R/S2, T6 C/S2, T3c R/S2c, T6c C/S2c, T6 Variant I. Relaxed battery rule.

### Metrics

- **Policy bias by bin** on test days: expected signed realized bias (after clipping, as a share of nameplate), expected |bias|, and probability mass on each option.
- **Regret (defined precisely).** Per learner, external regret:
  $R_T=\max_a\sum_t u_t(a)-\sum_t u_t(a_t)$, where $u_t(a)$ is the learner's reward had it played $a$, with every other learner's realized action fixed (including the same owner's other learners and the same audit draws). It is computed exactly by counterfactual simulation and reported as $R_T/T$ in $/day.
  - It is **not** the same as the **equilibrium deviation gain**: the best grid deviation of one owner against the others' frozen modal policies on test days. The deviation gain is reported separately.
- **Comparison with equilibria.** For each treatment, the probability mass that the learned policies put on each equilibrium action found (test days, Steps 3b/3c). Grid equilibria are also solved on the training days.
- **Variant I.** Payoff invariance is checked directly: every counterfactual reward must equal the realized reward (to 1e-6). The policy's bias is expected to drift, not to sit at zero.
- **Outcomes** of 20 sampled pure profiles per seed on test days: payments, accuracy against physical lost generation, uninstructed curtailment, reported vs physical congestion, energy, market value.

### Predictions (frozen before running)

| ID | Treatment | Prediction | Criterion (mean over seeds, 95% CI) |
|---|---|---|---|
| L1 | T1 R/S0 | Saturation: mode = cap in all bins; hide storage | mass on cap > 0.5 in each bin; mass on hide > 0.5 |
| L2 | T2 R/S1 f=5λ | Flat near tolerance; declare | mass on {0, 0.05} > 0.6 in each bin; mass on declare > 0.5 |
| L3 | T5 C/S1 f=3λ | Failing threshold: inflation in mid/high, low near τ | bias_mid and bias_high > bias_low |
| L4 | T3 R/S2 | Low/mid inflated, high near τ | bias_mid − bias_high > 0 |
| L5 | T6 C/S2 | Inflation in all bins; exact level undetermined (payoff-identical equilibria) | bias_low, bias_mid > 0.1 |
| L6 | T3c R/S2c | Reversal: deflation in high bin | bias_high < 0; bias_high < bias_low |
| L7 | T6c C/S2c | Deflation in high bin for most owners (possible role split) | bias_high < bias_low |
| L8 | T6 Variant I | Payoff invariance (exact); no systematic bin pattern | invariance holds; CI of bias_high − bias_low contains 0 |
| L9 | all except Variant I | Per-learner regret/T falls with T | regret/T at T < at T/4 |

**Known limits.** The grid floor of −0.1 understates S2c deflation (Step 3c). The bandit signal for small gains (S2c, S1 near τ) may be too weak at T = 20,000. If so, it will be reported as "not learned at this horizon", not as "no incentive".

---

## Step 4 v1 results (pre-registered design) and a design flaw (2026-11-25)

16 runs (8 treatments × daily/bin attribution, 10 seeds, T = 20,000). Outputs in `results/step4/`.

**Checks that passed:**
- Variant I payoff invariance is exact (max |Δ| = 0 in every counterfactual).
- Realized rewards equal engine payoffs.
- The counterfactual of the played arm equals the realized reward (asserted every round).

**Policy bias by bin, final policy, test days.** Signed, as a share of nameplate; mean over 10 seeds, 95% CI half-width ≤ 0.03.

| Treatment | Daily: low / mid / high | Bin: low / mid / high | Equilibrium (test) |
|---|---|---|---|
| T1 R/S0 | 1.00 / 0.45 / 0.44 | 1.01 / 0.71 / 0.45 | cap / cap / cap |
| T2 R/S1 f=5λ | 0.03 / 0.12 / 0.06 | 0.08 / **0.51** / 0.07 | τ / τ / τ |
| T5 C/S1 f=3λ | **0.62** / 0.32 / 0.36 | **0.98** / 0.68 / 0.39 | τ / cap / cap |
| T3 R/S2 | 0.41 / 0.25 / 0.04 | 0.70 / 0.59 / 0.04 | inflate / inflate / ≈τ |
| T6 C/S2 | 0.47 / 0.30 / 0.29 | 0.81 / 0.51 / 0.29 | inflate everywhere |
| T3c R/S2c | 0.28 / 0.17 / **−0.07** | 0.46 / 0.32 / **−0.07** | ≥0 / ≥0 / −0.1 |
| T6c C/S2c | 0.30 / 0.21 / 0.17 | 0.36 / 0.15 / 0.17 | mixed / mixed / −0.1 |
| Variant I | 0.26 / 0.21 / 0.17 | 0.26 / 0.22 / 0.17 | any |

**Headroom confound.** A uniform policy (Variant I) already shows low > high in realized bias. Clipping at N+P leaves less room to inflate in high-wind hours. So **realized bias by bin must be read against the Variant I baseline**, or through option probabilities. The pre-registered L8 criterion ("CI of high − low contains 0") was misspecified for that reason. Under Variant I the option probabilities are uniform, which is the correct invariance result.

**What v1 learned correctly:**
- **T1:** saturation in the low bin (P(cap) 0.97–0.98).
- **T3 (bin attribution):** low/mid inflated, high near τ.
- **T3c:** high-bin reversal (P(−0.1) 0.78–0.81 in both attributions).
- **Variant I:** uniform play, zero regret.

**T6c did not learn the predicted deflation. This is explained, not a failure.**
- Under C, the allocation is k = min(ℓ, κ).
- β = −0.1 pushes the report below κ in only 9% of high-bin owner-hours on training days (15% on test days).
- So the high-bin options are nearly payoff-equivalent (learner regret 14 $/round), and uniform play is correct at this grid.
- The large effect needs β ≤ −0.25 (Step 3c).

**Design flaw (found after the runs).** Under S1, learned play drifts toward cap, against the equilibrium:
- T2 bin attribution, mid bin;
- T5 low bin.

The modal-profile deviation gains are large: T2 bin 2.2k $/day; T5 0.6–1.3k $/day.

**Diagnosis (Monte Carlo, uniform rivals, mid bin, owner 2):**
- Rewards were clipped to [−1, 1] after scaling by 4 × the running mean |reward − baseline|. Audit fines are rare and large, so they are the clipped tail: 3–6% of S1 rewards are clipped.
- For T2, the true advantage of τ over cap is +0.025 (scaled units). After clipping it is +0.013: halved, same sign.
- Under bin attribution the mid learner's typical reward covers only ~3 hours, so fines are clipped far harder.
- Without fines (T3), nothing is clipped.

**Conclusion.** The v1 S1 results are an artifact of reward clipping. They are **not** evidence about audits.

**Design change (v2, decided before seeing any v2 result):**
- Same design, but **no clipping**. The scale is still 4 × the running mean |reward − baseline|, and importance-weighted rewards can exceed 1. The softmax is computed stably.
- All 16 runs are repeated with the same seeds. Outputs in `results/step4_v2/`.
- The v1 results stay in the log as a documented failure mode: bounded-reward bandits understate rare large penalties.
- **Evaluation fix:** criteria based on realized bias use the Variant I baseline (Δ vs uniform), or option probabilities.

---

## Step 4 v2 results: unclipped EXP3 (2026-11-25)

16 runs, same seeds, T = 20,000; ~40 min. Outputs in `results/step4_v2/` (policy_bias, regret, mass_on_equilibria, outcomes_by_seed, outcomes_honest).

**Checks passed:**
- Variant I invariance is exact.
- Rewards equal engine payoffs.
- **Treatments without fines (T1, T3, T6, T3c, T6c, Variant I) are bit-identical to v1.** This confirms that clipping changed only the fined treatments.

### Final policies

Bias by bin on test days, as a share of nameplate. Δ is measured against the **Variant I baseline** (uniform play: 0.26 / 0.21 / 0.17). Seed 95% CI half-widths are ≤ 0.02.

| Treatment | Daily: low / mid / high | Bin: low / mid / high | Main option mass (bin) | Equilibrium found |
|---|---|---|---|---|
| T1 R/S0 | 1.00 / 0.45 / 0.44 | 1.01 / 0.71 / 0.45 | cap 0.98 / 0.96 / 0.56 | cap everywhere, hide |
| T2 R/S1 f=5λ | 0.01 / 0.09 / 0.05 | 0.01 / 0.05 / 0.05 | {0, τ} 0.78 / 0.83 / 0.74 | τ everywhere, declare |
| T5 C/S1 f=3λ | 0.04 / 0.29 / 0.36 | 0.02 / 0.58 / 0.38 | {0, τ} 0.80; cap 0.62 / 0.40 | τ / cap / cap, hide |
| T3 R/S2 | 0.41 / 0.25 / 0.04 | 0.70 / 0.60 / 0.04 | ≥0.25: 0.98 / 0.98; ≤τ: 0.73 | inflate / inflate / ≈τ |
| T6 C/S2 | 0.47 / 0.30 / 0.29 | 0.81 / 0.50 / 0.29 | ≥0.25 in all bins | inflate everywhere (payoff-identical) |
| T3c R/S2c | 0.28 / 0.17 / **−0.07** | 0.46 / 0.35 / **−0.07** | −0.1 in high: 0.78 / 0.81 | ≥0 / ≥0 / −0.1 |
| T6c C/S2c | 0.30 / 0.21 / 0.17 | 0.36 / 0.16 / 0.17 | high ≈ uniform | mixed / mixed / −0.1 |
| Variant I | 0.26 / 0.21 / 0.17 | 0.26 / 0.22 / 0.17 | uniform | any |

### Pre-registered predictions

| ID | Result | Note |
|---|---|---|
| L1 S0 saturation | **Met (bin); partial (daily)** | Daily: cap mass in mid is 0.41, which is < 0.5. Hide 0.62–0.66. |
| L2 S1 f=5λ flat near τ, declare | **Met (bin); partial (daily)** | Daily: mid mass on {0, τ} is 0.46. Declare 0.57–0.59. |
| L3 S1 f=3λ mid/high > low | **Met** | The learners recover the threshold failure exactly where P3 predicts it (congested bins, C). |
| L4 S2 mid > high | **Met** | mid − high = +0.21 (daily) / +0.56 (bin). |
| L5 C/S2 inflate | **Met** | |
| L6 R/S2c reversal | **Met** | bias_high = −0.07 < 0 in both; P(−0.1) ≈ 0.8. |
| L7 C/S2c deflation | **Not learned (explained)** | The raw criterion high < low holds, but only through headroom (Δ vs Variant I is −0.04). Option probabilities in the high bin are uniform. Cause: with floor −0.1, deflation moves k = min(ℓ, κ) in only 9% of high-bin owner-hours, so the options are nearly payoff-equivalent (learner regret 14 $/round). |
| L8 Variant I | **Invariance met exactly;** pre-registered slope criterion misspecified | Uniform option probabilities still give low > high in realized bias (headroom). |
| L9 regret/T falls | **Mostly met** | All bias learners fall from T/4 to T, except T6c mid (flat at 22 $/round; indifferent). Declaration learners fall slowly or not at all (T1: 276 → 254; T5: 35 → 43). |

### Learning vs equilibrium

- **ε-equilibrium.** Modal learned profiles have mean maximum deviation gains of 30–670 $/day, range 0–1.6k. Owner profit is ~15k $/day. So these are approximate equilibria, not exact ones.
- **Mass on equilibrium actions.** 0.15–0.83. It is low where options are near payoff-equivalent (T3/T6: 0.5 vs cap; T6c; Variant I), and high where the incentive is sharp (T1 low bin; T2; T3c high bin).
- **Training- vs test-day equilibria.** Same qualitative pattern in every treatment; profiles differ in detail (e.g. T3 mid bin 0.25 on training days vs 0.5–cap on test days).
- **Daily vs bin attribution.** Same sign for every pattern. Bin attribution learns faster and sharper (lower regret). It is approximate (battery state crosses bins), but here it never changed a conclusion.
- **Remaining limitation.** The declaration learners are slow: P(hide) under S0 is only 0.62–0.66 after 20,000 days. The gain is real but small relative to daily payoff noise.

### Outcomes of learned play

Test days, 20 sampled profiles × 10 seeds, k$/day:

| Treatment | Paid | Over / under vs physical | Instructed h without physical congestion |
|---|---|---|---|
| T1 | 118–125 | 101–108 / 0.1–0.2 | 13.3 |
| T2 f=5λ | 21–23 | 7.3–8.7 / 1.4–1.6 | 2.6–2.8 |
| T5 f=3λ | 53–60 | 37–44 / 0.2–0.7 | 3.4–3.7 |
| T3 | 16.1–16.6 | 1.9–2.4 / 2.2–2.7 | 9.6–12.9 |
| T3c | 16.7–16.9 | 1.3–1.4 / 1.1 | 7.4–10.8 |
| Variant I | 13.3 | 0.6 / 2.5 | 1.6 |

For comparison, all-honest reports pay 13.1–15.8k with 1.6 h of false instructions.

### Step 4 conclusion

Learning owners **independently discover each mechanism's incentive** where it is non-trivial, and the bias–congestion relationship takes the form predicted by the equilibria and the theory:
- **saturation** (S0);
- **flat at tolerance** (S1, f = 5λ);
- **emerges only in congested bins** (S1, f = 3λ, C);
- **falls with congestion** (S2: low/mid > high);
- **reverses** (S2c R: deflation in the high bin);
- **absent** (Variant I: exactly invariant).

The one non-learned case (C/S2c) is a near-indifference that the math explains. It becomes a strong incentive once deeper deflation is allowed (Step 3c).

**Methodological finding.** Bounded-reward bandits (clipping) understate rare large penalties. In v1, S1 learners drifted to cap. In the S1 analysis, the learning model's reward normalization is part of the result.

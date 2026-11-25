# Experiment Report: curtailment-compensation game

Readable summary of every experiment and its main results, as of 2026-11-25.
- Game definition: `game_spec_v1.md` (rev. 2.5).
- Full chronological record, including failed attempts: `EXPERIMENT_LOG.md`.
- Code: `sim/`. Results: `results/`.

---

## 1. The game in one page

**Site.** Five wind farms with batteries share one export limit. Data: ERCOT Anchor Wind, March–April 2025. Ownership and the contract are hypothetical.

| Item | Value |
|---|---|
| Owners | N = 5; nameplate 16.0, 98.8, 88.8, 38.7, 19.3 MW |
| Export limit | K = 0.6 · Σ nameplate = 157 MW |
| Batteries | Power 0.29 · nameplate, 1.5 h duration, efficiency η_c, η_d |
| True wind | W = SCED HSL (available wind) |
| Honest forecast | μ = COP HSL (mostly day-ahead; error sd 16% of nameplate) |
| Contract | λ = 30 $/MWh for eligible lost generation |
| Days | Train: days 1–30 (congestion model; learning). Test: days 31–60 (all results) |

**Each hour:**
1. Each owner reports expected output ℓ = μ + bias.
2. If total reports exceed K, the hour is "congested" and export shares k are assigned.
3. Wind above the share is stored (in instructed hours, up to battery limits). The rest is curtailed.
4. Owners are paid for lost generation by the settlement rule.

**Battery rule (fixed, not strategic):**
- Charge only from surplus in instructed hours.
- Discharge when the day-ahead price is at or above the day's median.
- **Primary rule:** discharge is also allowed in instructed hours with nothing curtailed. **Robustness:** "strict" (no discharge while instructed).

**Owner strategy.** A bias for each ex-ante congestion bin (low π < 0.2 ≤ mid ≤ 0.8 < high π, where π is estimated from the training days), plus a daily choice to **declare or hide** stored energy.
- Bias options: −0.1, 0, 0.05 (= τ), 0.1, 0.25, 0.5 (× nameplate), or "cap" (nameplate + battery power).
- 7³ × 2 = 686 strategies per owner.

**Attacks:**
- **A1, inflation:** over-report to trigger congestion or raise the payment.
- **A2, hidden storage:** claim stored energy as lost generation.

## 2. Mechanisms tested

| Code | Allocation of the limit | Settlement |
|---|---|---|
| R | Pro-rata on reports | |
| C | Capacity shares κ = K·N_i/ΣN, no reallocation | |
| S0 | | Unchecked: pays λ × reported shortfall (minus storage if declared) |
| S1 | | Audited: random audits α = 0.2/day; repayment + fine f per MWh of inflation beyond τ = 5% (against the owner's forecast records) and per MWh of hidden storage |
| S2 | | Verified: pays λ × min(reported shortfall, estimated lost generation) |
| S2c | | Verified, cap at the estimate: λ × min((Ŵ − k)⁺, estimated lost generation). The report no longer caps payment |
| Variant I | Report-independent: the operator forecast sets trigger, shares and cap | S2 |

Monitor estimate: Ŵ = W + noise (sd 4% of nameplate).

**Treatments:**

| Treatment | Allocation | Settlement | Fine |
|---|---|---|---|
| T1 | R | S0 | – |
| T2 | R | S1 | 3λ, 5λ |
| T3 | R | S2 | – |
| T4 | C | S0 | – |
| T5 | C | S1 | 3λ, 5λ |
| T6 | C | S2 | – |
| T3c | R | S2c | – |
| T6c | C | S2c | – |
| Variant I | C | S2 | – |

## 3. Methods

| Method | What it does |
|---|---|
| **Equilibrium** | Pure-strategy Nash equilibrium on the strategy grid. Sequential best response from two starts (honest; everyone at cap). Payoff = mean daily payoff over the 30 test days. Expected audit penalties. |
| **Learning (EXP3)** | Each owner has 3 bin learners plus 1 declaration learner. Bandit feedback (own realized payoff only, sampled audits). Learned on training days for 20,000 days × 10 paired seeds; evaluated on unseen test days. |
| **Regret** | Per learner, exact: best fixed action in hindsight vs realized, computed by counterfactual replay. Not the same as the equilibrium deviation gain, which is reported separately. |
| **Theory checks** | Finite differences of the simulated payoff vs the closed forms P1–P3 and P2c. |

**Benchmarks:**
- **Physical lost generation** λ·Σ(W − g) in instructed hours. This is the accuracy reference.
- **Contract-eligible** λ·Σ min(reported shortfall, W − g). Capped by reports, so shown only for reference.
- **Market value** Σ p·x − battery wear.
- **Welfare is not measured.**

---

## 4. Results

### 4.1 Validation: code and math agree

**67/67 unit tests pass.**

| Check | Result |
|---|---|
| Hand example (spec §9) | Exact: owner 2's gain from lying is R/S0 +$82, C/S0 +$72, R/S2 +$40, C/S2 $0 |
| P1: S0 marginal gain from inflation = λ(1−a) + p̂a (R), λ (C), with a = KS/L² | Matches finite differences at p = 40, 10, −20; fails at p = −200 under R, as predicted |
| P2: S2 marginal = (p−λ)a (R), 0 (C), plus trigger/cap/charging channels | Matches |
| P2c: S2c marginal = (p−λ)a (R), p−λ (C, report below share) | Matches; it predicts **under-reporting** when λ > p |
| P3: deterrence threshold α·z·(λ+f) ≥ λ (C, and hidden storage) | Reproduced exactly: f* = 4λ at α = 0.2 |
| Variant I | Every report deviation leaves all payoffs unchanged (to 0.0) |
| Accounting | Energy balance, Σx ≤ K, overpayment decomposition sums exactly |

### 4.2 Data and calibration

| Item | Value |
|---|---|
| Physical congestion (ΣW > K) | 54% of train hours, 45% of test hours (10.7 h/day) |
| Bin calibration on test days (realized vs predicted) | low 0.07 vs 0.03; **mid 0.36 vs 0.53**; high 0.91 vs 0.93 |
| Bin hours per day (train / test) | low 9.1 / 10.8; mid 2.7 / 3.7; high 12.2 / 9.5 |
| Prices | Mean 25 $/MWh; negative in 38% of congested hours; p < λ in 84–88% of high-bin hours |

The mid bin is over-predicted out of sample.

### 4.3 Equilibria (test days, relaxed battery rule)

k$/day unless stated. Δ is measured against all-honest reports under the same mechanism. "Paper congestion" = instructed hours with no physical congestion.

| Treatment | Bias low / mid / high | Declare | ΔEnergy MWh | Paper cong. h/day | Paid | Over / under vs physical | ΔOwner profit |
|---|---|---|---|---|---|---|---|
| T1 R/S0 | cap / cap / cap | hide | −1.7 | 13.3 | 130.0 | 113.9 / 0 | +114.4 |
| T2 R/S1 f=5λ | τ / τ / τ | declare | +6.1 | 2.6 | 20.0 | 5.8 / 1.0 | +3.9 |
| T3 R/S2 | 0.1–cap / 0.5–cap / 0–τ | (irrelevant) | −3.2 | 13.3 | 16.7 | 2.4 / 1.8 | +3.9 |
| T4 C/S0 | cap / cap / cap | hide | +8.5 | 13.3 | 130.0 | 113.9 / 0 | +114.5 |
| T5 C/S1 f=3λ | τ / cap / cap | hide | +6.0 | 3.3 | 71.7 | 56.1 / 0 | +13.9 |
| T5 C/S1 f=5λ | τ / τ / τ | declare | +3.0 | 2.6 | 20.2 | 5.7 / 1.2 | +3.9 |
| T6 C/S2 | 0.5–cap / 0–cap / 0.25–0.5 | (irrelevant) | +8.5 | 13.3 | 17.8 | 2.8 / 1.1 | +4.8 |
| T3c R/S2c | 0–0.5 / 0–0.1 / **−0.1** | (irrelevant) | −3.8 | 6.2 | 15.5 | 1.3 / 1.0 | +0.7 |
| T6c C/S2c | 0.05–cap / 0–cap / **−0.1 to 0.05** | (irrelevant) | −31.9 | 13.3 | 17.6 | 1.5 / 1.2 | +1.6 |
| Variant I | any (reports irrelevant) | any | 0 | 1.6 | 13.3 | 0.6 / 2.5 | 0 |

**Reference:**
- All-honest reports pay 13.1–15.8k $/day.
- Physical congestion is 10.7 h/day.
- All 32 equilibrium runs converged, with 0 deviation gain on the grid.

**Expected audit recovery:** 1.2k (f = 5λ) and 11.2k (T5 f = 3λ) $/day.

**Multiple equilibria found:**
- T2 f=3λ: all-τ, or mid-bin inflation.
- T5 f=3λ: two variants.
- T6: two profiles with identical payoffs.
- T6c with a deeper floor: two.

Results describe **the equilibria found**, not a unique prediction.

### 4.4 Settlement accounting (reconciled)

Identity: contract-eligible + report-cap gap = physical (instructed hours). It holds exactly in all treatments.

| Treatment | Paid | Contract-eligible | Report-cap gap | Physical, instructed h | Unpaid curtailment outside instructed h |
|---|---|---|---|---|---|
| T1 R/S0 | 130.0 | 16.1 | 0 | 16.1 | 0 |
| T3 R/S2 | 16.7 | 15.2 | 0.9 | 16.0 | 0 |
| T3c R/S2c | 15.5 | 9.0 | 6.3 | 15.3 | 0.8 |
| T6c C/S2c | 17.6 | 11.7 | 5.6 | 17.4 | 0 |
| Variant I | 13.3 | 13.3 | 1.9 | 15.2 | 1.2 (40 MWh) |

**Reading the table:**
- Under S2c, owners under-report, so the *reported* shortfall shrinks. The contract-eligible figure falls, but physical lost generation does not.
- S2c pays close to physical lost generation. It is not exact, because the estimate is noisy.
- Variant I's total underpayment is 2.5k (instructed hours) + 1.2k (uninstructed) = **3.7k $/day gross**.

**Market value of exports.** Changes are small against ~59.6k $/day: T1 −9; T3 +232; T6 +235; T3c +115; T6c −722 $/day. The measured damage is mainly **financial (transfers)**, not lost market value.

### 4.5 Robustness

**Battery rule.** ΔEnergy vs honest, MWh/day:

| Treatment | Relaxed (primary) | Strict |
|---|---|---|
| T1 R/S0 | −1.7 | −78.9 |
| T2 R/S1 f=5λ | +6.1 | +2.6 |
| T3 R/S2 | −3.2 | −73.0 |
| T5 C/S1 f=5λ | +3.0 | +0.1 |
| T6 C/S2 | +8.5 | −51.8 |
| T3c R/S2c | −3.8 | −45.7 |
| T6c C/S2c | −31.9 | −40.9 |

The incentives and payments are almost unchanged (ΔProfit within 0.8k). The energy effect depends on the rule, by 0–77 MWh/day.

**No batteries.** Same inflation pattern under T1, T4 and T6:
- T1: paid 75.3 vs eligible 19.0k;
- T6: paid 20.4 vs 19.0k.

Storage raises the stakes but does not cause the incentive.

**Depth of under-reporting (S2c).** The lowest option was binding, so I widened it:

| Lowest option | T3c bias high | T3c ΔE | T6c bias high | T6c ΔE (MWh/day) | T6c ΔMarket value | T6c paid |
|---|---|---|---|---|---|---|
| −0.1 | −0.10 | −3.8 | −0.10 to 0.05 | −32 | −0.7k | 17.6k |
| −0.25 | −0.22 | −9.5 | −0.09 / +0.04 | −99 / −125 | −1.8k / −2.6k | 19.8k / 20.6k |
| −0.5 | −0.32 | −14.9 | −0.16 / −0.30 | **−426 / −454** | **−6.8k / −7.3k** | 29.9k / 27.2k |

- **Pro-rata (R):** partly self-limiting. Large owners stop early because deeper cuts would end the paid congestion.
- **Capacity shares (C):** owners split roles. Some report cap to keep congestion on (22–24 h/day); the others under-report to be paid for curtailment.
- At −0.5, T6c loses ~16% of exports.

### 4.6 Learning (contextual EXP3, v2, unclipped rewards)

Final policies on test days. Bias as a share of nameplate; seed 95% CI half-widths ≤ 0.02. Uniform play (Variant I) gives 0.26 / 0.21 / 0.17 from headroom alone: high-wind hours have less room below the cap. Read bias against that baseline.

| Treatment | Bias low / mid / high (bin rewards) | Dominant options | Matches equilibrium? |
|---|---|---|---|
| T1 R/S0 | 1.01 / 0.71 / 0.45 | cap 0.98 / 0.96 / 0.56; hide 0.62 | Yes (saturation) |
| T2 R/S1 f=5λ | 0.01 / 0.05 / 0.05 | {0, τ} 0.78 / 0.83 / 0.74; declare 0.59 | Yes (flat at tolerance) |
| T5 C/S1 f=3λ | 0.02 / 0.58 / 0.38 | {0, τ} 0.80 low; cap 0.62 / 0.40 | Yes (fails only in congested bins) |
| T3 R/S2 | 0.70 / 0.60 / 0.04 | ≥0.25 in low/mid; ≤τ 0.73 high | Yes (falls with congestion) |
| T6 C/S2 | 0.81 / 0.50 / 0.29 | ≥0.25 everywhere | Yes |
| T3c R/S2c | 0.46 / 0.35 / **−0.07** | −0.1 high: 0.81 | Yes (**reversal**) |
| T6c C/S2c | 0.36 / 0.16 / 0.17 | high ≈ uniform | Not learned (near-indifference, see below) |
| Variant I | 0.26 / 0.22 / 0.17 | uniform; regret exactly 0 | Yes (invariance) |

**Daily-payoff rewards** give the same sign for every pattern, but learn more slowly.

**Pre-registered predictions:**

| Predictions | Result |
|---|---|
| L3, L4, L5, L6 | Met |
| L1, L2 | Met with bin rewards; partial with daily rewards |
| L7 | Not learned, explained |
| L8 | Invariance exact; slope criterion misspecified (headroom) |
| L9 | Regret falls for bias learners; slowly or not at all for declaration learners |

**Why T6c is not learned.** Under C, the allocation is min(report, share). A −0.1 report falls below the share in only 9% of high-bin owner-hours, so the options pay almost the same (regret 14 $/round).

**Distance to equilibrium.** Learned modal profiles are approximate equilibria: mean maximum deviation gain 30–670 $/day, against ~15k $/day profit per owner.

**Outcomes of learned play (k$/day):**

| Treatment | Paid | Overpaid | Paper congestion (h/day) |
|---|---|---|---|
| T1 | 118–125 | 101–108 | 13.3 |
| T2 f=5λ | 21–23 | 7–9 | 2.6–2.8 |
| T5 f=3λ | 53–60 | 37–44 | – |
| T3 | 16.1–16.6 | – | 9.6–12.9 |
| T3c | 16.7–16.9 | – | 7.4–10.8 |
| Variant I | 13.3 | – | 1.6 |

---

## 5. Theory vs simulation

| Result | Theory | Simulation | Status |
|---|---|---|---|
| P1: unchecked pay rewards inflation | Marginal λ(1−a) + p̂a (R), λ (C) | Cap everywhere; learners saturate | Confirmed |
| P2: verified pay leaves 3 channels | Trigger, cap, charging permission | Inflation in low/mid bins; 13 paper-congestion h/day | Confirmed; channels larger than expected |
| P2c: cap at estimate reverses the sign | (p−λ)a (R), p−λ (C) < 0 when λ > p | Under-reporting in the high bin; learners find it (R) | Confirmed; **not local** under C |
| P3: deterrence threshold f* = 4λ | α(λ+f) ≥ λ | τ everywhere at 5λ; failure at 3λ under C | Confirmed exactly, in equilibrium and learning |
| Weak IC of Variant I | Reports irrelevant | Payoffs identical to 0.0; learners stay uniform | Confirmed exactly |
| P4: two-rate settlement | λ_q − λ_c per hidden MWh | – | Not run |

---

## 6. Main findings

1. **Unchecked self-reported compensation is fully exploited.** Owners report the maximum; payments are 8× eligible (130k vs 16k $/day). The damage is financial, not physical.
2. **Audits work when the fine clears the threshold.** At f = 5λ, owners stop exactly at the tolerance and declare storage. At 3λ, C fails in congested bins. Theory, equilibria and learning agree.
3. **Verifying claims is not enough while reports still decide when and how much compensation is available.**

   | Where the report still enters | What owners do |
   |---|---|
   | Trigger | Inflate to create instructions (13 h/day of paper congestion) |
   | Payment cap | Inflate to lift it; honest owners are underpaid |
   | Allocation | Under-report to be paid for curtailment (S2c). Under capacity shares this becomes severe: up to 16% of exports lost |

4. **Among the mechanisms tested, only the report-independent design (Variant I) removes the reporting incentive.** It pays for it in accuracy: 3.7k $/day gross underpayment from forecast errors. **Strategic robustness and settlement accuracy are different objectives.**
5. **Learning owners discover these incentives on their own.** The bias–congestion relationship saturates, stays flat, falls or reverses, by mechanism, as predicted.
6. **Storage amplifies but does not cause the problem.** The battery rule drives the energy effects (0–77 MWh/day), not the incentives.

---

## 7. Corrections made along the way

| Issue | Fix |
|---|---|
| Terminal battery value omitted wear | Added (rev. 2.1); the storage tests pass only with the fix |
| Honest owners fined on 97% of days (day-ahead forecast vs τ = 5%) | Fine base = bias against the owner's forecast records (user decision, rev. 2.2) |
| Grid lacked β = τ, so "inflate to τ" appeared as 0.1 | Added 0.05 (rev. 2.3) |
| Strict battery rule exaggerated energy losses | Relaxed rule made primary (rev. 2.4) |
| "$9/day" Variant I error hid offsetting errors | Gross over/under against physical lost generation |
| S2c "paid 15.5k vs eligible 9.0k" looked inconsistent | The benchmark is capped by reports; reconciled exactly |
| Under-reporting option −0.1 was binding | Checked −0.25 and −0.5; the effect is not local |
| Pre-registration miss | The trigger channel applies to R/S2 too (I4) |
| Learning v1 clipped rewards; audit learners drifted to cap | Unclipped v2. Treatments without fines identical; audits now match theory |
| Learning test "no slope under Variant I" | Misspecified (headroom); use the Variant I baseline |

## 8. Limitations

- One site, 30 test days, one season. Hypothetical owners and contract.
- Equilibria hold on the strategy grid only. Thresholds are conditional on α = 0.2, z = 1 and access to the owners' forecast records (a strong assumption).
- The honest forecast is day-ahead (COP), and the mid bin is miscalibrated out of sample.
- Battery behaviour follows a fixed rule; it is not optimized.
- Energy and market value are not welfare.
- Learning runs keep −0.1 as the lowest option, so S2c under-reporting from learning is a lower bound.
- Storage-declaration learning is slow.

## 9. Next steps

1. Sensitivity: λ, f, forecast accuracy (σ of the estimate), and learning with a −0.25 floor.
2. Quantify the robustness–accuracy trade-off across designs.
3. If time allows: two-rate settlement (P4).
4. Consolidate figures for the report and slides (Dec 10).

## 10. Files

| File | Content |
|---|---|
| `sim/engine.py`, `sim/params.py`, `sim/data.py` | Model, parameters, data |
| `sim/equilibrium.py`, `sim/run_step3.py` | Equilibria and core experiments |
| `sim/run_step3c.py` | Accounting reconciliation, market value, deflation-floor check |
| `sim/learning.py`, `sim/run_step4.py` | EXP3 learning and analysis (`STEP4_VERSION=v2`) |
| `sim/tests/test_engine.py` | 67 tests |
| `results/step3_summary.csv`, `step3_profiles.json` | Equilibrium results |
| `results/step3c_*.csv` | Accounting and deflation-floor results |
| `results/step4_v2/*.csv` | Learning results (`results/step4/` = v1, clipped) |

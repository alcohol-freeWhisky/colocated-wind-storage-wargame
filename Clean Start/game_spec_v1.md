# Game Specification v1.0

Single source of truth for theory and simulations. A change to the game must be written here first.
Status: **frozen (rev. 2, 2026-11-25)** after the final audit; rev. 2.1–2.5 are implementation fixes and reporting rules logged in `EXPERIMENT_LOG.md`.

**Reporting conventions (rev. 2.4):**
- Equilibria hold **on the tested strategy grid** only, not globally.
- Thresholds such as $f^*=4\lambda$ are **conditional** on the stated assumptions, not policy prescriptions.
- Audit access to authentic forecast records is a **strong assumption**.
- Reported congestion (instructions) is distinct from physical congestion ($\sum W>K$).
- Results report **the equilibria found** (two starting points), never a unique prediction (rev. 2.5).
- Among the mechanisms tested, only Variant I removes the reporting incentive. This is not a claim about all possible designs (rev. 2.5).
- One site; 30 evaluation days. The propositions in Section 9 are conditional statements. Unit tests check the implementation; they are not proofs.

**Framing.** A GB-motivated curtailment-compensation game, calibrated with ERCOT data. The site, ownership, contract, sharing rules and audits are a **proposed design**, not a replica of any market.

| Real-world anchor | What it supports | Source |
|---|---|---|
| Wind farms overstate notified output more when constraints are likely, and are paid for curtailment relative to it | Attack A1 and the learning validation target | Intini & Waterson (2023), *IJIO* 89 |
| Pay for lost output from an independent estimate (wind speed, power curve) | Verified settlement | German Redispatch 2.0; South African REIPPPP "deemed energy" |
| Misleading physical notifications are sanctioned, with repayment of gains plus a fine | Repayment + fine | Ofgem, InterGen (2020) |
| Several generators share one point of interconnection | Shared limit $K$ | Texas co-tenancy agreements; CAISO co-located resources |

---

## 1. Players, site, data

- **Owners** $i=1,\dots,N$. Theory: $N=2$. Simulations: $N=5$, i.e. the Anchor Wind units (16, 99, 89, 39, 19 MW), treated as **hypothetical** independent owners.
- **Monitor.** It commits to an announced rule before play (Section 7). The network operator follows fixed rules and is not a player.
- **Data.** ERCOT, 60 days (Mar–Apr 2025), hourly.
  - True available wind $W_{it}$ = SCED HSL.
  - Owner's honest forecast $\mu_{it}$ = COP HSL.
  - Price $p_t$ = HB_WEST real-time price; day-ahead price $p^{DA}_t$, known before the day.
  - **Proxies to validate:**
    - SCED HSL as available wind (telemetered potential; it is itself an estimate during curtailment).
    - COP HSL as the honest forecast (the snapshot at the start of the adjustment period, i.e. mostly day-ahead and known to the owner; published 60 days later).
- **Contract (hypothetical).** Owners are paid rate $\lambda$ per MWh of **eligible lost generation** caused by an instruction. No compensation is assumed to exist without this contract.

## 2. Physics (owner $i$, hour $t$; MW over one hour = MWh)

| Symbol | Meaning |
|---|---|
| $W$ | available wind |
| $g\le W$ | wind generated |
| $r=W-g\ge0$ | physical curtailment (lost generation) |
| $c\le\min(g,P)$ | charging, from own wind only |
| $d\le P$ | discharging |
| $x=g-c+d$ | metered export |
| $s$ | stored energy, $0\le s\le E$ |

$$s_{t+1}=s_t+\eta_c c_t-d_t/\eta_d,\qquad c_t\,d_t=0,\qquad x_{it}\le k_{it},\qquad \sum_i x_{it}\le K.$$

**Battery rule (fixed, not strategic in v1.0):**
1. **Instructed hour** ($v_{it}>0$, Section 4): export $\min(W,k)$. Store the surplus $(W-k)^+$ up to $\min(P,(E-s)/\eta_c)$ and curtail the rest. **Primary rule (rev. 2.4):** discharge is allowed only if nothing is curtailed ($r=0$, so $W\le k$ and the share has room). **Robustness:** "strict", i.e. no discharge in any instructed hour. The strict rule alone explained most of the measured energy loss (log, Step 3, F5).
2. **Other hours:** no charging. This is the storage counterfactual: no charging without an instruction. Discharge $d=\min(P,\ \eta_d s,\ k-g)$ if $p^{DA}_t\ge$ the median day-ahead price of the day, otherwise $d=0$. This rule uses no realized future prices.
3. Daily reset $s_0=0.5E$. Terminal value $(\bar p-10)^+\,\eta_d\,s_{24}$, where $\bar p$ is the day's mean positive **day-ahead** price. Wear is subtracted so that this matches $V_s$ in Section 9 (rev. 2.1, a fix found during implementation).

Parameters: $K=0.6\sum_iN_i$, $P_i=0.29N_i$, $E_i=1.5P_i$, $\eta_c=\eta_d=0.922$, wear cost $10$ \$/MWh discharged.

## 3. Information and timing

**Before play:** the monitor announces its rule: audit probability $\alpha$ or targeting, fine $f$, tolerance $\tau$.

**Each day:**
1. Each owner picks a **strategy**: a report option for each congestion bin, plus a storage-declaration choice (Section 5).
2. **Each hour, before delivery,** the owner knows $\mu_{it}$, its own $s_{it}$, the public $K$ and $N_j$, and the **ex-ante congestion probability** $\pi_t$. It does **not** know $W_{it}$ or rivals' reports. It submits $\ell_{it}$.
   - $\pi_t=\Pr\big(\sum_jW_{jt}>K\mid\sum_j\mu_{jt}\big)$, estimated from forecast errors on the 30 training days.
   - Bins: low $<0.2$, mid $0.2$–$0.8$, high $>0.8$.
3. **Allocation** $k_{it}$ and instruction $v_{it}$ (Section 4). Then $W_{it}$ is realized and the battery rule runs.
4. **Settlement** (Section 6). After the day: automated checks and audits (Section 7).

**What each side sees:**
- **Owners** see their own $\ell,k,x,v$ and payments. Under rule R they can infer the rivals' total report, $\sum_{j\ne i}\ell_j=K\ell_i/k_i-\ell_i$, in congested hours.
- **The monitor** sees all $\ell,k,x$ (export meters) and an independent estimate $\widehat W_{it}=W_{it}+\varepsilon_{it}$, with $\sigma_\varepsilon=4\%$ of $N_i$. This is an **assumption**, guided by ERCOT's hour-ahead forecast error of 3–4% but not calibrated for this measurement. Sensitivity 2–16%.
  - **Generation and battery meters** ($g,c$) are visible only under **verified settlement**, or in an audit.

## 4. Allocation (instruction to reduce)

Congestion trigger: the hour is congested if $L_t=\sum_j\ell_{jt}>K$. This is a stylized, report-based trigger; the GB operator does not literally compute it this way.

| Rule | Congested hour | Uncongested hour |
|---|---|---|
| **R** report-proportional | $k_i=\ell_iK/L$ | $k_i=\ell_i+(K-L)N_i/\sum_jN_j$ |
| **C** capacity-based fixed shares, **no reallocation** | $k_i=\min(\ell_i,\kappa_i)$, $\kappa_i=KN_i/\sum_jN_j$ | same as R |

**Instructed reduction:** $v_{it}=(\ell_{it}-k_{it})^+$ in congested hours, and $0$ otherwise.

**Variant I (one extra run, Section 10): fully report-independent.** The operator's own ex-ante forecast $\widehat W^{ex}_{jt}$ replaces the reports everywhere:
- **Trigger:** the hour is congested if $\sum_j\widehat W^{ex}_{jt}>K$.
- **Allocation:** $k_i=\kappa_i$ in congested hours; $k_i=\widehat W^{ex}_i+(K-\sum_j\widehat W^{ex}_j)N_i/\sum_jN_j$ otherwise.
- **Cap:** $v_i=(\widehat W^{ex}_i-\kappa_i)^+$.
- **Charging permission:** follows this $v_i$.

Reports then have no effect on payoffs. This makes them **weakly** incentive compatible (inflation gains nothing), but not strictly truthful (truth gains nothing either).

## 5. Owner strategies and attacks

- **Report.** $\ell_{it}=\min(\mu_{it}+\beta N_i,\ N_i+P_i)$, with bias option $\beta\in\{-0.1,\,0,\,\tau{=}0.05,\,0.1,\,0.25,\,0.5,\,\text{cap}\}$ and $\ell\ge0$ chosen **per congestion bin** (rev. 2.3 added $\beta=\tau$: without it the grid could not show inflation stopping exactly at the tolerance; log, Step 3). The bias is $b_{it}=\ell_{it}-\mu_{it}$. An honest forecast error $W-\mu$ is **not** manipulation.
- **Storage declaration** $\delta_i\in\{\text{declare},\text{hide}\}$, chosen once per day.

| Attack | Definition |
|---|---|
| **A1 baseline inflation** | $b>0$ |
| **A2 storage misrepresentation** | Hide the charging $c$ done during instructed hours, so stored energy is claimed as lost generation |

**A2 is a settlement vulnerability, not strategic storage behaviour.** Charging follows the fixed rule of Section 2. The only strategic storage choice is $\delta_i$: whether to declare the stored energy.

Out of scope in v1.0: strategic battery timing, strategic bid prices ($\lambda$ is fixed), collusion, other storage attacks.

## 6. Settlement

**Three quantities** (owner $i$, instructed hour):

| Quantity | Formula |
|---|---|
| Instructed reduction | $v=(\ell-k)^+$ |
| Delivered export reduction | $\ell-x$ (diagnostic only) |
| Eligible lost generation | $e=\min\{v,\ (\widehat g^{\,\text{cf}}-g)^+\}$ |

- **Counterfactual generation** $g^{\text{cf}}$ is what the owner would have generated without the instruction.
  - **Core assumption:** wind always generates absent an instruction (price + subsidy > 0), so $g^{\text{cf}}=W$, estimated by $\widehat g^{\,\text{cf}}=\widehat W$.
  - **Sensitivity:** $g^{\text{cf}}=0$ in hours with $p_t<-s$ (voluntary curtailment; $s$ = subsidy per MWh).
- With an exact estimate and a **non-binding cap** ($v\ge r$), $e=r$: the energy actually lost. An honest under-forecast ($\mu<W$) can make the cap bind, so that $e=v<r$. Stored energy is **not** lost, so it is never eligible.

| Settlement | Payment $T_{it}$ |
|---|---|
| **S0** self-reported, unchecked | $\lambda v$ if hide; $\lambda(v-c)^+$ if declare |
| **S1** self-reported, audited | Provisional S0 payment; corrected if audited (Section 7) |
| **S2** verified (automated reconciliation with generation and battery meters) | $\lambda e$ |
| **S2c** verified, cap at the estimate (rev. 2.4) | $\lambda\min\{(\widehat W-k)^+,(\widehat g^{\,\text{cf}}-g)^+\}$ in congested hours. The report no longer caps the payment; the trigger and allocation still use reports. |

**Owner payoff per day:**
$$U_i=\sum_t\big[p_tx_{it}+T_{it}-10\,d_{it}\big]+(\bar p-10)^+\eta_d s_{i,24}-\text{Repay}_i-\text{Fine}_i.$$

Base $\lambda=30$ \$/MWh (sensitivity 15, 60).

## 7. Verification and enforcement (S1)

- **Audit.** One owner-day per day ($\alpha=1/N$), chosen at random or **targeted** at the largest $\sum_t(\ell_{it}-\widehat W_{it})^+/N_i$. An audit reveals $W$, $g$, $c$ exactly (detection $z=1$; sensitivity $z<1$).
- **Invalid volume:** $\omega_i=\sum_t\big(v_{it}^{\text{paid}}-e^{\text{true}}_{it}\big)^+$, with $e^{\text{true}}=\min\{v,(g^{\text{cf}}-g)^+\}$.
- **Inspection vs. detection.**
  - An audited owner-day is **inspected**.
  - A violation is **detected** with probability $z$ (base $z=1$).
  - A false finding on a compliant owner-day occurs with probability $z_0$ (base $0$; sensitivity $>0$).
  - Repayment and fines apply **only on a finding**.
- **Repayment on a finding:** $\lambda\,\omega_i$.
- **Fine on a finding:**
  - inflation part, beyond the tolerance: $f\sum_t(\ell_{it}-\mu_{it}-\tau N_i)^+$. This is bias against the owner's own forecast records, which the audit reads (rev. 2.2; GB "best estimate" standard). Honest forecast error is therefore never fined: with the day-ahead COP as $\mu$ (sd 16% of $N$), a base of $(\ell-W-\tau N)^+$ would fine honest owners on 97% of days at $\tau=5\%$ (log, Step 2). $\tau$ covers record ambiguity;
  - hidden storage, **only if $\delta_i=$ hide**: $f\sum_t c_{it}$, with no tolerance because it is metered. Declared storage is never fined.
- **Parameters:** $\tau=5\%$ of $N_i$; $f\in\{0,1,3,5\}\times\lambda$.
- **Monitor.** It commits to the rule and is **not optimized** in the core experiment; this is a mechanism with best-responding owners. Its outcomes are reported **separately**, not summed (they have different units):
- overpayment (\$);
- lost energy (MWh);
- audits used;
- false findings (count and \$).

Optimizing over a small grid of $(\alpha,f)$ needs an explicit weighting and is an extension.

## 8. Solution concepts

- **Equilibrium.** Owners play Nash given the committed rule. Computed by best-response iteration over the strategy grid of Section 5.
  - Report the maximum unilateral deviation gain for every candidate profile.
  - Report best-response cycles; convergence is not assumed.
  - Unique or global equilibria are not claimed.
- **Learning.** **Contextual EXP3**: one learner per owner per congestion bin, plus one for the declaration choice.
  - **Reward of a bin learner:** the owner's payoff in that day's hours within that bin. Fines are attributed to bins in proportion to the inflation volume in each.
  - **Reward of the declaration learner:** the daily payoff.
  - Rewards are scaled to $[0,1]$.
  - Battery state couples hours, so bin rewards are approximate; state this.
  - Convergence to Nash is **not** assumed. Report regret and the frequency with which each option is played.
- **Data split.**
  - Days 1–30: estimate $\pi_t$ and the forecast-error distribution.
  - Days 31–60: equilibrium and learning evaluation, sampled with replacement for repeated play.

## 9. Theory (two owners, one hour; assumptions stated)

**Common assumptions (A):**
- the hour is congested, and the congestion state does not change with $\ell_i$;
- rivals' reports are fixed;
- $\lambda>0$;
- the audit probability does not depend on reports (random audits);
- reports are below the cap;
- $W\ge k$, i.e. the owner can fill its share;
- the cap is not binding ($v\ge$ true lost generation).

**Value of a stored MWh** (one MWh of surplus wind charged instead of exported now): $V_s=\eta_c\eta_d\,(\tilde p-10)$, where $\tilde p$ is the expected later sale price (or the terminal value per MWh delivered) and 10 is the wear cost.
- $V_s$ applies only when the marginal MWh **displaces charging**.
- When it displaces curtailment, use the curtailment case.

- **P1. Self-reported settlement rewards inflation.** Under (A) and S0 (hide). Let $a=KS/L^2\in(0,1)$, with $S=\sum_{j\ne i}\ell_j$. Let $\hat p$ be the value of one more MWh exported now: $\hat p=p$ if it displaces curtailment, $\hat p=p-V_s$ if it displaces charging.
  - Under C (when $\ell_i>\kappa_i$): $\partial U_i/\partial\ell_i=\lambda>0$. This always holds, because exports do not change.
  - Under R: $\partial U_i/\partial\ell_i=\lambda(1-a)+\hat p\,a$. It is positive **iff** $\hat p>-\lambda(1-a)/a$. That holds whenever $\hat p\ge0$, but **can fail** at sufficiently negative prices.
  - *Proof:* under R, $v_i=\ell_i(1-K/L)$, so $\partial v_i/\partial\ell_i=1-a$ and $\partial k_i/\partial\ell_i=a$, with $x_i=k_i$. Here $a\in(0,1)$ because $K<L$ and $S<L$. Under C, $k_i=\kappa_i$ is fixed, so $v_i$ rises one-for-one with $\ell_i$. ∎
- **P2. Verified settlement (S2): what it removes and what remains.**
  - **Removes:** under S2, the declaration choice (A2) has no effect, because $e$ uses metered $g$, so stored energy is never eligible.
  - **Overpayment can still occur** through the estimation error $\widehat W-W$. That is not misconduct.
  - **Under C:** with the trigger fixed and the cap not binding ($v\ge \widehat g^{\,\text{cf}}-g$), $e_i$ and $x_i$ do not depend on $\ell_i$, so A1 gains nothing.
  - **Under R:** extra share lowers eligible compensation one-for-one.
    - With curtailment and no storage: net gain from inflation $=(p-\lambda)\,KS/L^2$, which is zero or negative when $\lambda\ge p$.
    - With storage: net gain $=(p-V_s)\,KS/L^2$, where $V_s$ is the later value of one stored MWh.
  - **Three channels remain, even under C with S2:**
    1. **Trigger.** Inflation can create an instruction, paying $(\lambda-p_t)$ per MWh of induced lost generation.
    2. **Cap.** If $v<\widehat g^{\,\text{cf}}-g$ (an honest under-forecast, or $\widehat W>W$), raising $\ell$ raises $e$.
    3. **Charging permission.** An instruction unlocks charging under the Section 2 rule, which is worth up to $V_s$ per stored MWh.
  - **Report-irrelevant only under Variant I** (Section 4). There, inflation gains nothing, but truth is not strictly preferred either (weak incentive compatibility).
- **P2c. Cap at the estimate (S2c) reverses the incentive when $\lambda>p$** (rev. 2.4; tests `test_P2c_*`).
  - Curtailment case: under R, $\partial U_i/\partial\ell_i=(p-\lambda)a$. Under C with $\ell_i<\kappa_i$ ($k_i=\ell_i$), $\partial U_i/\partial\ell_i=p-\lambda$.
  - So when $\lambda>p$, owners gain by **under-reporting**: a smaller share means more paid curtailment.
  - Removing the report from the cap closes inflation through the cap, but opens deflation through the allocation. Only Variant I closes both.
  - **Not local** (rev. 2.5, log Step 3c). Under C the marginal stays $p-\lambda$ down to $\ell=0$, as long as rivals keep $L>K$. Equilibria then split roles: some owners inflate to hold the trigger, and others deflate. Under R, the gain $(p-\lambda)a$ is limited by owners being pivotal for the trigger. Widening the grid floor from −0.1 to −0.5 changes the T6c energy loss from −32 to −426/−454 MWh/day.
- **P3. Local deterrence condition** (S1, one shot, linear fine, beyond the tolerance). Per MWh of inflation:
  - C: $\alpha z(\lambda+f)\ge\lambda$.
  - R (curtailment, no storage): $\alpha z(\lambda+f)\ge\lambda+(p-\lambda)KS/L^2$.
  - Hidden storage: $\alpha(\lambda+f)\ge\lambda$.
  - This is a **local sufficient** condition for **random** audits: under R the share gain is concave. Targeted audits raise $\alpha$ with $b$, so the condition stays sufficient but is no longer necessary.
  - It is not a repeated-game guarantee. It must hold in the hour where lying pays most.
  - Within the tolerance only repayment applies. Inflating up to $\tau$ **can** then pay when $\alpha z<1$, but not always: other payoff effects (P1 with negative $\hat p$) can make it unprofitable.
- **P4. Two-rate extension.** If stored energy is paid $\lambda_c$ and lost generation $\lambda_q$, hiding storage gains $\lambda_q-\lambda_c$ per MWh. Equal rates remove A2 only, not A1.
- **Sensitivity (not a theorem).** Voluntary curtailment at negative prices ($p<-s$, with $s$ the subsidy per MWh) changes which payments count as overpayment. Storage value and contract revenue also matter.

**Hand-worked check (P0; continuous report, not a grid option).** Nameplates $N=(10,5)$, $K=9$, $W=\mu=(8,4)$, $p=40$, $\lambda=30$. Owner 1's battery is full; owner 2 has room. Owner 2 reports 6.4 instead of 4.

| | R, honest | R, owner 2 reports 6.4 | C, honest | C, owner 2 reports 6.4 |
|---|---|---|---|---|
| Shares $k$ | (6, 3) | (5, 4) | (6, 3) | (6, 3) |
| $v_2$ | 1 | 2.4 | 1 | 3.4 |
| Owner 2 export $x_2$ | 3 (stores 1) | 4 (stores 0) | 3 (stores 1) | 3 (stores 1) |
| $T_2$ under S0, hide | 30 | 72 | 30 | 102 |
| $T_2$ under S2 ($e_2$) | 0 | 0 | 0 | 0 |
| Owner 2 gain from the lie, S0 | | +40 energy, +42 payment | | +72 payment |
| Owner 2 gain from the lie, S2 | | +40 energy, = $(p-V_s)\times1$ with $V_s=0$ here | | 0 |

This is a one-hour example, so stored energy has no later value here. Under S0 the honest payment $T_2=30$ is itself invalid: it is A2, paying for the stored 1 MWh. Under S2 it is correctly 0. This example becomes a unit test.

## 10. Experiments

**Core (2 × 3), identical days and seeds:**

| Allocation | S0 unchecked | S1 audited | S2 verified |
|---|---|---|---|
| R report-proportional | T1 | T2 | T3 |
| C capacity shares | T4 | T5 | T6 |

- **Controls:** no-battery owners, which isolate what storage adds; truthful-only owners ($\beta=0$, declare).
- **Extra run:** T6 under Variant I (Section 4), to isolate the three remaining channels of P2.
- **Later:** two-rate settlement; weighted uniform allocation; stress days ($K$ lower); $\lambda$, $\tau$, $\sigma_\varepsilon$, $f$ sensitivity.

**Unit tests (must pass before any experiment):**

| # | Scenario | Expected |
|---|---|---|
| U1 | Honest report, real curtailment, exact $\widehat W$, non-binding cap | $T=\lambda r$ under S2 |
| U2 | Honest report, ordinary forecast error | No fine within $\tau$; not counted as inflation |
| U3 | Storage instead of curtailment | $e=0$ for stored energy under S2 |
| U4 | Battery full or empty | Feasible: $0\le s\le E$, $c\,d=0$ |
| U5 | No congestion | $v=0$, $T=0$ |
| U6 | Report-induced instruction | Trigger flips; payment counted as self-induced |
| U7 | T6, unilateral deviations over the strategy grid | Any gain arises only through the trigger, cap or charging channels (each logged) |
| U8 | All mechanisms | Energy balance; $\sum_ix_i\le K$; payments add up |
| U9 | Section 9 hand example | Table values reproduced, e.g. owner 2's gain: R/S0 \$82, C/S0 \$72, R/S2 \$40, C/S2 \$0 |
| U10 | Variant I | Every admissible unilateral report deviation leaves all payoffs unchanged |
| U11 | Storage declared | No hidden-storage fine |
| U12 | Imperfect verification ($z<1$, $z_0>0$) | Findings, repayments, fines and false findings are accounted for correctly |
| U13 | Overpayment decomposition | The parts add up exactly to total overpayment; no double counting |

**Headline test (rev. 2.5).** Does the relationship between bias $b=\ell-\mu$ and the ex-ante congestion bin **emerge, disappear or reverse** across mechanisms? Measured in equilibrium (Step 3) and under contextual EXP3 (Step 4, design and predictions L1–L9 pre-registered in the log).
- **Equilibria found:**
  - saturation (S0);
  - flat at $\tau$ (S1, $f=5\lambda$);
  - low/mid above high (S2);
  - reversal in the high bin (S2c);
  - payoff invariance (Variant I), where the level of $b$ is undetermined and EXP3 can drift.

**Metrics:**

| Metric | Measure |
|---|---|
| Reporting | bias $b$ by bin |
| Overpayment $O=T^{\text{act}}-\lambda e^{\text{true}}$ | **Telescoping decomposition** (the parts sum exactly to $O$): storage $=T^{\text{act}}-T(\text{declare},\ell)$; inflation $=T(\text{declare},\ell)-T(\text{declare},\mu)$; error $=T(\text{declare},\mu)-\lambda e^{\text{true}}$. The error part (forecast or estimation error) is not misconduct. The order of the steps is fixed and stated. |
| Self-induced instructions | Reported **separately**, not part of $O$: payments in hours that are congested only because of $i$'s inflation (congested given $\ell$, but not given $(\mu_i,\ell_{-i})$) |
| Settlement accuracy (rev. 2.5) | Against **physical** lost generation $\lambda\sum(W-g)$ in hours with reported congestion: gross over, gross under, net. Curtailment **outside** reported congestion (unpaid) is reported separately. The contract-eligible figure $\lambda\sum\min(v,W-g)$ is capped by the *reported* shortfall. It is shown only as "what a report-capped contract owes". Identity: contract-eligible + report-cap gap = physical. |
| Physical | curtailment $\sum r$, stored energy, energy delivered; market value of exports $\sum p\,x-$ wear. Neither is welfare: system replacement cost, the payer's cost of overpayment and the effects of false instructions on others are omitted. |
| Owners | profits; fairness across owners |
| Monitor | audits used; fines on honest owners (false positives) |
| Learning | regret; play frequencies over time |

## 11. Plan to December 10

| Dates | Output |
|---|---|
| Nov 25–26 | This spec; targeted consistency review; P0 example as a unit test |
| Nov 27–29 | P1–P4 written up; code: battery rule, forecasts, settlement S0–S2, audits |
| Nov 30–Dec 2 | Core T1–T6 equilibria and controls |
| Dec 3 | Exam (no project work) |
| Dec 4–5 | Contextual EXP3 and the headline test |
| Dec 6–7 | Two-rate settlement, sensitivity, limitations |
| Dec 8–9 | Report and slides |

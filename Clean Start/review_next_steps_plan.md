# Review of `docs/next_steps_plan.md` (remote `main`, commits 4bb00a7 → fe12f1f, Nov 22–23)

Question: does the teammate's two-branch plan describe something that exists in reality, and does it fit what we already decided (`Our References/update_20261120/`)?

**Short answer.** Part I is realistic in its physics but assumes information that rivals do not get in practice, and its maximum possible payoff is small (about 3%) and comes mostly from a charge we designed. Part II has a logic error: a compliant operator can never charge its battery or curtail wind, so the "violation" is the only way to use the battery. Its low-price violation also has no real-world counterpart. Both parts drop the reporting + inspection game that the Nov 20 Decision Log chose as the central game. The team has to settle that before Dec 10.

Legend: ✅ realistic · ⚠️ approximation; state it openly · ❌ not realistic or internally inconsistent; fix it

---

## Part I: Opponent learning

| # | Element of the plan | Check | Why |
|---|---|---|---|
| I-1 | Physics, SOC dynamics, wind-only charging, pro-rata realization | ✅ | Same as the Workshop 1 code (`realize.py`); calibrated to Anchor. |
| I-2 | Observation: **lagged owner-level exports** of rivals | ❌ / ⚠️ | ERCOT publishes resource-level SCED/COP data with a **60-day** delay (NP3-965, COP snapshot). A rival's output is visible within the day only if a shared-facility agreement says so. Present it as a contract design, not as current practice. |
| I-3 | Observation: **noisy rival SOC telemetry** | ❌ | ESR SOC goes to ERCOT/QSE as confidential telemetry. No mechanism gives it to a competitor. The "SOC-assisted" treatment has no real counterpart unless we design one. |
| I-4 | Observation: **public wind forecasts** | ⚠️ | Only system and regional STWPF/WGRPP are public (NP4-732/742). Resource-level COP HSL is 60-day lagged. Also, Anchor units have 0.94 availability correlation, so **own wind already predicts rival wind**. The hidden part is SOC and policy, not wind. |
| I-5 | "Accepted aggregate export is censored at a binding POI" | ⚠️ (understates what the owner knows) | Under the existing pro-rata rule, an owner sees **its own cut**. With $q\ge0$, cut$_i/q_i = 1-K/Q$, so the owner learns the **uncensored total request $Q$** in every binding hour (Simplified Proposal §4.4a makes the same point). The realistic "aggregate" treatment is close to one-hour-lagged full aggregate information. |
| I-6 | Owner-level vs aggregate learning as separate treatments | ⚠️ | Workshop 1 found FULL = aggregate **exactly**, because the payoff depends only on aggregates (README §6). Owner-level data can only help predict the aggregate. Expect a near-zero difference and say why in advance. |
| I-7 | Objective: $\pi\widetilde q - g\widetilde d - \lambda^{ov} w V$ | ❌ (double count) | The plan prices **accepted** export (which already includes the pro-rata loss) **and** charges attempted overflow. The current code uses **planned** revenue + overflow charge. Pick one. The realistic choice is accepted export with **no** overflow charge: no ERCOT fee exists (DEVIATIONS #4), and the real cost of misprediction is curtailed wind that could have been stored. |
| I-8 | Size of the effect | ⚠️ | Upper bound from Workshop 1 (perfect foresight): FULL − NONE ≈ $1,786/day of ~$61,800 (≈2.9%). Planner − FULL ≈ $150/day (0.24%). NONE is a strawman (zero rivals). A persistence predictor will likely close most of the gap, so learning over persistence may be worth well under 1%. That is a valid result, but plan the story around it rather than discover it on Dec 8. |
| I-9 | Particle filter + policy library, 30/10/20 day split | ⚠️ | Feasible, but 30 days of one season is a small training set, and all rivals in our code run the same LP optimizer, so the "policy types" are invented heterogeneity. Fine as a design; state it. |
| I-10 | Typo | - | "public asts" → "public forecasts". |

## Part II: One operator and one monitor

| # | Element of the plan | Check | Why |
|---|---|---|---|
| II-1 | Obligation $B_t=R_t$, $g_t\ge B_t$ (all reported wind must be exported) | ❌ **logic error** | It implies $c_t+r_t\le f_t=W_t-R_t$. Under truthful reporting $f_t=0$, so **$c_t=r_t=0$**. The compliant operator can never charge (grid charging is off) and can **never curtail, even at negative prices**. Storage is useful only through the violation, so the comparison favours violating by construction. In our window, 38% of congested hours had negative RT prices. |
| II-2 | "False wind derating at low prices to charge the battery" as a violation | ❌ | In ERCOT a wind resource and a co-located ESR are separate resources. Charging the ESR from on-site wind is allowed and dispatched through the ESR's bids. Wind can be curtailed **legally** through its offer curve, and IRRs are largely exempt from base-point deviation charges (Protocols §6.6.5). An owner who wants to store cheap wind does not need to lie. HSL under-reporting also lowers the WGR's own output; it does not free wind for charging. Real reasons to misreport availability are (a) **over-reporting** to get a bigger share or curtailment compensation (PPA deemed energy, redispatch) and (b) physical withholding with market power, which is not possible with exogenous prices. (a) is our Nov 20 game. |
| II-3 | High-price **SOC reserve-floor violation** | ✅ / ⚠️ | Real: since RTC+B (Dec 2025), ERCOT ESRs that carry AS awards must hold SOC to cover them, and failure-to-provide has consequences. But the plan omits the **AS capacity payment** that creates the floor. Without it, the floor is a free constraint with no reason to exist. |
| II-4 | Monitor investigates SOC with false positives/misses | ❌ / ⚠️ | ERCOT receives SOC telemetry every few seconds. A floor violation is visible almost immediately; no investigation is needed. To keep an inspection problem, the violation must be **falsified telemetry** (reported SOC ≠ true SOC) or **AS deliverability**, with the monitor checking records. |
| II-5 | Per-period investigation with budget $L^{audit}=1$ | ⚠️ timing | If the operator sees whether the low-price period was investigated, it knows the budget is spent and violates freely in the high period (end-game unraveling). Real IMM/PUCT reviews happen days to months **after** the fact. Make audits ex post (after the day) and committed, as in the Nov 20 proposal §4.7. |
| II-6 | Flat fines $\bar F_W,\bar F_S$ | ⚠️ | With a flat fine, once the operator violates it violates as much as it can (no marginal deterrence). Real penalties and our Nov 20 rule use **per-MWh** fines. Becker / Prop. 13 in `main.pdf` cover this. |
| II-7 | Who the monitor is | ⚠️ | Potomac Economics (ERCOT IMM) investigates and refers. Penalties come from the PUCT. The IMM focuses on market power, not on a price-taking 262 MW site. A contract auditor or the QSE is a better-motivated monitor (setup_step_by_step M1). |
| II-8 | Nonbinding POI | ⚠️ scope | Part II drops the shared connection, which is the project's premise. It becomes a single-plant compliance problem. |
| II-9 | $G_W(x)=[\eta_c\eta_d(\pi_H-g)-\pi_L]x$ | ✅ | Algebra is correct. |

## Fit with the Nov 20 decisions and the Workshop 2 deliverable

| Item | Nov 20 package (ours) | Teammate plan |
|---|---|---|
| Central game | Reports + pro-rata + committed checker (Decision Log row 1) | No reports in Part I; Part II has under-reporting, not over-reporting |
| Battery | Fixed rule, then strategic battery as task 1 | Strategic battery in both parts |
| Learning | EXP3 owners, then learning checker | Particle-filter opponent model |
| Resilient designs (deliverable item f) | R0–R6 rule comparison + stress | Only the overflow-share rule and sensitivity runs |
| Results already in hand | Equilibrium tables, EXP3 curves, stress figure | None yet for either branch |

The Workshop deliverable asks for learning/adaptation, attacks and defenses, and resilient designs. The Nov 20 package covers all three with results already computed. The teammate plan covers the first two and only weakly covers designs. With 17 days left, two new branches plus a 24-hour extension is a lot of scope.

## Recommendations

1. **Keep the reporting + inspection game as the core.** It is the setting where misreporting is real (HSL over-reporting under a report-based share). Our Nov 20 results already exist.
2. **Use Part I as the learning component, made realistic.** Owners learn from their own cut (which reveals $Q$) and from public regional forecasts. Drop rival SOC telemetry, or label it a contract design. Use accepted-export revenue and no overflow charge. Report the ≈3% ceiling up front.
3. **Rewrite Part II or fold it into the main game.**
   - Low-price violation: replace "false derating to charge" with over-reporting availability, which is what the Nov 20 game already models. Or, if a delivery obligation is wanted, it must allow economic curtailment and charging under compliance. Otherwise there is no compliant use of the battery.
   - High-price violation: keep the SOC-floor idea, but add the AS award and payment that create the floor. Make the violation falsified SOC/deliverability, not a telemetered floor breach.
   - Audits ex post, committed, with per-MWh fines.
4. **Sync the repo.** The local `origin/main` is 15 commits behind (SSH fetch fails here; `gh`/HTTPS works). Pull before editing `docs/`.

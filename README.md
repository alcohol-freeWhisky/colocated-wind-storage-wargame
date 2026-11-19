# Shared Wind–Storage Wargame

This repository compares centralized and decentralized operation of wind–battery resources sharing a point of interconnection (POI). The experiment varies foresight, overflow-charge allocation, and access to other owners' planned injections. It measures their effects on realized operating value, curtailment, battery use, and attempted POI overflow.

## 1. Setting and assumptions

| Item | Base case |
|---|---|
| Resources | Five Anchor Wind units, each modeled as a separate wind–battery owner |
| Operating window | March 1–April 30, 2025 |
| Episodes | 60 complete 24-hour days; the daylight-saving transition day is excluded |
| Resolution | Hourly |
| Dispatch | Reoptimize over the remaining day and execute the first hour |
| Cases | 14 cases per day; 840 day–case observations |
| Prices | Exogenous ERCOT HB_WEST day-ahead and real-time prices |
| Evaluation | Realized energy revenue less battery discharge degradation |

**Assumption 1 (Operating environment).** Owners take prices as given, wind availability is nonnegative, and $K>0$. Battery power and energy capacities are finite, $0<\eta_c,\eta_d\le1$, and the initial SOC lies within battery bounds. Separate ownership and the shared export limit are experimental assumptions. The model does not reproduce the site's actual ownership, ERCOT dispatch, or market settlement. Each day starts from the same prescribed battery state of charge; storage and information do not carry across days.

## 2. Inputs and notation

Time steps have duration $\Delta t=1$ hour. The equations below omit this factor.

| Symbol | Code field | Definition |
|---|---|---|
| $i=1,\ldots,N$ | `primary_agents` | Owner index; $N=5$ |
| $t=0,\ldots,23$ | `horizon_h` | Hour within an operating day |
| $W_{it}$ | `W_avail` | Realized available wind, from hourly SCED HSL (MW) |
| $\widehat W_{it}$ | `What_cop` | Wind availability forecast, from COP HSL (MW) |
| $\pi_t^{RT}$ | `pi_RT` | Real-time price ($/MWh) |
| $\pi_t^{DA}$ | `pi_DA` | Day-ahead price ($/MWh) |
| $b_{it}^{DAM}$ | `b_dam` | Disclosed day-ahead energy award; retained for provenance only |
| $N_i$ | `nameplate` | Calibrated wind nameplate capacity (MW) |
| $c_{it},d_{it},r_{it}$ | `c`, `d`, `r` | Planned charging, discharging, and wind curtailment (MW) |
| $s_{it}$ | `soc` | Battery state of charge (MWh) |
| $q_{it}$ | planned `q` | Requested net export (MW) |
| $\widetilde q_{it},\widetilde d_{it}$ | realized `q`, `d` | Executed export and discharge (MW) |

SCED HSL is used as available wind, rather than metered generation. DAM awards impose no minimum-delivery obligation. COP HSL supplies the wind forecast; it is not substituted for DAM awards.

### Base parameters

| Parameter | Value |
|---|---|
| Battery power | $P_i=0.29N_i$ |
| Battery energy capacity | $E_i=1.5P_i$ |
| Charge and discharge efficiencies | $\eta_c=\eta_d=0.922$ |
| Initial SOC | $s_{i0}=0.5E_i$ |
| Discharge degradation cost | $g_i=10$ $/MWh |
| Shared export limit | $K=0.6\sum_iN_i$ |
| Attempted-overflow charge | $\lambda=100$ $/MWh |
| Activity tie-break cost | $\epsilon=10^{-3}$ $/MWh |
| Charging source | Wind only |

Battery sizing is calibrated to observed co-located storage. The POI ratio and overflow charge are design parameters. Parameter sources are documented in [ASSUMPTIONS.md](docs/ASSUMPTIONS.md); executable settings are in [base.yaml](config/base.yaml).

## 3. Feasible dispatch

**Definition 1 (Owner feasibility).** At a fixed information view and initial SOC, the feasible set $\mathcal A_i$ consists of charging, discharging, curtailment, and SOC trajectories satisfying

$$
q_{it}=W_{it}-r_{it}-c_{it}+d_{it},
$$

$$
0\le c_{it}\le P_i,\qquad 0\le d_{it}\le P_i,\qquad
r_{it}\ge0,\qquad c_{it}+r_{it}\le W_{it},
$$

$$
s_{i,t+1}=s_{it}+\eta_c c_{it}-\frac{d_{it}}{\eta_d},
\qquad 0\le s_{it}\le E_i.
$$

**Lemma 1 (Nonnegative requested export).** Every feasible wind-only dispatch satisfies $q_{it}\ge0$.

*Proof.* The charging constraint gives $W_{it}-r_{it}-c_{it}\ge0$. Adding $d_{it}\ge0$ proves the claim. $\square$

**Definition 2 (Terminal target).** The nominal terminal constraint is $s_{i,24}\ge s_{i0}$. At replanning hour $h$, the target is reduced if the original target cannot be reached using the wind available in the current information view:

$$
s_i^{target}(h)=\min\left(s_{i0},\ s_{ih}+\eta_c\sum_{t=h}^{23}\min(P_i,W_{it}^{view})\right).
$$

**Lemma 2 (Feasibility of the terminal target).** In exact arithmetic, the target above can be attained or exceeded within the owner's physical constraints, with no discharge and no grid charging.

*Proof.* With no discharge, the maximum attainable final SOC is

$$
s_i^{max}(h)=\min\left(E_i,\ s_{ih}+\eta_c\sum_{t=h}^{23}\min(P_i,W_{it}^{view})\right).
$$

Charging up to the power and wind limits until the battery is full attains this value. Since $s_{i0}\le E_i$, the prescribed target does not exceed $s_i^{max}(h)$. Charging absorbs wind and remaining wind can be curtailed, so this construction also respects any positive export limit. $\square$

Both centralized and decentralized cases use this target. The lemma establishes feasibility of the revised target, not restoration of the original initial SOC in every forecast episode.

The optimization problems use continuous variables. A small activity cost and a cycle-removal transformation address simultaneous charging and discharging; formal runs also check the resulting plans and executed dispatches.

## 4. Decision models

Let $\mathcal T_h=\lbrace h,\ldots,23\rbrace$ denote the remaining operating horizon.

### Definition 3. Centralized planning problem

The planner jointly chooses all owners' dispatches:

$$
\max\sum_{t\in\mathcal T_h}\sum_i
\left[\pi_t^{view}q_{it}-g_id_{it}
-\epsilon(c_{it}+d_{it}+r_{it})\right],
$$

subject to the physical constraints and a hard POI limit:

$$
\sum_iq_{it}\le K\qquad\forall t\in\mathcal T_h.
$$

### Definition 4. Decentralized planning game

Each owner chooses its own dispatch, taking the available rival-injection signal as given:

$$
\max U_i=\sum_{t\in\mathcal T_h}
\left[\pi_t^{view}q_{it}-g_id_{it}
-\lambda w_{it}V_t
-\epsilon(c_{it}+d_{it}+r_{it})\right],
$$

where

$$
V_t=\left[\sum_jq_{jt}-K\right]_+.
$$

Owners have no individual POI quota and no hard aggregate export constraint in their planning problems. The charge discourages attempted overflow.

| Allocation | Weight $w_{it}$ |
|---|---|
| Equal (`EQ`) | $1/N$ |
| Injection-based (`INJ`) | $q_{it}^{+}/\sum_jq_{jt}^{+}$; equal fallback when the denominator is zero |

**Lemma 3 (Allocation of the aggregate charge).** At any common dispatch profile, either rule allocates exactly the aggregate attempted-overflow charge:

$$
\sum_i\lambda w_{it}V_t=\lambda V_t.
$$

*Proof.* Equal weights sum to one. Injection-based weights sum to one whenever total positive injection is nonzero; the equal fallback also sums to one. Multiplication by $\lambda V_t$ gives the identity. $\square$

This identity compares allocations at a fixed profile. It does not imply that the two games produce the same dispatch or total charge. The injection-based best response accounts for the dependence of the owner's share on its own decision. The code calls this rule “causal”; its precise definition is the positive-injection share above.

Owner objectives use **planned** energy revenue. They do not incorporate the physical export-reduction map below into their revenue calculation. The experiment therefore evaluates this planning incentive together with the specified realization rule.

## 5. Realization map and export feasibility

**Definition 5 (Realization map).** The realization layer checks battery bounds and enforces the shared export limit. If total requested export $Q_t$ exceeds $K$, each owner's assigned reduction is

$$
\Delta q_{it}=(Q_t-K)\frac{q_{it}^{+}}{\sum_jq_{jt}^{+}}.
$$

With nonnegative injections, this gives proportional export acceptance:

$$
\widetilde q_{it}=q_{it}\min\lbrace 1,K/Q_t\rbrace\qquad(Q_t>0).
$$

Within each owner's assigned reduction, the implementation proceeds as follows:

| Order | Adjustment |
|---|---|
| 1 | Increase wind curtailment |
| 2 | Reduce battery discharge, retaining the unexecuted energy subject to battery headroom |
| 3 | Record any remaining reduction as inverter-side dissipation (`spill`) |

**Theorem 1 (Feasibility of realized aggregate export).** Suppose the requests entering the reduction step are nonnegative and each assigned reduction is executed through curtailment, reduced discharge, or spill. In exact arithmetic,

$$
0\le\sum_i\widetilde q_{it}=\min(Q_t,K)\le K.
$$

*Proof.* If $Q_t\le K$, no reduction is required. If $Q_t>K$, Lemma 1 gives $\sum_iq_{it}^{+}=Q_t$. The assigned reductions sum to $Q_t-K$, and each reduction is at most its owner's request. Subtracting them leaves total export $K$ and preserves nonnegativity. $\square$

The implementation applies this identity after battery-bound adjustments and checks the aggregate limit with numerical tolerances. Wind export and battery discharge are not independently scaled by a common factor. The next optimization starts from the executed SOC.

## 6. Experimental design

| Factor | Levels | Comparison |
|---|---|---|
| Control | `C`, `D` | Joint planner versus independent owners |
| Foresight | `P`, `F` | Realized future inputs versus forecast future inputs |
| Charge allocation | `INJ`, `EQ` | Injection-based versus equal shares |
| Rival information | `FULL`, `PRICE`, `NONE` | Owner plans, aggregate signal, or zero-rival assumption |

The 14 cases are

$$
\lbrace C_P,C_F\rbrace \cup
\lbrace D_{f,a,m}:f\in\lbrace P,F\rbrace,\ a\in\lbrace INJ,EQ\rbrace,\ m\in\lbrace FULL,PRICE,NONE\rbrace\rbrace.
$$

Allocation and rival-information levels apply only to decentralized cases.

### Foresight

| Level | Current hour | Remaining future hours |
|---|---|---|
| Perfect (`P`) | Realized wind and RT price | Realized wind and RT price |
| Forecast (`F`) | Realized wind and RT price | COP wind and DA price |

Forecast cases assume knowledge of current-hour wind and RT price. DA price is a proxy for future RT price, rather than a separate settlement leg. COP forecasts are read from the input data; the simulation does not train a forecasting model.

### Rival information

| Level | Inputs to the best-response problem |
|---|---|
| `FULL` | Rival plans reduced to aggregate net injection and aggregate positive injection |
| `PRICE` | The same two aggregate quantities, without owner-level identities |
| `NONE` | Both rival quantities set to zero |

`PRICE` is a historical case identifier for **aggregate information**, not a congestion price.

**Theorem 2 (Sufficiency of aggregate rival injections).** Fix an owner's wind and price view, initial and terminal SOC, allocation rule, and rival profile. Its feasible set and payoff depend on rivals only through

$$
R_{it}=\sum_{j\ne i}q_{jt},\qquad
R_{it}^{+}=\sum_{j\ne i}q_{jt}^{+}.
$$

Consequently, FULL and aggregate information define the same best-response problem and the same best-response correspondence.

*Proof.* Rivals do not enter the owner's battery or wind constraints. They enter attempted overflow through $[q_{it}+R_{it}-K]_+$ and the injection-based share through $q_{it}^{+}/(q_{it}^{+}+R_{it}^{+})$. Equal sharing requires only $R_{it}$. No other rival quantity appears in the objective. Thus two rival profiles with the same aggregate signals yield identical optimization problems. $\square$

**Corollary 2.1 (Matched update paths).** Given identical initialization, owner order, damping, stopping rules, and best-response selection, FULL and aggregate cases have identical update paths in exact arithmetic.

*Proof.* Their first best-response problems coincide by Theorem 2. The selected solutions and damped updates therefore coincide. Induction over owner updates and sweeps proves the claim. $\square$

The selection qualification matters when best responses are nonunique. The completed numerical run reports zero differences between the two information cases.

NONE represents a zero-rival planning assumption. It is not a Bayesian game with unknown capacities.

## 7. Solution and acceptance criteria

At each hour, the simulation constructs the remaining-horizon information view, solves the planning problem, executes the first hour, and updates SOC.

| Setting | Value or method |
|---|---|
| Centralized problem | Joint continuous optimization |
| Equal-share best response | Continuous linear optimization |
| Injection-based best response | Convex formulation solved with Clarabel |
| Informed owner updates | Sequential best responses; signal refreshed after each owner update |
| Damping | 0.5 |
| Maximum sweeps | 200 per remaining-horizon game |
| NONE updates | One independent solve per owner |
| Acceptance threshold | Maximum unilateral payoff gain at most $1 |

**Definition 6 (Planning-game deviation gain).** For FULL and PRICE, define the maximum unilateral payoff gain at the returned profile by the left-hand side below. The numerical acceptance rule is

$$
\max_i\left[\max_{a_i'}U_i(a_i',a_{-i})-U_i(a_i,a_{-i})\right]\le1\text{ dollar}.
$$

**Proposition 1 (Interpretation of the acceptance rule).** If the deviation problems are solved globally and the maximum gain is at most one dollar, the returned feasible profile is a one-dollar approximate Nash equilibrium of the remaining-horizon planning game under its current information view.

*Proof.* By definition of the maximum gain, no feasible unilateral deviation improves any owner's planning payoff by more than one dollar. This is precisely the approximate Nash condition. $\square$

Numerical solver error affects the certificate. This proposition is conditional on the returned gain; it does not prove that sequential best responses converge, that the solution is unique, or that the executed policy is an equilibrium of the full stochastic dynamic game.

For NONE, deviation gains are also evaluated against zero rival injection. Its convergence flag certifies the individual perceived problems, not a Nash equilibrium of the actual joint profile. Best-response iteration involves no statistical learning or belief updates.

Formal runs reject failed convergence checks, realized POI overflow, and simultaneous charging/discharging in planned or realized operation. Dispatch residuals are retained as diagnostics; acceptance is based on payoff gains.

## 8. Evaluation and numerical observations

**Definition 7 (Realized system value).** All cases use the same metric:

$$
J=\sum_{t,i}\left[\pi_t^{RT}\widetilde q_{it}-g_i\widetilde d_{it}\right].
$$

Overflow charges are internal incentives and are reported separately. Neither those charges nor the numerical activity cost is deducted from $J$.

**Numerical observation 1 (Mean daily value).** The completed run produced the following averages ($/day, rounded). These are sample results, not general payoff-ordering theorems.

| Foresight | Planner | INJ full | INJ aggregate | INJ none | EQ full | EQ aggregate | EQ none |
|---|---:|---:|---:|---:|---:|---:|---:|
| P | 61,951 | 61,801 | 61,801 | 60,015 | 61,358 | 61,358 | 60,015 |
| F | 58,524 | 58,177 | 58,177 | 56,244 | 57,541 | 57,541 | 56,247 |

**Numerical observation 2 (Matched contrasts).** The same run produced the following daily mean differences.

| Contrast | Interpretation | Mean difference ($/day) |
|---|---|---:|
| $C_P-D_{P,INJ,FULL}$ | Centralized versus decentralized control | 149.47 |
| $C_P-C_F$ | Foresight under centralized control | 3,426.98 |
| $D_{F,INJ,FULL}-D_{F,EQ,FULL}$ | Charge allocation under forecast inputs | 635.42 |
| $D_{F,INJ,FULL}-D_{F,INJ,NONE}$ | Rival signal under forecast inputs | 1,932.53 |
| FULL minus aggregate | Owner identities beyond aggregate inputs | 0 |

The recorded run was generated on November 16, 2026. It contains 60 days and 840 day–case observations, with no failed days. The reported owner convergence-hour fractions are all 1, subject to the interpretation in Section 7. Realized export and simultaneous-operation checks passed. Full results are in the [Workshop 1 report](docs/workshop1/report.md).

Metadata sidecars record creation time, runtime, configuration hash, and the Git HEAD at execution. The recorded HEAD, `981b613`, predates the commit of the revised implementation; that field alone does not identify the uncommitted source used to generate the results.

## 9. Limits of the formal statements

| Component | Status |
|---|---|
| Wind–battery dispatch, SOC, hourly prices and wind forecasts | Included in the operating experiment |
| Shared physical export constraint and overflow-charge allocation | Included |
| Full, aggregate, and zero-rival information cases | Included |
| Detection probabilities, false positives, deterrence fines and sanction duration | Separate monitoring module; no feedback into operating decisions |
| Hidden capacity, strategic capacity reports, report-based allocation | Not implemented |
| Inspection probabilities updated from violation history | Not implemented in the operating experiment |
| Bayesian learning, Q-learning, or learning rival types | Not implemented |
| Demand-based interpretation of $K$ or endogenous market clearing | Not implemented; $K$ is an export limit |
| Minimum-generation obligation or delivery-shortfall penalty | Absent from the operating model |

The lemmas and theorems above concern the defined operating model. No theorem of equilibrium existence, best-response convergence, planner dominance in the reported metric, or superiority of one charge allocation is asserted here.

The monitor's `shortfall` denotes a statistical forecast residual, not proof of misconduct. Its discount and delay parameters belong to separate deterrence calculations. Results from the operating experiment do not validate a capacity-misreporting model or its propositions.

## 10. Repository map

| Component | Source |
|---|---|
| Dataset construction | [`build_dataset.py`](code/wargame/data/build_dataset.py) |
| Centralized solver | [`central.py`](code/wargame/solvers/central.py) |
| Owner objective and constraints | [`agent_lp.py`](code/wargame/solvers/agent_lp.py) |
| Best responses, charge shares, deviation checks | [`game.py`](code/wargame/solvers/game.py) |
| Information views, terminal targets, centralized receding horizon | [`receding.py`](code/wargame/solvers/receding.py) |
| Decentralized receding horizon and case definitions | [`design_matrix.py`](code/wargame/solvers/design_matrix.py) |
| Physical realization | [`realize.py`](code/wargame/solvers/realize.py) |
| Experiment entry point | [`07_design_matrix.py`](code/scripts/07_design_matrix.py) |
| Monitoring entry point | [`05_monitor.py`](code/scripts/05_monitor.py) |

| Output | Location |
|---|---|
| Daily results | `results/tables/design_matrix_by_day.csv` |
| Summary, pivot, and matched contrasts | `results/tables/design_matrix_{summary,pivot,effects}.csv` |
| Representative trajectories | `results/tables/trajectories/`; current representative day: March 29, 2025 |
| Figures | `results/figures/fig_design_*.{png,pdf}` |
| Report | `docs/workshop1/report.{md,html}` |
| Metadata | Corresponding `.meta.json` sidecars |

## 11. Reproduction

Run from the repository root:

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
PYTHONPATH=code .venv/bin/python code/scripts/02_build_dataset.py --config config/base.yaml
PYTHONPATH=code .venv/bin/python code/scripts/07_design_matrix.py --config config/base.yaml --workers 4
PYTHONPATH=code .venv/bin/python code/scripts/06_make_report.py --config config/base.yaml
PYTHONPATH=code .venv/bin/python -m pytest -q
```

Dataset construction requires local raw inputs; the download entry point is `code/scripts/01_download_raw.py`. Report generation reads existing artifacts without rerunning the experiment. Monitoring is run separately through `05_monitor.py`.

Further documentation: [implementation contract](docs/DESIGN.md), [model assumptions](docs/ASSUMPTIONS.md), [deviations from ERCOT practice](docs/DEVIATIONS.md), and [release checklist](docs/PROGRESS.md).

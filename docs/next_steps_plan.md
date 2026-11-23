# Next Steps: Opponent Learning and Strategic Compliance

## 1. Objectives

Extend the current wind–storage simulation along two separate paths, then combine them after each has been validated.

| Track | Question | First deliverable |
|---|---|---|
| A. Opponent learning | Can an owner improve dispatch by estimating rivals' generation, SOC, and operating behavior from limited observations? | A rolling belief-based dispatch policy evaluated against fixed opponents |
| B. Monitoring and compliance | How do dispatch obligations, reserve requirements, and limited investigations change reporting and battery operation? | Three operators, explicit violations, and a budget-constrained monitor |
| C. Combined experiment | Does learning change noncompliance and the value of monitoring? | Selected combinations of validated A and B policies |

The existing 14-case experiment remains a separate baseline. These extensions require new decision and observation models; they are not additional labels for the existing FULL, aggregate, and NONE cases.

This document specifies proposed work. It does not report completed implementation or new simulation results.

## 2. What carries over

| Existing component | Reuse | Required change |
|---|---|---|
| Wind, COP, DA and RT data | Same inputs and operating days | Explicit observation timestamps and chronological train/test split |
| Battery dynamics and wind-only charging | Same physical equations | Add reserve requirement in Track B |
| Shared POI | Same physical limit | Rename conceptually to $K^{POI}$; use a different symbol for investigation capacity |
| Hourly receding horizon | Same execute-first-hour loop | Per-owner information views and belief updates |
| Owner solver | Reuse constraints and solver infrastructure | Scenario-dependent objectives; reporting and reserve variables |
| Realization layer | Reuse physical safeguards | Preserve requested and accepted injections; log ISO-directed reductions |
| Overflow allocation | Retain EQ and INJ as controlled treatments | Keep overflow charges separate from enforcement fines |
| Monitor statistics | Reuse residual calibration and ROC utilities where justified | Add investigation selection, evidence, sanctions, and operator feedback |
| Result tables and metadata | Reuse output conventions | Add belief, violation, investigation, and enforcement records |

For the new tracks, optimize the same realized revenue used for evaluation. The current owner objective uses requested export before physical reduction. Retain that objective only as a named legacy benchmark; changing it silently would confound the effect of learning.

## 3. Common operating model

Use $T=24$, one-hour steps, and the existing constraints:

$$
g_{it}=W_{it}-c_{it}-r_{it},\qquad q_{it}=g_{it}+d_{it},
$$

$$
0\le c_{it},d_{it}\le P_i,\quad r_{it}\ge0,\quad c_{it}+r_{it}\le W_{it},
$$

$$
s_{i,t+1}=s_{it}+\eta_c c_{it}-d_{it}/\eta_d,\qquad 0\le s_{it}\le E_i.
$$

Let the realization map produce accepted export $\widetilde q_{it}$, executed discharge $\widetilde d_{it}$, and actual next SOC. For each new policy, distinguish:

$$
M_i=\sum_t(\pi_t\widetilde q_{it}-g_i^{deg}\widetilde d_{it}),
$$

$$
U_i=M_i-C_i^{overflow}-F_i.
$$

Here $M_i$ is operating margin, $C_i^{overflow}$ is the internal attempted-overflow charge, and $F_i$ is enforcement cost. Record all three separately. System operating value is $\sum_iM_i$; fines are transfers, not destroyed energy value. Investigation costs and external reserve-shortfall costs enter a separate social-cost measure.

The proportional realization map introduces nonlinear, piecewise behavior into the owner problem. The existing LP is therefore not an exact solver for this new objective. Start with a small discrete action library and exact enumeration of feasible candidate actions, followed by continuous refinement only if needed.

## 4. Track A: Learning under imperfect information

### 4.1 Private state and decision timing

Each owner knows its own SOC and available wind. In the first learning experiment, it also knows its own remaining-day wind and prices perfectly. Only rival information is imperfect. Introduce own-wind and price forecast errors later as a separate factor.

For owner $i$, rival $j$ has hidden state

$$
x_{jt}=(s_{jt},W_{jt},\theta_j),
$$

where $\theta_j$ describes operating behavior, such as the weight placed on congestion risk or the propensity to charge at low prices. A policy is a mapping from available information to an action; SOC is a state, not a strategy.

| Time | Simulator action | Information available to owner $i$ |
|---|---|---|
| Before hour $t$ | Publish exogenous prices, forecasts and allowed signals | Own state, permitted forecasts, observations through $t-1$ |
| Decision | Owners independently select plans | Their own information only |
| Execution | Apply POI realization | No learning from another owner's unexecuted current action |
| After execution | Publish permitted metering | Update beliefs for the next hour |

Use simultaneous actions within an operating hour. Any numerical inner iterations must not reveal rivals' private states or contemporaneous plans. The existing sequential FULL-information best-response loop is a benchmark, not the learning protocol.

### 4.2 Observation treatments

| ID | Observable rival information | Purpose |
|---|---|---|
| A0 | Zero rival signal | Existing NONE-style planning benchmark |
| A1 | Historical mean or persistence prediction | Nonlearning forecast benchmark |
| A2 | Lagged aggregate accepted export and public wind forecasts | Minimal practical learning case |
| A3 | Lagged owner-level accepted export and public wind forecasts | Test the value of attribution |
| A4 | A3 plus noisy, delayed SOC telemetry | Test the value of storage-state information |
| AO | True rival state and a specified rival policy | Oracle state benchmark |

AO is not the same as the existing FULL case, which receives rival plans. Keep state-oracle and plan-oracle results separate.

At a binding POI, aggregate accepted export equals the cap and does not identify requested export. Treat such observations as censored. Never use simulator-private requested export, true rival wind, or true SOC as training labels unless the treatment explicitly reveals them. Individual SOC is generally not identifiable from aggregate export alone; evaluate predictive distributions and aggregate forecasts rather than claiming exact state recovery.

### 4.3 Belief model

Maintain a distribution over rival SOC, wind, and policy parameters:

$$
b_{it}(x_{-i,t})=P(x_{-i,t}\mid\mathcal H_{it}).
$$

A filtering update has the form

$$
b_{i,t+1}(x')\propto p(y_{t+1}\mid x')
\int p(x'\mid x)b_{it}(x)\,dx.
$$

The transition integrates over unobserved rival actions under the assumed policy family. The observation likelihood must include the POI realization map, metering noise, and censoring.

Implementation order:

1. Fit a persistence and regularized linear model for aggregate rival export using hour, public wind forecasts, prices and lagged accepted export. Train on past observations only.
2. Add a particle filter with bounded SOC and a small library of rival policies. Update policy weights from observation likelihoods; retain uncertainty when several states explain the same measurement.
3. Use explicit SOC telemetry only in A4. Compare its improvement over inference without telemetry.
4. Consider recurrent models or reinforcement learning only after the simpler models pass out-of-sample checks.

### 4.4 Dispatch using learned beliefs

At hour $t$, sample $M$ rival trajectories from the belief and solve

$$
\max_{a_i}\frac1M\sum_{m=1}^M
\left[M_i(a_i,a_{-i}^{(m)})-C_i^{overflow}(a_i,a_{-i}^{(m)})\right].
$$

The current action must be identical across scenarios. Future actions may depend only on observations available at the relevant future node; independent scenario-wise dispatch with future state knowledge would leak information. The first implementation can use a common open-loop remainder-of-day schedule and replan hourly.

Start with 8–16 scenarios and a documented candidate-action library: charge, hold, discharge, and curtail at several feasible power levels. Use a two-hour discrete model first to validate the optimizer against exhaustive enumeration. On the 24-hour model, use receding-horizon rollouts over candidate policy parameters; report discretization and planning approximation explicitly.

Learning can predict high rival output and induce charging or reduced export. This is a hypothesis to test, not an imposed response: high prices, battery limits, and the allocation rule can make a different action optimal.

### 4.5 Learning experiments

| Stage | Opponents | Evaluation |
|---|---|---|
| A-I | Fixed, known policy family; hidden states | Isolate state estimation and information value |
| A-II | Fixed policy parameters unknown to learner | Test opponent-policy identification |
| A-III | All owners adapt | Study nonstationarity and joint outcomes |

Start A-I with three owners, then repeat with the existing five-owner site. Select the three resources explicitly in configuration and recompute battery parameters and $K^{POI}$ for that subset. Never compare the three-owner results directly against the five-owner baseline as if only learning changed.

Use chronological splits of the 60 complete days: first 30 training, next 10 validation, last 20 test. Reset physical SOC daily; carry learned parameters across days. Reset latent-state filters to their prescribed daily prior. Freeze hyperparameters before testing. Report both frozen-model testing and a separately labeled online-update test using only past test observations.

**Acceptance criteria**

- A timestamp audit shows no future or hidden-state leakage.
- Predictive RMSE, interval coverage and calibration are reported against persistence on held-out days.
- Requested-export prediction is scored only where ground truth is allowed for evaluation; private truth may be used by the evaluator, never by the policy.
- All actions satisfy battery and POI checks.
- Paired daily margin differences, overflow changes and uncertainty intervals are reported, including negative findings.
- Adaptive runs report empirical unilateral policy deviations or exploitability estimates; training stability alone is not an equilibrium certificate.

## 5. Track B: Reports, reserve obligations and a monitor

### 5.1 Resolve the dispatch contract first

The proposed rule $B_{it}=\widetilde W_{it}$ is incomplete when connected to storage and a shared POI:

- If truthful reporting requires exporting all available wind, ordinary wind charging becomes noncompliance unless explicitly authorized.
- If reported availability never affects obligations or settlement, underreporting has no operating benefit and is a redundant decision.
- A report is not a physical energy bound: charging must remain bounded by true wind.
- $K^{POI}$ is an export limit; investigation capacity is a separate quantity $L_t^{audit}$.

Use an explicit contractual baseline. Let $A_{it}$ be an exogenous, preauthorized wind-retention allowance (MW), identical across compliance treatments. Owners report $R_{it}$ with

$$
0\le R_{it}\le W_{it},\qquad f_{it}=W_{it}-R_{it}.
$$

Define eligible wind export and assigned responsibility by

$$
e_{it}=[R_{it}-A_{it}]_+,\qquad
B_{it}=e_{it}\min\left(1,\frac{K^{POI}}{\sum_je_{jt}}\right).
$$

Set $B_{it}=0$ when total eligibility is zero. Require planned wind export $g_{it}\ge B_{it}$. This separates the wind responsibility from battery export $d_{it}$. Dispatch assignments always sum to at most the physical export limit.

With a nonbinding POI and $R_{it}\ge A_{it}$, the constraint becomes

$$
c_{it}+r_{it}\le A_{it}+f_{it}.
$$

Thus underreporting can relax a real restriction on wind retention. Whether it increases profit depends on intertemporal prices, efficiency, congestion and enforcement. Its gain comes from the specified contract, not from storage physics alone.

Use $A_{it}=0$ as the strict must-offer case and a positive allowance as a sensitivity. Label both as designed contracts, not ERCOT rules. Preserve the current unrestricted truthful operating model as a separate economic benchmark. If unrestricted truthful charging is the intended institution, remove this false-derate mechanism or replace it with another explicit reporting-dependent settlement rule.

The dispatch contract applies before realization. Record ISO-directed wind cuts $x_{it}^{ISO}$ separately and excuse them from the obligation:

$$
\widetilde g_{it}\ge[B_{it}-x_{it}^{ISO}]_+.
$$

Otherwise the physical POI controller could create apparent noncompliance. Hold other reports fixed when calculating deviations, but recompute dispatch assignments because an owner's report changes other owners' responsibilities.

### 5.2 Reserve requirement

Use $S_{it}^{req}$ for the minimum SOC and assess violations at the end of each operating interval:

$$
v_{it}=[S_{i,t+1}^{req}-s_{i,t+1}]_+.
$$

Physical SOC bounds remain hard. The reserve requirement is an operational obligation:

| Treatment | Reporting | Reserve requirement |
|---|---|---|
| Compliant | $R_{it}=W_{it}$ | $s_{i,t+1}\ge S_{i,t+1}^{req}$ |
| Wind violation only | $R_{it}\le W_{it}$ | Hard reserve floor |
| SOC violation only | Truthful report | Reserve violation permitted and penalized if sanctioned |
| Both violations | Underreporting permitted | Reserve violation permitted |

Start with a constant reserve floor below the initial SOC, such as $0.2E_i$, and validate a feasible compliant schedule. Treat alternative floors as design sensitivities. Do not apply the current terminal-target relaxation to the reserve requirement: infeasible contractual cases must be rejected or assigned an explicit emergency exception. The existing terminal-return target remains a separate constraint and diagnostic.

### 5.3 Monitor observations and decisions

At the end of hour $t$, publish an observation vector containing reports, assignments, accepted export, prices, a weather-based wind estimate, and any permitted SOC telemetry. The simulator retains true wind and SOC privately for enforcement outcomes and evaluation.

Useful suspicion signals are

$$
z_{it}^{W}=W_{it}^{weather}-R_{it},\qquad
z_{it}^{S}=S_{i,t+1}^{req}-s_{i,t+1}^{telemetry}.
$$

A noisy weather residual is evidence, not a violation label. Initially use authenticated SOC telemetry. If SOC is observed exactly, a reserve deficit is already known; the investigation then verifies enforceable evidence rather than discovering the deficit. Strategic SOC reporting would require another action and evidence model and is deferred.

The monitor selects

$$
a_{it}\in\lbrace0,1\rbrace,\qquad\sum_i a_{it}\le L_t^{audit}.
$$

One investigation checks both violation types. Specify independent type-specific evidence errors initially; test correlated errors later.

### 5.4 Screening, investigation and sanction

Keep three events distinct: a screening flag, an investigation, and a sanction after evidence.

For type $k\in\lbrace W,S\rbrace$, let $Y_{it}^k$ indicate an adverse investigative finding and $D_{it}^k$ indicate a true violation above a fixed numerical tolerance. Define

$$
\alpha_k=P(Y^k=1\mid D^k=0,a=1),\qquad
\beta_k=P(Y^k=1\mid D^k=1,a=1).
$$

Perfect investigation uses $\alpha_k=0$, $\beta_k=1$; screening may still be noisy. Imperfect investigation varies the evidence model separately from screening noise.

Start with fixed financial consequences per adverse finding:

$$
F_i=\sum_{t,k}a_{it}Y_{it}^k\overline F_k.
$$

With fixed fines, both wrongful sanctions and missed violations are well defined. Severity-dependent fines require an explicit audited severity estimate; do not multiply a false-positive indicator by simulator-known true severity, which would force wrongful fines to zero.

Use immediate enforcement and no discounting initially. Add delayed evidence, appeals or discounting only as separately specified extensions.

### 5.5 Monitor policy

The operator objective becomes

$$
\max\mathbb E[U_i]
=\mathbb E[M_i-C_i^{overflow}-F_i].
$$

For the monitor, use

$$
\min\mathbb E\sum_{t,i}
\left[c_a a_{it}
+c_{FP}\sum_k(1-D_{it}^k)a_{it}Y_{it}^k
+c_{miss}\sum_kD_{it}^k(1-a_{it}Y_{it}^k)\right].
$$

The monitor optimizes conditional expectations from its information, not from true $D$. Distinguish missed-violation loss from actual external reserve or congestion harm in reporting.

Begin with four policies:

| Policy | Selection rule |
|---|---|
| No audit | No investigation |
| Random | Uniform sampling without replacement up to capacity |
| Risk based | Investigate the largest positive conditional expected loss reductions, up to capacity |
| Oracle evaluator | Select using private truth; an unattainable diagnostic bound |

Risk-based selection is optimal only for the one-period additive monitor objective with fixed beliefs, equal investigation resource use, and no effect on future behavior. Do not call it an optimal dynamic monitoring policy.

Reserve a small random audit component when learning violation probabilities. Log each selection probability; otherwise outcomes observed only for suspicious operators create selective-label bias. Initially calibrate on a declared synthetic reporting-policy population, then evaluate sensitivity to misspecified priors.

### 5.6 Game timing and solution concept

Use a committed monitoring policy for the first experiment:

1. Specify the contract, fine schedule, reserve requirements, and publicly known monitor policy.
2. Owners observe private operating information and choose reports and dispatch actions simultaneously.
3. Compute assignments from reports, enforce planning obligations, and realize physical operation.
4. Generate monitor signals, select investigations, obtain evidence, and levy sanctions.
5. Update states and permitted histories before the next hour.

Operators anticipate the signal-dependent probability of investigation, not its realized random draw. The monitor cannot use true violations before investigation. Monitor budget and realized actions must be simulated jointly; independent audit probabilities must not allow realized capacity overruns.

A fixed-policy experiment evaluates operator responses to a committed enforcement rule. A later search over monitor-policy parameters is a restricted leader–follower problem. Simultaneous adaptation of all policies is a further experiment, not automatically a solved Stackelberg or perfect Bayesian equilibrium.

For a first solvable instance, use three owners and two hours, a small reporting grid, and a small feasible dispatch library. Enumerate joint actions, monitor observations, and audit choices. Compute best responses and deviation gains directly. Then extend to 24-hour receding-horizon policy rollouts with common random numbers. Report approximate deviation gains over the searched policy class and all failures to converge.

Do not reuse the existing `F_star` formula as the enforcement condition. It includes gain-recovery and timing assumptions that differ from this fixed-fine game. With a fixed violation gain $G$ and matched compliant/deviating alternatives, a new one-shot check is

$$
G\le\mathbb E[F\mid\text{deviation}]-\mathbb E[F\mid\text{compliance}].
$$

Both audit-selection probabilities and evidence distributions may change with the report. Derive expectations under the specified observation and audit model.

## 6. Experiments and outputs

### Learning experiments

Hold physical parameters, objective, rival policies and seeds fixed when changing information or predictors. Run A0, A1, A2 and AO first; add A3 and A4 after the aggregate case is validated. Compare fixed and adaptive opponents separately.

### Enforcement experiments

| Factor | Initial values |
|---|---|
| Operators | 3; explicitly configured Anchor subset |
| Horizon | 2 hours for verification, then 24 |
| POI | Existing 0.6 nameplate ratio; add a nonbinding control |
| Audit capacity | 0, 1, 3 per hour |
| Fine scale | 0, 1, 4 times a fixed reference amount selected on training cases |
| Investigation | Perfect first; imperfect evidence afterward |
| Violations | Wind only, SOC only, both |
| Wind retention | Zero allowance and a declared positive allowance |
| Prices | Two-price synthetic case, then historical hourly prices |

Run a small staged matrix rather than the full Cartesian product. Determine fine reference amounts before testing, in dollars per adverse finding; report the actual dollar values. Use positive-price and negative-price synthetic cases, high/low wind, full/empty batteries, and binding/nonbinding POI controls.

### Required records

| Group | Fields |
|---|---|
| Operation | Requested/accepted exports, charging, discharge, curtailment, SOC, ISO cuts, spill |
| Learning | Observation timestamp, belief moments, predictive quantiles, policy weights, model version |
| Contract | True wind for evaluation, report, retention allowance, dispatch responsibility, reserve floor |
| Compliance | False derate, reserve deficit, duration and energy-weighted severity |
| Monitoring | Screening scores, selected audits, selection probabilities, evidence, sanctions |
| Economics | Margin before fines, overflow charge, fines, net private profit, investigation cost, external harm |
| Solution | Candidate set, planning approximation, deviation gains, runtime, seed, feasibility failures |

Use paired day/seed comparisons and day-block uncertainty intervals. Report detection precision and recall separately from the false-positive rate; specify their denominators. A monitor can improve detection while reducing net welfare through excessive investigations, so report both outcomes.

## 7. Implementation map

The paths below are proposed additions. Existing solver behavior remains unchanged.

| File or module | Responsibility |
|---|---|
| `code/wargame/information/observations.py` | Typed owner and monitor observations with timestamps |
| `code/wargame/learning/beliefs.py` | Priors, particle transitions and posterior updates |
| `code/wargame/learning/predictors.py` | Persistence and fitted rival-export predictors |
| `code/wargame/solvers/belief_dispatch.py` | Candidate rollouts under rival scenarios |
| `code/wargame/model/contracts.py` | Reports, wind-retention allowance, assignments and reserve obligations |
| `code/wargame/monitor/policies.py` | Random, risk-based and evaluator-only audit policies |
| `code/wargame/monitor/enforcement.py` | Evidence generation, sanction events and accounting |
| `code/wargame/experiments/sequential.py` | Common timing, execution and feedback loop |
| `code/scripts/08_learning_experiment.py` | Track A runner |
| `code/scripts/09_enforcement_experiment.py` | Track B runner |
| `config/learning.yaml`, `config/enforcement.yaml` | Separate configurations and seeds |
| `results/learning/`, `results/enforcement/` | Isolated artifacts and metadata |

Observation objects must not contain full simulator state. Oracle data is exposed through a separate evaluator interface. Keep the existing monitor utilities as statistical components rather than allowing them direct access to private operator variables.

## 8. Work sequence and completion gates

| Milestone | Tasks | Completion gate |
|---|---|---|
| M0. Contracts and timing | Specify observable fields, action timing, retention allowance, reserve indexing and accounting | One written contract plus two-hour examples with hand-computed outcomes |
| M1. Sequential environment | Implement observations, simultaneous actions and realization logs | No hidden information reaches policies; battery, export and audit budgets always hold |
| M2. Learning baseline | Persistence, fitted predictor, scenario rollouts against fixed opponents | Held-out predictive and economic comparisons against identical-objective controls |
| M3. State/policy inference | Particle filter and noisy SOC treatment | Calibration and identifiability limitations documented; no oracle-label leakage |
| M4. Enforcement baseline | Reports, reserve violations, perfect investigations, random/risk policies | Enumerated two-hour results match independent payoff/deviation calculations |
| M5. Strategic response | Operators anticipate committed audits | Violations respond to specified fines and audit coverage; report any nonmonotonic outcomes |
| M6. Imperfect evidence | False positives, missed violations and random audit exploration | Error rates and selection effects reproduce the configured observation model |
| M7. Combined experiment | Selected learned-opponent and monitoring cases | Matched comparison isolates learning, enforcement and their interaction |

At M0, approve the institutional interpretation of wind retention and dispatch responsibility. All later results depend on that choice. The remaining milestones can proceed as separate learning and enforcement branches once the common environment is verified.

## 9. Minimum verification cases

1. **Economic value of reporting:** With unrestricted truthful charging and no report-dependent contract, removing enforcement makes reporting payoff irrelevant. Under the proposed must-offer contract, construct a low/high-price case where underreporting expands feasible charging.
2. **Physical conservation:** All charging uses true wind; reports never create energy. Rejected battery discharge is retained or explicitly recorded as spill.
3. **Reserve accounting:** Violations use post-action SOC. Physical SOC remains nonnegative even when the contractual reserve floor is breached.
4. **ISO exceptions:** Forced wind cuts do not create a delivery violation.
5. **Audit budget:** Every realized audit set respects the per-hour capacity, including randomized policies.
6. **Evidence separation:** Perfect investigation has no evidentiary error even with noisy screening. Imperfect investigation produces configured false-positive and detection rates.
7. **Information isolation:** Changing hidden truth while holding an owner's observation history fixed cannot change its chosen action, except through its declared random seed.
8. **Learning controls:** Static predictions, learned predictions and oracle predictions use the same dispatch objective and action class.
9. **Behavioral responses:** No-audit and zero-fine cases recover the corresponding unconstrained compliance-choice benchmark. Full auditing with sufficiently large fines is checked against the restricted compliant optimum; use explicit tolerances and do not assume deterrence without calculating deviation gains.
10. **Regression:** Existing 14-case outputs remain reproducible under the original configuration.

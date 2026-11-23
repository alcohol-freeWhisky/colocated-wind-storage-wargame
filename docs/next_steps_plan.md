# Two Simulation Extensions for the Wind–Storage Game

The proposed work has two branches. The first studies how operators learn about one another under imperfect information. The second studies strategic reporting and reserve compliance under limited monitoring.

| | Part I: Opponent Learning | Part II: Strategic Compliance and Monitoring |
|---|---|---|
| Players | Wind–storage operators | Wind–storage operators and one market monitor |
| Strategic decision | Dispatch based on beliefs about rivals | Availability reports, dispatch, and reserve compliance |
| Information problem | Rivals' generation, SOC, and operating policies are hidden | The monitor observes noisy signals of violations |
| Main comparison | Learned beliefs versus fixed predictions and full information | Operator behavior under different investigation policies and capacities |
| Main outcome | Value of learning and its effect on congestion | Noncompliance, deterrence, and investigation efficiency |

Both branches use the current hourly wind–storage environment, exogenous electricity prices, and a shared export limit. Each is evaluated separately against matched controls.

## Part I. Opponent Learning under Imperfect Information

### Research question

How much operating value can an owner gain by learning rivals' wind availability, battery SOC, and dispatch behavior? Does better prediction reduce simultaneous exports and attempted POI overflow?

### Setup

There are $N$ wind–storage operators sharing an export connection of capacity $K^{POI}$. Each operator knows its own wind availability, SOC, battery parameters, and electricity prices. Rival wind, SOC, and policy parameters are hidden.

Each day contains 24 hourly decisions. Operators choose actions simultaneously, observe permitted metering after execution, and update their beliefs before the next decision. The initial experiment gives each operator perfect foresight of prices and its own wind, so the information treatment concerns rivals.

For owner $i$,

$$
q_{it}=W_{it}-c_{it}-r_{it}+d_{it},
$$

$$
s_{i,t+1}=s_{it}+\eta_c c_{it}-d_{it}/\eta_d,
$$

$$
0\le c_{it},d_{it}\le P_i,\qquad
c_{it}+r_{it}\le W_{it},\qquad
r_{it}\ge0,\qquad 0\le s_{it}\le E_i.
$$

The existing realization rule enforces the POI limit and produces accepted export $\widetilde q_{it}$ and executed discharge $\widetilde d_{it}$. Attempted overflow is

$$
V_t=\left[\sum_jq_{jt}-K^{POI}\right]_+.
$$

### Learning problem

The hidden rival state includes generation, SOC, and policy parameters:

$$
x_{-i,t}=(W_{-i,t},s_{-i,t},\theta_{-i}).
$$

Owner $i$ maintains a belief based on its observation history $\mathcal H_{it}$:

$$
b_{it}(x)=P(x_{-i,t}=x\mid\mathcal H_{it}).
$$

Observations can include lagged aggregate exports, owner-level exports, public wind forecasts, and noisy SOC telemetry. A state estimator updates beliefs from these observations and the battery transition model. An opponent model maps estimated states, prices, and operating parameters into predicted rival injections.

The dispatch policy uses sampled rival trajectories to maximize expected remaining-day profit:

$$
\max_{a_i}\mathbb E_{b_{it}}\sum_{\tau=t}^{23}
\left[\pi_\tau\widetilde q_{i\tau}
-g_i^{deg}\widetilde d_{i\tau}
-\lambda^{ov}w_{i\tau}V_\tau\right].
$$

The action $a_i$ specifies charging, discharging, and curtailment. Equal and injection-based overflow shares are retained from the current model. The policy executes its first-hour action and replans after receiving the next observation.

The learner is evaluated on its prediction of rival injections as well as its estimates of hidden states. At a binding POI, accepted export is a censored observation of requested export; the observation model includes this truncation.

### Experimental design

| Treatment | Rival information and prediction |
|---|---|
| Zero-rival baseline | Assume zero rival injection |
| Fixed predictor | Persistence or historical mean rival injection |
| Aggregate learning | Learn from lagged aggregate export and public wind forecasts |
| Owner-level learning | Learn from lagged owner-level exports and public wind forecasts |
| SOC-assisted learning | Add noisy, delayed owner-level SOC telemetry |
| Full-state benchmark | Observe rival generation and SOC, with the same specified opponent-policy family |

All treatments use the same dispatch objective, physical parameters, and action class. The first comparison uses fixed rival policies, allowing the experiment to isolate the value of state and policy inference. A second comparison allows all operators to adapt and measures the resulting changes in joint behavior.

The estimator can use a bounded-state particle filter with a small library of rival operating policies. A persistence model provides the forecasting baseline. Policy weights capture whether a rival tends to charge at low prices, discharge aggressively at high prices, or avoid congestion.

Use the existing 60-day window with a chronological 30-day training, 10-day validation, and 20-day test split. Reset physical SOC daily and retain learned policy parameters across days. Compare three-owner and five-owner settings separately. Price spread, wind correlation, battery size, observation noise, and POI tightness are the main sensitivity variables.

| Outcome | Measurement |
|---|---|
| Predictive performance | Rival-injection error, SOC estimation error where identifiable, predictive interval coverage |
| Private value | Realized operating margin and profit after overflow charges |
| Congestion | Attempted overflow, rejected exports, and simultaneous peak exports |
| Storage behavior | Charging/discharging timing, throughput, and SOC trajectories |
| System value | Total realized energy revenue less discharge degradation |
| Adaptation | Prediction and payoff changes as observation history grows |

The central hypothesis is that learning shifts exports away from periods of high expected rival injection. The experiment measures when that response creates value and how it depends on battery flexibility and the overflow allocation rule.

## Part II. Strategic Reporting, Reserve Compliance, and Monitoring

### Research question

How do operators choose availability reports and battery dispatch when violations can increase profit but investigations are limited? How should a monitor allocate investigations across operators using imperfect evidence?

### Setup

There are three wind–storage operators and one Independent Market Monitor. The horizon is 24 hours. Operators know future prices and their own available wind. They choose reported wind availability and battery dispatch while anticipating a publicly specified monitoring policy.

The wind and battery equations are the same as in Part I. Two contractual obligations create the compliance decisions: a report-dependent wind dispatch responsibility and an exogenous minimum SOC requirement.

### Wind availability reports and dispatch responsibility

Owner $i$ reports $R_{it}$ and may understate true availability:

$$
0\le R_{it}\le W_{it},\qquad f_{it}=W_{it}-R_{it}.
$$

Let $A_{it}$ be the wind-retention allowance authorized for storage or curtailment. Eligible wind export and assigned wind responsibility are

$$
e_{it}=[R_{it}-A_{it}]_+,
$$

$$
B_{it}=e_{it}\min\left(1,\frac{K^{POI}}{\sum_je_{jt}}\right),
$$

with $B_{it}=0$ when total eligible export is zero. The operator must schedule wind export

$$
g_{it}=W_{it}-c_{it}-r_{it}\ge B_{it}.
$$

When the POI is nonbinding and $R_{it}\ge A_{it}$, this condition becomes

$$
c_{it}+r_{it}\le A_{it}+f_{it}.
$$

Underreporting therefore expands the amount of wind that can be retained rather than assigned to current export. An operator may use that flexibility to charge at low prices and sell later at high prices. Physical charging remains bounded by true wind and battery limits.

Use $A_{it}=0$ for the strict dispatch-obligation case and a positive allowance to study authorized charging. Record POI-directed reductions separately and deduct them from the operator's delivery responsibility.

### Minimum SOC obligation

Each battery has a specified reserve requirement $S_{i,t+1}^{req}$. The end-of-hour reserve violation is

$$
v_{it}=[S_{i,t+1}^{req}-s_{i,t+1}]_+.
$$

Compliant dispatch satisfies $s_{i,t+1}\ge S_{i,t+1}^{req}$. A noncompliant operator may discharge below this requirement while remaining within the physical bound $s_{i,t+1}\ge0$.

This creates a second intertemporal incentive: high prices can make additional discharge profitable even when it breaches the reserve obligation.

### Monitor information and investigations

The monitor observes reports, assigned dispatch, accepted injections, prices, weather-based wind estimates, SOC telemetry, and past investigation outcomes. Its signals include

$$
z_{it}^{W}=W_{it}^{weather}-R_{it},\qquad
z_{it}^{S}=S_{i,t+1}^{req}-s_{i,t+1}^{telemetry}.
$$

The monitor chooses investigations after observing current operational signals:

$$
a_{it}^{M}\in\lbrace0,1\rbrace,\qquad
\sum_i a_{it}^{M}\le L_t^{audit}.
$$

One investigation checks both wind reporting and reserve compliance. The audit capacity $L_t^{audit}$ is distinct from the export capacity $K^{POI}$.

For violation type $k\in\lbrace W,S\rbrace$, let $D_{it}^k$ indicate a true violation and $Y_{it}^k$ an adverse investigative finding. Conditional evidence quality is described by

$$
\alpha_k=P(Y^k=1\mid D^k=0,a^M=1),\qquad
\beta_k=P(Y^k=1\mid D^k=1,a^M=1).
$$

Perfect investigation sets $\alpha_k=0$ and $\beta_k=1$. Imperfect investigation varies false-positive and detection probabilities. Weather and telemetry noise determine screening quality separately from investigative evidence quality.

An adverse finding triggers a fixed type-specific fine:

$$
F_i=\sum_{t,k}a_{it}^{M}Y_{it}^k\overline F_k.
$$

### Operator and monitor objectives

Operators maximize expected realized profit:

$$
\max U_i=\mathbb E\sum_t
\left[\pi_t\widetilde q_{it}
-g_i^{deg}\widetilde d_{it}
-\lambda^{ov}w_{it}V_t\right]-\mathbb E[F_i].
$$

The overflow charge and enforcement fine are separate incentives. The first prices attempted congestion; the second sanctions reporting or reserve violations.

The monitor minimizes investigation costs, wrongful findings, and undetected violations:

$$
\min C_M=\mathbb E\sum_{t,i}
\left[c_a a_{it}^{M}
+c_{FP}\sum_k(1-D_{it}^k)a_{it}^{M}Y_{it}^k
+c_{miss}\sum_kD_{it}^k(1-a_{it}^{M}Y_{it}^k)\right].
$$

Investigation decisions use conditional violation probabilities inferred from the monitor's signals and history. A risk-based policy ranks operators by the expected reduction in monitoring loss from an investigation. A randomized audit component supplies observations across the operator population and supports estimation of violation probabilities.

### Experimental design

The game uses a committed monitor policy. Operators choose reports and dispatch simultaneously; market operation produces signals; the monitor selects audits and applies sanctions. Operators anticipate the policy's signal-dependent investigation probabilities. Compare fixed enforcement rules first, then optimize parameters within the risk-based policy family.

| Factor | Treatments |
|---|---|
| Available violations | Wind underreporting only; SOC violation only; both |
| Monitor policy | No investigation; random investigation; risk-based investigation |
| Audit capacity | 0, 1, or 3 operators per hour |
| Fine level | Zero, moderate, and high type-specific fines |
| Investigation quality | Perfect and imperfect evidence |
| Wind-retention allowance | Zero and positive authorized retention |
| Reserve requirement | Low and high minimum SOC |
| Operating conditions | Low/high price spreads, low/high wind, binding/nonbinding POI |

Use a two-hour low-price/high-price instance to characterize the incentives, followed by the historical 24-hour cases. A discrete reporting and dispatch policy library permits direct payoff and unilateral-deviation calculations in the small instance. Receding-horizon policy rollouts extend the same formulation to the daily experiment. Report the action resolution and measured deviation gains alongside outcomes.

Fine levels are specified in dollars per adverse finding and held fixed across matched comparisons. The main comparisons isolate investigation capacity, policy targeting, evidence quality, and the interaction between the two violation types.

| Outcome | Measurement |
|---|---|
| Wind noncompliance | Underreported energy and frequency of false derates |
| Reserve noncompliance | Deficit magnitude, duration, and timing |
| Enforcement | Audit allocation, detection rate, false-positive rate, missed violations, and fines |
| Operator response | Reporting, charging, discharging, and private profit |
| Monitor performance | Investigation cost and total monitoring loss |
| System operation | Realized operating value, curtailment, congestion, and reserve deficits |

The central hypotheses are that stronger expected enforcement reduces profitable violations, targeted audits use limited capacity more effectively than random audits, and the relative incentives for false derating and reserve depletion depend on the price trajectory and storage capacity.

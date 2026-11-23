# Two Simulation Extensions for the Wind–Storage Game

The proposed work has two branches. The first studies how operators learn about one another under imperfect information. The second studies one operator and one monitor, with false wind derating at low prices and reserve depletion at high prices.

| | Part I: Opponent Learning | Part II: Strategic Compliance and Monitoring |
|---|---|---|
| Players | Wind–storage operators | One wind–storage operator and one market monitor |
| Strategic decision | Dispatch based on beliefs about rivals | Low-price false derating and high-price SOC violations |
| Information problem | Rivals' generation, SOC, and operating policies are hidden | The monitor observes noisy signals of violations |
| Main comparison | Learned beliefs versus fixed predictions and full information | Compliance and monitoring responses in low- and high-price periods |
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

## Part II. One Operator and One Monitor under Low and High Prices

### Research question

How does a wind–storage operator respond to low and high electricity prices when a monitor can investigate and penalize noncompliance? The two price regimes create different incentives: withholding wind availability to charge at low prices, and discharging below the reserve requirement at high prices.

### Setup

The game has two players: one wind–storage operator and one Independent Market Monitor. Prices are exogenous. The operator knows its available wind and the price trajectory, controls its availability report and battery dispatch, and anticipates the monitor's investigation policy.

Begin with two periods, low price followed by high price:

$$
\pi_L<\pi_H.
$$

The battery connects the periods through its SOC. The same model then extends to 24 hourly periods containing low- and high-price intervals.

| Price regime | Operator's compliant action | Operator's noncompliant action | Monitor's target |
|---|---|---|---|
| Low price | Report true wind availability and meet assigned wind dispatch | Underreport wind availability, reduce assigned export, and charge more wind for later sale | False wind derating |
| High price | Discharge while maintaining the required SOC | Discharge additional energy below the reserve floor | Minimum SOC violation |

### Physical operation and dispatch responsibility

Omit the owner index because there is one operator. Wind export, net export, and battery dynamics are

$$
g_t=W_t-c_t-r_t,\qquad q_t=g_t+d_t,
$$

$$
s_{t+1}=s_t+\eta_c c_t-\frac{d_t}{\eta_d},
$$

$$
0\le c_t,d_t\le P,\qquad r_t\ge0,\qquad
c_t+r_t\le W_t,\qquad 0\le s_t\le E.
$$

Each period lasts one hour. Charging uses wind. The assigned wind dispatch equals reported availability:

$$
B_t=R_t,\qquad 0\le R_t\le W_t,\qquad g_t\ge B_t.
$$

Here $B_t$ is the wind-delivery responsibility; battery discharge contributes additional export. Under truthful reporting, $R_t=W_t$, so available wind is assigned to current delivery. Underreporting reduces this responsibility and permits wind retention for charging. A nonbinding export limit isolates the reporting and reserve incentives in this branch.

### Low-price decision: false wind derating

The false derate is

$$
f_L=W_L-R_L\ge0.
$$

The dispatch obligation implies

$$
c_L+r_L\le f_L.
$$

Thus charging an additional amount $x$ of low-price wind requires a corresponding reduction in reported availability. If that energy can be discharged and sold in the high-price period, its incremental operating gain is

$$
G_W(x)=\left[\eta_c\eta_d(\pi_H-g^{deg})-\pi_L\right]x,
$$

subject to battery power, energy, and terminal constraints. The term $\pi_Lx$ is the foregone low-price sale; $\eta_c\eta_dx$ is the later delivered energy.

The low-price experiment compares truthful dispatch against strategic underreporting as the price spread and expected enforcement cost vary.

### High-price decision: minimum SOC violation

The battery has an exogenous end-of-period reserve requirement $S_{t+1}^{req}$. The high-price violation is

$$
v_H=[S_{H+1}^{req}-s_{H+1}]_+.
$$

Compliant operation maintains $s_{H+1}\ge S_{H+1}^{req}$. Noncompliant operation may discharge below the reserve floor while respecting the physical bound $s_{H+1}\ge0$.

If compliant dispatch would finish exactly at the reserve floor, an additional discharge $y$ creates a reserve deficit $y/\eta_d$ and an immediate gain

$$
G_S(y)=(\pi_H-g^{deg})y.
$$

For the two-period experiment, the reserve floor determines the required terminal SOC of the compliant policy. Both policies receive the same exogenous terminal energy value $\Phi(s_{H+1})$, so the full incremental gain also includes the change in remaining battery value. The noncompliant policy can finish below the contractual floor and face enforcement.

### Monitor information and action

The monitor observes reported wind, assigned dispatch, realized export, prices, a weather-based estimate of wind availability, SOC telemetry, and investigation history. Its two screening signals are

$$
z_L^W=W_L^{weather}-R_L,\qquad
z_H^S=S_{H+1}^{req}-s_{H+1}^{telemetry}.
$$

At each period, the monitor chooses whether to investigate the operator:

$$
a_t^M\in\lbrace0,1\rbrace.
$$

Monitoring effort is allocated across time and violation types. A daily investigation budget can be imposed as

$$
\sum_ta_t^M\le L^{audit}.
$$

In the two-period case, $L^{audit}=1$ forces a choice between investigating low-price reporting and high-price reserve compliance. Compare this with no investigation and the ability to investigate both periods.

An investigation verifies wind availability and operating records in the low-price period, or battery SOC and reserve compliance in the high-price period. Initially, investigated violations are revealed perfectly. Imperfect investigation introduces type-specific false positives and missed violations.

For type $k\in\lbrace W,S\rbrace$, write

$$
\alpha_k=P(Y^k=1\mid D^k=0,a^M=1),\qquad
\beta_k=P(Y^k=1\mid D^k=1,a^M=1),
$$

where $D^k$ denotes a true violation and $Y^k$ an adverse investigative finding. The fine is

$$
F=\overline F_Wa_L^MY_L^W+\overline F_Sa_H^MY_H^S.
$$

### Operator and monitor objectives

The operator chooses reporting and battery operation to maximize

$$
\max U=\mathbb E\left[
\sum_t(\pi_tq_t-g^{deg}d_t)+\Phi(s_T)-F
\right].
$$

The monitor minimizes investigation costs, false-positive sanctions, and missed violations:

$$
\min C_M=\mathbb E\left[
\sum_tc_aa_t^M+
\sum_{k\in\lbrace W,S\rbrace}
\left(c_{FP,k}(1-D^k)a_k^MY^k
+c_{miss,k}D^k(1-a_k^MY^k)\right)
\right].
$$

Here $a_W^M=a_L^M$ and $a_S^M=a_H^M$. The monitor evaluates expected losses conditional on its observations. Its policy determines investigation probabilities as a function of price regime, screening signals, history, and remaining budget. The operator anticipates these probabilities when choosing its actions.

For either violation, the incentive comparison is

$$
\text{incremental operating gain}
\quad\text{versus}\quad
\mathbb E[F\mid\text{violation}]-\mathbb E[F\mid\text{compliance}].
$$

### Experimental design

The main experiment is a two-period game with one low-price reporting decision and one high-price reserve decision. Compare fixed monitoring policies, then optimize the monitor's allocation between the two periods within the specified policy family. A discrete grid of reports and feasible charging/discharging actions permits direct payoff comparisons and unilateral-deviation calculations.

| Factor | Treatments |
|---|---|
| Operator choices | Truthful and reserve-compliant; false derating only; SOC violation only; both available |
| Price trajectory | Low/high price pairs with increasing spreads |
| Initial SOC | Low, intermediate, high |
| Reserve requirement | Low and high reserve floors |
| Battery flexibility | Power, energy capacity, and efficiency |
| Monitoring policy | Random; low-price focused; high-price focused; signal based |
| Investigation budget | Neither period, one period, both periods |
| Enforcement | Type-specific wind and SOC fines |
| Evidence | Perfect investigation, then imperfect investigation |

The 24-hour extension uses historical wind and prices to examine how repeated low- and high-price intervals change charging, reporting, reserve depletion, and the timing of investigations. The operator and monitor remain the two players.

| Outcome | Measurement |
|---|---|
| Low-price response | Reported availability, false-derated energy, charging, and foregone current sales |
| High-price response | Additional discharge, reserve deficit, and peak-price revenue |
| Intertemporal response | Energy shifted between price regimes and terminal SOC |
| Enforcement | Investigation timing, detected violations, false positives, missed violations, and fines |
| Private value | Operating margin, terminal energy value, and profit after fines |
| Monitor performance | Investigation cost and total monitoring loss |

The comparisons identify which price conditions make each violation attractive, how enforcement changes the operator's response, and when the monitor allocates its limited effort to wind reporting rather than reserve compliance.

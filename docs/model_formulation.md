# Wind–Storage Operation: Baseline, Opponent Forecasting, and Reserve Compliance

## 1. Model structure

| Model | Operators | Information and decision | Connection |
|---|---|---|---|
| Existing simulation | Five Anchor wind–battery operators | Central dispatch or owner best responses; perfect/forecast foresight; FULL/aggregate/NONE rival signals | Shared export limit $K$ |
| Part I: opponent forecasting | The same five operators | Simultaneous dispatch using forecasts of aggregate rival requests | The same shared export limit $K$ |
| Part II: reserve compliance | `ANCHOR_WIND2` and a monitor | Price-taking dispatch with a fixed ancillary-service commitment and observable SOC deficits | Nonbinding export limit |

All models use the same wind, price, battery, and daily operating conventions. Sections 2–5 specify the common notation and existing simulation. Sections 6–7 define the two extensions. Section 8 lists parameter values and provenance. The extension equations specify proposed experiments; the existing run is the 60-day, 14-case simulation.

## 2. Indices, variables, and information

### 2.1 Indices and units

| Symbol | Meaning | Units / range |
|---|---|---|
| $i,j$ | Operator indices | $\mathcal I=\lbrace1,2,3,4,5\rbrace$ |
| $\ell$ | Operating day | 60 complete days |
| $t$ | Hourly action index | $0,\ldots,T-1$ |
| $h$ | Current replanning hour | $0,\ldots,T-1$ |
| $T$ | Number of action intervals | 24 |
| $\Delta t$ | Interval duration | 1 h |
| $s_{it}$ | SOC at the start of interval $t$ | MWh; $t=0,\ldots,T$ |
| $[x]_+$ | Positive part | $\max(x,0)$ |

The day index is omitted from operating equations. Carry it explicitly in learning samples and paired comparisons.

### 2.2 Physical and market notation

| Symbol | Meaning | Code / data field |
|---|---|---|
| $W_{it}$ | Realized available wind (MW) | `W_avail`, `Episode.W` |
| $\widehat W_{it}$ | Own wind availability forecast (MW) | `What_cop`, `Episode.What` |
| $\pi_t^{RT},\pi_t^{DA}$ | Real-time and day-ahead energy prices ($/MWh) | `pi_RT`, `pi_DA` |
| $b_{it}^{DAM}$ | Day-ahead energy award; provenance only | `b_dam` |
| $N_i$ | Wind capacity proxy (MW) | `nameplate_mw` |
| $P_i,E_i$ | Battery power (MW), energy capacity (MWh) | `Battery.P`, `Battery.E` |
| $\eta_c,\eta_d$ | Charging and discharging efficiencies | `eta_c`, `eta_d` |
| $c_i^{deg}$ | Cost per MWh discharged | `c_deg` |
| $c_{it},d_{it},r_{it}$ | Requested charging, discharge, wind curtailment (MW) | planned `c`, `d`, `r` |
| $q_{it}$ | Requested net export (MW) | planned `q` |
| $\widetilde c_{it},\widetilde d_{it},\widetilde r_{it},\widetilde q_{it}$ | Executed quantities | realized `c`, `d`, `r`, `q` |
| $z_{it}$ | Inverter-side spill (MW) | `spill` |
| $K$ | Shared export capacity (MW) | `Episode.K` |
| $\lambda^+$ | Attempted-overflow charge ($/MWh) | `lambda_plus` |
| $\epsilon^{act}$ | Numerical activity cost ($/MWh) | `eps_tiebreak_usd_per_mwh` |

$N_i$ remains the capacity proxy and $E_i$ remains energy capacity throughout. SOC is always $s_{it}$; electricity price is always $\pi_t$. Reserve commitments introduced in Section 7 use $h_{it}^{AS}$, not $K$ or $R$.

### 2.3 Foresight views

For a replanning hour $h$ and future index $t\ge h$, the existing views are

$$
W_{it}^{P,h}=W_{it},\qquad \pi_t^{P,h}=\pi_t^{RT},
$$

$$
W_{it}^{F,h}=
\begin{cases}W_{ih},&t=h,\\\widehat W_{it},&t>h,\end{cases}
\qquad
\pi_t^{F,h}=
\begin{cases}\pi_h^{RT},&t=h,\\\pi_t^{DA},&t>h.\end{cases}
$$

Both extensions start with the $P$ view of the operator's own wind and prices. Own-wind and price forecast uncertainty can be tested with the same $F$ view.

### 2.4 Part I observation setup

| Quantity | Owner $i$ at hour $h$ | Other owners | Simulator / evaluator |
|---|---|---|---|
| Own SOC and past actions | Observed | Hidden | Observed |
| Own current wind and own remaining-day wind under $P$ | Observed | Hidden | Observed |
| Energy prices under the selected foresight view | Observed | Same price view | Observed |
| Own past requested and accepted exports | Observed | Hidden | Observed |
| Current rival requests, SOC, wind and COP | Hidden | Each knows its own | Observed |
| Aggregate past rival request inferred from proportional cuts | Available when identifiable from own metering | Each uses its own metering | Observed |
| Historical resource disclosures | Available only after their release time | Same | Observed |
| Full current rival plan | Ideal plan-information benchmark only | Benchmark only | Observed |

Actions at hour $h$ are simultaneous. Metering for hour $h$ enters observations at $h+1$. Historical resource disclosures use a 60-day lag in this experimental information model. The March–April resource-level COP tables are private own forecasts, not contemporaneous public rival forecasts. With only the current 60-day window, lagged disclosures supply no within-window training labels unless earlier data are added.

## 3. Common wind and battery equations

### 3.1 Requested dispatch

For every active operator and hour,

$$
q_{it}=W_{it}-r_{it}-c_{it}+d_{it},
\tag{1}
$$

$$
0\le c_{it}\le P_i,\qquad 0\le d_{it}\le P_i,
\tag{2}
$$

$$
r_{it}\ge0,\qquad c_{it}+r_{it}\le W_{it},
\tag{3}
$$

$$
s_{i,t+1}=s_{it}+\eta_c c_{it}\Delta t-\frac{d_{it}\Delta t}{\eta_d},
\tag{4}
$$

$$
0\le s_{it}\le E_i,\qquad s_{i0}=0.5E_i.
\tag{5}
$$

Equations (1)–(3) imply $q_{it}\ge0$. There is no minimum-generation obligation. Charging is wind-only.

The executable dispatch must also satisfy

$$
c_{it}d_{it}=0.
\tag{6}
$$

The existing continuous solvers handle this through an activity cost, cycle removal, and validation rather than binary variables. With $\rho=\eta_c\eta_d$, the cycle-removal map is

$$
a=\min\left(c,d/\rho,\frac{[W-r]_+}{1-\rho}\right),
\tag{7}
$$

$$
c'=c-a,\qquad d'=d-\rho a,\qquad r'=r+(1-\rho)a.
\tag{8}
$$

The last argument of (7) is omitted when $\rho=1$. This map preserves requested export and the SOC increment. Equation (6) is checked after transformation.

### 3.2 Terminal condition and hourly replanning

Let $\mathcal T_h=\lbrace h,\ldots,T-1\rbrace$. At hour $h$, retain the actual starting SOC and use the existing terminal target

$$
s_i^{tar}(h)=\min\left(s_{i0},\ s_{ih}+\eta_c\Delta t
\sum_{t\in\mathcal T_h}\min(P_i,W_{it}^{view,h})\right),
\tag{9}
$$

$$
s_{iT}^{plan}\ge s_i^{tar}(h).
\tag{10}
$$

Solve over $\mathcal T_h$, execute only hour $h$, update SOC from executed dispatch, and replan. Each day resets to (5). The terminal target is a return lower bound, not an equality. The reserve requirement in Section 7 is an additional obligation and is not relaxed by (9).

## 4. Shared connection and realized accounting

### 4.1 Physical realization

For feasible cycle-free requests entering the POI reduction step, define

$$
Q_t=\sum_iq_{it},\qquad V_t=[Q_t-K]_+,
\tag{11}
$$

$$
\Delta q_{it}=\begin{cases}V_tq_{it}/Q_t,&Q_t>0,\\0,&Q_t=0.\end{cases}
\tag{12}
$$

The existing implementation first increases wind curtailment, then reduces discharge, then records remaining reduction as spill. Write

$$
s_{i,t+1}^{pre}=s_{it}+\eta_cc_{it}\Delta t-d_{it}\Delta t/\eta_d,
\tag{13}
$$

$$
u_{it}=\min(\Delta q_{it},[W_{it}-r_{it}]_+),
\tag{14}
$$

$$
b_{it}=\min\left([\Delta q_{it}-u_{it}]_+,\ d_{it},\
\frac{\eta_d[E_i-s_{i,t+1}^{pre}]_+}{\Delta t}\right),
\tag{15}
$$

$$
z_{it}=[\Delta q_{it}-u_{it}-b_{it}]_+,
\tag{16}
$$

$$
\widetilde c_{it}=c_{it},\quad
\widetilde r_{it}=r_{it}+u_{it},\quad
\widetilde d_{it}=d_{it}-b_{it},
\tag{17}
$$

$$
\widetilde q_{it}=W_{it}-\widetilde r_{it}-\widetilde c_{it}
+\widetilde d_{it}-z_{it},
\tag{18}
$$

$$
s_{i,t+1}=s_{it}+\eta_c\widetilde c_{it}\Delta t
-\widetilde d_{it}\Delta t/\eta_d.
\tag{19}
$$

Here $u_{it}$ is additional wind curtailment and $b_{it}$ is cancelled discharge; neither is a market bid or DAM award. The realization code also repairs small battery-bound errors before this step. For feasible requests, (12)–(18) give

$$
\widetilde q_{it}=\begin{cases}q_{it}\min(1,K/Q_t),&Q_t>0,\\0,&Q_t=0,\end{cases}
\qquad\sum_i\widetilde q_{it}\le K.
\tag{20}
$$

### 4.2 Economic quantities

Daily realized operating margin is

$$
J_i=\sum_{t=0}^{T-1}
(\pi_t^{RT}\widetilde q_{it}-c_i^{deg}\widetilde d_{it})\Delta t,
\qquad J=\sum_iJ_i.
\tag{21}
$$

Numerical activity is

$$
A_i^{act}=\sum_t(c_{it}+d_{it}+r_{it})\Delta t.
\tag{22}
$$

The existing overflow allocations are

$$
w_{it}^{EQ}=1/N,\qquad
w_{it}^{INJ}=\begin{cases}[q_{it}]_+/\sum_j[q_{jt}]_+,&\sum_j[q_{jt}]_+>0,\\1/N,&\text{otherwise},\end{cases}
\tag{23}
$$

$$
C_i^{ov}=\lambda^+\sum_tw_{it}V_t\Delta t,
\qquad\sum_iC_i^{ov}=\lambda^+\sum_tV_t\Delta t.
\tag{24}
$$

$J$ excludes internal overflow charges, enforcement payments, and the numerical activity cost.

## 5. Existing simulation: reference formulation

### 5.1 Central planner

For either information view, the planner solves

$$
\max_{c,d,r,s}\sum_{t\in\mathcal T_h}\sum_i
\left[\pi_t^{view,h}q_{it}-c_i^{deg}d_{it}
-\epsilon^{act}(c_{it}+d_{it}+r_{it})\right]\Delta t,
\tag{25}
$$

subject to (1)–(5), (9)–(10), and

$$
\sum_iq_{it}\le K\qquad(t\in\mathcal T_h).
\tag{26}
$$

### 5.2 Owner planning game

The current code maximizes planned, rather than accepted, energy revenue:

$$
\max_{a_i}U_i^{legacy}=
\sum_{t\in\mathcal T_h}
\left[\pi_t^{view,h}q_{it}-c_i^{deg}d_{it}
-\lambda^+w_{it}V_t
-\epsilon^{act}(c_{it}+d_{it}+r_{it})\right]\Delta t,
\tag{27}
$$

subject to own physical and terminal constraints. Here $a_i=(c_i,d_i,r_i)$ denotes a remaining-horizon plan.

The rival inputs are

$$
Q_{-i,t}=\sum_{j\ne i}q_{jt},\qquad
Q_{-i,t}^{+}=\sum_{j\ne i}[q_{jt}]_+.
\tag{28}
$$

FULL converts owner-level plans to (28); `PRICE` supplies those aggregate signals directly; NONE sets both to zero. FULL and `PRICE` therefore define the same best-response problem. `PRICE` is an aggregate-information identifier.

The informed update is

$$
a_i^{BR}\in\arg\max_{a_i}U_i^{legacy}(a_i,a_{-i}),
\qquad a_i^{k+1}=(1-\alpha)a_i^k+\alpha a_i^{BR},
\tag{29}
$$

followed by cycle removal. Rivals are refreshed after each owner update. Acceptance uses

$$
G^{max}=\max_i\left[\max_{a_i'}U_i^{legacy}(a_i',a_{-i})
-U_i^{legacy}(a_i,a_{-i})\right]\le\varepsilon^{gain}.
\tag{30}
$$

NONE evaluates its deviation gains under its zero-rival assumption.

### 5.3 Cases

$$
\mathcal C=\lbrace C_P,C_F\rbrace\cup
\lbrace D_{f,a,m}:f\in\lbrace P,F\rbrace,
 a\in\lbrace INJ,EQ\rbrace,
 m\in\lbrace FULL,PRICE,NONE\rbrace\rbrace.
\tag{31}
$$

There are 14 cases and 840 day–case observations. Their reported outcome is (21).

## 6. Part I: aggregate opponent forecasting

### 6.1 Question and objective

Keep all five farms and the shared $K$. Compare simple forecasts of future rival requests before adding hidden-SOC estimation. The primary extension uses accepted energy revenue and $\lambda^+=0$:

$$
\max_{\mu_i}\mathbb E\left[
\sum_{t\in\mathcal T_h}
(\pi_t^{view,h}\widetilde q_{it}-c_i^{deg}\widetilde d_{it})\Delta t
-\epsilon^{act}A_{i,h}^{act}
\mid\mathcal H_{ih}\right].
\tag{32}
$$

$\mu_i$ is a causal dispatch policy and $\mathcal H_{ih}$ is the information history in Section 2.4. $A_{i,h}^{act}$ is (22) restricted to $\mathcal T_h$. Physical execution uses (11)–(20). Equation (32) replaces the planned-revenue objective (27) for every new learning treatment.

A positive $\lambda^+$ and the charge (24) form a separately labeled contract sensitivity. The original $100/MWh$ case remains the legacy reference.

### 6.2 Inferring historical rival requests

If $q_{ih}>0$, $\widetilde q_{ih}>0$, and proportional curtailment occurs, then

$$
\widehat Q_{-i,h}^{obs}
=K\frac{q_{ih}}{\widetilde q_{ih}}-q_{ih}.
\tag{33}
$$

This observation is available at $h+1$. When a positive request is fully accepted, the observation instead gives the bound

$$
0\le Q_{-i,h}\le K-q_{ih}.
\tag{34}
$$

A zero own request supplies no aggregate-request observation. Exact metering is the initial treatment. A reduction smaller than the numerical tolerance is classified as full acceptance.

### 6.3 Simple predictors

Let $\mathcal N_i=\sum_{j\ne i}N_j$ and normalize the target:

$$
y_{ih}=Q_{-i,h}/\mathcal N_i.
\tag{35}
$$

The baseline predictors are

$$
\widehat Q_{-i,t\mid h}^{ZERO}=0,
\tag{36}
$$

$$
\widehat Q_{-i,t\mid h}^{PERSIST}
=\mathcal N_i\bar y_{ih},\qquad t\ge h,
\tag{37}
$$

where $\bar y_{ih}$ is the latest exact normalized observation from (33). Before the first exact observation, initialize $\bar y_{ih}=0.5$. Carry this forecasting state across days while resetting physical SOC.

For a fitted predictor, define the observable feature vector

$$
x_{i,t\mid h}=\left(
1,\ \sin(2\pi t/24),\ \cos(2\pi t/24),\
\pi_t^{view,h}/p^{scale},\ W_{it}^{view,h}/N_i,\
s_{ih}/E_i,\ \bar y_{ih},\ a_{ih}^{age}/24,\ (t-h)/24
\right),
\tag{38}
$$

where $a_{ih}^{age}$ is elapsed hours since the latest exact aggregate observation, capped at 168 h. It is initialized to 168 h. No rival private COP or current SOC enters (38).

Let $\mathcal D_i^{=} $ contain samples with exact labels from (33), and $\mathcal D_i^{\le}$ contain upper bounds $u_n=(K-q_{in})/\mathcal N_i$ from (34). Fit separately for each forecast lead $k=t-h$:

$$
\widehat\theta_{ik}\in\arg\min_\theta
\frac{\sum_{n\in\mathcal D_{ik}^{=}}(y_n-x_n^\top\theta)^2
+\sum_{n\in\mathcal D_{ik}^{\le}}[x_n^\top\theta-u_n]_+^2}
{\max(1,|\mathcal D_{ik}^{=}|+|\mathcal D_{ik}^{\le}|)}
+\zeta\|\theta_{nonint}\|_2^2.
\tag{39}
$$

A training pair stores the features available at its forecast origin and the target subsequently observed at its delivery time. Fit only pairs whose outcomes have already been observed. The intercept is unpenalized.

$$
\widehat Q_{-i,t\mid h}^{FIT}
=\operatorname{clip}\left(\mathcal N_i x_{i,t\mid h}^{\top}\widehat\theta_{i,t-h},\
0,\ \sum_{j\ne i}(N_j+P_j)\right).
\tag{40}
$$

With fewer than 24 usable samples for a lead, use (37). Physical nameplate proxies need not bound every HSL observation; (40) is a chosen forecasting bound, while physical feasibility always uses actual $W$.

### 6.4 Dispatch under forecasts

The first comparison uses deterministic forecasts (36), (37), or (40). For uncertainty experiments, sample joint rival trajectories from empirical blocks of past forecast errors:

$$
Q_{-i,t\mid h}^{(m)}
=\operatorname{clip}\left(\widehat Q_{-i,t\mid h}+e_{it}^{(m)},0,
\sum_{j\ne i}(N_j+P_j)\right),\quad m=1,\ldots,M.
\tag{41}
$$

Residual blocks use exact-label forecast errors. If no complete 24-hour block exists, sample available exact residuals independently, centered by their training mean; if fewer than 24 residuals exist, use $e=0$. At $M=1$, set $e=0$.

Accepted export in each scenario is

$$
\widetilde q_{it}^{(m)}=
q_{it}^{(m)}\min\left(1,\frac{K}{q_{it}^{(m)}+Q_{-i,t\mid h}^{(m)}}\right),
\tag{42}
$$

with zero acceptance at zero total request. Executed discharge and SOC follow (13)–(19). Evaluate a common policy class $\mathcal P$:

$$
\widehat\mu_i\in\arg\max_{\mu\in\mathcal P}
\frac1M\sum_{m=1}^M\sum_{t\in\mathcal T_h}
\left[\pi_t^{view,h}\widetilde q_{it}^{(m)}
-c_i^{deg}\widetilde d_{it}^{(m)}
-\epsilon^{act}(c_{it}^{(m)}+d_{it}^{(m)}+r_{it}^{(m)})\right]\Delta t.
\tag{43}
$$

All scenarios use the same current action. Later actions can depend only on observations then available. Equations (42)–(43) require realized-dispatch rollouts; the existing owner LP does not directly optimize them.

An initial finite policy class uses price thresholds $p_L\le p_H$ and a congestion-response coefficient $\beta$. Given a forecast, define

$$
k_{it}^{target}=[K-\beta\widehat Q_{-i,t\mid h}]_+,
\tag{44}
$$

$$
c_{it}=\begin{cases}
\min(P_i,W_{it},(E_i-s_{it})/(\eta_c\Delta t)),&\pi_t\le p_L,\\0,&\text{otherwise},
\end{cases}
\tag{45}
$$

$$
d_{it}=\begin{cases}
\min(P_i,\eta_ds_{it}/\Delta t,k_{it}^{target}),&\pi_t>p_H,\\0,&\text{otherwise},
\end{cases}
\tag{46}
$$

$$
r_{it}=\min\left(W_{it}-c_{it},\ [W_{it}-c_{it}+d_{it}-k_{it}^{target}]_+\right).
\tag{47}
$$

Candidate rollouts violating (10) are excluded. The fallback return policy is

$$
c_{it}^{return}=\min\left(P_i,W_{it},\frac{[s_i^{tar}(h)-s_{it}]_+}{\eta_c\Delta t}\right),\qquad
d_{it}^{return}=0,\qquad r_{it}^{return}=W_{it}-c_{it}^{return}.
\tag{47a}
$$

It has zero requested export and restores the target whenever (9) permits it. All forecast treatments search the same candidates. Own-state and forecast updates within a rollout follow the same information timing as execution. This policy class measures forecast value at fixed controller complexity.

### 6.5 Comparisons and learning outcomes

| Treatment | Forecast | Dispatch and evaluation |
|---|---|---|
| ZERO | (36) | (43), same policy class |
| PERSIST | (37) | Same |
| FIT | (39)–(40) | Same |
| FIT-SCENARIO | (41), $M=16$ | Same causal policy class |
| ORACLE | True rival request trajectory supplied by the evaluator | Same controller; ideal plan-information benchmark |

First evaluate a single forecasting owner against four fixed reference policies. Fix the reference policy to the validation-selected persistence controller and preserve it across forecast treatments. Rotate the focal owner across all five farms. Then evaluate all five adapting together. ORACLE rollouts propagate the fixed opponents and their SOC conditional on each candidate focal policy. This supplies candidate-consistent rival trajectories.

The chronological split is March 1–31 for training (30 complete days), April 1–10 for validation (10 days), and April 11–30 for testing (20 days). March 9 is excluded. A common persistence-policy training run supplies the initial observation histories. Hyperparameters are selected on validation days. Frozen and online-updating test models are separate treatments.

For exact-label test observations,

$$
RMSE_i=\sqrt{\frac1{|\mathcal E_i|}\sum_{n\in\mathcal E_i}
(\widehat Q_{-i,n}-Q_{-i,n})^2}.
\tag{48}
$$

The evaluator also scores all test hours using private truth, separately from the observable-label score. Policy inputs never receive that truth.

$$
\Delta J_i^{FIT-PERSIST}=\frac1{|\mathcal L_{test}|}
\sum_{\ell\in\mathcal L_{test}}(J_{i\ell}^{FIT}-J_{i\ell}^{PERSIST}),
\tag{49}
$$

$$
E^{attempt}=\sum_tV_t\Delta t,\quad
E^{reject}=\sum_{t,i}(q_{it}-\widetilde q_{it})\Delta t,\quad
E^{through}=\sum_{t,i}(\widetilde c_{it}+\widetilde d_{it})\Delta t.
\tag{50}
$$

Report (48)–(50), total $J$, and paired day-level uncertainty intervals. Extensions to hidden SOC or policy learning use the same histories and physical equations after the simple forecast comparison.

## 7. Part II: single-farm reserve compliance

### 7.1 Farm, prices, and information

Choose $i^*=2$, `ANCHOR_WIND2`, from the existing five farms. Keep the $i^*$ subscript throughout. Use its actual $W_{i^*t}$, own COP forecast, the same HB_WEST prices, and all battery parameters and terminal rules from Sections 2–3.

Use a finite nonbinding limit compatible with the current episode loader:

$$
K_{single}=\max_{\ell,t}W_{i^*,\ell t}+P_{i^*}.
\tag{51}
$$

Then $V_t=0$, $z_{i^*t}=0$, and

$$
\widetilde q_{i^*t}=q_{i^*t},\quad
\widetilde c_{i^*t}=c_{i^*t},\quad
\widetilde d_{i^*t}=d_{i^*t},\quad
\widetilde r_{i^*t}=r_{i^*t}.
\tag{52}
$$

The shared-line constraint is inactive to isolate reserve compliance. A single farm still has a physical connection; a binding single-farm limit is an optional sensitivity using $K_{single}=\kappa^{single}N_{i^*}$.

| Quantity | Operator | Monitor |
|---|---|---|
| Prices and own wind | $P$ or $F$ view from Section 2.3 | Observed prices and operational records |
| True SOC | Observed | Accurate telemetry, observed after each interval |
| Reserve award and required duration | Observed | Observed |
| Reserve deficit | Known from own operation | Directly calculated from telemetry |
| Enforcement rule | Announced before the operating day | Selected or fixed before the day |

There is one operator and one monitor. The decision is additional high-price discharge that creates a true reserve deficit. SOC reports are accurate. The monitor records and enforces the obligation without an investigation or detection probability.

### 7.2 Ancillary-service commitment

Let $h_{i^*t}^{AS}$ be a fixed upward reserve commitment (MW), $\tau^{AS}$ its required delivery duration (h), and $\pi_t^{AS}$ its capacity payment ($/MW-h). Let $a_t^{AS}\in\lbrace0,1\rbrace$ indicate whether the obligation is active.

$$
h_{i^*t}^{AS}=a_t^{AS}\bar h_{i^*}^{AS},\qquad
\bar h_{i^*}^{AS}=\gamma^{AS}P_{i^*}.
\tag{53}
$$

There is no reserve deployment in the initial experiment. Energy needed to sustain the commitment is

$$
s_{i^*,t+1}^{req}=h_{i^*t}^{AS}\tau^{AS}/\eta_d.
\tag{54}
$$

This is the required post-interval SOC for maintaining the committed capability. Power headroom remains a hard constraint:

$$
d_{i^*t}+h_{i^*t}^{AS}\le P_{i^*}.
\tag{55}
$$

This conservative definition supplies the reserve through additional discharge, without counting cancellation of charging. The reserve commitment is fixed across the compliant and violation-permitted comparison.

Reserve revenue is

$$
R_{i^*}^{AS}=\sum_t\pi_t^{AS}h_{i^*t}^{AS}\Delta t.
\tag{56}
$$

### 7.3 True reserve deficit

Physical SOC limits (5) always hold. The reserve deficit is

$$
v_{i^*t}=[s_{i^*,t+1}^{req}-s_{i^*,t+1}]_+.
\tag{57}
$$

The compliant benchmark imposes

$$
s_{i^*,t+1}\ge s_{i^*,t+1}^{req}\qquad\forall t.
\tag{58}
$$

The violation-permitted case replaces (58) with (57). It retains all other physical, power-headroom, and terminal constraints.

A useful MW-equivalent shortfall is

$$
\delta h_{i^*t}^{AS}=\left[h_{i^*t}^{AS}-\frac{\eta_ds_{i^*,t+1}}{\tau^{AS}}\right]_+
=\frac{\eta_d}{\tau^{AS}}v_{i^*t}.
\tag{59}
$$

### 7.4 Enforcement and operator objective

Use one specified charge on reserve energy deficit-duration:

$$
F_{i^*}(\kappa^{res})=\kappa^{res}\sum_tv_{i^*t}\Delta t,
\tag{60}
$$

where $\kappa^{res}$ has units $/MWh-h. It is a chosen contractual enforcement parameter. Record reserve revenue (56) and enforcement cost (60) separately.

The operator's daily objective is

$$
\max_{c,d,r,s,v}\ U_{i^*}^{res}
=\sum_t(\pi_t^{RT}q_{i^*t}-c_{i^*}^{deg}d_{i^*t})\Delta t
+R_{i^*}^{AS}-F_{i^*}
-\epsilon^{act}A_{i^*}^{act},
\tag{61}
$$

subject to (1)–(10), (53)–(55), and either (58) or the epigraph

$$
v_{i^*t}\ge0,\qquad
v_{i^*t}\ge s_{i^*,t+1}^{req}-s_{i^*,t+1}.
\tag{62}
$$

For $\kappa^{res}=0$, calculate the exact deficit using (57) after solving; slack in an unpriced epigraph is not the measured deficit. At each replanning hour replace prices and wind by the selected view, retain actual SOC, and use the remaining sums in (61).

Since commitments are fixed, (56) is constant in the dispatch problem. It identifies the revenue attached to the obligation; (60) determines the marginal incentive to comply. The same terminal-return condition applies to all cases; no additional terminal salvage payment is introduced.

### 7.5 Monitor policy and outcomes

The initial monitor applies the announced $\kappa^{res}$ to the full SOC record. Compare a finite family of enforcement policies rather than selecting individual intervals for inspection:

$$
\kappa^{res}\in\mathcal K^{res}=\lbrace0,25,100,400\rbrace
\quad\text{dollars per MWh-h}.
\tag{63}
$$

For each policy, the operator solves (61). The monitor's outcomes are

$$
D_{i^*}^{res}=\sum_tv_{i^*t}\Delta t,\qquad
H_{i^*}^{viol}=\Delta t\sum_t\mathbf1(v_{i^*t}>\varepsilon^s),
\tag{64}
$$

$$
L_{i^*}^{AS}=\sum_t\delta h_{i^*t}^{AS}\Delta t,\qquad
C_M=\omega^{res}D_{i^*}^{res}.
\tag{65}
$$

$C_M$ is a reserve-shortfall loss measure; $\omega^{res}$ is a chosen valuation, not fine revenue. A monitor policy can be selected to meet a shortfall budget at the smallest charge:

$$
\kappa^{res,*}=\min\lbrace\kappa\in\mathcal K^{res}:
\frac1{|\mathcal L_{val}|}\sum_{\ell\in\mathcal L_{val}}
D_{i^*,\ell}^{res}(\kappa)\le\bar D^{res}\rbrace.
\tag{66}
$$

Write the set in (66) as empty if no candidate satisfies the target. Policy selection uses validation days; test outcomes are reported afterward. The base target is $\bar D^{res}=0$ up to the SOC tolerance; its numerical allowance is $T\Delta t\varepsilon^s$. Fixed-policy dispatch is an operator optimization problem with monitoring enforcement; (66) adds a restricted policy-design decision.

### 7.6 High-price incentive and comparisons

Suppose compliant dispatch ends an interval exactly at its reserve floor. Additional discharge $y$ MW creates deficit $y\Delta t/\eta_d$ MWh and immediate operating gain

$$
\Delta J_{i^*t}=(\pi_t^{RT}-c_{i^*}^{deg})y\Delta t.
\tag{67}
$$

If the deficit lasts only that interval, its charge is

$$
\Delta F_{i^*t}=\kappa^{res}\frac{y\Delta t}{\eta_d}\Delta t.
\tag{68}
$$

The immediate comparison is

$$
\pi_t^{RT}-c_{i^*}^{deg}>\kappa^{res}\Delta t/\eta_d.
\tag{69}
$$

The full optimizer also includes later deficits, wind recharge, power headroom, and terminal recovery. A discharge in the final hour that violates (10) is infeasible even when reserve violations are permitted.

Define high-price intervals for reporting by a training-sample threshold:

$$
p^{high}=\operatorname{Quantile}_{0.75}
(\pi_t^{RT}:\ell\in\mathcal L_{train}),\qquad
\mathcal H^{high}=\lbrace t:\pi_t^{RT}\ge p^{high}\rbrace,
\tag{70}
$$

$$
D_{i^*}^{high}=\sum_{t\in\mathcal H^{high}}v_{i^*t}\Delta t,
\qquad
\Delta J_{i^*}=J_{i^*}^{violation\ permitted}-J_{i^*}^{compliant}.
\tag{71}
$$

No constraint forces violations to occur only in high-price intervals; (70) measures whether they do.

| Case | Reserve energy condition | Enforcement |
|---|---|---|
| Energy-only reference | No reserve commitment | None |
| Compliant reserve | (58) hard | No deficit |
| Unenforced reserve | (57), violations permitted | $\kappa^{res}=0$ |
| Enforced reserve | (57), violations permitted | Positive values in (63) |

Use the same farm, days, initial SOC, battery parameters, and foresight in each matched reserve comparison. The energy-only case also removes reserve headroom (55), so its difference includes the cost of the commitment itself. Report $J_{i^*}$, $R^{AS}_{i^*}$, $F_{i^*}$, net monetary profit $J_{i^*}+R^{AS}_{i^*}-F_{i^*}$, and (64)–(71).

## 8. Parameters and provenance

### 8.1 Read directly from existing inputs

| Quantity | Current source | Use |
|---|---|---|
| $W_{it}$ | `data/processed/wind_hourly.parquet`, `W_avail` | Hourly available-wind input from SCED HSL |
| $\widehat W_{it}$ | `forecast_hourly.parquet`, `What_cop` | Own COP HSL forecast |
| $\pi_t^{RT},\pi_t^{DA}$ | `prices_hourly.parquet` | HB_WEST hourly prices |
| Resource identifier | `resources.csv`, `resource` | Match the same five operators |
| $b_{it}^{DAM}$ | `forecast_hourly.parquet`, `b_dam` | Provenance only |
| Metered generation / base point | `wind_hourly.parquet`, `W_out`, `basepoint_mean` | Historical diagnostics; not simulated rival requests |
| Calendar and timezone | Base configuration | March 1–April 30, 2025; US/Central |

SCED HSL is averaged to hourly availability; RT settlement prices are averaged to hourly prices. The 23-hour daylight-saving day is excluded, leaving 60 complete days. Dataset inputs describe wind capability and prices; simulated battery states and requested exports are generated by the model.

The current processed tables contain no farm-specific ancillary-service awards, ancillary-service payment series, reserve duration, or reserve-violation settlement schedule. Section 8.4 assigns these explicitly.

### 8.2 Derived or calibrated parameters

$$
N_i=\operatorname{Quantile}_{0.995}(W_{it}),\qquad
P_i=0.29N_i,\qquad E_i=1.5\,P_i.
\tag{72}
$$

The capacity proxy is computed over the existing data window and loaded from `resources.csv`. It is a fixed physical calibration in every treatment, not a forecast feature fitted on test outcomes.

| Farm | $N_i$ MW | $P_i$ MW | $E_i$ MWh | $s_{i0}$ MWh |
|---|---:|---:|---:|---:|
| ANCHOR_WIND1 | 16.000000 | 4.640000 | 6.960000 | 3.480000 |
| ANCHOR_WIND2 | 98.809500 | 28.654755 | 42.982133 | 21.491066 |
| ANCHOR_WIND3 | 88.801750 | 25.752508 | 38.628761 | 19.314381 |
| ANCHOR_WIND4 | 38.700000 | 11.223000 | 16.834500 | 8.417250 |
| ANCHOR_WIND5 | 19.275000 | 5.589750 | 8.384625 | 4.192313 |

Use full stored precision in computation.

| Parameter | Value | Calibration basis |
|---|---|---|
| Battery/wind power ratio | 0.29 | Existing Anchor co-located storage calibration |
| Battery duration | 1.5 h | Existing Anchor storage calibration |
| $\eta_c,\eta_d$ | 0.922, 0.922 | Existing literature-calibrated efficiency; product 0.850084 |
| $c_i^{deg}$ | $10/MWh discharged | Existing literature-calibrated dispatch cost |
| $\widehat\theta_{ik}$ | Estimated by (39) | Past observable training pairs only |
| $p^{high}$ | Training RT-price 75th percentile | (70) |
| Predictor residual blocks | Training/available past residuals | (41) |

### 8.3 Existing chosen and numerical parameters

| Parameter | Existing value | Role in extensions |
|---|---|---|
| $N$ | 5 | Part I unchanged; Part II selects $i^*=2$ |
| $T,\Delta t$ | 24, 1 h | Both unchanged |
| Initial SOC fraction | 0.5 | Both unchanged |
| Terminal condition | Return lower bound with (9) | Both unchanged |
| Grid charging | Disabled | Both unchanged |
| $\kappa_K$ | 0.6 | Part I unchanged |
| $K=0.6\sum_iN_i$ | 156.951750 MW | Shared Part I limit |
| $\lambda^+$ | $100/MWh in existing run | $0 in primary extensions; $100 legacy sensitivity |
| Overflow shares | EQ, INJ | Legacy / positive-charge sensitivity |
| $\epsilon^{act}$ | $0.001/MWh | Same numerical activity term |
| Best-response damping $\alpha$ | 0.5 | Existing informed game only |
| Maximum sweeps | 200 | Existing informed game only |
| Residual trigger | $10^{-5}\sum_iN_i$ MW | Existing payoff-check trigger |
| $\varepsilon^{gain}$ | $1 | Existing planning-game acceptance threshold |
| Gain-check interval | 5 sweeps | Existing game only |
| Warm start | Previous-hour tail | Existing informed solver |
| Base seed | 6974 | Common seed for paired simulations |
| Cycle / feasibility checks | $10^{-7}$ for simultaneous operation; POI $10^{-6}$ MW | Existing realization checks |

The generic synthetic `Episode.from_arrays` fallback uses different battery and POI ratios. All experiments in this document load `config/base.yaml` and the processed resource table.

### 8.4 Chosen extension parameters

| Parameter | Initial specification | Sensitivity / interpretation |
|---|---|---|
| Learning split | March 1–31 / April 1–10 / April 11–30 | 30 / 10 / 20 complete days; March 9 excluded |
| Part I observation delay | One interval for own accepted-export record | No current rival action signal |
| Resource-disclosure lag | 60 days | Historical information treatment |
| Initial normalized rival forecast $\bar y$ | 0.5 | Used until an exact aggregate observation |
| Forecast age cap | 168 h | Initial age 168 h |
| Price scale $p^{scale}$ | $100/MWh | Feature normalization |
| Training price quantiles | -26.660000, -0.816250, 16.332500, 34.285000, 154.617500 $/MWh | Threshold grid for (45)–(46) |
| High-price threshold $p^{high}$ | $34.285/MWh | Training 75th percentile |
| Ridge grid $\zeta$ | $10^{-4},10^{-2},1,100$ | Select on validation normalized forecast error |
| Minimum usable pairs per lead | 24 | Otherwise persistence |
| Training window | All prior available training pairs | Frozen and online tests separately |
| Scenario count $M$ | 1 primary; 16 uncertainty sensitivity | Deterministic first |
| Exact-residual minimum | 24 | Otherwise zero residual perturbation |
| Metering classification tolerance | $10^{-6}$ MW | Detect a strictly positive own export reduction |
| Residual-block length | 24 h | Preserve within-day dependence where exact labels are available; use observed consecutive blocks, not imputed truth |
| Policy price thresholds | Training price quantiles at 0, 0.25, 0.5, 0.75, 1; all ordered pairs | Same candidate set for every predictor |
| Congestion response $\beta$ | $0,0.5,1,1.5$ | (44) |
| Statistical comparison | 1,000 paired day-bootstrap replicates | 95% intervals; report daily samples |
| Monitor farm $i^*$ | ANCHOR_WIND2 | Battery parameters from Section 8.2 |
| $K_{single}$ | (51), 127.554755 MW using HSL maximum 98.9 MW | Nonbinding base; optional $\kappa^{single}=0.6,1,1.3$ |
| Reserve fraction $\gamma^{AS}$ | 0.2 | Sensitivity 0.1, 0.2, 0.3 |
| Reserve duration $\tau^{AS}$ | 1 h | Sensitivity 0.5, 1, 2 h; retain feasible hard-compliance cases |
| Active reserve hours $a_t^{AS}$ | 1 for all 24 intervals | Same obligation in compared reserve policies |
| Reserve capacity price $\pi_t^{AS}$ | $10/MW-h, constant | Chosen accounting input; sensitivities 0, 10, 30 |
| Enforcement $\kappa^{res}$ | $0,25,100,400 per MWh-h | Announced daily policy (63) |
| Monitor loss valuation $\omega^{res}$ | $100 per MWh-h | Chosen reporting valuation; same across policies |
| Policy shortfall target $\bar D^{res}$ | 0 up to tolerance | Validation selection in (66) |
| SOC measurement / violation tolerance $\varepsilon^s$ | $10^{-6}E_{i^*}$ MWh | Record raw deficit and tolerance-adjusted indicators |
| Reserve deployments | None | Readiness requirement during the active hours |
| SOC telemetry | Exact | No hidden state, inspection noise, or false reports |
| High-price reporting threshold | Training RT-price 75th percentile | Same threshold for all test policies |

For the selected farm, the base reserve parameters give

$$
\bar h_{i^*}^{AS}=5.730951\text{ MW},\qquad
s_{i^*,t+1}^{req}=6.215782\text{ MWh},
\tag{73}
$$

$$
R_{i^*}^{AS}=10\times5.730951\times24
=1375.42824\text{ dollars/day}.
\tag{74}
$$

Reserve prices, commitments, and charges above are experiment settings. They are not fitted from the current energy-market tables. When observed ancillary-service inputs are added, replace those settings and keep the equations and units unchanged.

### 8.5 Existing monitor module

The repository's separate forecast-residual monitor uses threshold grids, withholding fractions, discount 0.98, delays 1/4/12, and an enforceability function. Those parameters belong to its detection/deterrence calculation. Part II here instead uses observable reserve deficits and (60); it does not import those parameters.

## 9. Code and equation correspondence

| Source | Equations / role |
|---|---|
| `config/base.yaml` | Existing numerical and physical parameters |
| `code/wargame/model/env.py` | Data loading, farm construction, $K$, battery scaling |
| `code/wargame/model/physics.py` | (1)–(6), feasibility checks |
| `code/wargame/solvers/receding.py` | Foresight views, (9)–(10), actual-state feedback |
| `code/wargame/solvers/realize.py` | (11)–(21), battery-bound repair |
| `code/wargame/solvers/central.py` | (25)–(26) |
| `code/wargame/solvers/agent_lp.py` | (27), equal and injection-share best responses |
| `code/wargame/solvers/game.py` | (23), (28)–(30), cycle removal |
| `code/wargame/solvers/design_matrix.py` | (31), existing hourly dispatch execution |
| Proposed forecasting extension | (32)–(50), simultaneous owner actions and observable histories |
| Proposed reserve extension | (51)–(71), one selected farm and full-record enforcement |

The original 14-case outputs remain the baseline. New outputs should identify the objective, predictor, farm set, foresight view, connection limit, reserve commitment, and enforcement parameter so that each comparison changes only its named treatment.

## 10. First implemented learning experiment

`code/scripts/08_learning_experiment.py` implements the deterministic ZERO,
PERSIST, FIT and conditional ORACLE comparisons in Section 6. The five farms
rotate as focal operator against four fixed reference policies. The 30/10/20
chronological split, actual accepted-export objective, zero overflow charge,
censored forecast training and common threshold-policy class are used.

The threshold actions in (45)–(46) receive a common terminal-viability projection:

$$
L_{it}=\left[s_{i0}-\eta_c\Delta t\sum_{u=t+1}^{T-1}\min(P_i,W_{iu})\right]_+,
$$

$$
c_{it}\leftarrow\max\left(c_{it},\frac{[L_{it}-s_{it}]_+}{\eta_c\Delta t}\right),
\qquad
d_{it}\leftarrow\begin{cases}
0,&c_{it}>0,\\
\min(d_{it},\eta_d[s_{it}-L_{it}]_+/\Delta t),&c_{it}=0.
\end{cases}
$$

Charging is bounded by available wind, power, and battery headroom. The actual
SOC is at least the planned next SOC after a proportional cut cancels discharge,
so this projection preserves the daily return target during execution. It is
applied to reference opponents and all forecasting treatments.

The first experiment uses deterministic forecasts, frozen training coefficients,
and treatment-specific observable test histories. Scenario sampling, online
coefficient refitting, and simultaneous adaptation of all five controllers are
subsequent comparisons. Results and forecast errors at every lead are in
[`results/learning/report.md`](../results/learning/report.md).

## 11. Simultaneous aggregate learning

`09_simultaneous_learning.py` runs all five forecasting owners together. At each
hour, every owner selects its first action from its pre-action history; the five
actions are executed jointly. No within-hour best-response signal is exchanged.
The objective, controller and physical equations are those of Section 10.

The simultaneous cases are ZERO, PERSIST, FIT_FROZEN and FIT_ONLINE. Frozen
coefficients are the training fit selected in the original validation experiment.
For a test day $\ell$, online coefficients solve (39) using

$$
\mathcal D_{i,\ell}^{online}=\mathcal D_i^{train}
\cup\bigcup_{m<\ell,\ m\in\mathcal L_{test}}\mathcal D_{i,m}^{observable}.
$$

A forecast-origin sample enters this set only after its target interval has
finished. Daily refitting excludes the current day's observations. Physical SOC
resets each day; the observable request history and online dataset persist.
All methods start with the same training/validation pilot history. The results
use 20 paired test days and 1,000 day-bootstrap replicates with seed 6974.

See [`learning_simultaneous/report.md`](../results/learning_simultaneous/report.md).

## 12. Hidden rival SOC inference

`10_soc_learning.py` runs a separate particle-filter comparison after Section 11.
Each owner estimates four rivals' SOC and policy types. Own wind supplies a
correlated wind proxy; private rival wind and SOC enter only evaluator scores.

For particle $m$, rival $j$ and observing owner $i$, the wind model is

$$
e_{ij,t}^{(m)}=\rho^W e_{ij,t-1}^{(m)}+
\sigma^W\sqrt{1-(\rho^W)^2}\,\xi_{ij,t}^{(m)},\qquad \xi\sim\mathcal N(0,1),
$$

$$
W_{j,t}^{(m)}=N_j\operatorname{clip}\left(W_{it}/N_i+e_{ij,t}^{(m)},0,1.2\right).
$$

A particle contains $s_{j,t}^{(m)}$, wind error, and a threshold-policy index
$\theta_j^{(m)}$. The initial SOC is the known daily reset value $0.5E_j$.
Initial policy indices are uniform over finite threshold controllers from the
common candidate library. At each interval an index is replaced by another
uniform draw with probability $p^{change}$. The modeled policy is an approximation
to adaptive rivals. Within each particle, rival dispatch uses (44)–(47), the
terminal projection of Section 10, and the common realization map. SOC evolves as

$$
s_{j,t+1}^{(m)}=s_{jt}^{(m)}+\eta_c\widetilde c_{jt}^{(m)}\Delta t
-\widetilde d_{jt}^{(m)}\Delta t/\eta_d.
$$

Current owner actions in the filter update are the owner's actual chosen actions.
Future forecast rollouts use the particle policy model and the owner's known
wind trajectory. They return

$$
\widehat Q_{-i,t\mid h}^{SOC}=\sum_m\omega_{ih}^{(m)}Q_{-i,t\mid h}^{(m)}.
$$

Let $y_{it}$ be the exact inferred aggregate in (33), $u_{it}=K-q_{it}$ the upper
bound in (34), and $\sigma_i^{model}=\sigma^{obs}\sum_{j\ne i}N_j$. The likelihood is

$$
L_{it}^{(m)}\propto
\begin{cases}
\exp\left[-(y_{it}-Q_{-i,t}^{(m)})^2/(2(\sigma_i^{model})^2)\right],&\text{exact aggregate},\\
\Phi\left((u_{it}-Q_{-i,t}^{(m)})/\sigma_i^{model}\right),&\text{upper bound},\\
1,&\text{no informative own request}.
\end{cases}
$$

Here $\Phi$ is the standard-normal distribution function. Its scale represents
proxy-model error; own metering remains exact.

$$
\omega_{i,t+1}^{(m)}=
\frac{\omega_{it}^{(m)}L_{it}^{(m)}}{\sum_n\omega_{it}^{(n)}L_{it}^{(n)}},
\qquad ESS_{it}=\frac1{\sum_m(\omega_{it}^{(m)})^2}.
$$

Use systematic resampling when $ESS<M/2$. Resampling selects SOC, wind errors,
and policy indices together, then resets weights to $1/M$.

| Case | Observation conditioning | Rival SOC carried forward |
|---|---|---|
| SOC_PRIOR | No | Model transition |
| SOC_FILTER | Exact aggregate / bound likelihood | Posterior model transition |
| SOC_RESET | Same likelihood as SOC_FILTER | Reset to $0.5E_j$ each interval |
| PERSIST | Aggregate request persistence | No hidden-state model |
| FIT_FROZEN | Original fitted aggregate predictor | No hidden-state model |

All five owners act simultaneously in each case. The particle forecasts feed the
same candidate controller, so the contrasts isolate the forecasting model.

| Parameter | Value | Status |
|---|---|---|
| Particles per owner $M$ | 128 | Chosen |
| Wind error $\sigma^W$ | 0.15 in capacity-factor units | Chosen proxy uncertainty |
| Wind persistence $\rho^W$ | 0.8 | Chosen |
| Wind proxy clipping | $[0,1.2]$ times $N_j$ | Chosen |
| Likelihood scale $\sigma^{obs}$ | 0.05 of rival nameplate | Chosen model-error scale |
| Policy replacement probability | 0.05 per interval | Chosen |
| Resampling threshold | $M/2$ | Chosen |
| Seeds | 6974, 6975, 6976 | Declared before testing |
| Test dates | April 11–30, 2025 | Same 20-day split |

Score individual and aggregate SOC before the current action, excluding the known
hour-0 state. Compare SOC_FILTER with both SOC_PRIOR and SOC_RESET. Average seeds
within each operating day before paired economic bootstrap comparisons; calculate
prediction RMSE from seed-level errors before averaging.

See [`learning_soc/report.md`](../results/learning_soc/report.md). This experiment
estimates hidden rival storage states; the separate reserve-compliance model in
Section 7 is unchanged.

## 13. Direct battery control and reinforcement learning

`11_rl_dispatch.py` compares direct battery dynamic programming with independent
Double DQN. Both use signed battery commands

$$
a_{it}^{bat}\in\mathcal U=\lbrace-1,-0.75,-0.5,-0.25,0,0.25,0.5,0.75,1\rbrace.
$$

Battery commands are named `command` in the implementation.
A positive command discharges; a negative command charges. Before projection,

$$
c_{it}=\min\left([-a_{it}^{bat}]_+P_i,W_{it},\frac{E_i-s_{it}}{\eta_c\Delta t}\right),
\qquad d_{it}=[a_{it}^{bat}]_+P_i.
$$

Apply the terminal-viability projection in Section 10 and physical bounds.
Wind curtailment before the POI controller is

$$
r_{it}=\begin{cases}W_{it}-c_{it},&\pi_t<0,\\0,&\pi_t\ge0.\end{cases}
$$

All owners choose before joint realization. No extra overflow fee is charged.

### Dynamic-programming control

For an owner-specific rival forecast, write $\mathcal R_i$ for the own executed
export, discharge and next SOC under the common POI rule. With 81 equally spaced
SOC grid points, backward recursion is

$$
V_{i,t}(s)=\max_{a\in\mathcal U}\Big(
\left[\pi_t\widetilde q_{it}-c_i^{deg}\widetilde d_{it}
-\epsilon^{act}(c_{it}+d_{it}+r_{it})\right]\Delta t
+V_{i,t+1}(s')\Big),
$$

$$
(\widetilde q_{it},\widetilde d_{it},s')=
\mathcal R_i(s,a,W_{it},\widehat Q_{-i,t\mid h}),
\qquad
V_{iT}(s)=\begin{cases}0,&s\ge s_{i0},\\-\infty,&s<s_{i0}.\end{cases}
$$

Use linear interpolation between SOC grid values and execute only the first
command. DP_PERSIST and DP_FIT differ only in the aggregate rival forecast.
The implementation uses a finite terminal rejection value of $-10^9$ dollars;
executed terminal SOC is independently checked.

### Independent Double DQN

Each owner has its own 17-input, 48-hidden-unit tanh Q network and nine outputs.
Inputs contain own SOC, current and remaining own wind summaries, current and
remaining price summaries, time, battery/wind ratio, last inferred rival
request, and observation age. Cross-owner inputs and weights are separate.
DQN_NO_RIVAL masks the last-request and age inputs. DQN_HISTORY retains them.

The monetary reward is $R_{it}^{RL}=\pi_t^{RT}\widetilde q_{it}-c_i^{deg}\widetilde d_{it}$
for the one-hour interval. Training uses

$$
\bar R_{it}^{RL}=\frac{R_{it}^{RL}-B_{it}^{0}}{100N_i},\qquad
B_{it}^{0}=\pi_t^{RT}\min\left(W_{it},K\frac{N_i}{\sum_jN_j}\right).
$$

The baseline $B_{it}^{0}$ is independent of actions. Subtraction and positive
owner-specific scaling preserve each owner's expected-return ordering.
The state $o_{it}$ contains the owner's permitted observations. The target is

$$
y_{it}=\bar R_{it}^{RL}+\gamma(1-\mathrm{done}_t)
Q_{\theta_i^-}\left(o_{i,t+1},\arg\max_aQ_{\theta_i}(o_{i,t+1},a)\right).
$$

Minimize Huber loss with threshold 1 on $Q_{\theta_i}(o_{it},a_{it}^{bat})-y_{it}$.
Transitions contain actual simultaneous training interaction. Each owner updates
from its own reward and features. Replay does not include validation or
retrospective-evaluation days.

| Parameter | Value | Source |
|---|---|---|
| Hidden units | 48, tanh | Chosen |
| Replay size | 20,000 joint transitions, separate owner fields | Chosen |
| Batch size | 64 | Chosen |
| Optimizer | Adam; learning rate 0.001 | Chosen |
| Adam coefficients | 0.9, 0.999; denominator epsilon $10^{-8}$ | Chosen |
| Discount $\gamma$ | 1 | Daily finite horizon |
| Target refresh | Every 100 gradient updates | Chosen |
| Warmup | 256 transitions | Chosen |
| Updates | One per simulated hour | Chosen |
| Exploration | Linear decay 0.8 to 0.05 | Chosen |
| Training | 600 randomly sampled March episodes per seed and ablation | Existing training days |
| Validation | Every 100 episodes, April 1–10 | Existing validation days |
| Seeds | 6974, 6975, 6976 | Declared |
| Output | `results/learning_rl/` | Separate study |

Checkpoint selection uses validation system margin. April 11–30 was already
examined in earlier studies and is now retrospective evaluation. New data are
required for a fresh holdout estimate.

# Strategic Coordination in Co-Located Wind-Storage Systems

Part I of the 6.974 wargame project (MIT, Fall 2026): how much system value is lost when co-located wind-storage units that share one point of interconnection are operated by independent decision makers, and which parts of the operating design account for the loss.

## 1. The problem

### 1.1 Setting

$N = 5$ wind units, each with a co-located battery, share one point of interconnection (POI) with export limit $K$ and jointly owe a delivery obligation $D_t$ in every hour. Each unit sells its net injection at the real-time price. A unit that injects when the POI is already full displaces other units' energy; a unit that falls short of the obligation exposes everyone to a shortfall charge. The question is how much system value is lost when the five units are run by independent decision makers instead of one controller, and which features of the operating design account for the loss.

Units are indexed $i \in \mathcal{N} = \{1,\dots,N\}$, hours $t \in \mathcal{T} = \{1,\dots,T\}$ with $T = 24$; one operating day is one episode. Exogenous data:

| Symbol | Meaning | Source |
|---|---|---|
| $W_{it} \ge 0$ | available wind of unit $i$ in hour $t$ (MWh) | ERCOT SCED HSL |
| $\hat W_{it}$ | day-ahead forecast of $W_{it}$ | ERCOT COP HSL |
| $\pi_t$ | real-time price (\$/MWh), taken as given | ERCOT HB_WEST RTM SPP |
| $\hat\pi_t$ | day-ahead price (\$/MWh) | ERCOT HB_WEST DAM SPP |
| $N_i$ | nameplate of unit $i$ (MW) | ERCOT SCED |
| $K = \kappa_K \sum_i N_i$ | POI export limit (MW), $\kappa_K = 0.6$ | designed |
| $D_t = \delta_D \sum_i \hat W_{it}$ | system delivery obligation (MWh), $\delta_D = 0.5$ | designed |
| $D_{it} = \delta_D \hat W_{it}$ | unit $i$'s share of the obligation | designed |
| $\lambda^-, \lambda^+$ | shortfall and overflow penalty rates, 250 and 100 \$/MWh | designed |
| $E_i, P_i$ | battery energy (MWh) and power (MW) of unit $i$ | observed Anchor BESS, scaled |
| $\eta_c = \eta_d = \sqrt{0.85}$ | charging and discharging efficiency | NREL ATB |
| $c_{\mathrm{deg}} = 10$ | degradation cost per MWh discharged | literature |
| $s_i^0 = 0.5 E_i$ | initial state of charge | designed |

### 1.2 Decisions and physics

Unit $i$ chooses curtailment $r_{it}$, charging $c_{it}$ and discharging $d_{it}$, all non-negative. Net injection and aggregate injection are

$$q_{it} = W_{it} - r_{it} - c_{it} + d_{it}, \qquad Q_t = \sum_{i \in \mathcal{N}} q_{it}.$$

The feasible set $\mathcal{X}_i$ of unit $i$ is

$$s_{i,t+1} = s_{it} + \eta_c c_{it} - d_{it}/\eta_d, \quad 0 \le s_{it} \le E_i, \quad 0 \le c_{it}, d_{it} \le P_i, \quad 0 \le r_{it} \le W_{it}, \quad s_{i,1} = s_i^0, \quad s_{i,T+1} \ge s_i^0 .$$

Charging from the grid is allowed ($q_{it} < 0$ is feasible). The energy profit of unit $i$ is

$$\Pi_i = \sum_t \left[\pi_t q_{it} - c_{\mathrm{deg}}\, d_{it}\right].$$

### 1.3 Shared constraints

System shortfall and overflow in hour $t$ are

$$V_t^- = (D_t - Q_t)^+, \qquad V_t^+ = (Q_t - K)^+ .$$

Shortfall costs $\lambda^- V_t^-$. Overflow cannot physically occur; the charge $\lambda^+ V_t^+$ exists only in the units' planning problems, as the anticipated cost of being cut at the POI.

### 1.4 Realization and the system objective

Every operating policy is executed hour by hour: at hour $t$ the decision makers solve over $\{t,\dots,T\}$, submit the hour-$t$ actions, and the actions pass through a map $\Phi$ that enforces the physics. Actions are clipped to the battery bounds; if $Q_t > K$, the excess is removed from the positive injectors in proportion to $q_{it}^+$, first by curtailing wind and then by reducing discharge (the energy stays in the battery). Realized quantities $\tilde q_{it}, \tilde d_{it}, \tilde Q_t$ satisfy $\tilde Q_t \le K$ in every hour. The realized system objective is

$$J = \sum_t \left[\pi_t \tilde Q_t - c_{\mathrm{deg}} \sum_i \tilde d_{it} - \lambda^- (D_t - \tilde Q_t)^+\right].$$

Every comparison in this project is a difference in $J$ between two operating designs on the same 60 days.

## 2. What we vary

Four dimensions of the operating design are varied; everything else (site, data, battery, $K$, $D_t$, penalty rates) is held fixed.

| Dimension | Options | What it decides |
|---|---|---|
| F1 control | C, D | one controller for all units, or one decision maker per unit |
| F2 foresight | P, F | whether future wind and prices are known or forecast |
| F3 penalty allocation | EQ, INJ | how the system penalties are divided among units |
| F4 market information | FULL, PRICE, NONE | what a unit knows about the other units when it decides |

F3 and F4 only exist under decentralized control, so F1 = C is crossed with F2 only.

## 3. The options in each dimension

### 3.1 F1 control

**C, centralized.** One planner solves

$$
\begin{aligned}
\max_{(r,c,d) \in \prod_i \mathcal{X}_i} \quad & \sum_{i} \Pi_i - \lambda^- \sum_t V_t^- \\
\text{s.t.} \quad & Q_t \le K \quad \forall t .
\end{aligned}
$$

This is a linear program. Its multiplier $\mu_t^\star \ge 0$ on $Q_t \le K$ is the shadow price of POI capacity in hour $t$. Its realized value $J^{\mathrm{C}}$ is the benchmark.

**D, decentralized.** Unit $i$ chooses $x_i = (r_i, c_i, d_i) \in \mathcal{X}_i$ to maximize its own payoff $u_i(x_i, x_{-i})$, whose form is set by F3. The POI limit is not a constraint of unit $i$; it enters only through the overflow charge. A strategy profile $x^\star$ is a pure-strategy Nash equilibrium if

$$u_i(x_i^\star, x_{-i}^\star) \ge u_i(x_i, x_{-i}^\star) \qquad \forall x_i \in \mathcal{X}_i,\ \forall i \in \mathcal{N}.$$

The strategic loss of a profile $x$ is $J^{\mathrm{C}} - J(x)$ and the price of anarchy is $J^{\mathrm{C}} / J(x^\star)$. How the units reach a profile depends on F4.

### 3.2 F2 foresight

At hour $t$ a decision maker's information about wind and prices is one of

$$\mathcal{I}^{\mathrm{P}}_t = \{W_{i\tau}, \pi_\tau : \tau \ge t\}, \qquad
\mathcal{I}^{\mathrm{F}}_t = \{W_{it}, \pi_t\} \cup \{\hat W_{i\tau}, \hat\pi_\tau : \tau > t\}.$$

**P, perfect.** The remaining hours' realized wind and real-time prices are known. This is the upper bound on forecast quality.

**F, forecast.** Only the current hour is known; later hours use the ERCOT COP wind forecast and the day-ahead price. Under F the plans the units see, the prices the coordinator computes and the obligation $D_{it}$ are all built from forecasts, and realization uses the true $W_{it}$ and $\pi_t$.

### 3.3 F3 penalty allocation

**EQ, equal shares.** Each unit pays $1/N$ of each system penalty:

$$u_i^{\mathrm{EQ}} = \Pi_i - \frac{\lambda^-}{N} \sum_t V_t^- - \frac{\lambda^+}{N} \sum_t V_t^+ .$$

**INJ, causal shares.** Each unit pays the shortfall rate on its own deficit and a share of the system overflow proportional to its positive injection:

$$u_i^{\mathrm{INJ}} = \Pi_i - \lambda^- \sum_t (D_{it} - q_{it})^+ - \lambda^+ \sum_t \frac{q_{it}^+}{\sum_j q_{jt}^+}\, V_t^+ ,$$

with the overflow share set to $1/N$ when $\sum_j q_{jt}^+ = 0$. The overflow shares sum to one under both rules, so overflow charges add up to the system overflow penalty. Under INJ the shortfall charges sum to at least the system shortfall penalty and never to a multiple of it. The INJ overflow charge is convex in $q_{it}$, so each unit's problem remains a convex program.

When a unit cannot observe $Q_t$ (F4 = PRICE or NONE), it cannot compute $V_t^\pm$ and anticipates its shortfall charge from its own deficit, with weight $w_i^- = 1$ under INJ and $w_i^- = 1/N$ under EQ.

### 3.4 F4 market information

**FULL.** Unit $i$ observes the other units' plans $x_{-i}$ and best-responds: $x_i \in \arg\max_{x_i \in \mathcal{X}_i} u_i(x_i, x_{-i})$. The equilibrium is computed by damped Gauss–Seidel best-response iteration (damping 0.5, at most 200 sweeps). A profile is accepted when the undamped best-response residual is below $10^{-5} \sum_i N_i$ and the largest unilateral deviation gain is at most \$1.

**PRICE.** Unit $i$ observes only a congestion price vector $\mu \in \mathbb{R}_+^T$ announced by a coordinator who observes only $Q_t$. The price replaces the overflow charge:

$$x_i(\mu) \in \arg\max_{x_i \in \mathcal{X}_i} \ \sum_t \left[(\pi_t - \mu_t)\, q_{it} - c_{\mathrm{deg}}\, d_{it}\right] - w_i^- \lambda^- \sum_t (D_{it} - q_{it})^+ .$$

The coordinator iterates $\mu_t \leftarrow \left[\mu_t + \rho\,(Q_t(\mu) - K)\right]^+$ with $\rho = 0.2$ \$/MWh per MW until $\max_t (Q_t - K)^+ \le 10^{-3} \sum_i N_i$ and $\max_t \mu_t (K - Q_t)^+ \le 1$ \$, or 60 iterations. The unit responses carry a quadratic proximal term $\tfrac{\tau}{2}\|q_i - q_i^{\mathrm{prev}}\|^2$, $\tau = 2.0$, which is a numerical device for the fixed-point computation and not part of the payoff. If the units' shortfall terms coincided with the central one, this would be the Lagrangian decomposition of a linear program and the fixed point at $\mu = \mu^\star$ would reproduce the centralized dispatch; with the private shortfall charges above, the fixed point approximates it.

**NONE.** Unit $i$ observes nothing about the others and limits itself to a fixed share of the POI:

$$x_i \in \arg\max_{x_i \in \mathcal{X}_i} \ \Pi_i - w_i^- \lambda^- \sum_t (D_{it} - q_{it})^+ \quad \text{s.t.} \quad q_{it} \le K\, \frac{N_i}{\sum_j N_j} \ \ \forall t .$$

## 4. The simulations

Crossing the options gives $2 + 2 \times 2 \times 3 = 14$ operating designs, each run on the same 60 ERCOT days. Cell identifiers follow `C_<F2>` and `D_<F2>_<F3>_<F4>`:

| F2 | C | INJ, FULL | INJ, PRICE | INJ, NONE | EQ, FULL | EQ, PRICE | EQ, NONE |
|---|---|---|---|---|---|---|---|
| P | `C_P` | `D_P_INJ_FULL` | `D_P_INJ_PRICE` | `D_P_INJ_NONE` | `D_P_EQ_FULL` | `D_P_EQ_PRICE` | `D_P_EQ_NONE` |
| F | `C_F` | `D_F_INJ_FULL` | `D_F_INJ_PRICE` | `D_F_INJ_NONE` | `D_F_EQ_FULL` | `D_F_EQ_PRICE` | `D_F_EQ_NONE` |

Reading a cell: `D_F_INJ_PRICE` is decentralized control, forecast foresight, causal penalty shares, and units that see only the coordinator's price.

Let $J^{\mathrm{cell}}_\omega$ be the realized objective of a cell on day $\omega$ and $\bar J^{\mathrm{cell}}$ its mean over the 60 days. Each dimension is measured by differences between cells that differ in that dimension only:

$$
\begin{aligned}
\text{F1:}\quad & \Delta_1 = \bar J^{\mathrm{C}_f} - \bar J^{\mathrm{D}_{f,a,m}} && \text{for each } f \in \{P,F\},\ a \in \{INJ,EQ\},\ m \in \{FULL,PRICE,NONE\}, \\
\text{F2:}\quad & \Delta_2 = \bar J^{(\cdot)_P} - \bar J^{(\cdot)_F} && \text{for each of the 7 matched pairs}, \\
\text{F3:}\quad & \Delta_3 = \bar J^{\mathrm{D}_{f,INJ,m}} - \bar J^{\mathrm{D}_{f,EQ,m}} && \text{for each } (f,m), \\
\text{F4:}\quad & \Delta_4 = \bar J^{\mathrm{D}_{f,a,m}} - \bar J^{\mathrm{D}_{f,a,m'}} && \text{for } (m,m') \in \{(FULL,PRICE),(PRICE,NONE),(FULL,NONE)\} \text{ and each } (f,a).
\end{aligned}
$$

Each contrast is reported as a mean and median in \$/day and as the mean of the daily ratio $\Delta_\omega / J^{\mathrm{C_P}}_\omega$. The full implementation contract is in [docs/DESIGN.md](docs/DESIGN.md). The two-player case with a worked two-hour example is in [docs/two_player_formulation.md](docs/two_player_formulation.md).

## 5. Results by dimension

Percentages are means of the daily ratio to $J^{\mathrm{C_P}}$. All numbers below come from [`design_matrix_effects.csv`](results/tables/design_matrix_effects.csv); the figures are [`fig_design_matrix.png`](results/figures/fig_design_matrix.png) and [`fig_design_effects.png`](results/figures/fig_design_effects.png).

### 5.1 F1 control

Expected sign: C minus D is non-negative, because the central controller accounts for the shared POI and the shared obligation. Observed: C_P exceeds the mean of the six decentralized perfect-foresight cells by $1,101/day (median $473/day, 1.9% of C_P). All 12 matched central-minus-decentralized means are positive, and on no day does any decentralized cell exceed the central cell. The loss is smallest with causal penalty shares and price coordination (0.6%) and largest with equal shares and no information (3.3%).

### 5.2 F2 foresight

Expected sign: P minus F is non-negative. Observed: C_P exceeds C_F by $6,613/day (median $2,142/day, 11.1% of C_P). The seven matched differences range from $6,028 to $6,956/day, all positive. Foresight is the largest of the four factors by an order of magnitude.

### 5.3 F3 penalty allocation

Expected sign: INJ minus EQ is non-negative, because charging each agent for its own injection into an overflow and its own delivery deficit gives it a higher marginal cost of free riding than an equal split. Observed: under perfect foresight and full information the mean difference is $1,255/day (1.9% of C_P) but the median is $11/day. All six matched means are positive. The difference exceeds $100 on 28 of 60 days and is below -$100 on 14; the three largest days each contribute more than $9,000.

### 5.4 F4 market information

Expected signs: PRICE minus NONE and FULL minus NONE are non-negative. FULL minus PRICE has no expected sign, because the two cells differ in mechanism as well as in information. Observed, under perfect foresight and causal shares: PRICE exceeds NONE by $688/day and FULL exceeds NONE by $562/day; FULL is $126/day below PRICE. PRICE exceeds NONE in all four matched comparisons, FULL exceeds NONE in three of four, and PRICE exceeds FULL in all four. In FULL each agent best-responds to the others' plans and still injects into a congested hour whenever the price premium exceeds its marginal share of the overflow charge. In PRICE the coordinator raises the congestion price until the aggregate fits the POI, so the fixed point is close to the central solution.

## 6. Data

The operating window is 2025-03-01 through 2025-04-30. Sixty complete 24-hour days are evaluated; the 23-hour daylight-saving transition day is excluded. The base site is Anchor Wind, with five ERCOT wind resources, 262 MW calibrated aggregate nameplate, and an observed co-located 71.5 MW / 113 MWh battery used to calibrate storage ratios.

Observed inputs are HB_WEST day-ahead and real-time prices, SCED available wind, COP forecasts, DAM awards, ERCOT resource metadata, and EIA-860 assets. The system-level forecast-error snapshot used for monitor calibration covers publications from 2026-10-13 through 2026-10-20 because ERCOT retains those reports for only about eight days. Full provenance and references are in [docs/ASSUMPTIONS.md](docs/ASSUMPTIONS.md) and [data/processed/README.md](data/processed/README.md).

## 7. Repository layout

```text
config/                         Model and experiment configuration.
code/wargame/                   Importable data, model, solver, monitor, and experiment packages.
code/scripts/01_download_raw.py Download and cache the public source data.
code/scripts/02_build_dataset.py Build the common processed dataset.
code/scripts/05_monitor.py      Preliminary Part III monitor calibration.
code/scripts/06_make_report.py  Generate the Workshop 1 report.
code/scripts/07_design_matrix.py Run or summarize the 14-cell Part I matrix.
code/scripts/07b_tune_price_coordination.py Tune the PRICE fixed-point algorithm.
data/raw/                       Untouched downloads; never edit by hand.
data/interim/                   Cached per-day extracts.
data/processed/                 Common dataset and provenance README.
results/tables/design_matrix_*  Part I results and metadata.
results/figures/fig_design_*    Part I figures.
results/tables/trajectories/ Hourly dispatch for the plotted design-matrix day.
results/figures/monitor_*       Preliminary Part III monitor figures.
results/tables/monitor_*        Preliminary Part III monitor tables.
results/tables/price_tuning*    PRICE algorithm tuning grid.
docs/                           Design contract, assumptions, deviations, progress, and report.
tests/                          Offline synthetic pytest suite.
```

## 8. Reproduce

Create the environment with Python 3.11 or newer, then install the locked dependencies and package:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.lock.txt
.venv/bin/pip install -e code/
```

Run the current workflow from the repository root in this order:

```bash
.venv/bin/python code/scripts/01_download_raw.py --config config/base.yaml
.venv/bin/python code/scripts/02_build_dataset.py --config config/base.yaml
.venv/bin/python code/scripts/07_design_matrix.py --config config/base.yaml
.venv/bin/python code/scripts/05_monitor.py --config config/base.yaml
.venv/bin/python code/scripts/06_make_report.py --config config/base.yaml
```

Step 07 took 17 minutes with four workers (recorded in `results/tables/design_matrix_by_day.meta.json`). The processed data and the matrix tables are committed, so step 06 can be run on its own. Step 01 needs network access to ERCOT and EIA and is only needed to extend or refresh the data window.

## 9. Status and next steps

Part I and the preliminary monitor calibration for Part III are done. Part II and the rest of Part III have not started. Dated status, decisions, limitations, and next steps are in [docs/PROGRESS.md](docs/PROGRESS.md).

## 10. Conventions

- Use English in code, comments, documentation, and commit messages.
- Keep parameters in `config/base.yaml`; put scenario overrides in `config/scenarios/`.
- Never edit `data/raw/` by hand.
- Write a sibling `.meta.json` for every result table.
- Record departures from `docs/DESIGN.md` in `docs/DEVIATIONS.md` with a date and reason.
- Add offline synthetic tests under `tests/` and run `.venv/bin/pytest -q`.
- Use branches `part2/<topic>` and `part3/<topic>`; require one review before merging.
- Update `docs/PROGRESS.md` when a milestone changes status.

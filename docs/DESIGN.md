# Design Spec — Workshop 1 Testbed (6.974 Wargame)

Project: *Strategic Coordination, Learning, and Monitoring in Co-Located Wind–Storage Systems*
(Acevedo Villena, Saha, Wei). This file is the implementation contract for the Workshop 1 code.
Everything here was decided by the project lead; implementers should follow it and record any deviation in `docs/DEVIATIONS.md`.

## 0. Repository layout

```
6.974_wargame/
├── README.md                 how to install / run everything
├── requirements.txt          pinned in requirements.lock.txt ; venv in .venv/
├── config/
│   ├── base.yaml             all default parameters (empirical inputs vs designed wargame variables are labelled)
│   └── scenarios/*.yaml      optional site and experiment overrides
├── code/
│   ├── wargame/              importable package (`import wargame`, add code/ to sys.path or pip install -e code/)
│   │   ├── data/             ercot.py, eia.py, build_dataset.py   (raw -> processed)
│   │   ├── model/            physics.py (battery/POI), env.py (episode container, info masking)
│   │   ├── solvers/          central.py, agent_lp.py, game.py (best-response Nash), receding.py, design_matrix.py (cells), realize.py
│   │   ├── monitor/          calibration.py (forecast-error regimes), detection.py (q0,q1,F*,T*)
│   │   └── experiments/      design.py, metrics.py, io.py, plots.py
│   └── scripts/              numbered CLI entry points 01_download_raw.py ... 07_design_matrix.py
├── data/
│   ├── raw/                  untouched downloads (ercot/, eia/, nrel/); never edited by hand
│   ├── interim/              per-day extracted tables (parquet)
│   └── processed/            the common dataset (see §2) + data/processed/README.md provenance
├── results/
│   ├── tables/               csv summaries
│   ├── figures/              png/pdf
│   └── logs/                 run logs, timing, solver status
├── docs/
│   ├── proposal.tex          the project proposal (source of truth for notation)
│   ├── DESIGN.md             this file
│   └── workshop1/            report.md (+ slides material) for Workshop 1
└── tests/                    pytest unit tests (synthetic data; no network)
```

Python: `.venv/bin/python` (3.13). Libraries: numpy, pandas, scipy, cvxpy (default solver CLARABEL or HIGHS via scipy), matplotlib, pyyaml, gridstatus (ERCOT MIS access).

## 1. Data sources (all public, all verified reachable on 2026-10-20)

| Symbol | Source | Access (verified) | Notes |
|---|---|---|---|
| `pi_DA[t]` | ERCOT Historical DAM Settlement Point Prices (NP4-180-ER) | `gridstatus.Ercot().get_dam_spp(year)` → cols `Interval Start, Location, Location Type, Market, SPP` | use `Location == "HB_WEST"` (wind sites are in West zone); hourly |
| `pi_RT[t]` | ERCOT Historical RTM SPP (NP6-785-ER) | `get_rtm_spp(year)` → 15-min rows | average the four 15-min SPPs to hourly |
| `W[i,t]` (available wind, MW) | ERCOT 60-Day SCED Disclosure (NP3-965-ER), table `sced_gen_resource` | `get_60_day_sced_disclosure("YYYY-MM-DD")["sced_gen_resource"]`; date = operating day; keep `Resource Type == "WIND"`; cols `SCED Timestamp, Resource Name, QSE, DME, HSL, Base Point, Telemetered Net Output , Output Schedule, Telemetered Resource Status` (note trailing space in `Telemetered Net Output `) | 5-min rows → hourly mean. `HSL` = available power (what the wind could produce) ⇒ this is W. `Base Point` = dispatched; `HSL - Base Point` = observed curtailment (diagnostic only). |
| realized output | same table, `Telemetered Net Output ` | hourly mean | used for monitor calibration (actual vs. forecast) |
| `What[i,t]` (resource-level forecast) | ERCOT 60-Day COP Adjustment Period Snapshot | `get_cop_adjustment_period_snapshot_60_day(date)` → cols `Interval Start, Resource Name, QSE, Status, High Sustained Limit, ...` | QSE's own day-ahead-ish availability forecast of HSL; hourly |
| `b[i,t]` (DA award) | ERCOT 60-Day DAM Disclosure (NP3-966-ER), `dam_gen_resource` | `get_60_day_dam_disclosure(date)["dam_gen_resource"]`, cols `Interval Start, Resource Name, Resource Type, HSL, Awarded Quantity, Settlement Point Name, Energy Settlement Point Price` | most wind has no DAM award (NaN) → baseline rule: `b = Awarded Quantity` if > 0 else `b = What` (COP HSL). Store both. |
| forecast-error regimes (system/regional) | ERCOT Wind Power Production – Hourly Averaged Actual and Forecasted Values (NP4-732-CD) and by Geographical Region (NP4-742-CD) | MIS keeps only a rolling ~8-day window; snapshot already saved in `data/raw/ercot/wind_forecast_hourly/*.parquet` and `.../wind_forecast_region_hourly/*.parquet` (2026-10-13..20, one file per publish day, 24 publications/day, each 216 hourly rows: 48 h actual GEN + 168 h STWPF/WGRPP forecast) | build error-vs-horizon table: for each publication, horizon h = Interval Start − Publish Time; error = (STWPF − GEN)/HSL_SYSTEM_WIDE using the GEN that appears in later publications for the same interval. Columns: `GEN SYSTEM WIDE, STWPF SYSTEM WIDE, WGRPP SYSTEM WIDE, HSL SYSTEM WIDE`, and `GEN/STWPF/WGRPP LZ WEST` etc. |
| asset metadata | EIA-860 2023 | `https://www.eia.gov/electricity/data/eia860/archive/xls/eia8602023.zip` (verified 206 on range request). Sheets: `3_2_Wind_Y2023.xlsx`, `3_4_Energy_Storage_Y2023.xlsx`, `3_1_Generator_Y2023.xlsx` | TX wind nameplate for the selected plant (Horse Hollow, Callahan/Taylor County); distribution of BESS duration (MWh/MW) and BESS-to-wind power ratio for co-located TX hybrids (same Plant Code having both wind and storage) |
| battery tech params | NREL ATB 2024 utility-scale battery (cite), no download needed | round-trip efficiency 85 % ⇒ η_c = η_d = sqrt(0.85) ≈ 0.922; degradation cost C_deg = 10 $/MWh discharged, charged on `d` only rather than total charge-plus-discharge throughput | put values + citation in `config/base.yaml` |

Operating-day window: 2025-03-01 … 2025-04-30 (61 days; spring = high wind, frequent West-hub negative prices, strong price volatility). Prices for year 2025.

Wind resource pool (all 5-min SCED rows for these resources are kept in interim data). Real multi-unit plants whose units physically share one interconnection, registered partly under different QSEs. This is the empirical justification for "independently controlled co-located resources":

- Primary site (N = 5 agents, decided 2026-10-21): Anchor Wind. `ANCHOR_WIND1..5` (DME YENELT, Enel; ≈262 MW: sum of p99.5 nameplates over the window; 245.1 MW is the 2025-04-15 COP HSL used for the p_ratio calibration), a real wind plant with two observed co-located batteries `ANCHOR_BESS1/2` (71.5 MW / 113 MWh from the ERCOT COP snapshot) sharing the same POI; battery sizing in config is calibrated to this. Alternative sites in `config/scenarios/`: Vortex (4 units + observed 121.8 MW / 184 MWh BESS) and Horse Hollow (below, no observed storage).
- Secondary site: Horse Hollow. `HHGT_HHOLLOW1, HHGT_HHOLLOW2, HHGT_HHOLLOW3, HHGT_HHOLLOW4, HHGT_CALLAHAN` (DME YHHGT; QSEs QFPLE1/QFPL14/QFPLE3; ≈806 MW HSL max on 2025-04-15).
- Resource pool in the processed data (`data.pool` in `config/base.yaml`; correlations in `corr_matrix.csv`): `CAPRIDGE_CR1..CR3`, `ANCHOR_WIND1..5`, `VERAWIND_UNIT1..5`, `WHMESA_UNIT1, WHMESA_UNIT2_23, WHMESA_UNIT2_28, WHMESA_UNIT3_23, WHMESA_UNIT3_28`, `VORTEX_WIND1..4`, `LACY_CRK_UNIT1..4`, `CANYONWD_UNIT1..6`.
- Resource nameplate `N_i` := 99.5th percentile of hourly HSL over the window (robust to telemetry spikes); store also max.

## 2. Processed dataset (`data/processed/`)

- `prices_hourly.parquet`: index hourly `Interval Start` (tz US/Central, also store `t_utc`); cols `pi_DA, pi_RT` ($/MWh), `hub`.
- `wind_hourly.parquet`: long format `Interval Start, resource, W_avail (HSL mean), W_out (telemetered mean), basepoint_mean, curtail_obs = W_avail - basepoint_mean, n_5min`.
- `forecast_hourly.parquet`: `Interval Start, resource, What_cop (COP HSL), b_dam (Awarded Quantity, NaN if none), b_baseline` (rule above).
- `resources.csv`: `resource, site, dme, qse, nameplate_mw (p99.5), hsl_max, n_hours, coverage_frac, mean_cf`.
- `corr_matrix.csv`: pairwise Pearson correlation of hourly `W_avail` across the pool.
- `forecast_error_system.parquet`: `publish_time, interval_start, horizon_h, region, gen, stwpf, wgrpp, hsl, err_stwpf_norm, err_wgrpp_norm`.
- `forecast_error_resource.parquet`: `Interval Start, resource, What_cop, W_avail, err_norm = (W_avail - What_cop)/nameplate`.
- `episodes.parquet` (or a function): one episode = one operating day (24 hourly steps) × agent set; built on the fly by `wargame.model.env.build_episode(day, agents, cfg)` from the tables above.
- `README.md` in `data/processed/` documents every column, the source report, the download timestamp, and which quantities are *empirical* vs *designed* (K, D_t, information regime, monitoring thresholds, sanction duration, attack type are designed).

## 3. Physical and strategic model (hourly, Δt = 1 h)

Per agent i (wind + co-located battery with fixed E_i [MWh], P_i [MW]): decision c, d, r ≥ 0, with
`q = W - r - c + d`, SoC dynamics `soc[t+1] = soc[t] + eta_c*c - d/eta_d`, `0 ≤ soc ≤ E_i`, `0 ≤ c, d ≤ P_i`, `0 ≤ r ≤ W`,
`soc[0] = soc_init_frac*E_i`, terminal `soc[T] ≥ soc[0]` (config `terminal_soc: "return"`; alternative `"free"`).
Grid charging allowed by default (`allow_grid_charging: true`, i.e. q may be negative); if false add `c ≤ W - r`.
Simultaneous charge+discharge is not forbidden by an LP. A tiny configurable tie-break cost `eps_tiebreak_usd_per_mwh` on `c + d + r` (default 1e-3 $/MWh) selects curtailment over otherwise-free cycling; report simultaneous operation as a diagnostic.

Battery design (calibrated to the observed Anchor BESS and cross-checked with EIA-860 and LBNL ranges): `P_i = p_ratio * N_i`, `E_i = duration_h * P_i`, with `p_ratio = 0.29` and `duration_h = 1.5` in the headline matrix.

Shared POI: `Q[t] = Σ_i q[i,t]`; `K = kappa_K * Σ_i N_i` (designed, default kappa_K = 0.6 (designed stress level; 0.9 is the LBNL-anchored value, see docs/ASSUMPTIONS.md §4));
minimum delivery `D[t] = delta_D * Σ_i b[i,t]` (designed, default delta_D = 0.5).
Soft violations `Vminus = max(D - Q, 0)`, `Vplus = max(Q - K, 0)`; penalty prices `lambda_minus = 250 $/MWh` (≈ shortage charge), `lambda_plus = 100 $/MWh` (designed).

Settlement price for injections: `pi[t] = pi_RT[t]` (agents are price takers at RT; DA price is kept for descriptive statistics and for Workshop 2 DA/RT two-settlement extension).

Agent payoff: `U_i = Σ_t [ pi[t]*q[i,t] - C_deg*d[i,t] ]`, where degradation is charged on discharge `d` only, matching `agent_lp.py` and `central.py`. The coordinated variant is
`U_i_coord = U_i - Σ_t [ w^-_it*lambda_minus*Vminus_t + w^+_it*lambda_plus*Vplus_t ]`, where the penalty-share weights `w^-`, `w^+` are fixed by the F3 rule of the cell (section 4).

Physical realization layer (`solvers/realize.py`): whatever the agents *plan*, the POI controller cannot export more than K. Given planned q, realized injection `q_real = q - share_i * Vplus` with pro-rata (by q⁺) curtailment, SoC is re-simulated with the realized r (extra curtailment), and realized profit uses q_real. Report both *planned* violations (what the strategic layer attempted) and *realized* quantities. The central solution has Vplus = 0 by construction (hard constraint).

## 4. Design matrix (Part I headline experiment)

The headline experiment is a full factorial over four design factors.

- **F1 control:** `C` is centralized and `D` is decentralized. Central control is crossed only with foresight; penalty allocation and market information do not apply to it.
- **F2 foresight:** `P` uses true available wind and true RT prices throughout the remaining horizon. `F` uses true wind and RT price in the current hour and COP wind plus DA price thereafter.
- **F3 penalty allocation (D only):** `INJ` uses causal injection overflow shares and own-deficit shortfall charges; `EQ` uses equal shares.
- **F4 market information (D only):** `FULL` observes the other agents' current plans, `PRICE` observes only a coordinator's congestion price, and `NONE` observes neither.

The 14 canonical cells are `C_P`, `C_F`, followed by `D_{P|F}_{INJ|EQ}_{FULL|PRICE|NONE}` ordered by foresight, penalty share, and information. `experiments/design.py` provides this `CELL_ORDER` and the validating `parse_cell` function.

Every cell is an hourly receding-horizon policy. At hour `t`, each applicable decision maker solves over `t..T-1` with the selected information, only hour `t` is submitted, the joint action passes through `realize_hour`, and the realized SOC initializes hour `t+1`. An episode is one 24-hour operating day. The initial SOC is `soc0`, and every remaining-horizon optimization retains the existing `terminal_soc: return` constraint.

For `INJ`, the budget-balanced hourly overflow weight is

`w^+_it = q^+_it / Σ_j q^+_jt`

with a `1/N` fallback when the denominator is zero. Each agent's shortfall
charge is instead

`lambda_minus * (D_it - q_it)^+`, where `D_it = delta_D * b_it`.

Thus total INJ shortfall collection is
`lambda_minus * Σ_i (D_it-q_it)^+`, which is at least the system-shortfall
charge.
The optional `game.injection_shortfall: phi` setting charges a lagged scalar share
of the system shortfall on private deficits, but `own` is the default. Under `EQ`, both system-penalty
weights are always `1/N`.

In the FULL/INJ game, fix the other agents' plans and define
`P_t = Σ_{j != i} q^+_jt`, `S_t = Σ_{j != i} q_jt`, and
`c_t = P_t-S_t+K`. Agent i optimizes the exact causal overflow charge

`lambda_plus * q^+_it * (Q_t-K)^+ / (q^+_it+P_t)`.

The DPP-convex formulation uses `x_t >= q_it`, `x_t >= 0`,
`y_t = x_t+P_t`, and
`lambda_plus * pos(x_t-c_t+c_t*P_t*inv_pos(y_t))`. Clarabel solves these
causal conic best responses; all other agent models retain their existing LP
or QP solver. No lagged overflow weights enter the INJ game. Its deviation
check evaluates the same exact charge, so a converged INJ FULL cell is a Nash
equilibrium of the exact causal-share game rather than a linearized game. The
previous hour's plan tail still warm-starts the next hourly game. FULL/EQ
retains exact equal-weight system-shortfall and system-overflow terms.

Under PRICE, the overflow penalty is replaced by a congestion price: each agent solves with `beta_plus = 0`, `q_other = 0`, and the common nonnegative vector `mu`, with no private POI budget. Starting from the prior hour's price tail (zeros at hour 0), `q^0` is the unregularized response and iteration `k` uses the proximal response

`max u_i(q_i; mu^{k-1}) - (proximal_tau/2) * sum_t (q_it-q_it^{k-1})^2`.

The quadratic term is solely a numerical fixed-point device and is excluded from economic costs and reported objectives. A predictor-corrector evaluation of the same proximal QPs damps the otherwise neutral primal-dual oscillation (documented in `DEVIATIONS.md`). The corrected aggregate updates

`mu^k_t = max(0, mu^{k-1}_t + rho_k * (Q_t - K))`, with constant `rho_k = rho` by default; `step_decay: sqrt` selects `rho/sqrt(k)` as an option.

The coordinator stops when `max_t (Q_t-K)^+ <= overflow_tol_rel * ΣN`, `max_t mu_t * (K-Q_t)^+ <= cs_tol`, and either the infinity-norm price change is at most `$0.01/MWh` or the aggregate-injection change is within the overflow tolerance, or after `max_iterations`. It retains the last iterate on convergence; otherwise it retains the iterate with the smallest maximum overflow, breaking ties by the larger sum of agent objectives. The grid-selected defaults are `proximal_tau = 2.0`, constant `rho = 0.2`, 60 iterations, relative overflow tolerance `1e-3`, complementary-slackness tolerance `$1/hour`, and hourly price-tail warm starts. Per-hour diagnostics include iterations, convergence, final maximum overflow, and final maximum `mu`; by-day metrics include `price_converged_hours_frac`. The realization layer still applies pro-rata cuts to any remaining attempted overflow.

Under NONE, agent `i` has the fixed private budget `B_i = K * N_i / Σ_j N_j` in every remaining hour; the current-hour lower floor accounts for feasible grid charging as in `_budget_vector`. PRICE and NONE agents cannot compute system shortfall. They instead optimize against private shortfall `D_it`: the shortfall penalty weight is exactly 1 under INJ (the agent pays what it causes) and `1/N` under EQ (the anticipated equal split). This follows from the allocation rule and is not a tuning parameter.

Penalty allocations reported in the results are computed ex post from realized quantities. The primary per-agent fields use the cell's F3 rule; central cells use INJ as primary and also report the EQ allocation. INJ shortfall charges are `Σ_t lambda_minus (D_it-q_tilde_it)^+`, exactly what each agent pays under the own-deficit rule. EQ shortfall charges remain `Σ_t (1/N) lambda_minus Vminus_t`. Overflow allocation is unchanged at `Σ_t w^+_it lambda_plus Vplus_attempted_t` and remains budget balanced. Metrics add `per_agent_penalty_minus`, `per_agent_penalty_plus`, `per_agent_net_profit` (energy profit less allocated shortfall penalty), and `penalty_concentration`, the largest agent share of total shortfall charges (or `1/N` when the total is zero). System objective `J = profit - lambda_minus * Σ_t Vminus_t` is unchanged.

`code/scripts/07_design_matrix.py` writes `design_matrix_by_day.csv`, `design_matrix_summary.csv`, `design_matrix_effects.csv`, and `design_matrix_pivot.csv` under `results/tables/`, plus `design_<day>_<cell>.csv` trajectories. It writes `fig_design_matrix.png/.pdf`, `fig_design_effects.png`, and `results/logs/design_matrix.log`. Every CSV has the standard sibling metadata JSON.

## 5. Monitor calibration (Part III preliminary, Workshop 1 scope)

`monitor/calibration.py`: from `forecast_error_resource` (COP HSL vs realized HSL) and `forecast_error_system` (STWPF vs GEN by horizon) estimate the noise distribution of normalized error. Define three regimes by empirical σ: `low` (system-wide, h ≤ 6), `medium` (resource-level, COP), `high` (resource-level, worst-quartile hours or h ≥ 24). Output a table of σ, skew, kurtosis, empirical quantiles, and the Gaussian/t fit.

`monitor/detection.py`: signal `y = m + eps`, sanction if `y > tau`. Compute `q0(tau) = P(eps > tau)`, `q1(tau, m) = P(m + eps > tau)` both empirically (resampling the error sample) and under the Gaussian fit; ROC curves; `Delta_q = q1 - q0`. Strategic withholding `m` is specified in physical normalized units (fraction of nameplate), not as a multiple of each regime's σ; deterrence comparisons likewise use absolute normalized thresholds, while ROC threshold sweeps may remain in regime-specific σ multiples.
Deterrence: `F_star = g*(delta**(-d) - q1)/Delta_q` (one-shot deviation, gain g, discount δ per period, enforcement delay d); feasibility iff `F_star ≤ F_bar`. Finite-duration correction with per-period loss ℓ: deterred iff `g ≤ delta**d * ( q1*g + Delta_q * ell * Σ_{k=0}^{T-1} delta**k )`; `T_star` = smallest integer T satisfying this (∞ if never). Enforceability factor `kappa(sigma) = exp(-a*sigma)` applied to F. Produce grids over (σ regime, τ fraction, m fraction, δ, d) and figures: ROC by regime; F* vs σ for fixed τ; T* vs σ. Also an *empirical* check: inject withholding m into agent 1 of a decentralized FULL solution (reduce q by m MW for hours in the top-price quartile) and compute shortfall `z = b - q` with noise, to show how detection behaves with real baselines.

## 6. Experiments & outputs (`code/scripts/`)

1. `01_download_raw.py`: prices (2025), SCED/DAM/COP for every day in the window (skip if file exists), EIA-860 zip; writes per-day parquet into `data/interim/` (only WIND rows + the needed columns) and logs failures in `results/logs/download.log`. Must be resumable.
2. `02_build_dataset.py`: builds every table in §2 and `data/processed/README.md`.
3. `05_monitor.py`: §5 outputs → `results/tables/monitor_*.csv`, figures.
4. `06_make_report.py`: assembles the matrix-centered `docs/workshop1/report.md` and `.html`, including factor contrasts, solver diagnostics, operating metrics, and the illustrative trajectory.
5. `07_design_matrix.py`: runs the 14 cells and writes `design_matrix_by_day.csv`, `design_matrix_summary.csv`, `design_matrix_effects.csv`, `design_matrix_pivot.csv`, design trajectories, and design figures.
6. `07b_tune_price_coordination.py`: grid search over the PRICE coordinator parameters (`price_tuning.csv`).

Reproducibility: every script accepts `--config config/base.yaml` and optional `--scenario`; random seeds fixed; each results table gets a sibling `.meta.json` with git hash, timestamp, config hash.

## 7. Testing

`tests/` with synthetic cases: (i) battery dynamics feasibility; (ii) central LP equals brute force on a tiny instance; (iii) the best-response fixed point of `solve_game(..., share_rule=...)` passes the unilateral-deviation check; (iv) receding perfect-foresight central control equals the one-shot central LP, forecast views use the realized current hour, and `solve_cell` realizations never export above K for representative cells; (v) realization conserves energy; (vi) design-matrix cell parsing, share weights, exact causal charges, PRICE coordination, and every cell running; (vii) monitor formulas on closed-form Gaussian cases (q0 = 1-Φ(τ/σ)); (viii) data-build checks. `pytest tests/` must pass offline.

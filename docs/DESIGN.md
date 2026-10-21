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
│   └── scenarios/*.yaml      overrides for sensitivity runs
├── code/
│   ├── wargame/              importable package (`import wargame`, add code/ to sys.path or pip install -e code/)
│   │   ├── data/             ercot.py, eia.py, build_dataset.py   (raw -> processed)
│   │   ├── model/            physics.py (battery/POI), env.py (episode container, info masking)
│   │   ├── solvers/          central.py, game.py (best-response Nash), mpc.py (limited info), realize.py
│   │   ├── monitor/          calibration.py (forecast-error regimes), detection.py (q0,q1,F*,T*)
│   │   └── experiments/      run_regimes.py, sensitivity.py, metrics.py, plots.py
│   └── scripts/              numbered CLI entry points 01_download_raw.py ... 06_make_report.py
├── data/
│   ├── raw/                  untouched downloads (ercot/, eia/, nrel/) — never edited by hand
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
| `W[i,t]` (available wind, MW) | ERCOT 60-Day SCED Disclosure (NP3-965-ER), table `sced_gen_resource` | `get_60_day_sced_disclosure("YYYY-MM-DD")["sced_gen_resource"]`; date = **operating day**; keep `Resource Type == "WIND"`; cols `SCED Timestamp, Resource Name, QSE, DME, HSL, Base Point, Telemetered Net Output , Output Schedule, Telemetered Resource Status` (note trailing space in `Telemetered Net Output `) | 5-min rows → hourly mean. `HSL` = available power (what the wind could produce) ⇒ this is W. `Base Point` = dispatched; `HSL - Base Point` = observed curtailment (diagnostic only). |
| realized output | same table, `Telemetered Net Output ` | hourly mean | used for monitor calibration (actual vs. forecast) |
| `What[i,t]` (resource-level forecast) | ERCOT 60-Day COP Adjustment Period Snapshot | `get_cop_adjustment_period_snapshot_60_day(date)` → cols `Interval Start, Resource Name, QSE, Status, High Sustained Limit, ...` | QSE's own day-ahead-ish availability forecast of HSL; hourly |
| `b[i,t]` (DA award) | ERCOT 60-Day DAM Disclosure (NP3-966-ER), `dam_gen_resource` | `get_60_day_dam_disclosure(date)["dam_gen_resource"]`, cols `Interval Start, Resource Name, Resource Type, HSL, Awarded Quantity, Settlement Point Name, Energy Settlement Point Price` | most wind has no DAM award (NaN) → **baseline rule**: `b = Awarded Quantity` if > 0 else `b = What` (COP HSL). Store both. |
| forecast-error regimes (system/regional) | ERCOT Wind Power Production – Hourly Averaged Actual and Forecasted Values (NP4-732-CD) and by Geographical Region (NP4-742-CD) | MIS keeps only a rolling ~8-day window; snapshot already saved in `data/raw/ercot/wind_forecast_hourly/*.parquet` and `.../wind_forecast_region_hourly/*.parquet` (2026-10-13..20, one file per publish day, 24 publications/day, each 216 hourly rows: 48 h actual GEN + 168 h STWPF/WGRPP forecast) | build error-vs-horizon table: for each publication, horizon h = Interval Start − Publish Time; error = (STWPF − GEN)/HSL_SYSTEM_WIDE using the GEN that appears in later publications for the same interval. Columns: `GEN SYSTEM WIDE, STWPF SYSTEM WIDE, WGRPP SYSTEM WIDE, HSL SYSTEM WIDE`, and `GEN/STWPF/WGRPP LZ WEST` etc. |
| asset metadata | EIA-860 2023 | `https://www.eia.gov/electricity/data/eia860/archive/xls/eia8602023.zip` (verified 206 on range request). Sheets: `3_2_Wind_Y2023.xlsx`, `3_4_Energy_Storage_Y2023.xlsx`, `3_1_Generator_Y2023.xlsx` | TX wind nameplate for the selected plant (Horse Hollow, Callahan/Taylor County); distribution of BESS duration (MWh/MW) and BESS-to-wind power ratio for co-located TX hybrids (same Plant Code having both wind and storage) |
| battery tech params | NREL ATB 2024 utility-scale battery (cite), no download needed | round-trip efficiency 85 % ⇒ η_c = η_d = sqrt(0.85) ≈ 0.922; degradation/cycling cost C_deg = 10 $/MWh discharged (assumption, sensitivity 5–20) | put values + citation in `config/base.yaml`, flagged `source: calibrated_from_observed_colocated_bess` |

**Operating-day window**: 2025-03-01 … 2025-04-30 (61 days; spring = high wind, frequent West-hub negative prices, strong price volatility). Prices for year 2025.

**Wind resource pool** (all 5-min SCED rows for these resources are kept in interim data). Real multi-unit plants whose units physically share one interconnection, registered partly under different QSEs — this is the empirical justification for "independently controlled co-located resources":

- **Primary site (N = 5 agents, decided 2026-10-21): Anchor Wind** — `ANCHOR_WIND1..5` (DME YENELT, Enel; ≈262 MW: sum of p99.5 nameplates over the window; 245.1 MW is the 2025-04-15 COP HSL used for the p_ratio calibration), a real wind plant with two observed co-located batteries `ANCHOR_BESS1/2` (71.5 MW / 113 MWh from the ERCOT COP snapshot) sharing the same POI; battery sizing in config is calibrated to this. Alternative sites in `config/scenarios/`: Vortex (4 units + observed 121.8 MW / 184 MWh BESS) and Horse Hollow (below, no observed storage).
- Secondary site: Horse Hollow — `HHGT_HHOLLOW1, HHGT_HHOLLOW2, HHGT_HHOLLOW3, HHGT_HHOLLOW4, HHGT_CALLAHAN` (DME YHHGT; QSEs QFPLE1/QFPL14/QFPLE3; ≈806 MW HSL max on 2025-04-15).
- Correlation pool (for ρ sensitivity, mixing units from different sites): `CAPRIDGE_CR1..CR3`, `ANCHOR_WIND1..5`, `VERAWIND_UNIT1..5`, `WHMESA_UNIT1, WHMESA_UNIT2_23, WHMESA_UNIT2_28, WHMESA_UNIT3_23, WHMESA_UNIT3_28`, `VORTEX_WIND1..4`, `LACY_CRK_UNIT1..4`, `CANYONWD_UNIT1..6`.
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

Battery design (designed scenario variable, calibrated to the observed Anchor BESS, cross-checked with EIA-860 and LBNL ranges): `P_i = p_ratio * N_i`, `E_i = duration_h * P_i`, defaults `p_ratio = 0.29`, `duration_h = 1.5`; sensitivity over {0.10, 0.29, 0.50} × {1.0, 1.5, 4.0} (see `config/base.yaml`).

Shared POI: `Q[t] = Σ_i q[i,t]`; `K = kappa_K * Σ_i N_i` (designed, default kappa_K = 0.6 (designed stress level; 0.9 is the LBNL-anchored value, see docs/ASSUMPTIONS.md §4));
minimum delivery `D[t] = delta_D * Σ_i b[i,t]` (designed, default delta_D = 0.5).
Soft violations `Vminus = max(D - Q, 0)`, `Vplus = max(Q - K, 0)`; penalty prices `lambda_minus = 250 $/MWh` (≈ shortage charge), `lambda_plus = 100 $/MWh` (designed).

Settlement price for injections: `pi[t] = pi_RT[t]` (agents are price takers at RT; DA price is kept for descriptive statistics and for Workshop 2 DA/RT two-settlement extension).

Agent payoff: `U_i = Σ_t [ pi[t]*q[i,t] - C_deg*d[i,t] ]`, coordinated variant
`U_i_coord = U_i - beta_minus[i]*lambda_minus*Vminus[t] - beta_plus[i]*lambda_plus*Vplus[t]`, `beta_i = N_i/Σ N` by default (config: `"capacity_share" | "equal" | "full"`).

**Physical realization layer** (`solvers/realize.py`): whatever the agents *plan*, the POI controller cannot export more than K. Given planned q, realized injection `q_real = q - share_i * Vplus` with pro-rata (by q⁺) curtailment, SoC is re-simulated with the realized r (extra curtailment), and realized profit uses q_real. Report both *planned* violations (what the strategic layer attempted) and *realized* quantities. The central solution has Vplus = 0 by construction (hard constraint).

## 4. Operating regimes (Part I, Workshop 1 scope)

| id | regime | information | solver |
|---|---|---|---|
| R1 | centralized oracle | full state, perfect foresight over the episode | one LP, hard `Q ≤ K`, soft D with lambda_minus |
| R1_f | forecast centralized | full state across agents; realised current-hour wind/RT price and COP-wind/DA-price forecasts thereafter | receding-horizon central LP over `t..T-1`; execute hour `t`, realize, and re-plan; the end-of-episode SoC target is unchanged |
| R2 | full-information selfish game | each agent sees everything (all W, SoC, prices) and others' current plans | Gauss–Seidel best response: agent i solves its LP given q_{-i}, payoff U_i_coord with `beta_plus` = **capacity share of λ⁺ penalty** and `beta_minus` = capacity share; iterate until max |Δq| < 1e-3·ΣN or 50 sweeps; damping 0.5. Also verify the fixed point is a Nash eq. by one final unilateral-deviation check (report max gain). Record non-convergence. |
| R2_f | forecast full-information game | all agents see one another's plans; current-hour own wind/RT price are realised and future own wind/price use COP/DA forecasts | re-run the remaining-horizon Gauss–Seidel game each hour, warm-started from the prior plan tail; execute and realize hour `t`; log sweeps by hour |
| R3 | coordinated decentralized game | as R2 plus a coordinator broadcast | R2 but `beta = full` (each agent internalizes the whole shared penalty) **and** a headroom price: the coordinator adds to each agent's objective `- mu[t]*q[i,t]` where `mu[t]` is the dual of `Q ≤ K` from R1 (price-based coordination). Report both sub-variants R3a (penalty only), R3b (penalty + dual price). |
| R4a | limited information — aggregate | agent i sees own state and the aggregate signal `headroom[t-1] = K - Q[t-1]`; by default, own future RT prices and W are perfect (`mpc.price_info = wind_info = perfect`) | receding-horizon MPC each hour: own LP over remaining horizon with a private POI budget `q[i,t] ≤ max(0, headroom[t-1]) + q_real[i,t-1]`-style estimate (persistence of last headroom) |
| R4b | limited information — local | as R4a but **no** aggregate signal; agent assumes a fixed POI budget `K * N_i/ΣN` | same MPC |
| R4a_f | forecast-information aggregate | R4a with DA prices for future RT prices and own COP HSL for future W; current-hour RT price and W are realized | same MPC |
| R4b_f | forecast-information local | R4b with the same forecast information as R4a_f | same MPC |

The factorial information matrix has rows `C` (central), `G` (full-information game), `A` (aggregate-headroom MPC), and `L` (local MPC), and columns `perfect` and `forecast`. Its canonical regime ordering everywhere is `R1, R1_f, R2, R2_f, R3a, R3b, R4a, R4a_f, R4b, R4b_f`; R3a/R3b remain additional perfect-foresight coordination rows outside the 4×2 matrix.

All decentralized regimes end with the realization layer. Metrics per episode and regime (`experiments/metrics.py`): system profit (realized), individual profit vector, wind curtailment MWh (planned & realized), battery throughput MWh, under-delivery MWh `ΣVminus`, POI violation attempted MWh `ΣVplus` and #hours, simultaneous charge/discharge hours, convergence info. Gaps: `strategic_gap = J_R1 - J_R2`; `info_gap_aggregate = J_R2 - J_R4a`; `info_gap_local = J_R2 - J_R4b`; `signal_value = J_R4a - J_R4b`; `forecast_gap_central = J_R1 - J_R1_f`; `forecast_gap_game = J_R2 - J_R2_f`; `forecast_gap_mpc = J_R4a - J_R4a_f`; `PoA = J_R1 / J_R2`; and `PoA_f = J_R1_f / J_R2_f`.

## 5. Monitor calibration (Part III preliminary, Workshop 1 scope)

`monitor/calibration.py`: from `forecast_error_resource` (COP HSL vs realized HSL) and `forecast_error_system` (STWPF vs GEN by horizon) estimate the noise distribution of normalized error. Define three regimes by empirical σ: `low` (system-wide, h ≤ 6), `medium` (resource-level, COP), `high` (resource-level, worst-quartile hours or h ≥ 24). Output a table of σ, skew, kurtosis, empirical quantiles, and the Gaussian/t fit.

`monitor/detection.py`: signal `y = m + eps`, sanction if `y > tau`. Compute `q0(tau) = P(eps > tau)`, `q1(tau, m) = P(m + eps > tau)` both empirically (resampling the error sample) and under the Gaussian fit; ROC curves; `Delta_q = q1 - q0`. Strategic withholding `m` is specified in physical normalized units (fraction of nameplate), not as a multiple of each regime's σ; deterrence comparisons likewise use absolute normalized thresholds, while ROC threshold sweeps may remain in regime-specific σ multiples.
Deterrence: `F_star = g*(delta**(-d) - q1)/Delta_q` (one-shot deviation, gain g, discount δ per period, enforcement delay d); feasibility iff `F_star ≤ F_bar`. Finite-duration correction with per-period loss ℓ: deterred iff `g ≤ delta**d * ( q1*g + Delta_q * ell * Σ_{k=0}^{T-1} delta**k )`; `T_star` = smallest integer T satisfying this (∞ if never). Enforceability factor `kappa(sigma) = exp(-a*sigma)` applied to F. Produce grids over (σ regime, τ fraction, m fraction, δ, d) and figures: ROC by regime; F* vs σ for fixed τ; T* vs σ. Also an *empirical* check: inject withholding m into agent 1 of the R2 solution (reduce q by m MW for hours in the top-price quartile) and compute shortfall `z = b - q` with noise, to show how detection behaves with real baselines.

## 6. Experiments & outputs (`code/scripts/`)

1. `01_download_raw.py` — prices (2025), SCED/DAM/COP for every day in the window (skip if file exists), EIA-860 zip; writes per-day parquet into `data/interim/` (only WIND rows + the needed columns) and logs failures in `results/logs/download.log`. Must be resumable.
2. `02_build_dataset.py` — builds every table in §2 and `data/processed/README.md`.
3. `03_run_regimes.py` — base case (Anchor Wind, 5 agents, defaults) for all days: all regimes → `results/tables/regimes_by_day.csv`, `regimes_summary.csv`, per-day trajectories for a few illustrative days in `results/tables/trajectories/`.
4. `04_sensitivity.py` — grid over kappa_K × agent sets (3 sets chosen from the pool at low / medium / high mean pairwise ρ, documented in `results/tables/agent_sets.csv`) × storage designs, on a 20-day subset (every 3rd day) → `results/tables/sensitivity.csv`.
5. `05_monitor.py` — §5 outputs → `results/tables/monitor_*.csv`, figures.
6. `06_make_report.py` — assembles `docs/workshop1/report.md` with the headline tables and figure links; figures via `experiments/plots.py` (matplotlib, one figure per file, labelled axes with units).

Reproducibility: every script accepts `--config config/base.yaml` and optional `--scenario`; random seeds fixed; each results table gets a sibling `.meta.json` with git hash, timestamp, config hash.

## 7. Testing

`tests/` with synthetic 2-agent, 6-hour cases: (i) battery dynamics feasibility; (ii) central LP equals brute-force on a tiny instance; (iii) best-response fixed point is a Nash eq. (unilateral deviation check); (iv) realization layer never exports above K and conserves energy; (v) monitor formulas on closed-form Gaussian cases (q0 = 1-Φ(τ/σ)). `pytest tests/` must pass offline.

# Project Progress

**Last updated: 2026-10-21**

Project: *Strategic Coordination, Learning, and Monitoring in Co-Located Wind–Storage Systems — A Computational Wargame* (MIT 6.974, Fall 2026).

| Part | Scope (docs/proposal.tex §4) | Status |
|---|---|---|
| I | Strategic operation and information: centralized vs. decentralized, information regimes, correlation and POI sensitivity | Workshop 1 benchmark done |
| II | Multi-agent reinforcement learning (CTDE vs. DTDE, local vs. aggregate observations) | Not started |
| III | Market monitoring, enforcement and resilience | Preliminary calibration done; adaptive monitoring and attacks not started |

## Workshop 1 status (proposal §6)

| # | Plan item | Status | Delivered by | Evidence |
|---|---|---|---|---|
| 1 | Reproducible public-data pipeline (ERCOT prices, 60-day DAM/SCED, wind forecasts, EIA-860, BESS parameters) | Done | `code/wargame/data/`, `code/scripts/01_*.py`, `02_*.py`, `data/processed/` | 61 calendar days (2025-03-01 to 04-30), 37-resource correlation pool, 11 processed files; EIA-860 and Anchor BESS metadata included. Caveat: system-level forecast errors are from the Oct 2026 snapshot |
| 2 | Prototype with 3–5 real wind series, fixed co-located batteries, one configurable POI | Done | `code/wargame/model/`, `config/base.yaml` | Base case Anchor Wind: 5 resources (262 MW), battery 0.29 power ratio / 1.5 h, kappa_K configurable; `tests/` offline suite (5 test files) |
| 3 | Centralized benchmark and decentralized full-information game | Done | `solvers/central.py`, `game.py`, `realize.py`; `03_run_regimes.py` | R1 and R2 on 60 complete days (`results/tables/regimes_by_day.csv`: 600 rows = 60 days x 10 regimes); R2 converges on 97% of days |
| 4 | Comparison of full, aggregate and local information | Done | `solvers/mpc.py`, `receding.py`; `matrix_summary*.csv` | 4x2 matrix (C/G/A/L x perfect/forecast) plus R3a/R3b, all 10 regimes on 60 days; `fig_info_matrix` |
| 5 | Sensitivity over wind correlation and POI tightness (profit, battery behaviour, POI violations) | Done | `04_sensitivity.py`, `results/tables/sensitivity*.csv` | 90 configurations (6 kappa_K x 3 correlation sets x 5 storage designs) x 20 days x 6 regimes = 10,800 rows |
| 6 | Preliminary monitor calibration from observed forecast errors | Partial | `code/wargame/monitor/`, `05_monitor.py` | 3 noise regimes, ROC (72 rows), deterrence grid F*/T* (144 rows). Static thresholds only; no adaptive policy, no attacks; system-level noise from a different period than the operating window |

## Key results so far

Source: `docs/workshop1/report.md` (base case: Anchor Wind, 60 days, kappa_K = 0.6; objective J = raw profit minus 250 $/MWh x under-delivery).

- **Strategic gap** (J_R1 − J_R2): mean $724/day (1.5% of J_R1) but median $193/day and maximum $9,588/day (2025-04-26); heavy-tailed. Source: gap table, "Headline results".
- **Information gap** (R2 − R4a): mean $2,459/day (4.7% of mean J_R1), about 3x the strategic gap; local-only gap is $2,389/day; the aggregate headroom signal is worth −$70/day on average, i.e. no gain. Source: gap table; `fig_regime_profit`, `fig_info_matrix`.
- **Forecast gap**: perfect vs. forecast foresight costs $6,613/day in the central regime (12.5% of J_R1), the largest single effect; correlates with daily max RT price (r = 0.83). Source: gap table; `fig_prices`.
- **Coordination mechanisms**: R3a (full exposure to shared penalties) recovers 93.5% of the strategic gap; R3b (R3a plus POI dual price) recovers only 45.9%, because the dual price acts as a tax without rebate. Source: "Headline results" text.
- **Sensitivity trends**: tightening kappa_K from 1.0 to 0.5 raises the strategic gap from 0.39% to 1.11% and the information gap from 3.99% to 6.18% of J_R1; higher wind correlation raises both gaps at kappa_K = 0.6 (strategic 0.33% to 0.76%, information 4.27% to 6.15%); the gap grows with storage duration (1 h 0.60%, 4 h 1.90%). Source: `sensitivity_summary.csv`; `fig_gaps_vs_kappa`, `fig_violations_vs_kappa`, `fig_storage_design`.
- **Information floor at kappa_K = 1.0**: the POI does not bind, yet the information gap remains 2.9–5.2% of J_R1, attributed to private delivery commitments D_i in limited-information regimes. Source: Sensitivity section.
- **Monitor calibration**: q0 = 0.087 / 0.270 / 0.364 (low / medium / high noise, 5% threshold) and q1 = 0.442 / 0.431 / 0.515 for 5% withholding; empirical AUC at m = 0.05: 0.74 / 0.56 / 0.54. Required F* exceeds the cap (3g) in 5 of 12 reported cells and T* ranges from 2 to 182 periods. Source: `monitor_regimes.csv`, `monitor_roc.csv`, `monitor_deterrence.csv`; `monitor_roc`, `monitor_Fstar_vs_sigma`, `monitor_Tstar_vs_sigma`.
- **Solver reliability**: best-response regimes converge in 89.2% of base-day runs; the largest remaining unilateral gain is $12.39 (0.02% of J_R1). Source: "What we learned".

## Decisions and deviations log

Sources: `docs/DEVIATIONS.md`, `docs/ASSUMPTIONS.md`.

- **2026-10-21 — Base site.** Anchor Wind (5 ERCOT units, 262 MW) is the base case: the only multi-unit plant with observed co-located storage on the same POI (ANCHOR_BESS1/2). Vortex and Horse Hollow are available as scenario overrides.
- **2026-10-21 — kappa_K.** Base changed 0.9 to 0.6. At 0.9 (the LBNL-anchored realistic value) the POI binds in only 18% of hours and R3a = R3b, R4a = R4b on most days; at 0.6 it binds in 49% of hours. 0.9 stays in the sensitivity grid.
- **2026-10-21 — Battery calibration.** p_ratio 0.29 and duration 1.5 h from the observed Anchor BESS (71.5 MW / 113 MWh vs. 245 MW wind); round-trip efficiency 85% (NREL ATB); degradation cost 10 $/MWh; SoC starts at 50% and must return to it; grid charging allowed.
- **2026-10-21 — Information matrix.** Own foresight (perfect vs. forecast, `_f`) and information about others (C/G/A/L) were separated into a factorial design after a diagnostic showed they were confounded.
- **2026-10-21 — Objective definition.** Realized system objective J = raw profit − lambda_minus x under-delivery; lambda_plus is excluded because the realization layer enforces K (pro-rata curtailment). `GameSolution.objective` follows this definition. All gaps lead with J; raw-profit gaps are reported alongside.
- **2026-10-21 — Convergence criteria.** Game convergence uses the undamped best-response residual (tol_rel 1e-5, max 200 sweeps) and requires the final unilateral deviation gain <= $1.
- **2026-10-21 — Solver review fixes.** R4 private shortfall weighted by beta_i (capacity share) to match R2 incentives; R4a hour-0 budget floor changed to avoid infeasibility after grid charging; `04_sensitivity.py` runs only non-forecast regimes (no `_f` gaps in the grid).
- **2026-10-21 — Forecast-error schema.** Forecasts are compared with latest-publication realised HSL (not GEN) normalised by regional max HSL, to avoid curtailment contamination; supersedes DESIGN.md §2 and §5.
- **2026-10-21 — Realization layer.** A `spill` diagnostic records the degenerate case where pro-rata curtailment is exhausted and a full battery cannot absorb the reduction; the hard POI limit and SoC bounds are preserved.

## Known limitations / open issues

- Single season (Mar–Apr 2025), single base site (Anchor Wind) and 60 episodes; sensitivity uses every 3rd day (20 days).
- System-level forecast-error sample comes from the October 2026 MIS snapshot (publications 2026-10-13 to 10-20), a different period than the 2025 operating window; the resource-level sample matches the window.
- Price-taking at RT: no endogenous prices, no two-settlement bidding.
- MPC regimes use deterministic COP/DA forecasts and *private* delivery commitments D_i, which drive much of the information gap; this partly reflects modelling choice rather than pure information.
- No outages, causal intent or attacks modelled; the monitor uses static thresholds.
- Best-response regimes do not converge on about 11% of runs (residual gains are small, <= $12.39); convergence does not imply system optimality.
- The strategic gap is heavy-tailed; a few days (e.g. 2025-04-26) dominate the mean.
- The R4a-beats-R2 days (12 of 60) are explained only associatively (less overflow and throughput).
- No MARL yet.

## Next steps

### Part II — MARL (RQ2)

1. Generalise the environment to a partially observable Markov game with local and aggregate observations (`K − Q_{t−1}`) — owner: TBD.
2. Implement CTDE and DTDE training on the same episodes, price/wind data and reward (objective J, realization layer) as Part I — owner: TBD.
3. Evaluate against R1/R2/R4a/R4b on held-out days; report "MARL recovery" of the strategic and information gaps — owner: TBD.
4. Diagnose learned behaviour (anti-coordination, synchronised charging, cycling) across correlation sets and kappa_K — owner: TBD.
5. Fix seeds, training budgets and checkpoints in config; log with `.meta.json` — owner: TBD.

### Part III — Monitoring, enforcement, resilience (RQ3)

1. Couple the monitor to simulated agent behaviour: injected withholding m in the episodes, measured q0/q1 per regime — owner: TBD.
2. Adaptive thresholds and finite correction windows; compare no correction, one-shot fine, finite T*, excessive punishment — owner: TBD.
3. Attack library: POI derating, biased headroom signal, communication loss — owner: TBD.
4. Defenses: forecast cross-checking, headroom broadcasts, minimum reserve/SoC rules, limits on simultaneous sanctions; report resilience loss — owner: TBD.
5. Resolve the forecast-error period mismatch (append new MIS snapshots or use resource-level noise only) — owner: TBD.

### Code to add

- `code/wargame/learning/` package (environment wrapper, CTDE/DTDE trainers, policies, evaluation).
- `code/scripts/07_marl.py` (train/evaluate), `08_monitor_adaptive.py`, `09_attacks.py`.
- Extend `config/base.yaml` with `learning:` and `attacks:` blocks; scenario overrides in `config/scenarios/`.
- Tests under `tests/` for the new modules (offline, synthetic); record deviations in `docs/DEVIATIONS.md`.

## How to update this document

Edit the status table, results and logs whenever a milestone changes, and bump the "Last updated" date in the same commit.

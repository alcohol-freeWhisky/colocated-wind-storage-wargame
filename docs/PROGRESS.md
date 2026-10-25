# Project Progress

Last updated: 2026-10-25

Project: *Strategic Coordination, Learning, and Monitoring in Co-Located Wind-Storage Systems: A Computational Wargame* (MIT 6.974, Fall 2026).

| Part | Scope | Status |
|---|---|---|
| I | Four-factor operating design: control, foresight, penalty allocation, and market information/coordination | Complete for Workshop 1 |
| II | Multi-agent reinforcement learning with CTDE and DTDE under partial observation | Not started |
| III | Market monitoring, enforcement, and resilience | Preliminary monitor calibration complete; adaptive monitoring and attacks not started |

## Workshop 1 status

| Item | Status | Evidence |
|---|---|---|
| Public-data pipeline | Done | ERCOT prices, SCED wind, COP forecasts, DAM awards, EIA-860 assets, and forecast-error samples in `data/processed/`; 60 complete days from 2025-03-01 through 2025-04-30 |
| Shared-POI physical model and realization layer | Done | Five Anchor Wind units, calibrated storage, hourly battery physics, hard realized POI limit, delivery obligation, and realized objective J |
| F1 control | Done | `C_P`, `C_F`, and all 12 matched decentralized cells in `design_matrix_by_day.csv`; F1 contrasts in `design_matrix_effects.csv` |
| F2 foresight | Done | Perfect and forecast receding-horizon policies for every matching control/mechanism cell; seven F2 contrasts |
| F3 penalty allocation | Done | Exact causal INJ overflow charge plus own-deficit shortfall charge versus EQ; six matched contrasts |
| F4 market information and coordination | Done | FULL best-response games, PRICE coordinator fixed points, and NONE fixed-budget policies; 12 pairwise contrasts |
| Full 2 by 7 matrix | Done | 840 day-cell rows, 14 summary rows, 39 matched contrasts, and two pivot rows in `results/tables/design_matrix_*.csv` |
| Report | Done | Matrix-centered `docs/workshop1/report.md` and `.html`, with factor tables, solver diagnostics, operating metrics, and an illustrative matrix trajectory |
| Preliminary monitor calibration | Done as Part III input | Three empirical noise regimes, ROC table, deterrence grid, and monitor figures from `code/scripts/05_monitor.py` |

## Key results

- F1 control: `C_P - mean(D_P_*)` is $1,101/day, with a $473/day median and a mean daily effect of 1.923% of C_P. All 12 matched central-minus-decentralized means are positive. Source: `results/tables/design_matrix_effects.csv`.
- F2 foresight: `C_P - C_F` is $6,613/day, with a $2,142/day median and a mean daily effect of 11.136% of C_P. All seven matched P-minus-F means are positive, from $6,028 to $6,956/day. Source: `results/tables/design_matrix_effects.csv`.
- F3 penalty allocation: `D_P_INJ_FULL - D_P_EQ_FULL` is $1,255/day, but its median is $11/day. All six mean contrasts are positive and several medians are near zero, so the effect is heavy-tailed. Source: `results/tables/design_matrix_effects.csv`.
- F4 information and coordination: under perfect foresight and INJ, PRICE-minus-NONE is $688/day, FULL-minus-NONE is $562/day, and FULL-minus-PRICE is -$126/day. PRICE exceeds NONE and FULL in all four held-fixed mean comparisons. FULL and PRICE differ in mechanism as well as information. Source: `results/tables/design_matrix_effects.csv`.
- Solver reliability: FULL games converge in 99.39% of evaluated hours with 5.61 mean sweeps/hour; PRICE coordination converges in 96.68% of hours with 21.38 mean iterations/hour. Across FULL day-cells, max_gain averages $0.53 and reaches $12.39. Source: `results/tables/design_matrix_by_day.csv`.
- Preliminary monitor calibration: at a 5% threshold and 5% withholding, q0/q1 are 0.087/0.442, 0.270/0.431, and 0.364/0.515 for low, medium, and high noise. Source: `results/tables/monitor_deterrence.csv`.

Percentages of C_P above are means of daily percentages.

## Superseded results (kept for reference)

- The R1 through R4b_f regime comparison is retained in `regimes_*.csv`, but it was superseded because control, foresight, penalty rules, and information were not separated cleanly.
- The old information matrix is retained in `matrix_summary*.csv`, but it was superseded because it did not cross the revised F3 and F4 levels.
- The kappa_K, wind-correlation, and storage-design grid is retained in `sensitivity*.csv`, but it was superseded as a headline result by matched contrasts in the full design matrix.

## Decisions and deviations log

Sources: `docs/DEVIATIONS.md`, `docs/ASSUMPTIONS.md`, and `config/base.yaml`.

- 2026-10-21, base site: Anchor Wind is the base case because it has five wind resources and observed co-located storage at the same site. Vortex and Horse Hollow remain scenario overrides.
- 2026-10-21, objective: realized J is energy profit less discharge-only degradation cost and the system under-delivery charge. Attempted-overflow penalties remain planning incentives because the realization layer enforces K.
- 2026-10-21, base POI: kappa_K is 0.6 as a designed stress level; 0.9 remains the empirically anchored comparison value in legacy work.
- 2026-10-25, revised Part I design: the headline experiment became a 14-cell factorial over F1 control, F2 foresight, F3 penalty allocation, and F4 market information/coordination. The earlier ad hoc regime list is now legacy.
- 2026-10-25, PRICE mechanism: the congestion price replaces the overflow penalty. Proximal responses use a predictor-corrector update with tau = 2.0, rho = 0.2, at most 60 iterations, relative overflow tolerance 1e-3, and complementary-slackness tolerance $1/hour.
- 2026-10-25, exact INJ charges: FULL/INJ best responses use the exact convex causal positive-injection overflow charge. INJ shortfall charges use each agent's own deficit, while EQ uses equal shares of system penalties.

## Known limitations

- The operating experiment covers one spring window, one base site, five units, and 60 daily episodes.
- System-level monitor noise is calibrated from an October 2026 rolling MIS snapshot, while the operating experiment uses March-April 2025. The resource-level forecast-error sample matches the operating window.
- Agents are price takers at RT; the model has no endogenous prices or two-settlement bidding.
- COP wind and DA price are deterministic forecasts within each receding-horizon solve.
- The obligation, POI stress level, and penalty rates are designed wargame quantities, not ERCOT tariff rules.
- FULL outcomes are approximate equilibria and PRICE outcomes are approximate coordinator fixed points. The report places convergence, work, and max_gain diagnostics beside every affected contrast.
- No outages, causal intent, adaptive monitoring, attacks, or MARL policies are modeled yet.

## Next steps

### Analytical check

1. Two-player analytical model: verify the hand-solved example numerically. Owner: TBD.

### Part II: MARL (RQ2)

1. Generalize the environment to a partially observable Markov game with local and aggregate observations (`K - Q[t-1]`). Owner: TBD.
2. Implement CTDE and DTDE training on the same episodes, prices, wind data, objective J, and realization layer as Part I. Owner: TBD.
3. Evaluate against the centralized and revised decentralized design cells on held-out days; report recovery relative to matched Part I gaps. Owner: TBD.
4. Diagnose learned behavior, including anti-coordination, synchronized charging, and cycling. Owner: TBD.
5. Fix seeds, training budgets, and checkpoints in config; log runs with `.meta.json`. Owner: TBD.

### Part III: monitoring, enforcement, and resilience (RQ3)

1. Couple the monitor to simulated agent behavior: inject withholding in the episodes and measure q0/q1 by regime. Owner: TBD.
2. Add adaptive thresholds and finite correction windows; compare no correction, one-shot fines, finite T*, and excessive punishment. Owner: TBD.
3. Add attacks: POI derating, biased headroom signals, and communication loss. Owner: TBD.
4. Add defenses: forecast cross-checking, headroom broadcasts, minimum reserve/SoC rules, and limits on simultaneous sanctions; report resilience loss. Owner: TBD.
5. Resolve the forecast-error period mismatch by appending MIS snapshots or using resource-level noise only. Owner: TBD.

### Code to add

- `code/wargame/learning/` for environment wrappers, CTDE/DTDE trainers, policies, and evaluation.
- New numbered scripts for MARL, adaptive monitoring, and attacks, without reusing existing script numbers.
- `learning:` and `attacks:` blocks in `config/base.yaml`, with scenario overrides under `config/scenarios/`.
- Offline synthetic tests for new modules, with implementation departures recorded in `docs/DEVIATIONS.md`.

## How to update this document

Update the status table, results, decision log, and date whenever a milestone changes.

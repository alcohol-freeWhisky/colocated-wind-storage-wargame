Implemented both convergence fixes and completed tuning, tests, and the three-day smoke run.

### Verification

- Full suite: `31 passed` in 7.24 s.
- `git diff --check`: clean.
- Added INJ/FULL fixed-point identity test.
- PRICE toy converges within 30 iterations.
- No changes under `data/`.

### Smoke results

| Cell | Mean J ($) | Mean elapsed (s/day) | Converged hours | Mean sweeps/iterations |
|---|---:|---:|---:|---:|
| C_P | 56,829.15 | 0.59 | — | — |
| C_F | 45,346.83 | 0.58 | — | — |
| D_P_INJ_FULL | 56,596.56 | 1.37 | 100.0% | 1.60 sweeps |
| D_P_INJ_PRICE | 56,357.66 | 9.56 | 100.0% | 17.72 iterations |
| D_P_INJ_NONE | 56,225.27 | 0.99 | — | — |
| D_P_EQ_FULL | 47,452.43 | 1.31 | 100.0% | 1.61 sweeps |
| D_P_EQ_PRICE | 47,375.93 | 10.40 | 100.0% | 19.67 iterations |
| D_P_EQ_NONE | 47,143.70 | 0.99 | — | — |
| D_F_INJ_FULL | 44,675.79 | 3.42 | 98.6% | 12.47 sweeps |
| D_F_INJ_PRICE | 45,572.97 | 9.56 | 100.0% | 17.74 iterations |
| D_F_INJ_NONE | 44,374.52 | 0.96 | — | — |
| D_F_EQ_FULL | 45,135.34 | 2.14 | 100.0% | 6.18 sweeps |
| D_F_EQ_PRICE | 45,361.30 | 9.32 | 100.0% | 17.75 iterations |
| D_F_EQ_NONE | 44,121.19 | 0.95 | — | — |

Sanity checks:

- C_P exceeded every D_P cell on every smoke day; minimum daily margin was $29.02.
- Combined INJ/FULL convergence: 99.3% of hours.
- Slowest INJ/FULL day-cell: 4.38 seconds.
- All six PRICE cells: 100% converged hours.
- Serial-equivalent runtime: 57.30, 38.40, and 60.70 seconds/day; mean 52.13 seconds/day.
- Three-worker wall time: 20.36 seconds/day.

### Price tuning

| τ | ρ | Converged | Mean iterations | Selected |
|---:|---:|---:|---:|:---:|
| 0.1 | 0.2 | 28.70% | 43.10 | |
| 0.1 | 0.5 | 79.63% | 14.02 | |
| 0.1 | 1.0 | 87.96% | 8.64 | |
| 0.5 | 0.2 | 67.13% | 23.40 | |
| 0.5 | 0.5 | 85.65% | 11.09 | |
| 0.5 | 1.0 | 95.37% | 3.74 | |
| 2.0 | 0.2 | 100.00% | 18.38 | ✓ |
| 2.0 | 0.5 | 74.07% | 22.15 | |
| 2.0 | 1.0 | 99.54% | 4.12 | |

Artifacts: [price_tuning.csv](/Users/ziqiwei/6.974_wargame/results/tables/price_tuning.csv) and [design_matrix_by_day.csv](/Users/ziqiwei/6.974_wargame/results/tables/design_matrix_by_day.csv).

### Main files changed

- Solvers: [agent_lp.py](/Users/ziqiwei/6.974_wargame/code/wargame/solvers/agent_lp.py), [game.py](/Users/ziqiwei/6.974_wargame/code/wargame/solvers/game.py), [design_matrix.py](/Users/ziqiwei/6.974_wargame/code/wargame/solvers/design_matrix.py)
- Diagnostics/metrics: [realize.py](/Users/ziqiwei/6.974_wargame/code/wargame/solvers/realize.py), [receding.py](/Users/ziqiwei/6.974_wargame/code/wargame/solvers/receding.py), [metrics.py](/Users/ziqiwei/6.974_wargame/code/wargame/experiments/metrics.py)
- Scripts: [07_design_matrix.py](/Users/ziqiwei/6.974_wargame/code/scripts/07_design_matrix.py), [07b_tune_price_coordination.py](/Users/ziqiwei/6.974_wargame/code/scripts/07b_tune_price_coordination.py)
- Configuration/tests/docs: [base.yaml](/Users/ziqiwei/6.974_wargame/config/base.yaml), [test_design_matrix.py](/Users/ziqiwei/6.974_wargame/tests/test_design_matrix.py), [DESIGN.md](/Users/ziqiwei/6.974_wargame/docs/DESIGN.md), [DEVIATIONS.md](/Users/ziqiwei/6.974_wargame/docs/DEVIATIONS.md)

Deviation from the specification: the literal simultaneous proximal-primal/dual iteration remained neutrally oscillatory, including after 500 diagnostic iterations. PRICE therefore uses one predictor-corrector proximal evaluation per iteration. The requested proximal QPs, constant dual step, stopping tests, tuning grid, and executed-iterate policy remain intact; this extension is documented in `DEVIATIONS.md`.
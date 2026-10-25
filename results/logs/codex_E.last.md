Implemented the complete 14-cell revised Part I design matrix while preserving all legacy regimes and scripts.

### Verification

- Tests: **30 passed** — original 24 plus 6 new design-matrix tests.
- Required smoke command completed:
  - 2 days
  - 2 workers
  - 119.17 seconds total
  - 59.59 wall seconds per operating day throughput
- Maximum realized POI overflow: `8.53e-14 MWh` (numerical tolerance).
- `C_P ≥` every `D_P` cell on both days; minimum margin: **$247.46/day**.
- `C_P == R1`; maximum relative difference: **3.09e-16**.

### Smoke-run results

| Cell | Mean J ($/day) | Mean elapsed (s) |
|---|---:|---:|
| C_P | 60,350.16 | 0.611 |
| C_F | 44,229.75 | 0.577 |
| D_P_INJ_FULL | 17,653.76 | 36.026 |
| D_P_INJ_PRICE | 57,607.92 | 7.773 |
| D_P_INJ_NONE | 60,019.01 | 1.016 |
| D_P_EQ_FULL | 51,422.70 | 1.323 |
| D_P_EQ_PRICE | 49,296.23 | 11.087 |
| D_P_EQ_NONE | 51,436.31 | 1.023 |
| D_F_INJ_FULL | 27,095.01 | 29.727 |
| D_F_INJ_PRICE | 41,415.88 | 8.598 |
| D_F_INJ_NONE | 44,103.15 | 1.004 |
| D_F_EQ_FULL | 43,661.86 | 1.961 |
| D_F_EQ_PRICE | 40,858.29 | 8.308 |
| D_F_EQ_NONE | 43,545.56 | 1.012 |

Observed serial-equivalent time averaged 110.05 seconds/day. At the tested two-worker throughput, a 60-day run should take approximately **60 minutes**.

### Files changed

Core implementation:

- [design.py](/Users/ziqiwei/6.974_wargame/code/wargame/experiments/design.py)
- [design_matrix.py](/Users/ziqiwei/6.974_wargame/code/wargame/solvers/design_matrix.py)
- [agent_lp.py](/Users/ziqiwei/6.974_wargame/code/wargame/solvers/agent_lp.py)
- [game.py](/Users/ziqiwei/6.974_wargame/code/wargame/solvers/game.py)
- [receding.py](/Users/ziqiwei/6.974_wargame/code/wargame/solvers/receding.py)
- [realize.py](/Users/ziqiwei/6.974_wargame/code/wargame/solvers/realize.py)
- [metrics.py](/Users/ziqiwei/6.974_wargame/code/wargame/experiments/metrics.py)
- [plots.py](/Users/ziqiwei/6.974_wargame/code/wargame/experiments/plots.py)
- [07_design_matrix.py](/Users/ziqiwei/6.974_wargame/code/scripts/07_design_matrix.py)

Configuration, tests, and documentation:

- [base.yaml](/Users/ziqiwei/6.974_wargame/config/base.yaml)
- [test_design_matrix.py](/Users/ziqiwei/6.974_wargame/tests/test_design_matrix.py)
- [DESIGN.md](/Users/ziqiwei/6.974_wargame/docs/DESIGN.md)
- [DEVIATIONS.md](/Users/ziqiwei/6.974_wargame/docs/DEVIATIONS.md)

Generated outputs:

- [design_matrix_by_day.csv](/Users/ziqiwei/6.974_wargame/results/tables/design_matrix_by_day.csv)
- [design_matrix_summary.csv](/Users/ziqiwei/6.974_wargame/results/tables/design_matrix_summary.csv)
- [design_matrix_effects.csv](/Users/ziqiwei/6.974_wargame/results/tables/design_matrix_effects.csv)
- [design_matrix_pivot.csv](/Users/ziqiwei/6.974_wargame/results/tables/design_matrix_pivot.csv)
- [fig_design_matrix.png](/Users/ziqiwei/6.974_wargame/results/figures/fig_design_matrix.png)
- [fig_design_effects.png](/Users/ziqiwei/6.974_wargame/results/figures/fig_design_effects.png)
- 14 trajectory CSVs plus metadata for 2025-03-01.
- [design_matrix.log](/Users/ziqiwei/6.974_wargame/results/logs/design_matrix.log)

No implementation deviations from the specification. Some smoke-run FULL-INJ and PRICE cells did not satisfy their convergence diagnostics within configured limits; this is recorded as requested, with the best iterate retained and the realization layer enforcing the POI cap. The unrelated pre-existing `docs/two_player_formulation.md` was left untouched.
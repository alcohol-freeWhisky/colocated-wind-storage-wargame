Implemented Task E3’s exact causal overflow charge for INJ FULL.

Key changes:

- Added DPP-convex causal overflow mode to [agent_lp.py](/Users/ziqiwei/6.974_wargame/code/wargame/solvers/agent_lp.py:48), solved with Clarabel.
- Updated [game.py](/Users/ziqiwei/6.974_wargame/code/wargame/solvers/game.py:153) to use exact overflow charges and exact deviation payoffs without lagged INJ weights.
- Made `injection_shortfall: own` the default in [base.yaml](/Users/ziqiwei/6.974_wargame/config/base.yaml:78) and [env.py](/Users/ziqiwei/6.974_wargame/code/wargame/model/env.py:160); retained `phi`.
- Removed all `share_relaxation` code.
- Updated INJ own-deficit accounting and concentration metrics in [metrics.py](/Users/ziqiwei/6.974_wargame/code/wargame/experiments/metrics.py:15).
- Updated [design_matrix.py](/Users/ziqiwei/6.974_wargame/code/wargame/solvers/design_matrix.py:1), [DESIGN.md](/Users/ziqiwei/6.974_wargame/docs/DESIGN.md:121), and [DEVIATIONS.md](/Users/ziqiwei/6.974_wargame/docs/DEVIATIONS.md:27).
- Added the requested tests in [test_design_matrix.py](/Users/ziqiwei/6.974_wargame/tests/test_design_matrix.py:1).

Tests: **35 passed** in 7.23 seconds. No `data/` files were modified.

Verification:

| Day | Cell | Converged hours | Sweeps | Max gain ($) | Seconds | J ($) |
|---|---|---:|---:|---:|---:|---:|
| 2025-04-29 | D_P_INJ_FULL | 100.0% | 100 | 0.033 | 3.31 | 84,561.65 |
| 2025-04-29 | D_F_INJ_FULL | 100.0% | 336 | 0.294 | 6.41 | 60,479.17 |
| 2025-03-29 | D_P_INJ_FULL | 100.0% | 48 | 0.055 | 2.44 | 89,005.91 |
| 2025-03-29 | D_F_INJ_FULL | 100.0% | 352 | 0.257 | 6.67 | 71,449.58 |
| 2025-03-21 | D_P_INJ_FULL | 100.0% | 39 | 0.087 | 2.04 | 6,161.16 |
| 2025-03-21 | D_F_INJ_FULL | 100.0% | 242 | 0.190 | 4.89 | 4,414.48 |
| 2025-04-15 | D_P_INJ_FULL | 100.0% | 63 | 0.041 | 2.66 | 96,547.72 |
| 2025-04-15 | D_F_INJ_FULL | 100.0% | 296 | 0.313 | 5.57 | 94,441.25 |
| 2025-03-11 | D_P_INJ_FULL | 100.0% | 52 | 0.008 | 2.50 | 33,323.46 |
| 2025-03-11 | D_F_INJ_FULL | 87.5% | 1,565 | 0.020 | 28.92 | 33,485.69 |
| 2025-03-01 | D_P_INJ_FULL | 100.0% | 51 | 0.026 | 2.28 | 73,606.42 |
| 2025-03-01 | D_F_INJ_FULL | 100.0% | 258 | 0.273 | 4.93 | 61,153.39 |
| 2025-04-26 | D_P_INJ_FULL | 100.0% | 38 | 0.297 | 1.99 | 48,662.59 |
| 2025-04-26 | D_F_INJ_FULL | 100.0% | 245 | 0.274 | 4.48 | 45,762.14 |

Overall convergence was **99.1%**, exceeding the 90% target. The runtime target was missed on `2025-03-11 D_F_INJ_FULL` (28.92 s and 87.5% convergence), so I stopped without loosening tolerances.

Deviation from the requested implementation: the reciprocal cone is algebraically scaled by agent nameplate to prevent Clarabel numerical failures. This leaves the exact `cP/y` charge unchanged. No 60-day run was launched.
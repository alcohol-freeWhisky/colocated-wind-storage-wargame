# Implementation deviations

Departures of the implementation from `docs/DESIGN.md` and the proposal, with reasons.

- `solvers/realize.py` records a battery-side `spill` diagnostic in the degenerate case where pro-rata POI curtailment exhausts available wind curtailment and an already-full battery cannot retain all of the requested discharge reduction. This preserves both the hard POI limit and SoC bounds; ordinary feasible plans follow the specified wind-first, then reduced-discharge rule and have zero spill.
- `forecast_error_system.parquet` compares forecasts with latest-publication realised HSL and normalizes by each region's maximum observed HSL. GEN-based error is kept only as an explicitly curtailment-contaminated comparison.
- Game convergence is tested on the undamped best-response residual `max|BR_q - q| / sum(N)` (`game.tol_rel` 1e-5, `game.max_sweeps` 200). A solution is reported as converged only if the final unilateral-deviation gain is also at most `game.max_gain_tol` ($1); `max_delta` is that residual. `GameSolution.objective` follows the central definition (no lambda_plus term); the value with the overflow penalty is `objective_with_plus_penalty`.
- `poi.kappa_K` is 0.6, a designed stress level at which the POI binds in roughly half of the hours for the Anchor set. The LBNL-anchored value 0.9 is context only.
- The headline operating experiment is a 14-cell factorial over control, foresight, penalty allocation, and market information (`experiments/design.py`). Overflow allocations are budget balanced. In PRICE cells, the coordinator's dual congestion price replaces the agents' overflow penalty rather than stacking on top of it.
- PRICE uses QP proximal responses, constant dual steps by default, and records hour-level KKT diagnostics. The literal simultaneous proximal-primal/dual iteration remained neutrally oscillatory on the empirical hard horizons (including a 500-iteration diagnostic), so the implementation adds one predictor-corrector proximal evaluation per iteration. This is the sole algorithmic extension beyond the plain update and is needed to meet the 90% convergence criterion; the configured stopping tests and dual update are unchanged.

  Price tuning on `2025-03-01`, `2025-03-02`, and `2025-04-26` for `D_P_INJ_PRICE`, `D_P_EQ_PRICE`, and `D_F_INJ_PRICE` (216 receding hours per pair); chosen parameters are `proximal_tau = 2.0` and `rho = 0.2`:

  | proximal tau | rho | converged hours | fraction | mean iterations | selected |
  |---:|---:|---:|---:|---:|:---:|
  | 0.1 | 0.2 | 62 | 0.2870 | 43.1019 | |
  | 0.1 | 0.5 | 172 | 0.7963 | 14.0231 | |
  | 0.1 | 1.0 | 190 | 0.8796 | 8.6435 | |
  | 0.5 | 0.2 | 145 | 0.6713 | 23.3981 | |
  | 0.5 | 0.5 | 185 | 0.8565 | 11.0880 | |
  | 0.5 | 1.0 | 206 | 0.9537 | 3.7407 | |
  | 2.0 | 0.2 | 216 | 1.0000 | 18.3750 | yes |
  | 2.0 | 0.5 | 160 | 0.7407 | 22.1481 | |
  | 2.0 | 1.0 | 215 | 0.9954 | 4.1204 | |

- INJ penalty charges are exact. `game.injection_shortfall: own` is the default (with `phi` kept as an option), so agent i pays `lambda_minus * (D_it-q_it)^+`; total own-deficit collection is at least the system shortfall. FULL/INJ overflow best responses contain the exact convex causal charge `lambda_plus * q_it^+ * (Q_t-K)^+ / sum_j q_jt^+`, solved as a DPP conic model with Clarabel. The deviation check uses the same exact charge, overflow remains budget balanced ex post, and reported INJ shortfall allocations equal the agents' own-deficit charges.

# Implementation deviations

- `solvers/realize.py` records a battery-side `spill` diagnostic in the degenerate case where pro-rata POI curtailment exhausts available wind curtailment and an already-full battery cannot retain all of the requested discharge reduction. This preserves both the hard POI limit and SoC bounds; ordinary feasible plans follow the specified wind-first, then reduced-discharge rule and have zero spill.
- `forecast_error_system.parquet` follows the corrected schema requested in Task A2: forecasts are compared with latest-publication realised HSL and normalized by each region's maximum observed HSL. GEN-based error is retained only as the explicitly curtailment-contaminated comparison. This supersedes the older GEN/hourly-HSL schema in DESIGN.md sections 2 and 5.

- 2026-10-21 (lead): base-case `kappa_K` changed 0.9 → 0.6 after the code review showed the POI rarely binds at 0.9 (R3a = R3b, R4a = R4b on most days). 0.9 remains in the sensitivity grid and is documented as the empirically anchored value.
- 2026-10-21 (solver review fixes): (1) `solvers/game.py` now tests convergence on the undamped best-response residual max|BR_q - q| / sum(N) (`game.tol_rel` 1e-5, `game.max_sweeps` 200) and reports `converged` only if the final deviation gain is also <= `game.max_gain_tol` ($1); `max_delta` is that residual. `GameSolution.objective` now follows the central definition (no lambda_plus term); the old value is `objective_with_plus_penalty`. (2) R4 agents' *private* shortfall penalty is weighted by beta_i (`poi.beta_rule`, capacity share) via `mpc.private_shortfall_beta: game` (default), which matches marginal shortage incentives to R2; `full` restores beta_i = 1 (N times more shortage-averse than R2). (3) The R4a POI budget `max(K - Q_{t-1}, 0) + q_{i,t-1}` can be negative after grid charging; instead of the bare floor `-P_i` (still infeasible when the battery is full), hour 0 of the plan is floored at `-min(P_i, (E_i - soc)/eta_c)` and later planned hours at 0. (4) `poi.kappa_K` base value is 0.6 (designed stress level); 0.9 stays in the sensitivity grid. (5) `04_sensitivity.py` runs only `sensitivity.regimes` (non-forecast regimes) using its own regime loop; `_f` gaps are absent (NaN after concatenation) there. Note: `model/env.py::_minimal_config` still carries the old `game` defaults (50 sweeps, tol 1e-3) for synthetic episodes.

- 2026-10-25 (revised Part I design): the headline operating experiment is now a 14-cell factorial over control, foresight, penalty allocation, and market information. The change removes confounding in the earlier ad-hoc regime list. Overflow allocations are budget balanced. The old full-exposure shortfall allocation is superseded by Task E3's own-deficit INJ rule. In PRICE cells, the coordinator's dual congestion price replaces the agents' overflow penalty rather than stacking on top of it. Legacy regimes `R1..R4b_f` remain available unchanged for backward compatibility.

- 2026-10-25 (Task E2 convergence fixes, shortfall portion superseded by E3): FULL/INJ held the smooth scalar `phi = (D-Q)^+ / sum_i(D_i-q_i)^+` fixed inside each private-shortfall best response. Task E3 replaces that default with the own-deficit rule and keeps `phi` only as an explicit compatibility option. PRICE uses QP proximal responses, constant dual steps by default, and records hour-level KKT diagnostics. The literal simultaneous proximal-primal/dual iteration remained neutrally oscillatory on the empirical hard horizons (including a 500-iteration diagnostic), so the implementation adds one predictor-corrector proximal evaluation per iteration. This is the sole algorithmic extension beyond the requested update and is needed to meet the 90% convergence criterion; the configured stopping tests and dual update are unchanged.

  Price tuning on `2025-03-01`, `2025-03-02`, and `2025-04-26` for `D_P_INJ_PRICE`, `D_P_EQ_PRICE`, and `D_F_INJ_PRICE` (216 receding hours per pair):

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

- 2026-10-25 (Task E3 exact causal INJ charges): `game.injection_shortfall: own` is now the default (with `phi` retained as an option), so agent i pays `lambda_minus * (D_it-q_it)^+`; total own-deficit collection is at least the system shortfall rather than mechanically N times it. FULL/INJ overflow best responses now contain the exact convex causal charge `lambda_plus * q_it^+ * (Q_t-K)^+ / sum_j q_jt^+`, solved as a DPP conic model with Clarabel. This removes lagged overflow weights and the unused share-relaxation setting. The deviation check uses the same exact charge, overflow remains budget balanced ex post, and reported INJ shortfall allocations now equal the agents' own-deficit charges.

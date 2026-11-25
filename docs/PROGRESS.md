# Reproducibility Status

## Current model

- [x] Distinct SCED HSL, COP HSL, DAM award, DA price, and RT price fields.
- [x] No constructed DAM/COP baseline, minimum-delivery constraint, or
  shortfall penalty in the operating game.
- [x] Common physics, fixed overflow rate, and realization across owner cells.
- [x] Four matched dimensions and 14 canonical cells from the slide table.
- [x] FULL and aggregate-signal cells use the same best-response algorithm.
- [x] Exact equal and causal allocation of the same overflow charge.
- [x] Hourly receding-horizon operation and reproducible trajectories.
- [x] Hard validation of convergence, POI feasibility, and battery operation.

## Release gates

- [x] Complete 60 operating days with zero failed days.
- [x] Rebuild report, tables, figures, and representative trajectories.
- [x] Pass the full unit-test suite.
- [x] Confirm obsolete price-coordination artifacts are absent.
- [x] Commit and push the verified revision to `origin/main`.

This checklist is updated only from executed evidence.

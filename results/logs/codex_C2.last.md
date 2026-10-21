Implemented Task C2.

- Replaced σ-scaled withholding with `withholding_grid_frac`; added `thresholds_frac` in [base.yaml](/Users/ziqiwei/6.974_wargame/config/base.yaml:71).
- Updated the deterrence grid schema and calculations in [detection.py](/Users/ziqiwei/6.974_wargame/code/wargame/monitor/detection.py:161).
- Updated ROC and σ-comparison plotting in [05_monitor.py](/Users/ziqiwei/6.974_wargame/code/scripts/05_monitor.py:70).
- Updated [DESIGN.md](/Users/ziqiwei/6.974_wargame/docs/DESIGN.md:137) and focused tests.
- Regenerated all three monitor figures and CSV tables with:
  ```bash
  .venv/bin/python code/scripts/05_monitor.py --synthetic
  ```

Verification:

- `tests/test_monitor.py`: 6 passed
- Full suite: 16 passed
- Synthetic grid: 144 rows with the requested 14-column schema
- All three figures visually inspected

Only the synthetic workflow was rerun; empirical processed-data execution remains unverified.
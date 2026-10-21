Implemented Task B3 and verified the requested workflow.

Key results:

| Coordination | Perfect | Forecast | Perfect (% R1) | Forecast (% R1) |
|---|---:|---:|---:|---:|
| C | $54,972.42 | $43,634.49 | 100.00% | 79.38% |
| G | $53,696.57 | $43,866.53 | 97.68% | 79.80% |
| A | $54,801.54 | $43,194.41 | 99.69% | 78.57% |
| L | $54,615.96 | $43,433.74 | 99.35% | 79.01% |

Implemented:

- R1_f receding-horizon central dispatch.
- R2_f warm-started receding-horizon best-response game with hourly sweep logs.
- Canonical ten-regime ordering throughout.
- Decomposed information/forecast gaps and PoA_f.
- Full ten-regime sensitivity runner.
- Matrix CSV writers, heat map, and report sections.
- Explicit 23-hour DST-day handling.

Important files:

- [receding.py](/Users/ziqiwei/6.974_wargame/code/wargame/solvers/receding.py)
- [run_episode.py](/Users/ziqiwei/6.974_wargame/code/wargame/experiments/run_episode.py)
- [metrics.py](/Users/ziqiwei/6.974_wargame/code/wargame/experiments/metrics.py)
- [matrix_summary.csv](/Users/ziqiwei/6.974_wargame/results/tables/matrix_summary.csv)
- [matrix_summary_pct_r1.csv](/Users/ziqiwei/6.974_wargame/results/tables/matrix_summary_pct_r1.csv)
- [fig_info_matrix.png](/Users/ziqiwei/6.974_wargame/results/figures/fig_info_matrix.png)
- [report.md](/Users/ziqiwei/6.974_wargame/docs/workshop1/report.md)

Verification:

- `21 passed` with `.venv/bin/python -m pytest tests/ -q`
- Three-day experiment completed in 6.85 seconds.
- N=5, T=24, all ten regimes: 5.39 seconds, below the 30-second target.
- Report generation completed successfully.
- Processed window contains 61 calendar dates: 60 complete episodes plus 2025-03-09, explicitly recorded as a 23-hour DST skip in [regimes_skipped_days.csv](/Users/ziqiwei/6.974_wargame/results/tables/regimes_skipped_days.csv).

Run with:

```bash
.venv/bin/python code/scripts/03_run_regimes.py --days 3
MPLCONFIGDIR=/tmp/wargame-mpl .venv/bin/python code/scripts/06_make_report.py
```

Not run: the full 60-day regime experiment and the complete sensitivity grid. CVXPY emits a harmless canonicalization-backend fallback warning during central solves.
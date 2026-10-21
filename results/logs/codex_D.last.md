Implemented Task D end to end.

Created:

- [03_run_regimes.py](/Users/ziqiwei/6.974_wargame/code/scripts/03_run_regimes.py)
- [04_sensitivity.py](/Users/ziqiwei/6.974_wargame/code/scripts/04_sensitivity.py)
- [06_make_report.py](/Users/ziqiwei/6.974_wargame/code/scripts/06_make_report.py)
- [plots.py](/Users/ziqiwei/6.974_wargame/code/wargame/experiments/plots.py)
- [io.py](/Users/ziqiwei/6.974_wargame/code/wargame/experiments/io.py)
- [Workshop report](/Users/ziqiwei/6.974_wargame/docs/workshop1/report.md)
- [HTML report](/Users/ziqiwei/6.974_wargame/docs/workshop1/report.html)

Generated all requested tables, metadata files, trajectories, seven new PNG/PDF figure pairs, and reused the three monitor figures. Incomplete days are explicitly listed; the current dataset provided two complete days.

Verification:

- `03 --days 3`: 4.64 s internal, 6.01 s wall
- `04 --quick`: 30.78 s internal, 31.83 s wall; 300 rows, zero failed cases
- `05_monitor.py`: 7.79 s wall
- `06_make_report.py`: 3.09 s wall
- Tests: `19 passed` in 3.82 s
- All 10 report images opened successfully, all seven new PDFs validated, and every report image link resolves.

Run with:

```bash
.venv/bin/python code/scripts/03_run_regimes.py --config config/base.yaml --days 3
.venv/bin/python code/scripts/04_sensitivity.py --config config/base.yaml --quick
.venv/bin/python code/scripts/05_monitor.py --config config/base.yaml
.venv/bin/python code/scripts/06_make_report.py --config config/base.yaml
```

The full 61-day/full-grid runs were not performed, as requested. Results and report numbers currently reflect the two-day dataset and quick sensitivity grid. The reused monitor-duration figure has a crowded existing legend artifact; monitor plotting logic was left unchanged.
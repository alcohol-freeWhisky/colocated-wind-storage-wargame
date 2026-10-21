Implemented Task C.

Created:

- [calibration.py](/Users/ziqiwei/6.974_wargame/code/wargame/monitor/calibration.py)
- [detection.py](/Users/ziqiwei/6.974_wargame/code/wargame/monitor/detection.py)
- [empirical.py](/Users/ziqiwei/6.974_wargame/code/wargame/monitor/empirical.py)
- [05_monitor.py](/Users/ziqiwei/6.974_wargame/code/scripts/05_monitor.py)
- [test_monitor.py](/Users/ziqiwei/6.974_wargame/tests/test_monitor.py)

Verification:

- `.venv/bin/python -m pytest tests/ -q` — **7 passed**
- Synthetic CLI completed and generated all requested CSVs, metadata, and three inspected figures:
  `.venv/bin/python code/scripts/05_monitor.py --config config/base.yaml --synthetic`
- Without `--synthetic`, missing parquet files produce a clear error and no silent fallback.

Real-data calibration remains unverified because the two processed forecast-error parquet files are not yet present. No DESIGN deviations were necessary.
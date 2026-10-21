Implemented Task A’s complete data pipeline.

Created:

- [ercot.py](/Users/ziqiwei/6.974_wargame/code/wargame/data/ercot.py)
- [eia.py](/Users/ziqiwei/6.974_wargame/code/wargame/data/eia.py)
- [forecast_errors.py](/Users/ziqiwei/6.974_wargame/code/wargame/data/forecast_errors.py)
- [build_dataset.py](/Users/ziqiwei/6.974_wargame/code/wargame/data/build_dataset.py)
- [01_download_raw.py](/Users/ziqiwei/6.974_wargame/code/scripts/01_download_raw.py)
- [02_build_dataset.py](/Users/ziqiwei/6.974_wargame/code/scripts/02_build_dataset.py)
- [test_data_build.py](/Users/ziqiwei/6.974_wargame/tests/test_data_build.py)

Verification completed:

- Two ERCOT operating days downloaded successfully and resumably.
- Full 2025 HB_WEST price year cached: 8,760 hourly rows.
- Processed two-day dataset:
  - 48 price hours
  - 1,776 wind rows
  - 1,776 forecast rows
  - 37 resources
  - 157,815 system/regional forecast-error rows
  - 1,776 resource forecast-error rows
- EIA-860 results: Horse Hollow 735.5 MW across three units, 90 Texas storage units, four co-located hybrids.
- Table heads and baseline/nameplate/timezone invariants inspected successfully.
- Tests: `16 passed`; three existing CVXPY backend warnings.
- No DESIGN deviations.

Run the full window with:

```bash
.venv/bin/python code/scripts/01_download_raw.py --config config/base.yaml
.venv/bin/python code/scripts/02_build_dataset.py --config config/base.yaml
```

Only the full 61-day download remains unverified, intentionally, as requested.
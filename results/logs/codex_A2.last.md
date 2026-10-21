Implemented the forecast-error correction and rebuilt the processed dataset.

### Forecast diagnostics

Values are percentages of `cap_proxy`; bias is forecast minus comparator. Buckets use `[0,1]`, `(1,3]`, etc.

**SYSTEM WIDE**

| Horizon h | HSL σ | HSL MAE | HSL bias | GEN σ | GEN MAE | GEN bias |
|---|---:|---:|---:|---:|---:|---:|
| 0–1 | 4.30% | 3.30% | −1.28% | 6.41% | 4.90% | +2.53% |
| 1–3 | 5.29% | 3.98% | −1.21% | 7.25% | 5.59% | +2.61% |
| 3–6 | 5.67% | 4.21% | −1.09% | 7.45% | 5.83% | +2.74% |
| 6–12 | 5.87% | 4.55% | −1.09% | 7.55% | 6.06% | +2.77% |
| 12–24 | 6.35% | 4.79% | −0.70% | 7.98% | 6.49% | +3.26% |
| 24–48 | 7.66% | 5.42% | −0.11% | 8.70% | 7.37% | +4.06% |
| 48–168 | 7.20% | 5.76% | +1.38% | 7.70% | 6.99% | +4.53% |

**LZ WEST**

| Horizon h | HSL σ | HSL MAE | HSL bias | GEN σ | GEN MAE | GEN bias |
|---|---:|---:|---:|---:|---:|---:|
| 0–1 | 2.11% | 2.67% | +2.38% | 8.17% | 5.96% | +2.57% |
| 1–3 | 2.47% | 2.66% | +2.27% | 9.18% | 6.68% | +2.41% |
| 3–6 | 3.89% | 3.49% | +2.39% | 9.33% | 6.94% | +2.51% |
| 6–12 | 5.04% | 4.42% | +2.74% | 9.31% | 7.19% | +2.77% |
| 12–24 | 5.91% | 5.16% | +3.31% | 9.66% | 7.56% | +3.26% |
| 24–48 | 8.65% | 6.38% | +3.18% | 11.12% | 8.65% | +3.77% |
| 48–168 | 7.77% | 7.18% | +4.90% | 9.69% | 8.36% | +4.77% |

“HSL” uses `err_stwpf_norm`; “GEN” uses the retained curtailment-contaminated `err_stwpf_vs_gen_norm`.

### Monitor output

| regime | sample_source | n | sigma | robust_sigma |
|---|---|---:|---:|---:|
| low | system STWPF, horizon ≤ 6 h | 1,295 | 0.051935 | 0.043161 |
| medium | resource COP, all hours | 54,131 | 0.156720 | 0.108464 |
| high | resource COP worst quartile or system STWPF horizon ≥ 24 h | 26,833 | 0.211933 | 0.229146 |

### Files and verification

Updated:

- [forecast_errors.py](/Users/ziqiwei/6.974_wargame/code/wargame/data/forecast_errors.py)
- [build_dataset.py](/Users/ziqiwei/6.974_wargame/code/wargame/data/build_dataset.py)
- [test_data_build.py](/Users/ziqiwei/6.974_wargame/tests/test_data_build.py)
- [processed README](/Users/ziqiwei/6.974_wargame/data/processed/README.md)
- [DEVIATIONS.md](/Users/ziqiwei/6.974_wargame/docs/DEVIATIONS.md)

The resource table now includes `cap_proxy = nameplate_mw`. The system table has the exact requested schema and one constant capacity proxy per region.

Commands:

```bash
.venv/bin/python code/scripts/02_build_dataset.py --config config/base.yaml
.venv/bin/python code/scripts/05_monitor.py --config config/base.yaml
.venv/bin/python -m pytest tests/ -q
```

Final test result: **21 passed**, with four existing CVXPY canonicalization warnings.

One cross-task compatibility issue remains: the unchanged monitor validator still asks for legacy `gen`/`hsl` names. The reported monitor run used temporary aliases solely for validation, then restored the exact required parquet schema. The monitor-side task should update that validator before the command can be rerun directly against the final schema.
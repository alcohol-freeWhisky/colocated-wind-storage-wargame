# Processed data

Built at `2026-10-21T04:53:15.135799+00:00` from public ERCOT and EIA source reports. Latest local
source-cache modification (download timestamp): `2026-10-21T03:36:19.709585+00:00`. All interval
timestamps are timezone-aware `US/Central`; `t_utc`/`interval_start_utc` is the
same instant in UTC.

| File | Columns and source | Classification |
|---|---|---|
| `prices_hourly.parquet` | index `Interval Start`; `t_utc`, `pi_DA`, `pi_RT`, `hub`; ERCOT NP4-180-ER and NP6-785-ER | Empirical |
| `wind_hourly.parquet` | `Interval Start`, `t_utc`, `resource`, hourly SCED means `W_avail`, `W_out`, `basepoint_mean`, observed `curtail_obs`, and row count `n_5min`; ERCOT NP3-965-ER | Empirical |
| `forecast_hourly.parquet` | `Interval Start`, `t_utc`, `resource`, COP `What_cop`, DAM `b_dam`, and `b_baseline` (positive DAM award, otherwise COP); ERCOT COP/NP3-966-ER | Empirical with documented baseline construction |
| `resources.csv` | resource/site identifiers, modal DME/QSE, 99.5th-percentile and maximum HSL, coverage, and mean capacity factor | Empirical summary |
| `corr_matrix.csv` | Pairwise Pearson correlation of hourly SCED HSL | Empirical summary |
| `forecast_error_system.parquet` | `publish_time`, interval timestamps, `horizon_h`, `region`, latest reported `hsl_actual` and `gen_actual`, publication-vintage `stwpf`, `wgrpp`, and `cop_hsl`, constant regional `cap_proxy` (maximum observed realised HSL), HSL-based normalized forecast errors, and the curtailment-contaminated `err_stwpf_vs_gen_norm`; ERCOT NP4-732-CD/NP4-742-CD | Empirical summary |
| `forecast_error_resource.parquet` | COP HSL versus SCED HSL, `cap_proxy` (resource nameplate), and nameplate-normalized error | Empirical summary |
| `eia860_summary.json`, `eia860_tx_storage.csv` | Horse Hollow wind and Texas battery/hybrid calibration summaries; EIA-860 2023 | Empirical summary |

Episodes are views of these tables, constructed by operating day and agent set,
and are not materialized as files. Battery sizing, shared POI limit `K`,
minimum delivery `D_t`, information regimes, monitoring thresholds, sanction
duration, and attack type are designed wargame variables taken from the
configuration.

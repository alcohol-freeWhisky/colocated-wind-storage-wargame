# Strategic Coordination, Learning, and Monitoring in Co-Located Wind–Storage Systems

A Computational Wargame, MIT 6.974, Fall 2026

Team: Nicolás Acevedo Villena, Subham Saha, Ziqi Wei

This repository is a reproducible computational testbed for studying how independently controlled wind–storage resources behave when they share one point of interconnection (POI) but not objectives or information. It has three layers. **Part I** (strategic decentralized operation) compares a centralized oracle with decentralized games, limited-information regimes and coordination mechanisms, and measures the strategic and information gaps against real ERCOT wind, price and forecast data. **Part II** (limited information and multi-agent reinforcement learning) asks whether adaptive agents can recover coordination from local or aggregate observations (CTDE vs. DTDE). **Part III** (monitoring, enforcement and resilience) studies how an imperfect market monitor can deter strategic withholding when forecast error hides intent, and how the mechanism survives attacks such as POI derating, biased headroom signals and communication loss. The Workshop 1 scope (Part I plus a preliminary monitor calibration) is implemented; see [Status](#status).

## Repository structure

```
config/        base.yaml (all parameters) and scenarios/ (overrides: vortex, horse_hollow)
code/          Python package `wargame` (code/wargame/) and entry-point scripts (code/scripts/)
data/raw/      untouched downloads (ERCOT MIS reports, EIA-860); never edited by hand
data/interim/  per-operating-day extracts (parquet)
data/processed/ common dataset + forecast-error tables + README.md (provenance)
results/       tables/ (CSV + .meta.json), figures/ (PNG + PDF), logs/
docs/          proposal.tex, DESIGN.md, ASSUMPTIONS.md, DEVIATIONS.md, PROGRESS.md,
               references/, workshop1/report.md
tests/         offline pytest suite on synthetic episodes
```

### `code/wargame/` subpackages

| Subpackage | Modules | Role |
|---|---|---|
| `data/` | `ercot`, `eia`, `build_dataset`, `forecast_errors` | Download ERCOT/EIA reports, build the processed dataset and the forecast-error tables |
| `model/` | `physics`, `env` | Battery dynamics, shared-POI constraints, episode (one operating day, 24 hourly steps) |
| `solvers/` | `central`, `game`, `agent_lp`, `mpc`, `receding`, `realize` | Central LP (R1), best-response game (R2/R3), per-agent LP, limited-information MPC (R4), receding-horizon (`_f`) variants, physical realisation layer (pro-rata POI curtailment) |
| `monitor/` | `calibration`, `detection`, `empirical` | Forecast-error noise regimes, detection q0/q1 and ROC, deterrence F* and T* |
| `experiments/` | `run_episode`, `metrics`, `io`, `plots` | Regime runner, gap/PoA metrics, table I/O with `.meta.json`, figures |

### `code/scripts/` entry points

| Script | What it does | Writes |
|---|---|---|
| `01_download_raw.py` | Download ERCOT prices, 60-day SCED/DAM/COP disclosures, wind-forecast reports, EIA-860 (resumable) | `data/raw/`, `data/interim/`, `results/logs/` |
| `02_build_dataset.py` | Build the common dataset from cached raw/interim data | `data/processed/` |
| `03_run_regimes.py` | Run R1..R4b (10 regimes) on every complete day, base case Anchor Wind | `results/tables/regimes_by_day.csv`, `regimes_summary.csv`, `matrix_summary*.csv`, `illustrative_days.csv`, `regimes_skipped_days.csv` |
| `03b_trajectories.py` | Hourly dispatch trajectories for chosen days (`--days ...`), identical to the 03 run | `results/tables/trajectories/` |
| `04_sensitivity.py` | Grid: POI tightness x wind correlation set x storage design | `results/tables/sensitivity*.csv`, `agent_sets.csv`, `sensitivity_failures.csv` |
| `05_monitor.py` | Noise regimes, ROC, required fine F*, correction duration T* | `results/tables/monitor_regimes.csv`, `monitor_roc.csv`, `monitor_deterrence.csv` |
| `06_make_report.py` | Figures and the Workshop 1 report | `results/figures/`, `docs/workshop1/report.md` and `.html` |

## Setup (macOS / Linux)

Requires Python >= 3.11 (developed on 3.13).

```bash
git clone https://github.com/alcohol-freeWhisky/colocated-wind-storage-wargame.git
cd colocated-wind-storage-wargame
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt     # loose dependency list
pip install -e code/                # installs the `wargame` package
pytest tests/ -q
```

`requirements.lock.txt` contains the exact pinned versions used for the committed results; use `pip install -r requirements.lock.txt` for bit-for-bit reproduction.

## Reproduce Workshop 1

Run from the repository root, in order:

```bash
python code/scripts/01_download_raw.py  --config config/base.yaml   # ~45 min for 61 days
python code/scripts/02_build_dataset.py --config config/base.yaml   # ~1 min
python code/scripts/03_run_regimes.py   --config config/base.yaml   # ~7 min
python code/scripts/04_sensitivity.py   --config config/base.yaml   # ~16 min
python code/scripts/05_monitor.py       --config config/base.yaml   # < 1 min
python code/scripts/06_make_report.py   --config config/base.yaml   # < 1 min
```

`data/processed/` and `results/` are committed, so collaborators can start at step 03 (re-run the regimes) or step 06 (rebuild the report) without downloading anything. Step 01 is only needed to extend the window or refresh the wind-forecast snapshot.

## Data and provenance

- **Observed**: HB_WEST DA/RT prices, SCED available wind (HSL), COP forecasts, DAM awards, resource metadata, EIA-860 assets, and the observed co-located BESS at Anchor Wind.
- **Calibrated**: nameplates, battery power ratio/duration/efficiency/degradation cost, monitor noise regimes, correlation sets chosen from real series.
- **Designed** (wargame variables): POI limit K, minimum delivery D, penalties, information structures, monitor thresholds and enforcement parameters.

The full parameter-by-parameter record is in [docs/ASSUMPTIONS.md](docs/ASSUMPTIONS.md); the schema of each processed file is in [data/processed/README.md](data/processed/README.md).

Note: ERCOT keeps the hourly wind-forecast reports (NP4-732-CD / NP4-742-CD) on MIS for only about 8 days. The system-level snapshot used here (publications 2026-10-13 to 2026-10-20) is committed under `data/raw/ercot/wind_forecast_*`. Re-running step 01 adds newer publications without deleting the snapshot.

## Status

Workshop 1 deliverables are complete; Parts II and III beyond the preliminary monitor calibration are not started. See [docs/PROGRESS.md](docs/PROGRESS.md) for the dated status, decisions and next steps, and [docs/workshop1/report.md](docs/workshop1/report.md) for the results.

## Conventions for collaborators

- English only in code, comments, docs and commit messages.
- Experiments are config-driven: parameters live in `config/base.yaml`; variants go in `config/scenarios/`. No magic numbers in code.
- Never edit `data/raw/` by hand.
- Every results table gets a `.meta.json` (written through `experiments/io.py`).
- Record any departure from `docs/DESIGN.md` in `docs/DEVIATIONS.md` (dated, with reason).
- Add tests under `tests/`; they must run offline on synthetic data (`pytest tests/ -q`).
- Branches: `part2/<topic>`, `part3/<topic>`; every PR is reviewed by one other team member before merging.
- Update `docs/PROGRESS.md` when a milestone changes status.

## Data sources

Full references (R1–R14) are in [docs/ASSUMPTIONS.md](docs/ASSUMPTIONS.md#references).

- R1: ERCOT DAM/RTM hub prices, NP4-180-ER and NP6-785-ER (via `gridstatus`).
- R2: ERCOT 60-Day SCED (NP3-965-ER), DAM (NP3-966-ER) and COP Adjustment Period disclosures.
- R3: ERCOT wind production and forecasts, NP4-732-CD and NP4-742-CD.
- R4: U.S. EIA, Form EIA-860 (2023 release).
- R6: LBNL, *Hybrid Power Plants: Status of Operating and Proposed Plants, 2025 Data Update* (copy in `docs/references/`).
- R7: NREL Annual Technology Baseline, utility-scale battery storage.
- R8–R13: Battery degradation, CAISO hybrid resources, ERCOT Protocols and VOLL references.

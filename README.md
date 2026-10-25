# Strategic Coordination in Co-Located Wind-Storage Systems

Part I asks how much realized system value is lost when co-located wind-storage units sharing one point of interconnection (POI) are operated by independent decision makers, and which of four design factors matters most: control, foresight, penalty allocation, or market information and coordination. The experiment compares 14 matched cells over 60 complete ERCOT operating days and evaluates every contrast on the realized system objective J.

## Design factors

| Factor | Levels | What it represents in practice | Model implementation | How its effect is measured on realized J |
|---|---|---|---|---|
| F1 control | `C`, `D` | One plant controller versus independent unit controllers | A central receding-horizon LP versus decentralized policies | `C_x - D_x_*`, holding F2 fixed; every matching decentralized F3/F4 cell is reported |
| F2 foresight | `P`, `F` | Knowing future realized wind and RT prices versus using operational forecasts | `P` uses true wind and RT price over the remaining horizon; `F` uses current truth followed by COP wind and DA price | `X_P - X_F` for every matching cell |
| F3 penalty allocation | `INJ`, `EQ` | Responsibility based on causal contribution versus equal responsibility | `INJ` uses positive-injection overflow shares and own-deficit shortfall charges; `EQ` uses equal shares of system penalties | `INJ - EQ`, holding F2 and F4 fixed |
| F4 market information | `FULL`, `PRICE`, `NONE` | Other agents' plans, a coordinator congestion price, or neither | Best-response game, coordinator price iteration, or a fixed capacity-share POI budget | `FULL - PRICE`, `PRICE - NONE`, and `FULL - NONE`, holding F2 and F3 fixed |

The 2 by 7 design has the following canonical cell ids, defined in `code/wargame/experiments/design.py`:

| F2 | Central | INJ/FULL | INJ/PRICE | INJ/NONE | EQ/FULL | EQ/PRICE | EQ/NONE |
|---|---|---|---|---|---|---|---|
| `P` | `C_P` | `D_P_INJ_FULL` | `D_P_INJ_PRICE` | `D_P_INJ_NONE` | `D_P_EQ_FULL` | `D_P_EQ_PRICE` | `D_P_EQ_NONE` |
| `F` | `C_F` | `D_F_INJ_FULL` | `D_F_INJ_PRICE` | `D_F_INJ_NONE` | `D_F_EQ_FULL` | `D_F_EQ_PRICE` | `D_F_EQ_NONE` |

## Model in one page

Each of five Anchor Wind units has available wind and a co-located battery. In every hour, its controller chooses curtailment `r`, battery charging `c`, and discharging `d`. Net injection is `q = W - r - c + d`; state of charge follows charging and discharging efficiency, stays within the battery energy bound, and returns to at least its initial daily level. The degradation cost is charged on discharge only, `c_deg * d`.

The units share an export limit `K` at the POI and a system delivery obligation `D`. Planned shortfall is `(D - Q)+`, and planned overflow is `(Q - K)+`, where `Q` is aggregate injection. F3 determines how agents anticipate the resulting charges. F4 determines whether an agent sees other plans, responds to a coordinator's congestion price, or uses only its fixed share of POI capacity.

Every cell is an hourly receding-horizon policy. It optimizes the remaining hours, submits the current action, and passes the joint action through a realization layer. If the submitted aggregate exceeds K, the POI controller cuts injections pro rata, first through additional wind curtailment and then through reduced discharge. Realized export therefore never exceeds K.

The reported system objective is

`J = realized energy profit - c_deg * realized discharge - lambda_minus * realized under-delivery`.

The attempted-overflow penalty is a planning incentive and is not subtracted from J because the realization layer prevents physical overflow. See [docs/DESIGN.md](docs/DESIGN.md) for the complete implementation contract and [docs/two_player_formulation.md](docs/two_player_formulation.md) for the minimal two-player model and hand-solved example.

## Experiments

### F1 control

The hypothesis is `C - D >= 0`: central control should weakly increase J because it internalizes the shared POI and obligation. The perfect-foresight headline contrast `C_P - mean(D_P_*)` is $1,101/day, with a $473/day median and a mean daily effect of 1.923% of C_P. All 12 held-fixed central-minus-decentralized mean contrasts are positive, so the data confirm the expected sign. Source: [`design_matrix_effects.csv`](results/tables/design_matrix_effects.csv); overview: [`fig_design_effects.png`](results/figures/fig_design_effects.png).

### F2 foresight

The hypothesis is `P - F >= 0`: accurate remaining-horizon wind and RT prices should weakly increase J. For the central cell, `C_P - C_F` is $6,613/day, with a $2,142/day median and a mean daily effect of 11.136% of C_P. All seven matched means are positive, ranging from $6,028 to $6,956/day, so the data confirm the expected sign and identify foresight as the largest factor. Source: [`design_matrix_effects.csv`](results/tables/design_matrix_effects.csv); matrix: [`fig_design_matrix.png`](results/figures/fig_design_matrix.png).

### F3 penalty allocation

The hypothesis is `INJ - EQ >= 0`: causal overflow shares and own-deficit charges should align private incentives better than equal system-penalty shares. Under perfect foresight and FULL, the mean contrast is $1,255/day, or a mean daily 1.860% of C_P, while the median is only $11/day. All six held-fixed means are positive, confirming the expected sign, but the near-zero medians in several cells show that the effect is heavy-tailed. Source: [`design_matrix_effects.csv`](results/tables/design_matrix_effects.csv).

### F4 market information and coordination

The expected signs are `PRICE - NONE >= 0` and generally `FULL - NONE >= 0`; `FULL - PRICE` is not a pure information ordering because PRICE also changes the mechanism. Under perfect foresight and INJ, PRICE exceeds NONE by $688/day, FULL exceeds NONE by $562/day, and `FULL - PRICE` is -$126/day. PRICE beats NONE in all four held-fixed means, while FULL beats NONE in three of four, so the first expectation is confirmed and the second is mostly confirmed. PRICE also exceeds FULL in all four mean comparisons. This does not mean that more information is worse: FULL is a non-cooperative equilibrium that can overshoot the POI, while PRICE is a coordination mechanism whose fixed point approximates the central solution. Source: [`design_matrix_effects.csv`](results/tables/design_matrix_effects.csv).

## Data

The operating window is 2025-03-01 through 2025-04-30. Sixty complete 24-hour days are evaluated; the 23-hour daylight-saving transition day is excluded. The base site is Anchor Wind, with five ERCOT wind resources, 262 MW calibrated aggregate nameplate, and an observed co-located 71.5 MW / 113 MWh battery used to calibrate storage ratios.

Observed inputs are HB_WEST day-ahead and real-time prices, SCED available wind, COP forecasts, DAM awards, ERCOT resource metadata, and EIA-860 assets. The system-level forecast-error snapshot used for monitor calibration covers publications from 2026-10-13 through 2026-10-20 because ERCOT retains those reports for only about eight days. Full provenance and references are in [docs/ASSUMPTIONS.md](docs/ASSUMPTIONS.md) and [data/processed/README.md](data/processed/README.md).

## Repository layout

```text
config/                         Model and experiment configuration.
code/wargame/                   Importable data, model, solver, monitor, and experiment packages.
code/scripts/01_download_raw.py Download and cache the public source data.
code/scripts/02_build_dataset.py Build the common processed dataset.
code/scripts/03_run_regimes.py  Legacy, superseded by the design matrix.
code/scripts/03b_trajectories.py Legacy trajectory export for the old regimes, superseded by the design matrix.
code/scripts/04_sensitivity.py  Legacy, superseded by the design matrix.
code/scripts/05_monitor.py      Preliminary Part III monitor calibration.
code/scripts/06_make_report.py  Generate the matrix-centered Workshop 1 report.
code/scripts/07_design_matrix.py Run or summarize the 14-cell Part I matrix.
code/scripts/07b_tune_price_coordination.py Tune the PRICE fixed-point algorithm.
data/raw/                       Untouched downloads; never edit by hand.
data/interim/                   Cached per-day extracts.
data/processed/                 Common dataset and provenance README.
results/tables/design_matrix_*  Current Part I results and metadata.
results/figures/fig_design_*    Current Part I figures.
results/tables/regimes_*        Legacy, superseded by the design matrix.
results/tables/sensitivity*     Legacy, superseded by the design matrix.
results/tables/matrix_summary*  Legacy, superseded by the design matrix.
results/                        Other old-regime figures and trajectories are legacy, superseded by the design matrix.
docs/                           Design contract, assumptions, deviations, progress, and report.
tests/                          Offline synthetic pytest suite.
```

The old R1 through R4b_f cells remain available for backward compatibility, including R3a and R4a artifacts, but they are legacy, superseded by the design matrix, and are not headline results.

## Reproduce

Create the environment with Python 3.11 or newer, then install the locked dependencies and package:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.lock.txt
.venv/bin/pip install -e code/
```

Run the current workflow from the repository root in this order:

```bash
.venv/bin/python code/scripts/01_download_raw.py --config config/base.yaml
.venv/bin/python code/scripts/02_build_dataset.py --config config/base.yaml
.venv/bin/python code/scripts/07_design_matrix.py --config config/base.yaml
.venv/bin/python code/scripts/05_monitor.py --config config/base.yaml
.venv/bin/python code/scripts/06_make_report.py --config config/base.yaml
```

The committed design-matrix metadata records 1,033.9 seconds, about 17 minutes, for step 07 with four workers. The metadata written by steps 01, 02, and 05 does not record runtime; step 06 does not write result metadata. Cached data and committed matrix tables let collaborators run step 06 directly. Step 01 is needed only to extend or refresh the data window.

## Status and next steps

Workshop 1 Part I and the preliminary Part III monitor calibration are complete. Parts II and the remaining Part III work have not started. See [docs/PROGRESS.md](docs/PROGRESS.md) for the dated factor-by-factor status, decisions, limitations, and next steps.

## Conventions

- Use English in code, comments, documentation, and commit messages.
- Keep parameters in `config/base.yaml`; put scenario overrides in `config/scenarios/`.
- Never edit `data/raw/` by hand.
- Write a sibling `.meta.json` for every result table.
- Record departures from `docs/DESIGN.md` in `docs/DEVIATIONS.md` with a date and reason.
- Add offline synthetic tests under `tests/` and run `.venv/bin/pytest -q`.
- Use branches `part2/<topic>` and `part3/<topic>`; require one review before merging.
- Update `docs/PROGRESS.md` when a milestone changes status.

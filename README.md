# Strategic Coordination in Co-Located Wind-Storage Systems

Part I measures how much system value is lost when co-located wind-storage units that share one point of interconnection (POI) are operated by independent decision makers, and which of four design factors accounts for the loss: control, foresight, penalty allocation, or market information. The experiment runs 14 cells over 60 complete ERCOT operating days and evaluates every contrast on the realized system objective J.

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

## Model

Each of five Anchor Wind units has available wind and a co-located battery. In every hour, its controller chooses curtailment `r`, battery charging `c`, and discharging `d`. Net injection is `q = W - r - c + d`; state of charge follows charging and discharging efficiency, stays within the battery energy bound, and returns to at least its initial daily level. The degradation cost is charged on discharge only, `c_deg * d`.

The units share an export limit `K` at the POI and a system delivery obligation `D`. Planned shortfall is `(D - Q)+`, and planned overflow is `(Q - K)+`, where `Q` is aggregate injection. F3 sets how the resulting charges are divided among agents. F4 sets what an agent knows about the others: their plans, a coordinator's congestion price, or nothing beyond its own fixed share of POI capacity.

Every cell is solved hour by hour. At each hour the decision makers optimize over the remaining hours of the day, submit the current hour's action, and the joint action goes through a realization step. If the submitted aggregate exceeds K, injections are cut pro rata, first by curtailing wind and then by reducing discharge, so realized export never exceeds K.

The reported system objective is

`J = realized energy profit - c_deg * realized discharge - lambda_minus * realized under-delivery`.

The overflow penalty enters the agents' planning problems but not J, since the realization step prevents physical overflow. The full implementation contract is in [docs/DESIGN.md](docs/DESIGN.md). A two-player version of the model with a worked two-hour example is in [docs/two_player_formulation.md](docs/two_player_formulation.md).

## Experiments

Each factor is measured as a difference in mean daily J between two cells that differ in that factor alone. Percentages are means of the daily ratio to C_P. All numbers below come from [`design_matrix_effects.csv`](results/tables/design_matrix_effects.csv); the figures are [`fig_design_matrix.png`](results/figures/fig_design_matrix.png) and [`fig_design_effects.png`](results/figures/fig_design_effects.png).

### F1 control

Expected sign: C minus D is non-negative, because the central controller accounts for the shared POI and the shared obligation. Observed: C_P exceeds the mean of the six decentralized perfect-foresight cells by $1,101/day (median $473/day, 1.9% of C_P). All 12 matched central-minus-decentralized means are positive, and on no day does any decentralized cell exceed the central cell. The loss is smallest with causal penalty shares and price coordination (0.6%) and largest with equal shares and no information (3.3%).

### F2 foresight

Expected sign: P minus F is non-negative. Observed: C_P exceeds C_F by $6,613/day (median $2,142/day, 11.1% of C_P). The seven matched differences range from $6,028 to $6,956/day, all positive. Foresight is the largest of the four factors by an order of magnitude.

### F3 penalty allocation

Expected sign: INJ minus EQ is non-negative, because charging each agent for its own injection into an overflow and its own delivery deficit gives it a higher marginal cost of free riding than an equal split. Observed: under perfect foresight and full information the mean difference is $1,255/day (1.9% of C_P) but the median is $11/day. All six matched means are positive. The difference exceeds $100 on 28 of 60 days and is below -$100 on 14; the three largest days each contribute more than $9,000.

### F4 market information

Expected signs: PRICE minus NONE and FULL minus NONE are non-negative. FULL minus PRICE has no expected sign, because the two cells differ in mechanism as well as in information. Observed, under perfect foresight and causal shares: PRICE exceeds NONE by $688/day and FULL exceeds NONE by $562/day; FULL is $126/day below PRICE. PRICE exceeds NONE in all four matched comparisons, FULL exceeds NONE in three of four, and PRICE exceeds FULL in all four. In FULL each agent best-responds to the others' plans and still injects into a congested hour whenever the price premium exceeds its marginal share of the overflow charge. In PRICE the coordinator raises the congestion price until the aggregate fits the POI, so the fixed point is close to the central solution.

## Data

The operating window is 2025-03-01 through 2025-04-30. Sixty complete 24-hour days are evaluated; the 23-hour daylight-saving transition day is excluded. The base site is Anchor Wind, with five ERCOT wind resources, 262 MW calibrated aggregate nameplate, and an observed co-located 71.5 MW / 113 MWh battery used to calibrate storage ratios.

Observed inputs are HB_WEST day-ahead and real-time prices, SCED available wind, COP forecasts, DAM awards, ERCOT resource metadata, and EIA-860 assets. The system-level forecast-error snapshot used for monitor calibration covers publications from 2026-10-13 through 2026-10-20 because ERCOT retains those reports for only about eight days. Full provenance and references are in [docs/ASSUMPTIONS.md](docs/ASSUMPTIONS.md) and [data/processed/README.md](data/processed/README.md).

## Repository layout

```text
config/                         Model and experiment configuration.
code/wargame/                   Importable data, model, solver, monitor, and experiment packages.
code/scripts/01_download_raw.py Download and cache the public source data.
code/scripts/02_build_dataset.py Build the common processed dataset.
code/scripts/05_monitor.py      Preliminary Part III monitor calibration.
code/scripts/06_make_report.py  Generate the Workshop 1 report.
code/scripts/07_design_matrix.py Run or summarize the 14-cell Part I matrix.
code/scripts/07b_tune_price_coordination.py Tune the PRICE fixed-point algorithm.
data/raw/                       Untouched downloads; never edit by hand.
data/interim/                   Cached per-day extracts.
data/processed/                 Common dataset and provenance README.
results/tables/design_matrix_*  Part I results and metadata.
results/figures/fig_design_*    Part I figures.
results/tables/trajectories/ Hourly dispatch for the plotted design-matrix day.
results/figures/monitor_*       Preliminary Part III monitor figures.
results/tables/monitor_*        Preliminary Part III monitor tables.
results/tables/price_tuning*    PRICE algorithm tuning grid.
docs/                           Design contract, assumptions, deviations, progress, and report.
tests/                          Offline synthetic pytest suite.
```

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

Step 07 took 17 minutes with four workers (recorded in `results/tables/design_matrix_by_day.meta.json`). The processed data and the matrix tables are committed, so step 06 can be run on its own. Step 01 needs network access to ERCOT and EIA and is only needed to extend or refresh the data window.

## Status and next steps

Part I and the preliminary monitor calibration for Part III are done. Part II and the rest of Part III have not started. Dated status, decisions, limitations, and next steps are in [docs/PROGRESS.md](docs/PROGRESS.md).

## Conventions

- Use English in code, comments, documentation, and commit messages.
- Keep parameters in `config/base.yaml`; put scenario overrides in `config/scenarios/`.
- Never edit `data/raw/` by hand.
- Write a sibling `.meta.json` for every result table.
- Record departures from `docs/DESIGN.md` in `docs/DEVIATIONS.md` with a date and reason.
- Add offline synthetic tests under `tests/` and run `.venv/bin/pytest -q`.
- Use branches `part2/<topic>` and `part3/<topic>`; require one review before merging.
- Update `docs/PROGRESS.md` when a milestone changes status.

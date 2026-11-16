# Shared Wind-Storage Wargame

This repository studies independent wind-battery owners that share one point of
interconnection (POI). The primary experiment is the 14-cell ablation table in
`workshop1_recreated.pdf`: control, foresight, overflow-penalty allocation, and
information are varied one factor at a time.

## Research question

How much operating value is lost when co-located resources decide separately,
and how much of that loss is explained by forecast error, blame allocation, and
limited information?

The operating model intentionally has **no minimum-generation requirement and no
shortfall penalty**. A DAM award and a COP forecast are different ERCOT data:

- `b_dam` is a resource's disclosed day-ahead cleared energy award. It is kept
  in the processed data for provenance but is not an operating constraint.
- `What_cop` is the resource's COP High Sustained Limit and is the wind
  availability forecast used in forecast-foresight cells.
- `W_avail` is hourly SCED HSL and is the realized available wind input.

## Operating model

For owner `i` and hour `t`, `q_it = W_it - r_it - c_it + d_it`, where `r`, `c`,
and `d` are wind curtailment, battery charging, and battery discharging.
Charging is wind-only in the base experiment, so `c_it + r_it <= W_it`.
Battery power, energy, efficiency, initial state of charge, and terminal state
constraints apply to every cell.

The shared export limit is `K = 0.6 * sum(nameplate)`. Owner plans may attempt to
exceed it and incur the same fixed `lambda_plus = 100 $/MWh` charge in every
owner cell. The realization layer scales exports pro rata so realized total
export never exceeds `K`. It does not remove unexecuted battery discharge from
state of charge.

Each owner maximizes its own planned real-time energy revenue less battery
degradation and its allocated attempted-overflow charge. System comparisons use
the same realized metric in every cell:

```text
J = realized RT energy revenue - discharge degradation cost
```

The attempted-overflow charge is an internal strategic rule, so it is reported
separately and not subtracted from system value.

## Four matched dimensions

| Dimension | Levels | What changes |
|---|---|---|
| Control | `C` planner / `D` owners | One joint optimization or independent owner best responses |
| Foresight | `P` perfect / `F` forecast | Remaining-horizon realized wind and RT price, or current truth followed by COP wind and DA price |
| Penalty | `INJ` causal / `EQ` equal | Allocation of the same aggregate attempted-overflow charge |
| Information | `FULL` / `PRICE` / `NONE` | Owner-level plans, aggregate injection signal, or no current rival signal |

`PRICE` is retained only as the cell ID used in the slide table. In this revised
experiment it means **aggregate signal**, not a congestion price and not a
different coordination mechanism. FULL and aggregate use the same sequential
best-response algorithm. Their payoff, constraints, penalty rate, stopping
criteria, and realization are identical. Because the payoff is aggregative,
owner identities may add no value beyond the aggregate; equality is a valid
ablation result rather than a coding shortcut.

The 14 canonical cells are `C_P`, `C_F`, and
`D_{P|F}_{INJ|EQ}_{FULL|PRICE|NONE}`.

## Data

The base case uses five Anchor Wind ERCOT resources from 2025-03-01 through
2025-04-30. Sixty complete 24-hour days are evaluated; the daylight-saving day
is excluded. Inputs include ERCOT hourly DAM/RT prices, SCED HSL, COP HSL, DAM
awards, resource metadata, and calibrated co-located battery parameters.

See [ASSUMPTIONS.md](docs/ASSUMPTIONS.md) for sources and parameter provenance,
[DESIGN.md](docs/DESIGN.md) for the implementation contract, and
[two_player_formulation.md](docs/two_player_formulation.md) for the minimal game.

## Reproduce

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
PYTHONPATH=code .venv/bin/python code/scripts/02_build_dataset.py --config config/base.yaml
PYTHONPATH=code .venv/bin/python code/scripts/07_design_matrix.py --config config/base.yaml --workers 4
PYTHONPATH=code .venv/bin/python code/scripts/06_make_report.py --config config/base.yaml
PYTHONPATH=code .venv/bin/python -m pytest -q
```

Primary outputs are `results/tables/design_matrix_*.csv`, one representative
trajectory per cell under `results/tables/trajectories/`, the design figures in
`results/figures/`, and `docs/workshop1/report.{md,html}`. Every table has a
metadata sidecar. The formal run fails if any owner game does not converge,
realized POI export exceeds `K`, or simultaneous charging/discharging remains.

## Scope

This is a stylized price-taking operating game, not a complete ERCOT market
clearing or settlement model. The proportional realization rule and internal
overflow charge are experimental assumptions. The model does not claim that an
ERCOT DAM award is a physical minimum-output instruction.

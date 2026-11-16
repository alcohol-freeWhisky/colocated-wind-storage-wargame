#!/usr/bin/env python3
"""Build the Workshop 1 report from completed design-matrix artifacts."""

from __future__ import annotations

import argparse
import html
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from wargame.experiments.design import CELL_ORDER
from wargame.experiments.io import load_config

TEAM = "Nicolas Acevedo Villena, Subham Saha, and Ziqi Wei"


def _fmt(value: Any, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):,.{digits}f}"


def _table(headers: list[str], rows: list[list[Any]]) -> str:
    clean = lambda value: str(value).replace("|", "\\|").replace("\n", " ")
    lines = ["| " + " | ".join(map(clean, headers)) + " |"]
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    lines.extend("| " + " | ".join(clean(value) for value in row) + " |" for row in rows)
    return "\n".join(lines)


def _inline(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"!\[([^]]*)\]\(([^)]+)\)", r'<img src="\2" alt="\1">', escaped)
    escaped = re.sub(r"\[([^]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', escaped)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    return escaped


def _to_html(markdown: str, title: str) -> str:
    lines = markdown.splitlines()
    body: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.startswith("| ") and index + 1 < len(lines) and lines[index + 1].startswith("| ---"):
            headers = [cell.strip() for cell in line.strip("|").split("|")]
            index += 2
            rows: list[list[str]] = []
            while index < len(lines) and lines[index].startswith("|"):
                rows.append([cell.strip() for cell in lines[index].strip("|").split("|")])
                index += 1
            body.append("<table><thead><tr>" + "".join(f"<th>{_inline(x)}</th>" for x in headers) + "</tr></thead><tbody>")
            body.extend("<tr>" + "".join(f"<td>{_inline(x)}</td>" for x in row) + "</tr>" for row in rows)
            body.append("</tbody></table>")
            continue
        if line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            body.append(f"<h{level}>{_inline(line[level:].strip())}</h{level}>")
        elif line.startswith("- "):
            body.append(f"<p>&bull; {_inline(line[2:])}</p>")
        elif line.startswith("!["):
            body.append(f"<figure>{_inline(line)}</figure>")
        elif line:
            body.append(f"<p>{_inline(line)}</p>")
        index += 1
    css = """
body{font:15px/1.5 Arial,sans-serif;max-width:1200px;margin:2rem auto;padding:0 1rem;color:#202124}
table{border-collapse:collapse;width:100%;margin:1rem 0;font-size:.88rem}
th,td{border:1px solid #ccc;padding:.4rem;text-align:right;vertical-align:top}
th:first-child,td:first-child{text-align:left} img{max-width:100%;height:auto}
code{background:#f4f4f4;padding:.1rem .25rem} h1,h2,h3{line-height:1.2}
"""
    return f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(title)}</title><style>{css}</style></head><body>{''.join(body)}</body></html>\n"


def _validate(by_day: pd.DataFrame) -> None:
    missing = set(CELL_ORDER) - set(by_day["cell"].astype(str))
    if missing:
        raise ValueError(f"Missing design cells: {sorted(missing)}")
    counts = by_day.groupby("cell", observed=True)["day"].nunique()
    if counts.nunique() != 1 or int(counts.iloc[0]) != 60:
        raise ValueError(f"Expected 60 days in every cell, found {counts.to_dict()}")
    gates = {
        "realized POI overflow": by_day["realized_overflow_mwh"].max(),
        "realized simultaneous operation": by_day["simultaneous_charge_discharge_hours"].max(),
        "planned simultaneous operation": by_day["simultaneous_charge_discharge_planned_hours"].max(),
    }
    failed = {name: value for name, value in gates.items() if float(value) > 1e-6}
    if failed:
        raise ValueError(f"Physical completion gates failed: {failed}")
    owners = by_day[by_day["control"] == "D"]
    if owners["game_converged_hours_frac"].fillna(0.0).min() < 1.0:
        raise ValueError("At least one owner cell-hour did not converge")


def _matrix(by_day: pd.DataFrame) -> str:
    means = by_day.groupby("cell", observed=True)["system_objective"].mean()
    rows = []
    for foresight in ("P", "F"):
        values = [foresight, _fmt(means[f"C_{foresight}"], 0)]
        values.extend(
            _fmt(means[f"D_{foresight}_{share}_{info}"], 0)
            for share in ("INJ", "EQ")
            for info in ("FULL", "PRICE", "NONE")
        )
        rows.append(values)
    return _table(
        ["Foresight", "Planner", "Causal full", "Causal aggregate", "Causal none", "Equal full", "Equal aggregate", "Equal none"],
        rows,
    )


def _diagnostics(summary: pd.DataFrame) -> str:
    indexed = summary.set_index("cell")
    rows = []
    for cell in CELL_ORDER:
        row = indexed.loc[cell]
        rows.append(
            [
                cell.replace("_PRICE", "_AGGREGATE"),
                _fmt(row["system_objective_mean"], 0),
                _fmt(row["curtailment_realized_mwh_mean"], 1),
                _fmt(row["throughput_mwh_mean"], 1),
                _fmt(row["attempted_overflow_mwh_mean"], 1),
                _fmt(row.get("game_converged_hours_frac_mean"), 3),
                _fmt(row.get("max_gain_mean"), 3),
            ]
        )
    return _table(
        ["Cell", "J ($/day)", "Curtailment (MWh)", "Throughput (MWh)", "Attempted overflow (MWh)", "Converged-hour fraction", "Max gain ($)"],
        rows,
    )


def _information_equivalence(by_day: pd.DataFrame) -> tuple[float, str]:
    pivot = by_day.pivot(index="day", columns="cell", values="system_objective")
    rows = []
    maxima = []
    for foresight in ("P", "F"):
        for share in ("INJ", "EQ"):
            full = f"D_{foresight}_{share}_FULL"
            aggregate = f"D_{foresight}_{share}_PRICE"
            delta = pivot[full] - pivot[aggregate]
            maxima.append(float(delta.abs().max()))
            rows.append([foresight, share, _fmt(delta.mean(), 6), _fmt(delta.abs().max(), 6)])
    return max(maxima), _table(
        ["Foresight", "Allocation", "Mean full - aggregate ($/day)", "Maximum absolute difference ($/day)"],
        rows,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/base.yaml"))
    args = parser.parse_args()
    cfg = load_config(args.config)
    root = Path(str(cfg.get("paths", {}).get("results", "results")))
    tables = root / "tables"
    by_day = pd.read_csv(tables / "design_matrix_by_day.csv")
    summary = pd.read_csv(tables / "design_matrix_summary.csv")
    effects = pd.read_csv(tables / "design_matrix_effects.csv")
    _validate(by_day)

    effect_rows = [
        [row.factor, row.contrast.replace("PRICE", "AGGREGATE"), row.held_fixed.replace("PRICE", "AGGREGATE"), _fmt(row.mean_usd, 2), _fmt(row.mean_pct_cp, 3)]
        for row in effects.itertuples(index=False)
    ]
    info_max, info_table = _information_equivalence(by_day)
    all_converged = float(by_day.loc[by_day["control"] == "D", "game_converged_hours_frac"].min())
    days = int(by_day["day"].nunique())
    markdown = f"""# Workshop 1 Report: Shared Wind-Storage Operation

Team: {TEAM}

## Scope

The experiment asks how control, foresight, overflow-blame allocation, and
information affect realized operating value for five Anchor Wind owners sharing
one export POI. It contains no minimum-delivery target or shortfall penalty.
DAM awards are retained as market data but are not physical operating limits.

## Matched design

| Dimension | Levels | Isolated change |
| --- | --- | --- |
| Control | planner / owners | joint versus separate decisions |
| Foresight | perfect / forecast | realized future versus COP wind and DA price forecasts |
| Penalty allocation | causal / equal | allocation of the same fixed attempted-overflow charge |
| Information | full / aggregate / none | owner plans, sufficient aggregate signal, or no current rival signal |

The historical `PRICE` cell identifier denotes **aggregate signal** in this
revision. It is not a congestion-price mechanism. FULL and aggregate use the
same payoff, constraints, sequential update, damping, and stopping criteria.

## Data and completion gates

- Operating window: 2025-03-01 to 2025-04-30.
- Complete operating days: {days}.
- Cells: {len(CELL_ORDER)}; day-cell observations: {len(by_day)}.
- Minimum owner converged-hour fraction: {all_converged:.3f}.
- Realized POI overflow and simultaneous battery operation: zero by validation.

## Mean system value

{_matrix(by_day)}

![Mean design-matrix outcomes](../../results/figures/fig_design_matrix.png)

## Matched factor contrasts

{_table(["Factor", "Contrast", "Held fixed", "Mean ($/day)", "Mean (% of C_P)"], effect_rows)}

![Matched daily contrasts](../../results/figures/fig_design_effects.png)

## Information sufficiency check

{info_table}

The maximum daily FULL-versus-aggregate difference is {info_max:.6f} dollars.
Under the current aggregative payoff, owner identities provide no additional
decision-relevant quantity beyond aggregate rival injection. This is the direct
result of the matched information ablation, not evidence that information is
irrelevant in non-aggregative games.

## Operating diagnostics

{_diagnostics(summary)}

## Interpretation boundary

The common reported objective is realized RT energy revenue less discharge
degradation. The attempted-overflow charge is a designed internal incentive and
is reported separately. Results describe one site, one 60-day spring window,
hourly resolution, fixed prices, and a proportional POI realization rule. They
do not represent full ERCOT market clearing or settlement.

See [DESIGN.md](../DESIGN.md), [ASSUMPTIONS.md](../ASSUMPTIONS.md), and the CSV
tables with metadata sidecars for the complete reproducibility record.
"""
    output = Path("docs/workshop1")
    output.mkdir(parents=True, exist_ok=True)
    (output / "report.md").write_text(markdown, encoding="utf-8")
    (output / "report.html").write_text(
        _to_html(markdown, "Workshop 1 Report"), encoding="utf-8"
    )
    print(f"Wrote {output / 'report.md'} and {output / 'report.html'}")


if __name__ == "__main__":
    main()

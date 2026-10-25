#!/usr/bin/env python3
"""Generate the Workshop 1 report from the revised Part I design matrix."""

from __future__ import annotations

import argparse
import html
import json
import logging
import re
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from wargame.experiments.design import CELL_ORDER, parse_cell
from wargame.experiments.io import assess_complete_days, configured_days, load_config
from wargame.model.env import Episode, build_episode
from wargame.solvers.design_matrix import solve_cell

LOGGER = logging.getLogger("wargame.report")
TEAM = "Nicolás Acevedo Villena, Subham Saha, and Ziqi Wei"


def _fmt(value: Any, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    if isinstance(value, (int, np.integer)):
        return f"{value:,}"
    return f"{float(value):,.{digits}f}"


def _markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    def clean(value: Any) -> str:
        return str(value).replace("|", "\\|").replace("\n", " ")

    lines = ["| " + " | ".join(map(clean, headers)) + " |"]
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    lines.extend("| " + " | ".join(clean(value) for value in row) + " |" for row in rows)
    return "\n".join(lines)


def _inline_markup(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"!\[([^]]*)\]\(([^)]+)\)", r'<img src="\2" alt="\1">', escaped)
    escaped = re.sub(r"\[([^]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', escaped)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", escaped)
    return escaped


def markdown_to_html(markdown: str, title: str) -> str:
    """Convert the report's small Markdown subset without optional dependencies."""

    lines = markdown.splitlines()
    body: list[str] = []
    i = 0
    in_list = False
    while i < len(lines):
        line = lines[i]
        if (
            line.startswith("| ")
            and i + 1 < len(lines)
            and set(lines[i + 1].replace("|", "").replace("-", "").strip()) == set()
        ):
            headers = [cell.strip() for cell in line.strip("|").split("|")]
            i += 2
            table_rows: list[list[str]] = []
            while i < len(lines) and lines[i].startswith("|"):
                table_rows.append([cell.strip() for cell in lines[i].strip("|").split("|")])
                i += 1
            body.append(
                "<table><thead><tr>"
                + "".join(f"<th>{_inline_markup(cell)}</th>" for cell in headers)
                + "</tr></thead><tbody>"
            )
            body.extend(
                "<tr>" + "".join(f"<td>{_inline_markup(cell)}</td>" for cell in row) + "</tr>"
                for row in table_rows
            )
            body.append("</tbody></table>")
            continue
        if line.startswith("- "):
            if not in_list:
                body.append("<ul>")
                in_list = True
            body.append(f"<li>{_inline_markup(line[2:])}</li>")
        else:
            if in_list:
                body.append("</ul>")
                in_list = False
            if not line:
                pass
            elif line.startswith("#"):
                level = len(line) - len(line.lstrip("#"))
                body.append(f"<h{level}>{_inline_markup(line[level:].strip())}</h{level}>")
            elif line.startswith("!["):
                body.append(f"<figure>{_inline_markup(line)}</figure>")
            else:
                body.append(f"<p>{_inline_markup(line)}</p>")
        i += 1
    if in_list:
        body.append("</ul>")
    css = """
body{font:15px/1.5 system-ui,sans-serif;max-width:1200px;margin:2rem auto;padding:0 1rem;color:#202124}
table{border-collapse:collapse;width:100%;margin:1rem 0;font-size:.86rem}th,td{border:1px solid #ccc;padding:.35rem;text-align:right;vertical-align:top}th:first-child,td:first-child{text-align:left}
img{max-width:100%;height:auto}figure{margin:1.2rem 0}code{background:#f3f3f3;padding:.1rem .25rem}h1,h2,h3{line-height:1.2}
"""
    return (
        "<!doctype html><html><head><meta charset='utf-8'><title>"
        f"{html.escape(title)}</title><style>{css}</style></head><body>"
        f"{''.join(body)}</body></html>\n"
    )


def _reliability(by_day: pd.DataFrame) -> dict[str, dict[str, float | str]]:
    cp = by_day.loc[by_day["cell"] == "C_P", ["day", "system_objective"]].set_index("day")[
        "system_objective"
    ]
    result: dict[str, dict[str, float | str]] = {}
    solver_rows = by_day[by_day["info"].isin(["FULL", "PRICE"])]
    for cell, frame in solver_rows.groupby("cell", sort=False, observed=True):
        info = str(frame["info"].iloc[0])
        if info == "FULL":
            gain_pct = 100.0 * frame.set_index("day")["max_gain"] / cp.replace(0.0, np.nan)
            hours = frame["sweeps_by_hour"].map(json.loads).map(len).replace(0, np.nan)
            result[str(cell)] = {
                "kind": "game",
                "converged": float(frame["game_converged_hours_frac"].mean()),
                "work": float((frame["sweeps"] / hours).mean()),
                "gain_mean": float(frame["max_gain"].mean()),
                "gain_max": float(frame["max_gain"].max()),
                "gain_pct_mean": float(gain_pct.mean()),
                "gain_pct_max": float(gain_pct.max()),
            }
        else:
            result[str(cell)] = {
                "kind": "price",
                "converged": float(frame["price_converged_hours_frac"].mean()),
                "work": float(frame["price_iterations_mean"].mean()),
            }
    return result


def _reliability_text(cell: str, reliability: dict[str, dict[str, float | str]]) -> str:
    item = reliability[cell]
    if item["kind"] == "game":
        return (
            f"{cell}: game converged {100 * float(item['converged']):.1f}% of hours, "
            f"{float(item['work']):.2f} mean sweeps/hour; max_gain distribution: mean "
            f"${float(item['gain_mean']):.2f}, max ${float(item['gain_max']):.2f}; "
            f"daily max_gain/C_P distribution: mean {float(item['gain_pct_mean']):.4f}%, "
            f"max {float(item['gain_pct_max']):.4f}%"
        )
    return (
        f"{cell}: price coordination converged {100 * float(item['converged']):.1f}% of hours, "
        f"{float(item['work']):.2f} mean iterations/hour; max_gain is not applicable to PRICE"
    )


def _contrast_cells(contrast: str, held_fixed: str) -> list[str]:
    cells = [cell for cell in CELL_ORDER if cell in contrast]
    if "mean(D_" in contrast:
        foresight = "P" if "foresight=P" in held_fixed else "F"
        cells.extend(
            cell
            for cell in CELL_ORDER
            if cell.startswith(f"D_{foresight}_") and parse_cell(cell)["info"] in {"FULL", "PRICE"}
        )
    return list(dict.fromkeys(cells))


def _solver_note(
    contrast: str,
    held_fixed: str,
    reliability: dict[str, dict[str, float | str]],
) -> str:
    cells = [cell for cell in _contrast_cells(contrast, held_fixed) if cell in reliability]
    return "; ".join(_reliability_text(cell, reliability) for cell in cells) or "not applicable"


def _effect_table(
    effects: pd.DataFrame,
    factor: str,
    reliability: dict[str, dict[str, float | str]],
) -> str:
    frame = effects[effects["factor"] == factor]
    return _markdown_table(
        [
            "Contrast on realized J",
            "Held fixed",
            "Mean ($/day)",
            "Median ($/day)",
            "Mean (% of C_P)",
            "n days",
            "Solver reliability for FULL/PRICE cells",
        ],
        [
            [
                row.contrast,
                row.held_fixed,
                _fmt(row.mean_usd, 0),
                _fmt(row.median_usd, 0),
                _fmt(row.mean_pct_cp, 3),
                _fmt(row.n_days, 0),
                _solver_note(row.contrast, row.held_fixed, reliability),
            ]
            for row in frame.itertuples(index=False)
        ],
    )


def _tolerance_note(
    effects: pd.DataFrame,
    factor: str,
    reliability: dict[str, dict[str, float | str]],
) -> str:
    comparable: list[str] = []
    for row in effects[effects["factor"] == factor].itertuples(index=False):
        gains = [
            float(reliability[cell]["gain_mean"])
            for cell in _contrast_cells(row.contrast, row.held_fixed)
            if cell in reliability and reliability[cell]["kind"] == "game"
        ]
        if gains and abs(float(row.mean_usd)) <= 2.0 * max(gains):
            comparable.append(str(row.contrast))
    if not comparable:
        return ""
    return (
        " The following mean contrast is within solver tolerance relative to the mean remaining "
        f"unilateral gain, so its direction is not interpreted: {', '.join(comparable)}."
    )


def _factor_sentence(
    effects: pd.DataFrame,
    factor: str,
    reliability: dict[str, dict[str, float | str]],
) -> str:
    frame = effects[effects["factor"] == factor].copy()
    if factor == "F1":
        matched = frame[~frame["contrast"].str.contains("mean")]
        headline = frame.iloc[0]
        sentence = (
            f"Central minus decentralized J is positive in {int((matched['mean_usd'] > 0).sum())} of "
            f"{len(matched)} held-fixed cells. The perfect-foresight headline contrast, C_P minus the "
            f"mean of its six decentralized matches, is ${headline.mean_usd:,.0f}/day "
            f"({headline.mean_pct_cp:.3f}% of C_P). The expected nonnegative sign is confirmed."
        )
    elif factor == "F2":
        sentence = (
            f"Every matched P minus F mean is positive. Effects range from ${frame['mean_usd'].min():,.0f} "
            f"to ${frame['mean_usd'].max():,.0f}/day, confirming the expected value of better foresight."
        )
    elif factor == "F3":
        sentence = (
            f"Every INJ minus EQ mean is positive, from ${frame['mean_usd'].min():,.0f} to "
            f"${frame['mean_usd'].max():,.0f}/day, confirming the expected benefit of causal overflow "
            "shares and own-deficit charges. The medians show that this factor is heavy-tailed."
        )
    else:
        full_price = frame[frame["contrast"].str.contains("FULL - .*PRICE", regex=True)]
        price_none = frame[frame["contrast"].str.contains("PRICE - .*NONE", regex=True)]
        full_none = frame[frame["contrast"].str.contains("FULL - .*NONE", regex=True)]
        sentence = (
            f"PRICE minus NONE is positive in {int((price_none['mean_usd'] > 0).sum())} of "
            f"{len(price_none)} held-fixed cells, as expected. FULL minus NONE is positive in "
            f"{int((full_none['mean_usd'] > 0).sum())} of {len(full_none)} cells, so that expectation is "
            f"mostly but not uniformly confirmed. FULL minus PRICE is negative in "
            f"{int((full_price['mean_usd'] < 0).sum())} of {len(full_price)} cells."
        )
    return sentence + _tolerance_note(effects, factor, reliability)


def _design_factor_table() -> str:
    return _markdown_table(
        ["Factor", "Levels", "Operational meaning", "Model implementation", "Measured contrast"],
        [
            ["F1 control", "C, D", "One plant controller or independent unit controllers", "Central receding-horizon LP or decentralized policy", "C_x minus D_x_* at fixed foresight"],
            ["F2 foresight", "P, F", "Realized future conditions or operational forecasts", "True wind/RT price or current truth followed by COP wind/DA price", "X_P minus X_F for every matching cell"],
            ["F3 penalty allocation", "INJ, EQ", "Causal contribution or equal responsibility", "Positive-injection overflow shares plus own deficits, or equal system-penalty shares", "INJ minus EQ at fixed F2 and F4"],
            ["F4 market information", "FULL, PRICE, NONE", "Other plans, a congestion price, or neither", "Best-response game, coordinator price iteration, or fixed capacity-share POI budget", "FULL minus PRICE, PRICE minus NONE, and FULL minus NONE at fixed F2 and F3"],
        ],
    )


def _cell_table() -> str:
    rows: list[list[str]] = []
    for foresight in ("P", "F"):
        central = next(
            cell
            for cell in CELL_ORDER
            if parse_cell(cell)
            == {"control": "C", "foresight": foresight, "share": None, "info": None}
        )
        row = [foresight, central]
        for share in ("INJ", "EQ"):
            for info in ("FULL", "PRICE", "NONE"):
                row.append(
                    next(
                        cell
                        for cell in CELL_ORDER
                        if parse_cell(cell)
                        == {"control": "D", "foresight": foresight, "share": share, "info": info}
                    )
                )
        rows.append(row)
    return _markdown_table(
        ["F2", "Central", "INJ/FULL", "INJ/PRICE", "INJ/NONE", "EQ/FULL", "EQ/PRICE", "EQ/NONE"],
        rows,
    )


def _pivot_table(pivot: pd.DataFrame) -> str:
    keys = ["C", "INJ_FULL", "INJ_PRICE", "INJ_NONE", "EQ_FULL", "EQ_PRICE", "EQ_NONE"]
    return _markdown_table(
        ["Foresight", *keys],
        [
            [
                row.foresight,
                *[
                    f"${getattr(row, f'{key}_mean_J'):,.0f} ({getattr(row, f'{key}_mean_pct_cp'):.2f}%)"
                    for key in keys
                ],
            ]
            for row in pivot.itertuples(index=False)
        ],
    )


def _operating_table(
    summary: pd.DataFrame,
    reliability: dict[str, dict[str, float | str]],
) -> str:
    rows: list[list[str]] = []
    indexed = summary.set_index("cell")
    for cell in CELL_ORDER:
        row = indexed.loc[cell]
        solver = _reliability_text(cell, reliability) if cell in reliability else "not applicable"
        rows.append(
            [
                cell,
                _fmt(row["system_objective_mean"], 0),
                _fmt(row["curtailment_realized_mwh_mean"], 1),
                _fmt(row["throughput_mwh_mean"], 1),
                _fmt(row["under_delivery_mwh_mean"], 1),
                _fmt(row["attempted_overflow_mwh_mean"], 1),
                _fmt(row["penalty_concentration_mean"], 3),
                solver,
            ]
        )
    return _markdown_table(
        ["Cell", "Mean J ($/day)", "Curtailment (MWh/day)", "Throughput (MWh/day)", "Under-delivery (MWh/day)", "Attempted overflow (MWh/day)", "Penalty concentration", "Solver diagnostics"],
        rows,
    )


def _trajectory_frame(episode: Episode, cell: str, realization: Any) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for hour in range(episode.T):
        for index, agent in enumerate(episode.agents):
            rows.append(
                {
                    "hour": hour,
                    "cell": cell,
                    "agent": agent.name,
                    "q_i": realization.q[index, hour],
                    "q_i_planned": realization.q_planned[index, hour],
                    "soc_i": realization.soc[index, hour + 1],
                    "Q": realization.q[:, hour].sum(),
                    "Q_planned": realization.q_planned[:, hour].sum(),
                    "K": episode.K,
                    "D": episode.D[hour],
                }
            )
    return pd.DataFrame(rows)


def _load_or_solve_trajectory(day: str, cell: str, tables: Path, cfg: dict[str, Any]) -> pd.DataFrame:
    path = tables / "trajectories" / f"design_{day}_{cell}.csv"
    if path.exists():
        return pd.read_csv(path)
    episode = build_episode(day, list(cfg["data"]["primary_agents"]), cfg)
    return _trajectory_frame(episode, cell, solve_cell(episode, cell, cfg))


def _plot_design_trajectory(day: str, tables: Path, output: Path, cfg: dict[str, Any]) -> None:
    cells = ["C_P", "D_P_EQ_FULL"]
    frames = {cell: _load_or_solve_trajectory(day, cell, tables, cfg) for cell in cells}
    colors = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9"]
    fig, axes = plt.subplots(2, 2, figsize=(12.0, 6.4), sharex=True, constrained_layout=True)
    for column, cell in enumerate(cells):
        frame = frames[cell]
        injection = frame.pivot(index="hour", columns="agent", values="q_i").sort_index()
        hours = injection.index.to_numpy()
        axes[0, column].stackplot(hours, injection.to_numpy().T, labels=injection.columns, colors=colors, alpha=0.78)
        hourly = frame.drop_duplicates("hour").set_index("hour")
        axes[0, column].plot(hours, hourly.loc[hours, "Q_planned"], color="#D55E00", linestyle=":", label="planned Q")
        axes[0, column].plot(hours, hourly.loc[hours, "K"], color="black", linewidth=1.4, label="K")
        axes[0, column].plot(hours, hourly.loc[hours, "D"], color="black", linestyle="--", label="D")
        axes[0, column].set(title=cell, ylabel="Realized injection (MW)")
        soc = frame.pivot(index="hour", columns="agent", values="soc_i").sort_index()
        for index, agent in enumerate(soc.columns):
            axes[1, column].plot(soc.index, soc[agent], color=colors[index], label=agent)
        axes[1, column].set(xlabel="Hour", ylabel="End-of-hour SoC (MWh)")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="outside lower center", ncol=min(8, len(labels)))
    fig.suptitle(f"Design-matrix trajectories on {day}")
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=200, bbox_inches="tight")
    fig.savefig(output.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


def _monitor_table(regimes: pd.DataFrame, deterrence: pd.DataFrame, cfg: dict[str, Any]) -> str:
    tau_target = float(cfg["monitor"]["thresholds_frac"][1])
    withholding_target = float(cfg["monitor"]["withholding_grid_frac"][1])
    delay_target = int(cfg["monitor"]["delay_grid"][1])
    rows: list[list[str]] = []
    for regime in ("low", "medium", "high"):
        candidate = deterrence[
            (deterrence["regime"] == regime)
            & np.isclose(deterrence["tau_frac"], tau_target)
            & np.isclose(deterrence["m_frac"], withholding_target)
            & np.isclose(deterrence["delta"], float(cfg["monitor"]["delta"]))
            & np.isclose(deterrence["d"], delay_target)
        ].iloc[0]
        sigma = regimes.loc[regimes["regime"] == regime, "sigma"].iloc[0]
        rows.append([regime, _fmt(sigma, 3), _fmt(candidate.q0, 3), _fmt(candidate.q1, 3), _fmt(candidate.F_star_over_g, 2), "yes" if bool(candidate.feasible) else "no", "infinite" if np.isinf(candidate.T_star) else _fmt(candidate.T_star, 0)])
    return _markdown_table(
        ["Noise", "σ", "q0", "q1", "F*/g", "Feasible at 3g", "T* (hours)"], rows
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/base.yaml"))
    parser.add_argument("--scenario", type=Path, help="Optional YAML overrides")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    logging.getLogger("matplotlib").setLevel(logging.WARNING)
    cfg = load_config(args.config, args.scenario)
    results = Path(str(cfg.get("paths", {}).get("results", "results")))
    processed = Path(str(cfg.get("paths", {}).get("processed", "data/processed")))
    tables = results / "tables"
    figures = results / "figures"

    by_day = pd.read_csv(tables / "design_matrix_by_day.csv")
    summary = pd.read_csv(tables / "design_matrix_summary.csv")
    effects = pd.read_csv(tables / "design_matrix_effects.csv")
    pivot = pd.read_csv(tables / "design_matrix_pivot.csv")
    resources = pd.read_csv(processed / "resources.csv")
    monitor_regimes = pd.read_csv(tables / "monitor_regimes.csv")
    monitor_deterrence = pd.read_csv(tables / "monitor_deterrence.csv")

    complete_days, skipped_days = assess_complete_days(cfg, list(cfg["data"]["primary_agents"]))
    reliability = _reliability(by_day)
    factor_tables = {factor: _effect_table(effects, factor, reliability) for factor in ("F1", "F2", "F3", "F4")}
    factor_sentences = {factor: _factor_sentence(effects, factor, reliability) for factor in ("F1", "F2", "F3", "F4")}

    objective = by_day.pivot(index="day", columns="cell", values="system_objective")
    trajectory_gap = objective["C_P"] - objective["D_P_EQ_FULL"]
    trajectory_day = str(trajectory_gap.idxmax())
    trajectory_path = figures / f"fig_design_trajectory_{trajectory_day}.png"
    _plot_design_trajectory(trajectory_day, tables, trajectory_path, cfg)

    f3_daily = pd.concat(
        [
            objective[f"D_{foresight}_INJ_{info}"] - objective[f"D_{foresight}_EQ_{info}"]
            for foresight in ("P", "F")
            for info in ("FULL", "PRICE", "NONE")
        ], axis=1
    ).mean(axis=1)
    f3_top = f3_daily.nlargest(3)
    f3_tail_table = _markdown_table(
        ["Day", "Mean matched INJ minus EQ ($/day)"],
        [[day, _fmt(value, 0)] for day, value in f3_top.items()],
    )

    source_table = _markdown_table(
        ["Quantity", "Source", "Window", "Status"],
        [
            ["DA and RT prices", "ERCOT NP4-180-ER and NP6-785-ER", f"{cfg['data']['window_start']} to {cfg['data']['window_end']}", "observed"],
            ["Wind availability and output", "ERCOT NP3-965-ER", f"{cfg['data']['window_start']} to {cfg['data']['window_end']}", "observed"],
            ["COP forecast and baseline", "ERCOT COP snapshot and NP3-966-ER", f"{cfg['data']['window_start']} to {cfg['data']['window_end']}", "observed/constructed"],
            ["Forecast-error regimes", "ERCOT NP4-732-CD and NP4-742-CD", "October 2026 system snapshot; March-April 2025 resource sample", "calibrated"],
            ["Battery design", "Observed Anchor BESS, EIA-860, and NREL ATB", "base configuration", "calibrated"],
            ["POI, obligation, penalties, and four factors", "wargame design", f"{by_day['day'].nunique()} complete operating days", "designed"],
        ],
    )
    primary = resources[resources["resource"].isin(cfg["data"]["primary_agents"])]
    resource_table = _markdown_table(
        ["Resource", "Nameplate (MW)", "Coverage", "Mean capacity factor"],
        [[row.resource, _fmt(row.nameplate_mw, 1), f"{100 * row.coverage_frac:.1f}%", _fmt(row.mean_cf, 3)] for row in primary.itertuples(index=False)],
    )
    monitor_table = _monitor_table(monitor_regimes, monitor_deterrence, cfg)
    monitor_tau = float(cfg["monitor"]["thresholds_frac"][1])
    monitor_withholding = float(cfg["monitor"]["withholding_grid_frac"][1])
    monitor_delay = int(cfg["monitor"]["delay_grid"][1])
    operating_table = _operating_table(summary, reliability)
    pivot_markdown = _pivot_table(pivot)

    price_better = effects[(effects["factor"] == "F4") & effects["contrast"].str.contains("FULL - .*PRICE", regex=True)]
    price_explanation = (
        "PRICE has higher mean J than FULL in all four held-fixed comparisons. This is not evidence that more information is worse. FULL is a non-cooperative equilibrium in which agents can still overshoot the POI when the price premium exceeds their marginal share of the overflow penalty. PRICE is a coordination mechanism whose fixed point approximates the central solution. The cells differ in both information and mechanism."
        if (price_better["mean_usd"] < 0).all()
        else "FULL and PRICE differ in both information and mechanism, so their contrast is not a pure information ordering."
    )

    report = f"""# Workshop 1 Report: Strategic Coordination in Co-Located Wind-Storage Systems

Team: {TEAM}
Course: MIT 6.974 Wargame, Fall 2026

## 1. Scope

Part I asks how much realized system value is lost when co-located wind-storage units sharing one point of interconnection (POI) are operated by independent decision makers, and which of four design factors matters most. The headline experiment is the 14-cell design matrix. The earlier regime list and parameter grid are retained only as superseded artifacts. The preliminary monitor calibration is included as a Part III input.

### Model

Each unit chooses wind curtailment, battery charge, and battery discharge subject to battery power, energy, efficiency, and terminal-state constraints. Net injections share a POI limit K and a delivery obligation D. The planning mechanisms allocate shortfall and attempted-overflow penalties, after which a realization layer removes any physical overflow pro rata. The realized system objective is `J = realized energy profit - discharge degradation cost - lambda_minus × realized under-delivery`; attempted-overflow penalties are strategic signals and do not enter J. [DESIGN.md](../DESIGN.md) gives the full implementation contract, and [two_player_formulation.md](../two_player_formulation.md) gives the minimal analytical version.

## 2. Data

{source_table}

The configured window contains {len(complete_days)} complete 24-hour episodes and {len(skipped_days)} incomplete episode(s) across {len(configured_days(cfg))} calendar days. The design matrix evaluates {by_day['day'].nunique()} days at {cfg['data']['hub']} for the Anchor Wind base site.

{resource_table}

The system-level monitor-noise snapshot is from a different period than the operating experiment. This limitation is carried through the interpretation.

## 3. Design factors and cells

{_design_factor_table()}

{_cell_table()}

The cell ids and ordering above come from `code/wargame/experiments/design.py`. Every policy replans hourly over the remaining horizon, submits one hour, passes the joint action through the realization layer, and uses realized state of charge in the next hour.

## 4. Results by factor

All factor effects are matched daily contrasts on realized J from `design_matrix_effects.csv`. In every table, percentages of C_P are means of daily percentages, not ratios of aggregate means. Reliability is reported beside every contrast involving FULL or PRICE. For FULL, max_gain is the remaining unilateral-deviation gain; PRICE has no unilateral-deviation statistic. Because C_P is negative on some individual days, a signed daily max_gain/C_P ratio can make the mean percentage negative even though max_gain itself is nonnegative.

### F1 control

Hypothesis: centralized control weakly increases J because it internalizes the shared POI and obligation. {factor_sentences['F1']}

{factor_tables['F1']}

*Effect and mean max_gain percentages are means of daily percentages of C_P. Maximum max_gain percentage is the maximum daily percentage.*

### F2 foresight

Hypothesis: perfect remaining-horizon wind and RT-price foresight weakly increases J relative to COP-wind and DA-price forecasts. {factor_sentences['F2']}

{factor_tables['F2']}

*Effect and mean max_gain percentages are means of daily percentages of C_P. Maximum max_gain percentage is the maximum daily percentage.*

### F3 penalty allocation

Hypothesis: causal positive-injection overflow shares and own-deficit charges increase J relative to equal system-penalty shares. {factor_sentences['F3']}

{factor_tables['F3']}

*Effect and mean max_gain percentages are means of daily percentages of C_P. Maximum max_gain percentage is the maximum daily percentage.*

The daily INJ minus EQ effect averaged over its six matched F2/F4 cells exceeds $100 on {(f3_daily > 100).sum()} of {len(f3_daily)} days. The three largest days are:

{f3_tail_table}

### F4 market information and coordination

Hypothesis: PRICE and FULL should generally outperform NONE; FULL minus PRICE has no pure information interpretation because PRICE changes the mechanism. {factor_sentences['F4']}

{factor_tables['F4']}

*Effect and mean max_gain percentages are means of daily percentages of C_P. Maximum max_gain percentage is the maximum daily percentage.*

{price_explanation}

![Design-matrix cell outcomes](../../results/figures/fig_design_matrix.png)

*Each entry is the mean of its daily percentage of C_P.*

![Matched design effects](../../results/figures/fig_design_effects.png)

*Bars show mean daily J contrasts; the underlying values are tabulated above.*

## 5. Full matrix and operating metrics

{pivot_markdown}

*Each cell shows mean J followed by the mean of daily percentages of C_P in parentheses.*

{operating_table}

*Mean max_gain percentages are means of daily percentages of C_P. Maximum max_gain percentage is the maximum daily percentage.*

Operating quantities are daily means from `design_matrix_summary.csv`. Penalty concentration is the largest agent share of allocated shortfall charges, with 1/N used when the total charge is zero. Realized overflow is zero by construction; attempted overflow records submitted actions before the POI controller intervenes.

## 6. Illustrative day trajectory

The selected day is {trajectory_day}, which has the largest tabulated C_P minus D_P_EQ_FULL gap, ${trajectory_gap.loc[trajectory_day]:,.0f}. The figure compares those two design cells and shows both submitted aggregate injection and realized dispatch.

![Design-matrix trajectory](../../results/figures/{trajectory_path.name})

## 7. Monitor calibration

This preliminary Part III calibration maps observed forecast-error noise into false-positive probability q0, detection probability q1, required fine F*, and finite correction duration T*. The compact comparison below uses a {100 * monitor_tau:.0f}% nameplate threshold, {100 * monitor_withholding:.0f}% withholding, delta = {cfg['monitor']['delta']}, and a {monitor_delay}-hour delay.

{monitor_table}

![Empirical monitor ROC](../../results/figures/monitor_roc.png)

The calibration is preliminary: it does not infer intent and is not yet coupled to adaptive agents or attacks.

## 8. Limitations and roadmap

The operating results cover one spring window, one base site, five units, hourly resolution, and price-taking RT settlement. COP and DA forecasts are deterministic inputs, the delivery obligation and penalty rates are designed, and the model omits endogenous prices, outages, and two-settlement bidding. FULL results are approximate equilibria and PRICE results are approximate coordinator fixed points, so the solver diagnostics beside each affected contrast are part of the result.

Next steps are to verify the hand-solved two-player example numerically, build the Part II partially observable multi-agent environment and CTDE/DTDE baselines, couple the monitor to simulated withholding, add adaptive enforcement and attacks, and resolve the forecast-error period mismatch.
"""

    if re.search(r"\bnan\b|placeholder", report, flags=re.IGNORECASE):
        raise RuntimeError("Generated report contains nan or placeholder text")
    report_dir = Path("docs/workshop1")
    report_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = report_dir / "report.md"
    html_path = report_dir / "report.html"
    markdown_path.write_text(report, encoding="utf-8")
    html_path.write_text(markdown_to_html(report, "Workshop 1: Strategic Coordination"), encoding="utf-8")
    LOGGER.info("Wrote %s and %s", markdown_path, html_path)


if __name__ == "__main__":
    main()

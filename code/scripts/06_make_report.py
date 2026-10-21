#!/usr/bin/env python3
"""Generate Workshop 1 figures and assemble Markdown and HTML reports."""

from __future__ import annotations

import argparse
import html
import inspect
import json
import logging
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from wargame.experiments.io import assess_complete_days, configured_days, load_config
from wargame.experiments.metrics import add_system_objective, gaps
from wargame.experiments.plots import make_all_figures, sensitivity_config_means
from wargame.monitor import detection as _detection

LOGGER = logging.getLogger("wargame.report")
TEAM = "Nicolás Acevedo Villena, Subham Saha, and Ziqi Wei"
REGIME_ORDER = ["R1", "R1_f", "R2", "R2_f", "R3a", "R3b", "R4a", "R4a_f", "R4b", "R4b_f"]


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


def _sensitivity_gaps(frame: pd.DataFrame) -> pd.DataFrame:
    index = ["kappa_K", "correlation_set", "storage_design", "day"]
    return gaps(frame, index_columns=index)


def _monitor_table(
    regimes: pd.DataFrame,
    roc: pd.DataFrame,
    deterrence: pd.DataFrame,
    cfg: dict[str, Any],
) -> tuple[str, pd.DataFrame]:
    del roc  # deterrence rows contain matched empirical q0/q1 values
    target_thresholds = (0.05, 0.10)
    target_withholding = (0.05, 0.10)
    delta_target = float(cfg["monitor"]["delta"])
    delay_target = 4
    fine_cap = float(cfg["monitor"]["fine_cap_multiple_of_gain"])
    rows: list[dict[str, Any]] = []
    for regime in ("low", "medium", "high"):
        sigma = float(regimes.loc[regimes["regime"] == regime, "sigma"].iloc[0])
        for target in target_thresholds:
            threshold = float(
                deterrence.loc[
                    deterrence["regime"] == regime,
                    "tau_frac",
                ].iloc[
                    (
                        deterrence.loc[deterrence["regime"] == regime, "tau_frac"]
                        - target
                    ).abs().argmin()
                ]
            )
            for withholding_target in target_withholding:
                regime_rows = deterrence[deterrence["regime"] == regime]
                withholding = float(
                    regime_rows.loc[
                        (regime_rows["m_frac"] - withholding_target).abs().idxmin(),
                        "m_frac",
                    ]
                )
                selected = deterrence[
                    (deterrence["regime"] == regime)
                    & np.isclose(deterrence["tau_frac"], threshold)
                    & np.isclose(deterrence["m_frac"], withholding)
                ].copy()
                closest_delta = selected.loc[
                    (selected["delta"] - delta_target).abs().idxmin(), "delta"
                ]
                selected = selected[np.isclose(selected["delta"], closest_delta)]
                closest_delay = selected.loc[
                    (selected["d"] - delay_target).abs().idxmin(), "d"
                ]
                row = selected[np.isclose(selected["d"], closest_delay)].iloc[0]
                rows.append(
                    {
                        "regime": regime,
                        "sigma": sigma,
                        "tau_frac": threshold,
                        "m_frac": withholding,
                        "q0": row["q0"],
                        "q1": row["q1"],
                        "delta": row["delta"],
                        "d": row["d"],
                        "F_star_over_g": row["F_star_over_g"],
                        "F_star_kappa_over_g": row["F_star_kappa_over_g"],
                        "feasible": bool(row["feasible"]),
                        "T_star": row["T_star"],
                    }
                )
    table = pd.DataFrame(rows)
    markdown = _markdown_table(
        [
            "Noise", "σ", "τ/nameplate", "m/nameplate", "q0", "q1", "δ", "d (h)", "F*/g",
            "F*·κ/g", f"Feasible (F* ≤ F̄ = {fine_cap:g}g)", "T*",
        ],
        [
            [
                row.regime,
                _fmt(row.sigma, 3),
                _fmt(row.tau_frac, 2),
                _fmt(row.m_frac, 2),
                _fmt(row.q0, 3),
                _fmt(row.q1, 3),
                _fmt(row.delta, 2),
                _fmt(row.d, 0),
                _fmt(row.F_star_over_g, 2),
                _fmt(row.F_star_kappa_over_g, 2),
                "yes" if row.feasible else "no",
                "∞" if np.isinf(row.T_star) else _fmt(row.T_star, 0),
            ]
            for row in table.itertuples(index=False)
        ],
    )
    return markdown, table


def _inline_markup(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(
        r"!\[([^]]*)\]\(([^)]+)\)",
        r'<img src="\2" alt="\1">',
        escaped,
    )
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
        if line.startswith("| ") and i + 1 < len(lines) and set(lines[i + 1].replace("|", "").replace("-", "").strip()) == set():
            headers = [cell.strip() for cell in line.strip("|").split("|")]
            i += 2
            table_rows: list[list[str]] = []
            while i < len(lines) and lines[i].startswith("|"):
                table_rows.append([cell.strip() for cell in lines[i].strip("|").split("|")])
                i += 1
            body.append("<table><thead><tr>" + "".join(f"<th>{_inline_markup(cell)}</th>" for cell in headers) + "</tr></thead><tbody>")
            body.extend("<tr>" + "".join(f"<td>{_inline_markup(cell)}</td>" for cell in row) + "</tr>" for row in table_rows)
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
body{font:15px/1.5 system-ui,sans-serif;max-width:1050px;margin:2rem auto;padding:0 1rem;color:#202124}
table{border-collapse:collapse;width:100%;margin:1rem 0;font-size:.9rem}th,td{border:1px solid #ccc;padding:.35rem;text-align:right}th:first-child,td:first-child{text-align:left}
img{max-width:100%;height:auto}figure{margin:1.2rem 0}code{background:#f3f3f3;padding:.1rem .25rem}h1,h2,h3{line-height:1.2}
"""
    return f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(title)}</title><style>{css}</style></head><body>{''.join(body)}</body></html>\n"


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
    outputs = make_all_figures(cfg)
    results = Path(str(cfg.get("paths", {}).get("results", "results")))
    processed = Path(str(cfg.get("paths", {}).get("processed", "data/processed")))
    tables = results / "tables"
    lambda_minus = float(cfg["poi"]["lambda_minus"])

    regimes = add_system_objective(pd.read_csv(tables / "regimes_by_day.csv"), lambda_minus)
    matrix = pd.read_csv(tables / "matrix_summary.csv")
    matrix_pct = pd.read_csv(tables / "matrix_summary_pct_r1.csv")
    sensitivity = add_system_objective(pd.read_csv(tables / "sensitivity.csv"), lambda_minus)
    agent_sets = pd.read_csv(tables / "agent_sets.csv")
    resources = pd.read_csv(processed / "resources.csv")
    monitor_regimes = pd.read_csv(tables / "monitor_regimes.csv")
    monitor_roc = pd.read_csv(tables / "monitor_roc.csv")
    monitor_deterrence = pd.read_csv(tables / "monitor_deterrence.csv")

    regime_means = regimes.groupby("regime", sort=False).agg(
        objective=("system_objective", "mean"),
        profit=("system_profit_realized", "mean"),
        curtailment=("curtailment_realized_mwh", "mean"),
        throughput=("throughput_mwh", "mean"),
        under_delivery=("under_delivery_mwh", "mean"),
        overflow=("attempted_overflow_mwh", "mean"),
        convergence=("converged", "mean"),
    ).reindex(REGIME_ORDER)
    headline = _markdown_table(
        [
            "Regime", "System objective J ($/day)", "Raw profit ($/day)",
            "Curtailment (MWh)", "Throughput (MWh)", "Under-delivery (MWh)",
            "Overflow attempt (MWh)", "Converged",
        ],
        [
            [
                regime, _fmt(row.objective, 0), _fmt(row.profit, 0),
                _fmt(row.curtailment, 1), _fmt(row.throughput, 1),
                _fmt(row.under_delivery, 1), _fmt(row.overflow, 1),
                "n/a" if pd.isna(row.convergence) else f"{100 * row.convergence:.0f}%",
            ]
            for regime, row in regime_means.iterrows()
        ],
    )

    day_gaps = gaps(regimes)
    gap_labels = (
        ("strategic_gap", "Strategic gap"),
        ("info_gap_aggregate", "Aggregate-information gap"),
        ("info_gap_local", "Local-information gap"),
        ("signal_value", "Aggregate-signal value"),
        ("forecast_gap_central", "Central forecast gap"),
        ("forecast_gap_game", "Game forecast gap"),
        ("forecast_gap_mpc", "Aggregate-MPC forecast gap"),
    )
    objective_gaps = _markdown_table(
        ["Objective-based gap", "Mean ($/day)", "Median ($/day)", "Mean of daily % of J_R1", "Maximum ($/day)"],
        [
            [
                label, _fmt(day_gaps[column].mean()), _fmt(day_gaps[column].median()),
                _fmt(day_gaps[f"{column}_pct_r1"].mean()), _fmt(day_gaps[column].max()),
            ]
            for column, label in gap_labels
        ],
    )
    profit_gaps = _markdown_table(
        ["Raw-profit gap", "Mean ($/day)", "Median ($/day)", "Mean of daily % of R1 profit", "Maximum ($/day)"],
        [
            [
                label, _fmt(day_gaps[f"{column}_profit"].mean()),
                _fmt(day_gaps[f"{column}_profit"].median()),
                _fmt(day_gaps[f"{column}_profit_pct_r1"].mean()),
                _fmt(day_gaps[f"{column}_profit"].max()),
            ]
            for column, label in gap_labels
        ],
    )
    poa_table = _markdown_table(
        ["Efficiency ratio", "Objective mean", "Objective median", "Raw-profit mean", "Raw-profit median"],
        [
            [
                label, _fmt(day_gaps[column].mean(), 3), _fmt(day_gaps[column].median(), 3),
                _fmt(day_gaps[f"{column}_profit"].mean(), 3),
                _fmt(day_gaps[f"{column}_profit"].median(), 3),
            ]
            for column, label in (("PoA", "R1 / R2"), ("PoA_f", "R1_f / R2_f"))
        ],
    )

    prices = pd.read_parquet(processed / "prices_hourly.parquet").reset_index()
    price_time = "Interval Start" if "Interval Start" in prices else prices.columns[0]
    prices["day"] = pd.to_datetime(prices[price_time]).dt.strftime("%Y-%m-%d")
    daily_price = prices.groupby("day", as_index=False)["pi_RT"].max().rename(
        columns={"pi_RT": "max_rt_price"}
    )
    wind = pd.read_parquet(processed / "wind_hourly.parquet")
    wind = wind[wind["resource"].isin(cfg["data"]["primary_agents"])].copy()
    wind["day"] = pd.to_datetime(wind["Interval Start"]).dt.strftime("%Y-%m-%d")
    daily_wind = wind.groupby("day", as_index=False)["W_avail"].sum().rename(
        columns={"W_avail": "wind_availability_mwh"}
    )
    top_strategic = (
        day_gaps.nlargest(3, "strategic_gap")
        .merge(daily_price, on="day", how="left")
        .merge(daily_wind, on="day", how="left")
    )
    top_strategic_table = _markdown_table(
        ["Day", "Strategic gap ($)", "Gap (% J_R1)", "Max RT price ($/MWh)", "Wind availability (MWh)"],
        [
            [
                row.day, _fmt(row.strategic_gap, 0), _fmt(row.strategic_gap_pct_r1, 1),
                _fmt(row.max_rt_price, 2), _fmt(row.wind_availability_mwh, 1),
            ]
            for row in top_strategic.itertuples(index=False)
        ],
    )

    objective_wide = regimes.pivot(index="day", columns="regime", values="system_objective")
    r4a_better_days = objective_wide.index[objective_wide["R4a"] > objective_wide["R2"]]
    r4a_comparison = (
        regimes[
            regimes["day"].isin(r4a_better_days)
            & regimes["regime"].isin(["R2", "R4a"])
        ]
        .groupby("regime")[[
            "system_objective", "under_delivery_mwh", "attempted_overflow_mwh", "throughput_mwh"
        ]]
        .mean()
    )
    overflow_all = regime_means["overflow"]
    tol_mwh = 0.5
    diff_parts = []
    for col, label in (
        ("under_delivery_mwh", "mean under-delivery"),
        ("attempted_overflow_mwh", "mean attempted overflow"),
        ("throughput_mwh", "mean throughput"),
    ):
        v2, v4 = r4a_comparison.loc["R2", col], r4a_comparison.loc["R4a", col]
        if abs(v2 - v4) > tol_mwh:
            diff_parts.append((col, f"{label} is {_fmt(v2, 1)} MWh in R2 versus {_fmt(v4, 1)} MWh in R4a", v4 < v2))
    if diff_parts:
        r4a_detail = "On those days only, " + "; ".join(t for _, t, _ in diff_parts) + ". "
        lower = [
            {"under_delivery_mwh": "a smaller delivery shortfall",
             "attempted_overflow_mwh": "less attempted shared-POI overflow",
             "throughput_mwh": "less throughput"}[c]
            for c, _, is_lower in diff_parts if is_lower
        ]
        if lower:
            r4a_detail += "On those days, R4a's advantage is associated with " + " and ".join(lower) + ". "
    else:
        r4a_detail = (
            f"On those days, R2 and R4a do not differ materially in mean under-delivery, attempted overflow, "
            f"or throughput (all within {tol_mwh} MWh), so the advantage is not explained by these quantities. "
        )
    r4a_paragraph = (
        f"R4a exceeds R2 on {len(r4a_better_days)} of {regimes['day'].nunique()} days. "
        + r4a_detail
        + f"Over all {regimes['day'].nunique()} days, the mean attempted overflow is "
        f"{_fmt(overflow_all['R2'], 1)} MWh in R2 and {_fmt(overflow_all['R4a'], 1)} MWh in R4a, so "
        + (
            "R4a attempts more overflow than R2 over all days."
            if overflow_all["R4a"] > overflow_all["R2"]
            else "R4a does not attempt more overflow than R2 over all days."
        )
    )
    forecast_price = day_gaps[["day", "forecast_gap_central"]].merge(daily_price, on="day")
    forecast_price_r = float(forecast_price["forecast_gap_central"].corr(forecast_price["max_rt_price"]))
    price_max_day = daily_price.loc[daily_price["max_rt_price"].idxmax(), "day"]
    worst_forecast = day_gaps.loc[day_gaps["forecast_gap_central"].idxmax()]
    worst_forecast_price = float(
        daily_price.loc[daily_price["day"] == worst_forecast["day"], "max_rt_price"].iloc[0]
    )

    matrix_table = _markdown_table(
        ["Coordination", "Perfect J ($/day)", "Forecast J ($/day)", "Perfect raw profit", "Forecast raw profit"],
        [
            [
                row.coordination, _fmt(row.perfect, 0), _fmt(row.forecast, 0),
                _fmt(row.perfect_profit, 0), _fmt(row.forecast_profit, 0),
            ]
            for row in matrix.itertuples(index=False)
        ],
    )
    matrix_pct_table = _markdown_table(
        ["Coordination", "Perfect (% J_R1)", "Forecast (% J_R1)", "Perfect (% R1 profit)", "Forecast (% R1 profit)"],
        [
            [
                row.coordination, _fmt(row.perfect, 1), _fmt(row.forecast, 1),
                _fmt(row.perfect_profit, 1), _fmt(row.forecast_profit, 1),
            ]
            for row in matrix_pct.itertuples(index=False)
        ],
    )

    cm = sensitivity_config_means(sensitivity)
    base_p, base_d = float(cfg["battery"]["p_ratio"]), float(cfg["battery"]["duration_h"])
    kappas = sorted(cm["kappa_K"].unique())
    base_k = min(kappas, key=lambda k: abs(k - float(cfg["poi"]["kappa_K"])))
    sets = [c for c in ("low", "medium", "high") if c in set(cm["correlation_set"])]
    is_base = np.isclose(cm["p_ratio"], base_p) & np.isclose(cm["duration_h"], base_d)
    cmb = cm[is_base]
    base_design_name = cmb["storage_design"].iloc[0]

    def cval(metric: str, k: float, cs: str, frame: pd.DataFrame = cmb) -> float:
        sel = frame[np.isclose(frame["kappa_K"], k) & (frame["correlation_set"] == cs)]
        return float(sel[metric].mean())

    def cfg_label(row: Any) -> str:
        return f"κK = {_fmt(row.kappa_K, 2)}, {row.correlation_set}, {row.storage_design}"

    top_s = cm.loc[cm["strategic_gap_pct"].idxmax()]
    top_i = cm.loc[cm["info_gap_pct"].idxmax()]
    cross_rows = []
    for cs in sets:
        ok = [k for k in sorted(kappas, reverse=True) if cval("strategic_gap_pct", k, cs) > 1.0]
        # first exceedance while tightening POI from loose (1.0) toward tight (0.5)
        cross_rows.append([cs, f"κK = {_fmt(ok[0], 2)}" if ok else "never above 1 % on the grid"])
    poa_k = cm[np.isclose(cm["kappa_K"], base_k)].groupby("storage_design")["PoA"].mean()
    poa_hi, poa_lo = poa_k.idxmax(), poa_k.idxmin()
    sensitivity_highlights = _markdown_table(
        ["Configuration-level finding (means over days)", "Configuration / κK", "Value"],
        [
            ["Largest mean strategic gap", cfg_label(top_s), f"{_fmt(top_s.strategic_gap_pct, 2)}% of mean J_R1"],
            ["Largest mean information gap (R2 − R4a)", cfg_label(top_i), f"{_fmt(top_i.info_gap_pct, 2)}% of mean J_R1"],
            *[[f"Mean strategic gap first exceeds 1 % of J_R1 (loosest-to-tightest κK), {r[0]} set, {base_design_name}", r[1], ""] for r in cross_rows],
            [f"Highest mean PoA at κK = {_fmt(base_k, 2)}", poa_hi, _fmt(poa_k.max(), 4)],
            [f"Lowest mean PoA at κK = {_fmt(base_k, 2)}", poa_lo, _fmt(poa_k.min(), 4)],
            ["Largest mean attempted overflow (R2)", cfg_label(cm.loc[cm["attempted_overflow_mwh"].idxmax()]), f"{_fmt(cm['attempted_overflow_mwh'].max(), 1)} MWh/day"],
            ["Largest mean under-delivery (R2)", cfg_label(cm.loc[cm["under_delivery_mwh"].idxmax()]), f"{_fmt(cm['under_delivery_mwh'].max(), 1)} MWh/day"],
        ],
    )

    def kappa_table(metric: str) -> str:
        return _markdown_table(
            ["κK", *[f"{cs} set" for cs in sets]],
            [[_fmt(k, 2), *[_fmt(cval(metric, k, cs), 2) + " %" for cs in sets]] for k in kappas],
        )

    strategic_table = kappa_table("strategic_gap_pct")
    info_table = kappa_table("info_gap_pct")
    k_lo, k_hi = kappas[0], kappas[-1]
    hi_set = sets[-1]
    lo_set = sets[0]
    strat_k_lo = np.mean([cval("strategic_gap_pct", k_lo, cs) for cs in sets])
    strat_k_hi = np.mean([cval("strategic_gap_pct", k_hi, cs) for cs in sets])
    info_k_lo = np.mean([cval("info_gap_pct", k_lo, cs) for cs in sets])
    info_k_hi = np.mean([cval("info_gap_pct", k_hi, cs) for cs in sets])
    strat_c_lo, strat_c_hi = cval("strategic_gap_pct", base_k, lo_set), cval("strategic_gap_pct", base_k, hi_set)
    info_c_lo, info_c_hi = cval("info_gap_pct", base_k, lo_set), cval("info_gap_pct", base_k, hi_set)
    dur_frame = cm[np.isclose(cm["p_ratio"], base_p) & np.isclose(cm["kappa_K"], base_k)]
    dur = dur_frame.groupby("duration_h")["strategic_gap_pct"].mean().sort_index()
    dur_dir = (
        "increases" if dur.iloc[-1] > dur.iloc[0] + 0.05
        else "decreases" if dur.iloc[-1] < dur.iloc[0] - 0.05 else "barely changes"
    )
    dur_text = (
        f"the mean strategic gap {dur_dir} with storage duration ("
        + ", ".join(f"{_fmt(d, 1)} h: {_fmt(v, 2)} %" for d, v in dur.items())
        + f" at κK = {_fmt(base_k, 2)}, p = {_fmt(base_p, 2)})"
    )
    sensitivity_bullet = (
        f"Sensitivity (means over days at the base storage design): tightening the POI from κK = {_fmt(k_hi, 1)} to {_fmt(k_lo, 1)} "
        f"moves the strategic gap from {_fmt(strat_k_hi, 2)} % to {_fmt(strat_k_lo, 2)} % of J_R1 and the information gap (R2 − R4a) from "
        f"{_fmt(info_k_hi, 2)} % to {_fmt(info_k_lo, 2)} % (averaged over correlation sets); at κK = {_fmt(base_k, 1)}, going from the {lo_set}- to the "
        f"{hi_set}-correlation set moves the strategic gap from {_fmt(strat_c_lo, 2)} % to {_fmt(strat_c_hi, 2)} % and the information gap from "
        f"{_fmt(info_c_lo, 2)} % to {_fmt(info_c_hi, 2)} %; {dur_text}."
    )
    info_kmax_text = ", ".join(f"{cs} {_fmt(cval('info_gap_pct', k_hi, cs), 2)} %" for cs in sets)
    info_floor_sentence = (
        f"At κK = {_fmt(k_hi, 1)} the POI does not bind, so the remaining information gap ({info_kmax_text} of J_R1) cannot come from POI competition; "
        f"it measures the cost of private delivery commitments in the limited-information regimes, where each agent must cover its own D_i = δ_D·b_i "
        f"because it cannot observe the aggregate shortfall, whereas game agents share the aggregate D."
    )
    top_strat_set = max(sets, key=lambda cs: cval("strategic_gap_pct", k_lo, cs))
    top_info_set = max(sets, key=lambda cs: cval("info_gap_pct", k_lo, cs))
    sig_lo, sig_med, sig_hi = (cval("signal_value_pct", base_k, cs) for cs in (lo_set, sets[1], hi_set))
    fig_gap_extra = (
        f" The aggregate headroom signal changes J by {_fmt(sig_lo, 2)} % ({lo_set}) and {_fmt(sig_med, 2)} % ({sets[1]}) versus {_fmt(sig_hi, 2)} % ({hi_set}) of J_R1 at κK = {_fmt(base_k, 1)}"
        f" (positive means the signal helps). Both gaps grow as the POI tightens; at κK = {_fmt(k_lo, 1)} the strategic gap is largest for the {top_strat_set} set and the information gap for the {top_info_set} set."
    )
    fig_gap_caption = (
        f"*At the base storage design ({base_design_name}; configuration means over days), the strategic gap for the {hi_set}-correlation set "
        f"is {_fmt(cval('strategic_gap_pct', k_hi, hi_set), 2)} % of J_R1 at κK = {_fmt(k_hi, 1)} and {_fmt(cval('strategic_gap_pct', k_lo, hi_set), 2)} % at κK = {_fmt(k_lo, 1)}, "
        f"versus {_fmt(cval('strategic_gap_pct', k_hi, lo_set), 2)} % and {_fmt(cval('strategic_gap_pct', k_lo, lo_set), 2)} % for the {lo_set} set; "
        f"the information gap for the {hi_set} set goes from {_fmt(cval('info_gap_pct', k_hi, hi_set), 2)} % to {_fmt(cval('info_gap_pct', k_lo, hi_set), 2)} %, "
        f"and signal value from {_fmt(cval('signal_value_pct', k_hi, hi_set), 2)} % to {_fmt(cval('signal_value_pct', k_lo, hi_set), 2)} % (20 days, every 3rd day)." + fig_gap_extra + "*"
    )
    fig_viol_caption = (
        f"*For the {hi_set}-correlation set at the base storage design, mean R2 attempted overflow rises from "
        f"{_fmt(cval('attempted_overflow_mwh', k_hi, hi_set), 1)} MWh/day at κK = {_fmt(k_hi, 1)} to {_fmt(cval('attempted_overflow_mwh', k_lo, hi_set), 1)} MWh/day at κK = {_fmt(k_lo, 1)} "
        f"and mean under-delivery moves from {_fmt(cval('under_delivery_mwh', k_hi, hi_set), 1)} to {_fmt(cval('under_delivery_mwh', k_lo, hi_set), 1)} MWh/day "
        f"(the {lo_set} set: {_fmt(cval('attempted_overflow_mwh', k_lo, lo_set), 1)} and {_fmt(cval('under_delivery_mwh', k_lo, lo_set), 1)} MWh/day at κK = {_fmt(k_lo, 1)}); "
        f"the realization layer keeps physical export within K (20 days, every 3rd day).*"
    )
    processed_complete, processed_skipped = assess_complete_days(cfg, cfg["data"]["primary_agents"])
    expected_sensitivity_days = len(processed_complete[:: int(cfg["sensitivity"]["day_stride"])])
    n_kappa = sensitivity["kappa_K"].nunique()
    n_days = sensitivity["day"].nunique()
    sensitivity_full = not (n_kappa < 3 or n_days < 5)
    stride = int(cfg["sensitivity"]["day_stride"])
    kappa_set = ", ".join(f"{k:.1f}" for k in kappas)
    n_sets = sensitivity["correlation_set"].nunique()
    n_designs = sensitivity["storage_design"].nunique()
    n_regimes = sensitivity["regime"].nunique()
    if sensitivity_full:
        sensitivity_status = (
            f"Full grid: κK ∈ {{{kappa_set}}}, {n_sets} correlation sets, {n_designs} storage designs, "
            f"{n_days} days (every {stride}{'rd' if stride == 3 else 'th'} day), {n_regimes} regimes."
        )
    else:
        sensitivity_status = (
            f"Quick grid: κK ∈ {{{kappa_set}}}, {n_sets} correlation sets, {n_designs} storage designs, "
            f"{n_days} day(s), {n_regimes} regimes."
        )

    monitor_markdown, monitor_selected = _monitor_table(
        monitor_regimes, monitor_roc, monitor_deterrence, cfg
    )
    medium_detection = monitor_selected[
        (monitor_selected["regime"] == "medium")
        & np.isclose(monitor_selected["tau_frac"], 0.05)
        & np.isclose(monitor_selected["m_frac"], 0.05)
    ].iloc[0]
    medium_sentence = (
        f"In the medium regime (resource-level COP σ = {_fmt(medium_detection.sigma, 3)} of nameplate), "
        f"a {_fmt(100 * medium_detection.m_frac, 0)}% withholding at a "
        f"{_fmt(100 * medium_detection.tau_frac, 0)}% threshold raises sanction probability only from "
        f"q0 = {_fmt(medium_detection.q0, 3)} to q1 = {_fmt(medium_detection.q1, 3)}, so it is detectable "
        "only weakly and with a substantial false-positive rate."
    )

    primary = resources[resources["resource"].isin(cfg["data"]["primary_agents"])]
    resource_table = _markdown_table(
        ["Resource", "Site", "Nameplate (MW)", "Coverage", "Mean CF"],
        [[row.resource, row.site, _fmt(row.nameplate_mw, 1), f"{100 * row.coverage_frac:.1f}%", _fmt(row.mean_cf, 3)] for row in primary.itertuples(index=False)],
    )
    sets_table = _markdown_table(
        ["Set", "Members", "Target ρ", "Mean ρ", "Range ρ", "Nameplate (MW)"],
        [[row.correlation_set, ", ".join(json.loads(row.members)), _fmt(row.target_rho, 2), _fmt(row.mean_rho, 3), f"{_fmt(row.min_rho, 3)}–{_fmt(row.max_rho, 3)}", _fmt(row.total_nameplate_mw, 1)] for row in agent_sets.itertuples(index=False)],
    )
    source_table = _markdown_table(
        ["Quantity", "Public source/report", "Window used", "Status"],
        [
            ["DA and RT prices", "ERCOT NP4-180-ER and NP6-785-ER", f"{cfg['data']['window_start']} to {cfg['data']['window_end']}", "Observed"],
            ["Wind availability/output", "ERCOT NP3-965-ER", f"{cfg['data']['window_start']} to {cfg['data']['window_end']}", "Observed"],
            ["COP forecast and baseline", "ERCOT COP snapshot and NP3-966-ER", f"{cfg['data']['window_start']} to {cfg['data']['window_end']}", "Observed/constructed"],
            ["Forecast-error regimes", "ERCOT NP4-732-CD and NP4-742-CD", "Rolling MIS snapshot, publications 2026-10-13 … 10-20 (system level); 2025-03-01 … 04-30 (resource level)", "Calibrated from observations"],
            ["Battery design", "Observed co-located BESS, EIA-860, NREL ATB", "Base configuration", "Calibrated"],
            ["POI, delivery, penalties, information, monitor policy", "Wargame design", "Experiment grid", "Designed"],
        ],
    )

    gap_means = day_gaps.mean(numeric_only=True)
    best_regime = regime_means["objective"].idxmax()
    worst_regime = regime_means["objective"].idxmin()
    convergence = regimes[regimes["regime"].isin(["R2", "R2_f", "R3a", "R3b"])]["converged"].mean()
    corr_means = agent_sets.set_index("correlation_set")["mean_rho"]
    price_min = float(prices[["pi_DA", "pi_RT"]].min().min())
    price_max = float(prices[["pi_DA", "pi_RT"]].max().max())
    selected_day = outputs["trajectory"].stem.removeprefix("fig_trajectory_")
    selected_rows = regimes[(regimes["day"] == selected_day) & regimes["regime"].isin(["R1", "R2", "R4b"])]
    selected_spread = selected_rows["system_objective"].max() - selected_rows["system_objective"].min()
    matrix_min = matrix_pct.set_index("coordination")[["perfect", "forecast"]].stack().idxmin()
    sensitivity_configs = sensitivity[["kappa_K", "correlation_set", "storage_design"]].drop_duplicates()
    total_configured_days = len(configured_days(cfg))

    bat, poi = cfg["battery"], cfg["poi"]
    base_params_line = (
        f"Base parameters: kappa_K = {_fmt(poi['kappa_K'], 1)}, delta_D = {_fmt(poi['delta_D'], 1)}, "
        f"λ⁻ = {_fmt(poi['lambda_minus'], 0)}, λ⁺ = {_fmt(poi['lambda_plus'], 0)} $/MWh, "
        f"p = {_fmt(bat['p_ratio'], 2)}, E/P = {_fmt(bat['duration_h'], 1)} h, "
        f"η_RT = {_fmt(float(bat['eta_c']) * float(bat['eta_d']), 2)}, "
        f"C_deg = {_fmt(bat['c_deg_usd_per_mwh'], 0)} $/MWh (config/base.yaml)"
    )

    # ROC AUC per regime at one fixed withholding level
    auc_m = 0.05
    trapezoid = getattr(np, "trapezoid", None) or np.trapz
    auc = {}
    for regime in ("low", "medium", "high"):
        sub = monitor_roc[(monitor_roc["regime"] == regime) & np.isclose(monitor_roc["m_frac"], auc_m)]
        pts = sub[["q0", "q1"]].drop_duplicates().sort_values(["q0", "q1"])
        x = np.concatenate([[0.0], pts["q0"].to_numpy(), [1.0]])
        y = np.concatenate([[0.0], pts["q1"].to_numpy(), [1.0]])
        auc[regime] = float(trapezoid(y, x))
    auc_text = ", ".join(f"{k} {v:.2f}" for k, v in auc.items())

    # storage-design summary
    design_poa = cm.groupby("storage_design")["PoA"].mean()
    design_curt = sensitivity.groupby("storage_design")["curtailment_realized_mwh"].mean()
    best_poa_design = design_poa.idxmax()
    curt_lo, curt_hi = design_curt.idxmin(), design_curt.idxmax()
    storage_text = (
        f"the design with the largest mean PoA is {best_poa_design} ({design_poa.max():.3f}); mean realized "
        f"curtailment differs by {design_curt.max() - design_curt.min():,.1f} MWh/day between the designs with "
        f"the smallest ({curt_lo}, {design_curt.min():,.1f}) and largest ({curt_hi}, {design_curt.max():,.1f}) mean curtailment"
    )
    low_set = agent_sets.set_index("correlation_set").loc["low"]
    sel_r1 = regimes[(regimes["day"] == selected_day) & (regimes["regime"] == "R1")].iloc[0]
    sel_r2 = regimes[(regimes["day"] == selected_day) & (regimes["regime"] == "R2")].iloc[0]
    if abs(sel_r2["throughput_mwh"] - sel_r1["throughput_mwh"]) <= tol_mwh:
        sel_tp_text = (
            f"throughput is essentially unchanged ({_fmt(sel_r2['throughput_mwh'], 1)} MWh in R2 "
            f"versus {_fmt(sel_r1['throughput_mwh'], 1)} MWh in R1)"
        )
    else:
        sel_tp_text = (
            f"R2 has throughput {_fmt(sel_r2['throughput_mwh'], 1)} versus "
            f"{_fmt(sel_r1['throughput_mwh'], 1)} MWh in R1"
        )
    sel_ud_text = (
        f"under-delivery is {_fmt(sel_r2['under_delivery_mwh'], 1)} MWh in R2 versus "
        f"{_fmt(sel_r1['under_delivery_mwh'], 1)} MWh in R1"
    )

    # convergence, coordination, and information-vs-strategy statistics
    nash_runs = regimes[regimes["regime"].isin(["R2", "R3a", "R3b"])]
    max_gain_max = float(nash_runs["max_gain"].max())
    max_gain_mean = float(nash_runs["max_gain"].mean())
    j_r1_mean = float(regime_means.loc["R1", "objective"])
    j_means = regime_means["objective"]
    strat_total = j_means["R1"] - j_means["R2"]
    rec_r3a = 100 * (j_means["R3a"] - j_means["R2"]) / strat_total if strat_total else float("nan")
    rec_r3b = 100 * (j_means["R3b"] - j_means["R2"]) / strat_total if strat_total else float("nan")
    r3b_note = (
        " Because R3b recovers less than R3a, charging the central dual price on injections acts as a "
        "tax without rebate and reduces J."
        if j_means["R3b"] < j_means["R3a"] else ""
    )
    coord_higher = "R3b" if j_means["R3b"] > j_means["R3a"] else "R3a"
    coord_sentence = (
        f"Of the mean strategic gap (J_R1 − J_R2 = ${_fmt(strat_total, 0)}/day), R3a (full exposure to the shared "
        f"shortage/overflow penalties) recovers {rec_r3a:.1f}% and R3b (R3a plus the POI dual price broadcast) "
        f"recovers {rec_r3b:.1f}%; {coord_higher} recovers more.{r3b_note}"
    )
    info_pct = 100 * day_gaps["info_gap_aggregate"].mean() / j_r1_mean
    strat_pct = 100 * day_gaps["strategic_gap"].mean() / j_r1_mean
    sig_mean = day_gaps["signal_value"].mean()
    sig_pct = 100 * sig_mean / j_r1_mean
    info_sentence = (
        f"The mean aggregate-information gap (R2 − R4a) is ${_fmt(day_gaps['info_gap_aggregate'].mean(), 0)}/day "
        f"({info_pct:.1f}% of mean J_R1) versus a mean strategic gap (R1 − R2) of "
        f"${_fmt(day_gaps['strategic_gap'].mean(), 0)}/day ({strat_pct:.1f}%); the mean headroom-signal value "
        f"(R4a − R4b) is {'-' if sig_mean < 0 else ''}${_fmt(abs(sig_mean), 0)}/day ({sig_pct:.1f}% of mean J_R1), so the signal "
        f"{'helps' if sig_mean > 0 else 'does not help'} on average."
    )
    n_gap100 = int((day_gaps["strategic_gap"] > 100).sum())
    n_days_total = len(day_gaps)

    # monitor horizon and an infinite-T* example
    t_max = inspect.signature(
        next(f for _, f in inspect.getmembers(_detection, inspect.isfunction) if "T_max" in inspect.signature(f).parameters)
    ).parameters["T_max"].default
    inf_rows = monitor_deterrence[np.isinf(monitor_deterrence["T_star"])]
    if len(inf_rows):
        ex = inf_rows.iloc[0]
        inf_text = (
            f"for example, regime {ex['regime']} with τ = {_fmt(ex['tau_frac'], 2)} of nameplate and "
            f"m = {_fmt(ex['m_frac'], 2)} of nameplate (d = {_fmt(ex['d'], 0)} h) has T* = ∞"
        )
    else:
        inf_text = "no (regime, τ, m) combination in the grid has T* = ∞"
    medium_gain = float(medium_detection.q1 - medium_detection.q0)

    figure_rel = {key: f"../../results/figures/{path.name}" for key, path in outputs.items()}
    monitor_rel = {
        "roc": "../../results/figures/monitor_roc.png",
        "fine": "../../results/figures/monitor_Fstar_vs_sigma.png",
        "duration": "../../results/figures/monitor_Tstar_vs_sigma.png",
    }
    report = f"""# Workshop 1 Report: Strategic Coordination in Co-Located Wind–Storage Systems

Team: {TEAM}  
Course: MIT 6.974 Wargame, Fall 2026

## Scope

This deliverable implements the Workshop 1 operating benchmark: a reproducible public-data pipeline, a real multi-resource wind–storage site with a shared POI, centralized and decentralized dispatch, a coordination-by-foresight matrix, sensitivity experiments, and empirical monitor calibration. MARL, adaptive monitoring, and resilience attacks remain later-workshop tasks.

## Data

{source_table}

The configured window is {cfg['data']['window_start']} through {cfg['data']['window_end']} at {cfg['data']['hub']}. It contains {len(processed_complete)} complete daily episodes and {len(processed_skipped)} incomplete episode(s) across {total_configured_days} calendar days; the base table evaluates all {regimes['day'].nunique()} complete episodes.

### Base-case resources: {cfg['data']['primary_site']}

{resource_table}

### Designed correlation sets

{sets_table}

![Wind correlation and selected sets]({figure_rel['wind_corr']})

*The selected low, medium, and high sets have mean correlations {_fmt(corr_means['low'], 2)}, {_fmt(corr_means['medium'], 2)}, and {_fmt(corr_means['high'], 2)} (within the low set, pairwise ρ ranges from {_fmt(low_set['min_rho'], 2)} to {_fmt(low_set['max_rho'], 2)}), so the sensitivity grid spans materially different coincidence in wind availability.*

![HB_WEST prices]({figure_rel['prices']})

*DA and RT prices range from ${price_min:,.2f} to ${price_max:,.2f}/MWh, the largest forecast loss {'coincides' if worst_forecast['day'] == price_max_day else 'does not coincide'} with the window's price maximum, and across days the correlation between the daily forecast gap and the daily maximum RT price is r = {forecast_price_r:.2f}.*

[ASSUMPTIONS.md](../ASSUMPTIONS.md) records every source and status. Prices, wind, forecasts, awards, and resource metadata are observed; nameplate, storage size, efficiency, degradation cost, and monitor-noise regimes are calibrated; K, D, λ⁻ = {_fmt(lambda_minus, 0)} $/MWh, information structures, thresholds, and enforcement parameters are designed.

{base_params_line}

## Model summary

The physical and strategic model follows [DESIGN.md §3–§4](../DESIGN.md). Its realized system objective is `J = raw realized profit − λ⁻ × under-delivery`; λ⁺ is excluded from realized J because the realization layer enforces K. Attempted overflow remains a strategic diagnostic. Every gap and PoA below leads with J; raw-profit counterparts are retained separately.

## Headline results

{headline}

{objective_gaps}

{poa_table}

Raw-profit comparisons omit the system shortage charge:

{profit_gaps}

The strategic gap is small on a typical day but heavy-tailed: its mean is ${_fmt(day_gaps['strategic_gap'].mean(), 0)}/day versus a ${_fmt(day_gaps['strategic_gap'].median(), 0)}/day median, and the gap exceeds $100 on {n_gap100} of {n_days_total} days. {coord_sentence} {info_sentence} The three largest days are:

{top_strategic_table}

{r4a_paragraph}

The central forecast gap dominates the other average losses: it averages ${_fmt(day_gaps['forecast_gap_central'].mean(), 0)}/day, or {_fmt(day_gaps['forecast_gap_central_pct_r1'].mean(), 1)} % of daily J_R1 on average, versus a median ${_fmt(day_gaps['forecast_gap_central'].median(), 0)}/day and {_fmt(day_gaps['forecast_gap_central_pct_r1'].median(), 1)} %. The worst day is {worst_forecast['day']}, with a ${_fmt(worst_forecast['forecast_gap_central'], 0)} gap and a maximum RT price of ${_fmt(worst_forecast_price, 2)}/MWh; the largest forecast loss {'coincides' if worst_forecast['day'] == price_max_day else 'does not coincide'} with the window's price maximum (on {price_max_day}). Across the {len(forecast_price)} days, the correlation between the daily forecast gap and the daily maximum RT price is r = {forecast_price_r:.2f}.

![Daily system objective by regime]({figure_rel['regime_profit']})

*{best_regime} has the highest mean J (${regime_means.loc[best_regime, 'objective']:,.0f}/day), {worst_regime} has the lowest (${regime_means.loc[worst_regime, 'objective']:,.0f}/day), and a few extreme days dominate the strategic-gap mean.*

![Illustrative dispatch trajectory]({figure_rel['trajectory']})

*On {selected_day}, the objective spread among R1, R2, and R4b is ${_fmt(selected_spread, 0)}, on the day with the largest strategic gap in the window. Relative to R1, {sel_tp_text}, and {sel_ud_text}.*

## Information-structure matrix

{matrix_table}

{matrix_pct_table}

![Information-structure matrix]({figure_rel['info_matrix']})

*The lowest matrix cell in J is {matrix_min[0]} under {matrix_min[1]} foresight, while the perfect-to-forecast column change is much larger than the differences across coordination rows.*

## Sensitivity

{sensitivity_status} The grid has {len(sensitivity_configs)} κK-by-correlation-by-storage configurations. All gaps below use J and are computed from configuration means over days (mean J by regime, then ratios). Figures and the tables below use the base storage design ({base_design_name}) unless stated.

{sensitivity_highlights}

Mean strategic gap (R1 − R2, % of mean J_R1) by POI tightness and correlation set:

{strategic_table}

Mean information gap (R2 − R4a, % of mean J_R1):

{info_table}

{info_floor_sentence}

![Objective gaps versus POI tightness]({figure_rel['gaps_vs_kappa']})

{fig_gap_caption}

![Violations versus POI tightness]({figure_rel['violations_vs_kappa']})

{fig_viol_caption}

![Storage design comparison]({figure_rel['storage_design']})

*Configuration-mean PoA spans {_fmt(cm['PoA'].min(), 3)}–{_fmt(cm['PoA'].max(), 3)} over the grid and, at κK = {_fmt(base_k, 2)}, from {_fmt(poa_k.min(), 4)} ({poa_lo}) to {_fmt(poa_k.max(), 4)} ({poa_hi}), so storage design changes both efficiency and curtailment; {storage_text} (20 days, every 3rd day).*

## Monitor calibration

The low, medium, and high σ regimes come from real data. Results are given for both absolute thresholds and both withholding levels at δ = {_fmt(cfg['monitor']['delta'], 2)} and d = {_fmt(monitor_selected['d'].iloc[0], 0)}.

{monitor_markdown}

{medium_sentence}

![Empirical monitor ROC]({monitor_rel['roc']})

*The ROC curves overlap substantially across calibrated regimes, so a threshold that suppresses false positives also misses a material share of small withholding. Empirical AUC at m = {_fmt(auc_m, 2)} of nameplate: {auc_text}.*

![Required fine versus noise]({monitor_rel['fine']})

*Required F*/g increases when q1 separates less from q0, making small withholding expensive to deter under noisier signals.*

![Correction duration versus noise]({monitor_rel['duration']})

*Finite correction periods lengthen sharply when detection gain q1 − q0 is small; some low-detection combinations are not finitely deterrable on the plotted horizon (T_max = {t_max:,} periods); {inf_text}.*

## What we learned / what breaks

- The mean strategic gap is {_fmt(gap_means['strategic_gap_pct_r1'], 1)} % of daily J_R1, with a ${_fmt(day_gaps['strategic_gap'].median(), 0)} median and a ${_fmt(day_gaps['strategic_gap'].max(), 0)} maximum, so the mean is not representative of a typical day.
- R4a beats the full-information Nash outcome on {len(r4a_better_days)} days; on those days it is associated with less throughput and less attempted shared-POI overflow, although over all days R4a's mean attempted overflow is {_fmt(overflow_all['R4a'], 1)} MWh versus {_fmt(overflow_all['R2'], 1)} MWh in R2.
- Perfect foresight is worth an average of {_fmt(gap_means['forecast_gap_central_pct_r1'], 1)} % of daily J_R1, larger than the mean strategic and information effects.
- Best-response regimes converge in {100 * convergence:.1f}% of evaluated base-day runs (converged requires residual ≤ tol and maximum unilateral gain ≤ $1); non-converged runs are not a tolerance artefact: over all R2/R3a/R3b day-runs the largest remaining unilateral gain is ${_fmt(max_gain_max, 2)}, i.e. {100 * max_gain_max / j_r1_mean:.2f} % of mean J_R1 (mean ${_fmt(max_gain_mean, 2)}, {100 * max_gain_mean / j_r1_mean:.3f} %). Convergence does not imply system optimality.
- {sensitivity_bullet}
- Coordination mechanisms: {coord_sentence}
- Information versus strategy: {info_sentence}
- With medium resource-level noise, a small withholding remains difficult to separate from legitimate forecast error: at m = 0.05 and τ = 0.05 of nameplate, q1 − q0 = {_fmt(medium_gain, 3)}.

## Limitations

The base results cover {regimes['day'].nunique()} complete episodes in one spring window at one co-located site. {sensitivity_status} The forecast-error (monitor) regimes rest on a rolling MIS snapshot (publications 2026-10-13 … 10-20 at system level; resource-level data for 2025-03-01 … 04-30), so the system-level noise is calibrated on a different period from the operating window. The model is price-taking at RT, uses deterministic COP and DA forecasts inside MPC, and does not yet model two-settlement bidding, endogenous prices, outages, causal intent, or attacks.

## Post-Workshop-1 roadmap

Next steps are MARL under local and aggregate observations, adaptive thresholds and enforcement, explicit withholding and false-data attacks, and resilience mechanisms. Those extensions will retain this objective definition, centralized benchmark, realization layer, and reproducible data split.
"""

    report_dir = Path("docs/workshop1")
    report_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = report_dir / "report.md"
    html_path = report_dir / "report.html"
    markdown_path.write_text(report, encoding="utf-8")
    html_path.write_text(
        markdown_to_html(report, "Workshop 1 — Strategic Coordination"), encoding="utf-8"
    )
    LOGGER.info(
        "Wrote %s and %s; generated %d PNG/PDF figure pairs",
        markdown_path,
        html_path,
        len(outputs),
    )
    print("\nObjective-based daily gaps")
    print(objective_gaps)
    print("\nR4a-above-R2 comparison")
    print(r4a_paragraph)


if __name__ == "__main__":
    main()

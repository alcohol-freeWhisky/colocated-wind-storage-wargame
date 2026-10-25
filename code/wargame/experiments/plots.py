"""Workshop 1 publication figures from experiment result tables."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch, Rectangle

from wargame.experiments.metrics import add_system_objective, gaps

REGIME_ORDER = ["R1", "R1_f", "R2", "R2_f", "R3a", "R3b", "R4a", "R4a_f", "R4b", "R4b_f"]
REGIME_COLORS = {
    "R1": "#0072B2",
    "R1_f": "#56B4E9",
    "R2": "#D55E00",
    "R2_f": "#F0A202",
    "R3a": "#009E73",
    "R3b": "#56B4E9",
    "R4a": "#CC79A7",
    "R4b": "#E69F00",
    "R4a_f": "#882255",
    "R4b_f": "#AA4499",
}
SET_COLORS = {"low": "#0072B2", "medium": "#E69F00", "high": "#D55E00"}
DESIGN_FACTOR_COLORS = {
    "F1": "#0072B2",
    "F2": "#E69F00",
    "F3": "#009E73",
    "F4": "#CC79A7",
}


def _style() -> None:
    plt.rcParams.update(
        {
            "font.size": 9,
            "axes.grid": True,
            "grid.alpha": 0.22,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "legend.frameon": False,
        }
    )


def _save(fig: plt.Figure, png_path: Path) -> None:
    png_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(png_path, dpi=200, bbox_inches="tight")
    fig.savefig(png_path.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


def plot_regime_profit(frame: pd.DataFrame, output: Path) -> None:
    """Plot daily realized system-objective distributions and mean gaps."""

    _style()
    present = [regime for regime in REGIME_ORDER if regime in set(frame["regime"])]
    values = [
        frame.loc[frame["regime"] == regime, "system_objective"].dropna().to_numpy()
        for regime in present
    ]
    fig, ax = plt.subplots(figsize=(8.6, 4.8), constrained_layout=True)
    boxes = ax.boxplot(values, tick_labels=present, patch_artist=True, widths=0.55)
    for box, regime in zip(boxes["boxes"], present, strict=True):
        box.set(facecolor=REGIME_COLORS[regime], alpha=0.35, edgecolor=REGIME_COLORS[regime])
    rng = np.random.default_rng(6974)
    for position, (regime, series) in enumerate(zip(present, values, strict=True), start=1):
        ax.scatter(
            position + rng.uniform(-0.10, 0.10, len(series)),
            series,
            s=17,
            alpha=0.7,
            color=REGIME_COLORS[regime],
            edgecolors="none",
        )
    gap_frame = gaps(frame)
    annotation = "\n".join(
        [
            f"Strategic gap: ${gap_frame['strategic_gap'].mean():,.0f}/day",
            f"Aggregate information gap: ${gap_frame['info_gap_aggregate'].mean():,.0f}/day",
            f"Signal value: ${gap_frame['signal_value'].mean():,.0f}/day",
            f"PoA: {gap_frame['PoA'].mean():.3f}",
        ]
    )
    ax.text(
        0.99,
        0.98,
        annotation,
        transform=ax.transAxes,
        ha="right",
        va="top",
        bbox={"facecolor": "white", "edgecolor": "0.75", "alpha": 0.9},
    )
    ax.set(xlabel="Operating regime", ylabel="Daily system objective J ($/day)")
    ax.set_title("System objective across operating days")
    _save(fig, output)


def _sensitivity_profit_gaps(frame: pd.DataFrame) -> pd.DataFrame:
    index = [
        "kappa_K",
        "correlation_set",
        "storage_design",
        "p_ratio",
        "duration_h",
        "day",
    ]
    pivot = frame.pivot_table(
        index=index,
        columns="regime",
        values="system_objective",
        aggfunc="first",
    ).reset_index()
    pivot["strategic_gap"] = pivot["R1"] - pivot["R2"]
    pivot["info_gap_aggregate"] = pivot["R2"] - pivot["R4a"]
    pivot["signal_value"] = pivot["R4a"] - pivot["R4b"]
    pivot["PoA"] = np.where(
        (pivot["R1"] > 0) & (pivot["R2"] > 0), pivot["R1"] / pivot["R2"], np.nan
    )
    for metric in ("strategic_gap", "info_gap_aggregate", "signal_value"):
        pivot[f"{metric}_pct_R1"] = np.where(
            pivot["R1"] > 0, 100 * pivot[metric] / pivot["R1"], np.nan
        )
    return pivot


def sensitivity_config_means(frame: pd.DataFrame) -> pd.DataFrame:
    """Configuration-level means over days.

    One row per (kappa_K, correlation_set, storage_design): mean J by regime over
    days, then gaps/PoA from those means (no single-day ratios).
    """

    keys = ["kappa_K", "correlation_set", "storage_design", "p_ratio", "duration_h"]
    j = frame.pivot_table(index=keys, columns="regime", values="system_objective", aggfunc="mean")
    out = j.reset_index()
    out["strategic_gap_pct"] = 100 * (out["R1"] - out["R2"]) / out["R1"]
    out["info_gap_pct"] = 100 * (out["R2"] - out["R4a"]) / out["R1"]
    out["signal_value_pct"] = 100 * (out["R4a"] - out["R4b"]) / out["R1"]
    out["PoA"] = out["R1"] / out["R2"]
    r2 = frame[frame["regime"] == "R2"].groupby(keys)[["attempted_overflow_mwh", "under_delivery_mwh"]].mean()
    return out.merge(r2.reset_index(), on=keys, how="left")


def _base_design(frame: pd.DataFrame, base: tuple[float, float] | None) -> pd.DataFrame:
    if base is None:
        return frame
    mask = np.isclose(frame["p_ratio"], base[0]) & np.isclose(frame["duration_h"], base[1])
    return frame[mask] if mask.any() else frame


def plot_gaps_vs_kappa(
    frame: pd.DataFrame, output: Path, base_design: tuple[float, float] | None = None
) -> None:
    """Plot configuration-mean gaps (% of mean J_R1) at the base storage design."""

    _style()
    means = _base_design(sensitivity_config_means(frame), base_design)
    metrics = [
        ("strategic_gap_pct", "Strategic gap (R1 - R2)"),
        ("info_gap_pct", "Information gap (R2 - R4a)"),
        ("signal_value_pct", "Signal value (R4a - R4b)"),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(12.6, 3.8), sharex=True, constrained_layout=True)
    for ax, (metric, title) in zip(axes, metrics, strict=True):
        for label in ("low", "medium", "high"):
            subset = means[means["correlation_set"] == label].sort_values("kappa_K")
            ax.plot(subset["kappa_K"], subset[metric], marker="o", color=SET_COLORS[label], label=label)
        ax.axhline(0, color="0.45", linewidth=0.8)
        ax.set(title=title, xlabel="POI capacity ratio κK", ylabel="Mean gap (% of mean J_R1)")
    axes[-1].legend(title="Correlation set")
    _save(fig, output)


def plot_violations_vs_kappa(
    frame: pd.DataFrame, output: Path, base_design: tuple[float, float] | None = None
) -> None:
    """Plot R2 mean attempted overflow and under-delivery at the base storage design."""

    _style()
    means = _base_design(sensitivity_config_means(frame), base_design)
    metrics = [
        ("attempted_overflow_mwh", "Mean attempted POI overflow, R2 (MWh/day)"),
        ("under_delivery_mwh", "Mean under-delivery, R2 (MWh/day)"),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(10.4, 4.1), constrained_layout=True)
    for ax, (metric, ylabel) in zip(axes, metrics, strict=True):
        for label in ("low", "medium", "high"):
            subset = means[means["correlation_set"] == label].sort_values("kappa_K")
            ax.plot(subset["kappa_K"], subset[metric], marker="o", color=SET_COLORS[label], label=label)
        ax.set(xlabel="POI capacity ratio κK", ylabel=ylabel)
    axes[-1].legend(title="Correlation set")
    _save(fig, output)


def plot_storage_design(frame: pd.DataFrame, output: Path) -> None:
    """Compare price of anarchy and curtailment across storage designs."""

    _style()
    gap_frame = _sensitivity_profit_gaps(frame)
    design_order = (
        frame[["storage_design", "p_ratio", "duration_h"]]
        .drop_duplicates()
        .sort_values(["p_ratio", "duration_h"])["storage_design"]
        .tolist()
    )
    x = np.arange(len(design_order))
    fig, axes = plt.subplots(1, 2, figsize=(12.2, 4.5), constrained_layout=True)
    poa = gap_frame.groupby(["storage_design", "correlation_set"])["PoA"].mean().reset_index()
    for label in ("low", "medium", "high"):
        values = poa[poa["correlation_set"] == label].set_index("storage_design")["PoA"].reindex(design_order)
        axes[0].plot(x, values, marker="o", color=SET_COLORS[label], label=label)
    axes[0].axhline(1, color="0.45", linewidth=0.8)
    axes[0].set(ylabel="Price of anarchy (J_R1 / J_R2)", title="Efficiency")
    axes[0].legend(title="Correlation set")

    curtail = frame.groupby(["storage_design", "regime"], observed=True)["curtailment_realized_mwh"].mean().reset_index()
    for regime in REGIME_ORDER:
        values = curtail[curtail["regime"] == regime].set_index("storage_design")[
            "curtailment_realized_mwh"
        ].reindex(design_order)
        if values.notna().any():
            axes[1].plot(x, values, marker="o", color=REGIME_COLORS[regime], label=regime)
    axes[1].set(ylabel="Realized wind curtailment (MWh/day)", title="Curtailment")
    axes[1].legend(title="Regime", ncol=2)
    for ax in axes:
        ax.set_xticks(x, design_order, rotation=30, ha="right")
        ax.set_xlabel("Storage design")
    _save(fig, output)


def plot_trajectory(day: str, trajectory_dir: Path, output: Path) -> None:
    """Plot dispatch and state of charge for R1, R2, and R4b."""

    _style()
    regimes = ["R1", "R2", "R4b"]
    fig, axes = plt.subplots(2, 3, figsize=(14.0, 6.6), sharex=True, constrained_layout=True)
    agent_colors = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00"]
    for column, regime in enumerate(regimes):
        frame = pd.read_csv(trajectory_dir / f"{day}_{regime}.csv")
        q = frame.pivot(index="hour", columns="agent", values="q_i").sort_index()
        hours = q.index.to_numpy()
        axes[0, column].stackplot(hours, q.to_numpy().T, labels=q.columns, colors=agent_colors[: len(q.columns)], alpha=0.82)
        hourly = frame.drop_duplicates("hour").set_index("hour")
        axes[0, column].plot(hours, hourly.loc[hours, "K"], color="black", linewidth=1.6, label="K")
        axes[0, column].plot(hours, hourly.loc[hours, "D"], color="black", linestyle="--", linewidth=1.3, label="D")
        axes[0, column].set(title=regime, ylabel="Injection q (MW)")
        soc = frame.pivot(index="hour", columns="agent", values="soc_i").sort_index()
        for i, agent in enumerate(soc.columns):
            axes[1, column].plot(soc.index, soc[agent], color=agent_colors[i], label=agent)
        axes[1, column].set(xlabel="Hour of operating day", ylabel="End-of-hour SoC (MWh)")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="outside lower center", ncol=min(len(labels), 7))
    fig.suptitle(f"Dispatch trajectories on {day}")
    _save(fig, output)


def plot_info_matrix(frame: pd.DataFrame, output: Path) -> None:
    """Plot the 4x2 coordination-by-own-foresight profit matrix."""

    _style()
    mapping = [
        ("C", "Central oracle", "R1", "R1_f"),
        ("G", "Full-information game", "R2", "R2_f"),
        ("A", "Aggregate signal", "R4a", "R4a_f"),
        ("L", "Local only", "R4b", "R4b_f"),
    ]
    means = frame.groupby("regime", observed=True)["system_objective"].mean()
    denominator = float(means["R1"])
    values = np.asarray(
        [[means[perfect], means[forecast]] for _, _, perfect, forecast in mapping],
        dtype=float,
    )
    percentages = (
        100.0 * values / denominator
        if abs(denominator) > 1e-12
        else np.full_like(values, np.nan)
    )
    fig, ax = plt.subplots(figsize=(6.8, 5.0), constrained_layout=True)
    finite = percentages[np.isfinite(percentages)]
    lower = float(finite.min()) - 5.0 if finite.size else -5.0
    upper = 100.0
    image = ax.imshow(percentages, cmap="YlGnBu", vmin=lower, vmax=upper, aspect="auto")
    for row in range(percentages.shape[0]):
        for column in range(percentages.shape[1]):
            value = percentages[row, column]
            label = "—" if not np.isfinite(value) else f"{value:.1f}%"
            ax.text(column, row, label, ha="center", va="center", fontweight="bold")
    ax.set_xticks([0, 1], ["Perfect", "Forecast"])
    ax.set_yticks(range(4), [f"{code}: {label}" for code, label, _, _ in mapping])
    ax.set_xlabel("Own foresight")
    ax.set_ylabel("Information about others / coordination")
    ax.set_title("Mean daily system objective (% of J_R1)")
    fig.colorbar(image, ax=ax, label="System objective (% of J_R1)")
    _save(fig, output)


def plot_design_matrix(frame: pd.DataFrame, output: Path) -> None:
    """Plot the revised 7-by-2 cell matrix as mean daily J relative to C_P."""

    _style()
    rows = [
        ("C", "Central"),
        ("INJ_FULL", "INJ / FULL"),
        ("INJ_PRICE", "INJ / PRICE"),
        ("INJ_NONE", "INJ / NONE"),
        ("EQ_FULL", "EQ / FULL"),
        ("EQ_PRICE", "EQ / PRICE"),
        ("EQ_NONE", "EQ / NONE"),
    ]
    objective = frame.pivot_table(
        index="day",
        columns="cell",
        values="system_objective",
        aggfunc="first",
        observed=True,
    )
    values = np.full((len(rows), 2), np.nan)
    for column, foresight in enumerate(("P", "F")):
        for row, (key, _) in enumerate(rows):
            cell = f"C_{foresight}" if key == "C" else f"D_{foresight}_{key}"
            if cell in objective and "C_P" in objective:
                values[row, column] = (
                    100.0 * objective[cell] / objective["C_P"].replace(0.0, np.nan)
                ).mean()
    finite = values[np.isfinite(values)]
    lower = min(float(finite.min()) - 3.0, 97.0) if finite.size else 0.0
    upper = max(float(finite.max()) + 1.0, 100.0) if finite.size else 100.0
    fig, ax = plt.subplots(figsize=(6.7, 6.0), constrained_layout=True)
    image = ax.imshow(values, cmap="YlGnBu", vmin=lower, vmax=upper, aspect="auto")
    for row in range(values.shape[0]):
        for column in range(values.shape[1]):
            value = values[row, column]
            ax.text(
                column,
                row,
                "—" if not np.isfinite(value) else f"{value:.1f}%",
                ha="center",
                va="center",
                fontweight="bold",
            )
    ax.set_xticks([0, 1], ["Perfect (P)", "Forecast (F)"])
    ax.set_yticks(range(len(rows)), [label for _, label in rows])
    ax.set(xlabel="Foresight", ylabel="Control / penalty share / market information")
    ax.set_title("Mean daily system objective (% of daily C_P)")
    ax.grid(False)
    fig.colorbar(image, ax=ax, label="Mean J (% of C_P)")
    _save(fig, output)


def plot_design_effects(daily: pd.DataFrame, output: Path) -> None:
    """Plot all F1--F4 daily contrasts with one-standard-error bars."""

    _style()
    output.parent.mkdir(parents=True, exist_ok=True)
    if daily.empty:
        fig, ax = plt.subplots(figsize=(7.0, 2.0), constrained_layout=True)
        ax.text(0.5, 0.5, "No matched design contrasts", ha="center", va="center")
        ax.axis("off")
    else:
        keys = ["factor", "contrast", "held_fixed"]
        grouped = daily.groupby(keys, sort=False, observed=True)["difference_usd"]
        effects = grouped.agg(["mean", "std", "count"]).reset_index()
        effects["se"] = effects["std"].fillna(0.0) / np.sqrt(effects["count"].clip(lower=1))
        effects["label"] = effects["contrast"] + " | " + effects["held_fixed"]
        height = max(5.0, 0.25 * len(effects) + 1.4)
        fig, ax = plt.subplots(figsize=(11.5, height), constrained_layout=True)
        positions = np.arange(len(effects))
        colors = effects["factor"].map(DESIGN_FACTOR_COLORS).to_list()
        ax.barh(
            positions,
            effects["mean"],
            xerr=effects["se"],
            color=colors,
            alpha=0.82,
            error_kw={"ecolor": "0.25", "capsize": 2, "linewidth": 0.8},
        )
        ax.axvline(0.0, color="0.3", linewidth=0.9)
        ax.set_yticks(positions, effects["label"], fontsize=7)
        ax.invert_yaxis()
        ax.set(xlabel="Mean daily J contrast ($/day)", ylabel="Contrast")
        ax.set_title("Four-factor design contrasts (error bars: ±1 s.e. across days)")
        handles = [Patch(facecolor=color, label=factor) for factor, color in DESIGN_FACTOR_COLORS.items()]
        ax.legend(handles=handles, title="Factor", ncol=4, loc="lower right")
    fig.savefig(output, dpi=200, bbox_inches="tight")
    plt.close(fig)


def plot_wind_correlation(
    corr_path: Path,
    agent_sets_path: Path,
    wind_path: Path,
    output: Path,
) -> None:
    """Plot the pool correlation matrix, selected sets, and Horse Hollow wind."""

    _style()
    corr = pd.read_csv(corr_path, index_col="resource")
    agent_sets = pd.read_csv(agent_sets_path)
    fig, axes = plt.subplots(1, 2, figsize=(16.0, 6.8), constrained_layout=True, gridspec_kw={"width_ratios": [1.35, 1]})
    image = axes[0].imshow(corr.to_numpy(), vmin=-1, vmax=1, cmap="RdBu_r", aspect="equal")
    axes[0].set_xticks(range(len(corr)), corr.columns, rotation=90, fontsize=4.5)
    axes[0].set_yticks(range(len(corr)), corr.index, fontsize=4.5)
    axes[0].grid(False)
    axes[0].set_title("Hourly available-wind correlation and chosen sets")
    legend: list[Patch] = []
    for row in agent_sets.itertuples(index=False):
        members = json.loads(row.members)
        color = SET_COLORS[row.correlation_set]
        positions = [corr.index.get_loc(name) for name in members]
        for i in positions:
            for j in positions:
                axes[0].add_patch(Rectangle((j - 0.5, i - 0.5), 1, 1, fill=False, edgecolor=color, linewidth=0.7))
        legend.append(Patch(facecolor="none", edgecolor=color, label=f"{row.correlation_set} (ρ̄={row.mean_rho:.2f})"))
    axes[0].legend(handles=legend, loc="upper left", fontsize=8)
    fig.colorbar(image, ax=axes[0], label="Pearson correlation ρ", shrink=0.75)

    wind = pd.read_parquet(wind_path)
    wind["Interval Start"] = pd.to_datetime(wind["Interval Start"])
    horse = wind[wind["resource"].str.startswith("HHGT_")].copy()
    if not horse.empty:
        start = horse["Interval Start"].min()
        horse = horse[horse["Interval Start"] < start + pd.Timedelta(days=7)]
        for resource, group in horse.groupby("resource"):
            axes[1].plot(group["Interval Start"], group["W_avail"], label=resource, linewidth=1.1)
    axes[1].set(xlabel="Operating time", ylabel="Available wind W (MW)", title="Horse Hollow units (first available week)")
    axes[1].tick_params(axis="x", rotation=30)
    axes[1].legend(fontsize=7)
    _save(fig, output)


def plot_prices(prices_path: Path, illustrative_day: str, output: Path) -> None:
    """Plot HB_WEST prices over the window and for one illustrative day."""

    _style()
    prices = pd.read_parquet(prices_path).reset_index()
    time_column = "Interval Start" if "Interval Start" in prices else prices.columns[0]
    prices[time_column] = pd.to_datetime(prices[time_column])
    date = prices[time_column].dt.date
    selected = prices[date == pd.Timestamp(illustrative_day).date()]
    fig, axes = plt.subplots(2, 1, figsize=(11.0, 6.0), constrained_layout=True)
    for ax, data, title in (
        (axes[0], prices, "HB_WEST prices over the available window"),
        (axes[1], selected, f"HB_WEST prices on {illustrative_day}"),
    ):
        ax.plot(data[time_column], data["pi_DA"], color="#0072B2", label="πDA", linewidth=1.0)
        ax.plot(data[time_column], data["pi_RT"], color="#D55E00", label="πRT", linewidth=1.0)
        ax.axhline(0, color="0.45", linewidth=0.7)
        ax.set(ylabel="Price ($/MWh)", title=title)
        ax.legend()
    axes[1].set_xlabel("Operating time")
    for ax in axes:
        ax.tick_params(axis="x", rotation=20)
    _save(fig, output)


def make_all_figures(cfg: Mapping[str, Any]) -> dict[str, Path]:
    """Create all non-monitor Workshop 1 figures and return their PNG paths."""

    results = Path(str(cfg.get("paths", {}).get("results", "results")))
    processed = Path(str(cfg.get("paths", {}).get("processed", "data/processed")))
    tables = results / "tables"
    figures = results / "figures"
    regimes = pd.read_csv(tables / "regimes_by_day.csv")
    sensitivity = pd.read_csv(tables / "sensitivity.csv")
    lambda_minus = float(cfg.get("poi", {}).get("lambda_minus", 250.0))
    regimes = add_system_objective(regimes, lambda_minus)
    sensitivity = add_system_objective(sensitivity, lambda_minus)
    # Illustrative day for the trajectory figure: the day with the largest
    # strategic gap (J_R1 - J_R2), where decentralisation visibly changes dispatch.
    objective = regimes.pivot_table(index="day", columns="regime", values="system_objective", aggfunc="first")
    day = str((objective["R1"] - objective["R2"]).idxmax())
    outputs = {
        "regime_profit": figures / "fig_regime_profit.png",
        "info_matrix": figures / "fig_info_matrix.png",
        "gaps_vs_kappa": figures / "fig_gaps_vs_kappa.png",
        "violations_vs_kappa": figures / "fig_violations_vs_kappa.png",
        "storage_design": figures / "fig_storage_design.png",
        "trajectory": figures / f"fig_trajectory_{day}.png",
        "wind_corr": figures / "fig_wind_corr.png",
        "prices": figures / "fig_prices.png",
    }
    plot_regime_profit(regimes, outputs["regime_profit"])
    plot_info_matrix(regimes, outputs["info_matrix"])
    base_design = (
        float(cfg.get("battery", {}).get("p_ratio", 0.29)),
        float(cfg.get("battery", {}).get("duration_h", 1.5)),
    )
    plot_gaps_vs_kappa(sensitivity, outputs["gaps_vs_kappa"], base_design)
    plot_violations_vs_kappa(sensitivity, outputs["violations_vs_kappa"], base_design)
    plot_storage_design(sensitivity, outputs["storage_design"])
    plot_trajectory(day, tables / "trajectories", outputs["trajectory"])
    plot_wind_correlation(
        processed / "corr_matrix.csv",
        tables / "agent_sets.csv",
        processed / "wind_hourly.parquet",
        outputs["wind_corr"],
    )
    plot_prices(processed / "prices_hourly.parquet", day, outputs["prices"])
    return outputs

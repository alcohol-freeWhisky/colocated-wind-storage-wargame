"""Design-matrix figures from experiment result tables."""

from __future__ import annotations

from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

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



def plot_design_matrix(frame: pd.DataFrame, output: Path) -> None:
    """Plot the 7-by-2 cell matrix as mean daily J relative to C_P."""

    _style()
    rows = [
        ("C", "Central"),
        ("INJ_FULL", "INJ / FULL"),
        ("INJ_PRICE", "INJ / AGGREGATE"),
        ("INJ_NONE", "INJ / NONE"),
        ("EQ_FULL", "EQ / FULL"),
        ("EQ_PRICE", "EQ / AGGREGATE"),
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
    lower = float(np.floor(finite.min())) if finite.size else 0.0
    upper = float(np.ceil(finite.max())) if finite.size else 100.0
    if np.isclose(lower, upper):
        lower -= 1.0
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
    ax.set(xlabel="Foresight", ylabel="Control / penalty allocation / information")
    ax.set_title("Mean daily system objective (% of daily C_P)")
    ax.grid(False)
    fig.colorbar(image, ax=ax, label="Mean J (% of C_P)")
    _save(fig, output)


def plot_design_effects(daily: pd.DataFrame, output: Path) -> None:
    """Plot the four matched ablations with one-standard-error bars."""

    _style()
    output.parent.mkdir(parents=True, exist_ok=True)
    if daily.empty:
        fig, ax = plt.subplots(figsize=(7.0, 2.0), constrained_layout=True)
        ax.text(0.5, 0.5, "No matched design contrasts", ha="center", va="center")
        ax.axis("off")
    else:
        selected = daily[
            ~(
                daily["factor"].eq("F1")
                & daily["contrast"].str.contains("mean(D", regex=False)
            )
        ].copy()
        # FULL-NONE duplicates the two adjacent information contrasts.
        selected = selected[
            ~(
                selected["factor"].eq("F4")
                & selected["contrast"].str.contains("FULL - D_")
                & selected["contrast"].str.endswith("_NONE")
            )
        ]
        keys = ["factor", "contrast", "held_fixed"]
        grouped = selected.groupby(keys, sort=False, observed=True)["difference_usd"]
        effects = grouped.agg(["mean", "std", "count"]).reset_index()
        effects["se"] = effects["std"].fillna(0.0) / np.sqrt(effects["count"].clip(lower=1))

        def short_label(row: pd.Series) -> str:
            left, right = row["contrast"].split(" - ", maxsplit=1)
            factor = row["factor"]
            if factor == "F1":
                _, foresight, share, info = right.split("_")
                return f"{foresight} | {share} | {info.replace('PRICE', 'AGG')}"
            if factor == "F2":
                if left == "C_P":
                    return "Planner"
                _, _, share, info = left.split("_")
                return f"{share} | {info.replace('PRICE', 'AGG')}"
            if factor == "F3":
                _, foresight, _, info = left.split("_")
                return f"{foresight} | {info.replace('PRICE', 'AGG')}"
            _, foresight, share, left_info = left.split("_")
            right_info = right.split("_")[-1]
            return (
                f"{foresight} | {share} | "
                f"{left_info.replace('PRICE', 'AGG')}-{right_info.replace('PRICE', 'AGG')}"
            )

        effects["label"] = effects.apply(short_label, axis=1)
        titles = {
            "F1": "Control: planner minus owners",
            "F2": "Foresight: perfect minus forecast",
            "F3": "Allocation: causal minus equal",
            "F4": "Information: adjacent levels",
        }
        fig, axes = plt.subplots(2, 2, figsize=(10.5, 9.0), constrained_layout=True)
        for ax, factor in zip(axes.flat, ("F1", "F2", "F3", "F4"), strict=True):
            panel = effects[effects["factor"].eq(factor)].reset_index(drop=True)
            positions = np.arange(len(panel))
            ax.barh(
                positions,
                panel["mean"],
                xerr=panel["se"],
                color=DESIGN_FACTOR_COLORS[factor],
                alpha=0.82,
                error_kw={"ecolor": "0.25", "capsize": 2, "linewidth": 0.8},
            )
            ax.axvline(0.0, color="0.3", linewidth=0.9)
            ax.set_yticks(positions, panel["label"], fontsize=8)
            ax.invert_yaxis()
            ax.set_title(titles[factor], loc="left", fontsize=10)
            ax.set_xlabel("Mean daily J contrast ($/day)")
        fig.suptitle("Matched ablation effects (error bars: ±1 s.e. across days)", fontsize=12)
    _save(fig, output)

"""Design-matrix figures from experiment result tables."""

from __future__ import annotations

from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

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

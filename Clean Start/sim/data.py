"""ERCOT Anchor Wind data -> daily arrays, forecast-based congestion probability, estimate noise.

Spec rev. 2: Sections 1 (data), 3 (information: pi_t, bins), 8 (data split).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .engine import DayInputs

REPO = Path(__file__).resolve().parents[2]
UNITS = ["ANCHOR_WIND1", "ANCHOR_WIND2", "ANCHOR_WIND3", "ANCHOR_WIND4", "ANCHOR_WIND5"]
BIN_EDGES = (0.2, 0.8)   # low < 0.2 <= mid <= 0.8 < high


@dataclass
class Dataset:
    days: pd.DatetimeIndex     # operating days
    W: np.ndarray              # (D,24,N) SCED HSL (true available wind)
    mu: np.ndarray             # (D,24,N) COP HSL (honest forecast)
    p: np.ndarray              # (D,24) RT price
    pDA: np.ndarray            # (D,24) DA price
    nameplate: np.ndarray      # (N,)


def load(units=UNITS) -> Dataset:
    w = pd.read_parquet(REPO / "data/processed/wind_hourly.parquet")
    w = w[w.resource.isin(units)]
    A = w.pivot_table(index="Interval Start", columns="resource", values="W_avail")[units]
    f = pd.read_parquet(REPO / "data/processed/forecast_error_resource.parquet")
    f = f[f.resource.isin(units)]
    M = f.pivot_table(index="Interval Start", columns="resource", values="What_cop").reindex(index=A.index, columns=units)
    pr = pd.read_parquet(REPO / "data/processed/prices_hourly.parquet").reindex(A.index)
    df = pd.concat({"W": A, "mu": M}, axis=1)
    day = A.index.tz_convert("US/Central").normalize()
    keep = [d for d, g in df.groupby(day) if len(g) == 24 and not g.isna().any().any()
            and not pr.loc[g.index, ["pi_RT", "pi_DA"]].isna().any().any()]
    idx = day.isin(keep)
    D = len(keep)
    res = pd.read_csv(REPO / "data/processed/resources.csv").set_index("resource")
    return Dataset(days=pd.DatetimeIndex(keep),
                   W=A[idx].to_numpy().reshape(D, 24, -1), mu=M[idx].to_numpy().reshape(D, 24, -1),
                   p=pr.loc[idx, "pi_RT"].to_numpy().reshape(D, 24),
                   pDA=pr.loc[idx, "pi_DA"].to_numpy().reshape(D, 24),
                   nameplate=res.loc[units, "nameplate_mw"].to_numpy(float))


def congestion_model(ds: Dataset, train: slice, K: float):
    """pi_t = P(sum_j W_jt > K | sum_j mu_jt), from training-day residuals of the total."""
    resid = (ds.W.sum(-1) - ds.mu.sum(-1))[train].ravel()
    tot_mu = ds.mu.sum(-1)                                          # (D,24)
    pi = (tot_mu[..., None] + resid[None, None, :] > K).mean(-1)
    bins = np.digitize(pi, BIN_EDGES, right=False)                  # 0 low, 1 mid, 2 high
    return pi, bins, resid


def day_inputs(ds: Dataset, sel, sigma_est: float = 0.04, seed: int = 0) -> DayInputs:
    """Build engine inputs for selected days. The monitor's estimate What = W + eps,
    eps ~ N(0, sigma_est * N_i), clipped to [0, N_i]; seeded for common random numbers."""
    W, mu = ds.W[sel], ds.mu[sel]
    rng = np.random.default_rng(seed)
    What = np.clip(W + rng.normal(0, 1, W.shape) * sigma_est * ds.nameplate, 0, ds.nameplate)
    pDA = ds.pDA[sel]
    dis_ok = pDA >= np.median(pDA, axis=1, keepdims=True)
    pbar = np.array([r[r > 0].mean() if (r > 0).any() else 0.0 for r in pDA])
    return DayInputs(W=W, mu=mu, What=What, Wex=mu, p=ds.p[sel], dis_ok=dis_ok, pbar=pbar)

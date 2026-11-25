"""Parameters of the curtailment-compensation game (spec: game_spec_v1.md, rev. 2).

Units: MW and MWh (one period = one hour), $/MWh for prices and rates.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np


@dataclass(frozen=True)
class Params:
    nameplate: np.ndarray                  # N_i (MW), shape (N,)
    K: float                               # shared export limit (MW)
    P: np.ndarray                          # battery power (MW), shape (N,)
    E: np.ndarray                          # battery energy (MWh), shape (N,)
    eta_c: float = 0.922
    eta_d: float = 0.922
    wear: float = 10.0                     # $/MWh discharged
    s0_frac: float = 0.5                   # daily initial SOC as a fraction of E
    lam: float = 30.0                      # compensation rate lambda ($/MWh)
    rule: str = "R"                        # "R" report-proportional | "C" capacity shares
    settlement: str = "S0"                 # "S0" unchecked | "S1" audited | "S2" verified |
                                           # "S2c" verified with the cap at the estimate, not the report
    variant_I: bool = False                # fully report-independent trigger/allocation/cap (spec 4)
    subsidy: float | None = None           # s ($/MWh); if set, g_cf = 0 when p < -s (sensitivity)
    # enforcement (S1)
    alpha: float = 0.2                     # audit probability per owner-day (random audits)
    z: float = 1.0                         # detection probability given a violation
    z0: float = 0.0                        # false-finding probability given compliance
    f: float = 90.0                        # fine per MWh ($/MWh)
    tau: float = 0.05                      # tolerance as a fraction of nameplate
    terminal_value: bool = True            # value end-of-day SOC at (pbar - wear) * eta_d
    discharge_rule: str = "uncurtailed"    # primary (rev. 2.4): discharge also allowed in instructed hours with r = 0;
                                           # "strict": never in instructed hours (rev. 2 rule; robustness)

    @property
    def N(self) -> int:
        return len(self.nameplate)

    @property
    def kappa(self) -> np.ndarray:
        """Capacity shares kappa_i = K N_i / sum_j N_j."""
        return self.K * self.nameplate / self.nameplate.sum()

    def with_(self, **kw) -> "Params":
        return replace(self, **kw)


def anchor_params(nameplate: np.ndarray, kappa_K: float = 0.6, p_ratio: float = 0.29,
                  duration_h: float = 1.5, **kw) -> Params:
    """Calibrated Anchor-like site: K = 0.6 sum N, P = 0.29 N, E = 1.5 P."""
    nameplate = np.asarray(nameplate, dtype=float)
    P = p_ratio * nameplate
    return Params(nameplate=nameplate, K=kappa_K * nameplate.sum(), P=P, E=duration_h * P, **kw)

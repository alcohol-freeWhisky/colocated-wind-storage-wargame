"""Physical objects and feasibility checks for wind--battery agents."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray


@dataclass(frozen=True, slots=True)
class Battery:
    """Fixed battery parameters, with energy in MWh and power in MW."""

    E: float
    P: float
    eta_c: float
    eta_d: float
    c_deg: float
    soc0: float

    def __post_init__(self) -> None:
        if self.E < 0 or self.P < 0:
            raise ValueError("Battery E and P must be non-negative")
        if not (0 < self.eta_c <= 1 and 0 < self.eta_d <= 1):
            raise ValueError("Battery efficiencies must lie in (0, 1]")
        if self.c_deg < 0:
            raise ValueError("Battery degradation cost must be non-negative")
        if not (0 <= self.soc0 <= self.E):
            raise ValueError("Initial SoC must lie in [0, E]")


@dataclass(frozen=True, slots=True)
class Agent:
    """A wind resource and its co-located battery."""

    name: str
    nameplate: float
    battery: Battery

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Agent name cannot be empty")
        if self.nameplate < 0:
            raise ValueError("Agent nameplate must be non-negative")


def simulate_soc(
    c: ArrayLike,
    d: ArrayLike,
    battery: Battery,
    *,
    initial_soc: float | None = None,
) -> NDArray[np.float64]:
    """Return the T+1 SoC path implied by hourly charge and discharge."""

    charge = np.asarray(c, dtype=float)
    discharge = np.asarray(d, dtype=float)
    if charge.ndim != 1 or discharge.ndim != 1 or charge.shape != discharge.shape:
        raise ValueError("c and d must be one-dimensional arrays of equal length")
    start = battery.soc0 if initial_soc is None else float(initial_soc)
    increments = battery.eta_c * charge - discharge / battery.eta_d
    return np.concatenate(([start], start + np.cumsum(increments)))


def battery_is_feasible(
    c: ArrayLike,
    d: ArrayLike,
    battery: Battery,
    *,
    initial_soc: float | None = None,
    terminal: str = "return",
    terminal_soc: float | None = None,
    tol: float = 1e-7,
) -> bool:
    """Check battery power, SoC, and optional terminal-return constraints."""

    charge = np.asarray(c, dtype=float)
    discharge = np.asarray(d, dtype=float)
    if charge.ndim != 1 or discharge.shape != charge.shape:
        return False
    if np.any(~np.isfinite(charge)) or np.any(~np.isfinite(discharge)):
        return False
    if np.any(charge < -tol) or np.any(discharge < -tol):
        return False
    if np.any(charge > battery.P + tol) or np.any(discharge > battery.P + tol):
        return False
    soc = simulate_soc(charge, discharge, battery, initial_soc=initial_soc)
    if np.any(soc < -tol) or np.any(soc > battery.E + tol):
        return False
    if terminal not in {"return", "free"}:
        raise ValueError("terminal must be 'return' or 'free'")
    if terminal == "return":
        target = (
            (battery.soc0 if initial_soc is None else float(initial_soc))
            if terminal_soc is None
            else float(terminal_soc)
        )
        if soc[-1] < target - tol:
            return False
    return True


def dispatch_is_feasible(
    W: ArrayLike,
    c: ArrayLike,
    d: ArrayLike,
    r: ArrayLike,
    battery: Battery,
    *,
    initial_soc: float | None = None,
    terminal: str = "return",
    allow_grid_charging: bool = True,
    tol: float = 1e-7,
) -> bool:
    """Check all single-agent physical constraints from DESIGN.md section 3."""

    wind = np.asarray(W, dtype=float)
    charge = np.asarray(c, dtype=float)
    discharge = np.asarray(d, dtype=float)
    curtail = np.asarray(r, dtype=float)
    if any(x.ndim != 1 for x in (wind, charge, discharge, curtail)):
        return False
    if not (wind.shape == charge.shape == discharge.shape == curtail.shape):
        return False
    if np.any(~np.isfinite(wind)) or np.any(wind < -tol):
        return False
    if np.any(curtail < -tol) or np.any(curtail > wind + tol):
        return False
    if not allow_grid_charging and np.any(charge > wind - curtail + tol):
        return False
    return battery_is_feasible(
        charge,
        discharge,
        battery,
        initial_soc=initial_soc,
        terminal=terminal,
        tol=tol,
    )


def assert_dispatch_feasible(
    W: ArrayLike,
    c: ArrayLike,
    d: ArrayLike,
    r: ArrayLike,
    battery: Battery,
    **kwargs: object,
) -> None:
    """Raise a clear error when a dispatch violates a physical constraint."""

    if not dispatch_is_feasible(W, c, d, r, battery, **kwargs):
        raise ValueError("Dispatch violates wind, power, SoC, or terminal constraints")


# Verbose aliases make call sites self-documenting and are kept for API clarity.
check_battery_feasibility = battery_is_feasible
check_dispatch_feasibility = dispatch_is_feasible

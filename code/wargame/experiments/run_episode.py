"""Run every Workshop 1 operating regime for one episode."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Mapping

from wargame.experiments.metrics import episode_metrics
from wargame.model.env import Episode
from wargame.solvers.central import Solution, solve_central
from wargame.solvers.game import GameSolution, solve_r2, solve_r3a, solve_r3b
from wargame.solvers.mpc import solve_r4a, solve_r4b
from wargame.solvers.receding import solve_r1_f, solve_r2_f
from wargame.solvers.realize import Realization, realize

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class RegimeResult:
    """Optimization, physical realization, metrics, and elapsed wall time."""

    solution: Solution | GameSolution | Realization
    realization: Realization
    metrics: dict[str, Any]
    elapsed_s: float

    def __getitem__(self, key: str) -> Any:
        """Also support lightweight dictionary-style result access."""

        if key not in {"solution", "realization", "metrics", "elapsed_s"}:
            raise KeyError(key)
        return getattr(self, key)


def run_all_regimes(
    episode: Episode,
    cfg: Mapping[str, Any] | None = None,
) -> dict[str, RegimeResult]:
    """Run all ten operating regimes in the canonical reporting order."""

    config = episode.cfg if cfg is None else cfg
    output: dict[str, RegimeResult] = {}

    def record(regime: str, started: float, solution: Any, physical: Realization) -> None:
        elapsed = time.perf_counter() - started
        metrics = episode_metrics(episode, physical, regime)
        output[regime] = RegimeResult(solution, physical, metrics, elapsed)
        LOGGER.info("regime=%s day=%s elapsed_s=%.3f", regime, episode.day, elapsed)

    started = time.perf_counter()
    central = solve_central(episode, config)
    record("R1", started, central, realize(episode, central))

    started = time.perf_counter()
    r1_f = solve_r1_f(episode, config)
    record("R1_f", started, r1_f, r1_f)

    started = time.perf_counter()
    r2 = solve_r2(episode, config)
    record("R2", started, r2, realize(episode, r2))

    started = time.perf_counter()
    r2_f = solve_r2_f(episode, config)
    record("R2_f", started, r2_f, r2_f)

    started = time.perf_counter()
    r3a = solve_r3a(episode, config)
    record("R3a", started, r3a, realize(episode, r3a))

    started = time.perf_counter()
    r3b = solve_r3b(episode, central.duals, config)
    record("R3b", started, r3b, realize(episode, r3b))

    started = time.perf_counter()
    r4a = solve_r4a(episode, config)
    record("R4a", started, r4a, r4a)

    forecast_config = dict(config)
    forecast_config["mpc"] = {
        **dict(config.get("mpc", {})),
        "price_info": "forecast",
        "wind_info": "forecast",
    }

    started = time.perf_counter()
    r4a_f = solve_r4a(episode, forecast_config)
    record("R4a_f", started, r4a_f, r4a_f)

    started = time.perf_counter()
    r4b = solve_r4b(episode, config)
    record("R4b", started, r4b, r4b)

    started = time.perf_counter()
    r4b_f = solve_r4b(episode, forecast_config)
    record("R4b_f", started, r4b_f, r4b_f)
    return output

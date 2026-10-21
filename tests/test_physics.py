"""Synthetic checks of battery dynamics and episode validation."""

import numpy as np
import pytest

from wargame.model.env import Episode
from wargame.model.physics import (
    Agent,
    Battery,
    battery_is_feasible,
    dispatch_is_feasible,
    simulate_soc,
)


def test_soc_dynamics_and_feasibility() -> None:
    battery = Battery(E=4.0, P=2.0, eta_c=0.9, eta_d=0.8, c_deg=10.0, soc0=1.0)
    c = np.array([1.0, 0.0, 0.0])
    d = np.array([0.0, 0.8, 0.0])
    soc = simulate_soc(c, d, battery)
    np.testing.assert_allclose(soc, [1.0, 1.9, 0.9, 0.9])
    assert battery_is_feasible(c, d, battery, terminal="free")
    assert not battery_is_feasible(c, d, battery, terminal="return")
    assert dispatch_is_feasible([2, 2, 2], c, d, [0, 1, 0], battery, terminal="free")
    assert not dispatch_is_feasible([2, 2, 2], c, d, [0, 3, 0], battery, terminal="free")


def test_episode_from_arrays_builds_batteries_and_rejects_missing_wind() -> None:
    episode = Episode.from_arrays(
        np.ones((2, 6)), nameplates=[4.0, 8.0], pi_DA=np.arange(6), pi_RT=np.arange(6)
    )
    assert episode.W.shape == (2, 6)
    assert episode.agents[1].battery.P == pytest.approx(2.0)
    assert episode.K == pytest.approx(0.7 * 12.0)
    with pytest.raises(ValueError, match="W must be complete"):
        Episode.from_arrays(np.array([[1.0, np.nan], [1.0, 1.0]]))


def test_agent_and_battery_validation() -> None:
    with pytest.raises(ValueError):
        Battery(E=1, P=1, eta_c=0, eta_d=1, c_deg=0, soc0=0)
    battery = Battery(E=1, P=1, eta_c=1, eta_d=1, c_deg=0, soc0=0)
    with pytest.raises(ValueError):
        Agent("", 1, battery)


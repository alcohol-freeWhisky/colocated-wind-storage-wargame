"""Physical-realization invariants on a synthetic six-hour profile."""

from types import SimpleNamespace

import numpy as np

from wargame.model.env import Episode
from wargame.solvers.realize import realize


def test_realization_caps_poi_and_conserves_battery_energy() -> None:
    W = np.array([[5, 5, 5, 5, 5, 5], [4, 4, 4, 4, 4, 4]], dtype=float)
    episode = Episode.from_arrays(W, nameplates=[6, 5], pi_RT=np.ones(6) * 20, K=6, D=np.zeros(6))
    c = np.zeros_like(W)
    d = np.zeros_like(W)
    r = np.zeros_like(W)
    q = W.copy()
    plan = SimpleNamespace(q=q, c=c, d=d, r=r)
    result = realize(episode, plan)
    assert np.all(result.q.sum(axis=0) <= episode.K + 1e-6)
    assert np.all(result.r >= -1e-9)
    assert np.all(result.r <= W + 1e-9)
    for i, agent in enumerate(episode.agents):
        expected = (
            result.soc[i, :-1]
            + agent.battery.eta_c * result.c[i]
            - result.d[i] / agent.battery.eta_d
        )
        np.testing.assert_allclose(result.soc[i, 1:], expected, atol=1e-8)
        assert result.soc[i].min() >= -1e-8
        assert result.soc[i].max() <= agent.battery.E + 1e-8
    np.testing.assert_allclose(result.Vplus_attempted, np.full(6, 3.0))


def test_realization_reduces_discharge_after_wind_is_fully_curtailed() -> None:
    episode = Episode.from_arrays(
        np.array([[0.0], [0.0]]), nameplates=[4, 4], pi_RT=[50], K=1, D=[0]
    )
    d = np.array([[1.0], [1.0]])
    zeros = np.zeros((2, 1))
    plan = SimpleNamespace(q=d.copy(), c=zeros.copy(), d=d, r=zeros.copy())
    result = realize(episode, plan)
    assert result.q.sum() <= 1 + 1e-6
    assert result.d.sum() <= 1 + 1e-6
    assert np.all(result.soc >= -1e-9)


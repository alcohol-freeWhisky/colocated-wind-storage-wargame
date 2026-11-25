"""Small shared helpers for the toy scripts (numpy only).

Notation (same as the proposal):
    K      connection limit (MW)
    a[i]   available power of owner i this hour (MW): what it really can send
    l[i]   report of owner i (MW): what it says it can send
    k[i]   share given by the coordinator (MW)
    x[i]   energy actually sent in the hour (MWh) = min(a[i], k[i])
"""
import math

import numpy as np


def pro_rata(reports, K):
    """Pro-rata rule: if reports fit in K, everyone gets its report;
    otherwise everyone is scaled down by the same factor K / sum(reports)."""
    reports = np.asarray(reports, dtype=float)
    total = reports.sum()
    if total <= K:
        return reports.copy()
    return reports * K / total


def pro_rata_rows(R, K):
    """Same rule applied to every row (hour) of a (T, N) array."""
    tot = R.sum(axis=1, keepdims=True)
    return R * np.minimum(1.0, K / np.maximum(tot, 1e-12))


def sends(a, k):
    """Energy actually sent: an owner cannot send more than it has
    or more than its share."""
    return np.minimum(a, k)


def water_fill(caps, weights, K):
    """Weighted fill used by the meter-feedback rule:
    k[i] = min(cap[i], lam * w[i]) with sum(k) = K.
    If the caps add up to less than K, every owner gets its cap PLUS a part of
    the leftover (by weights), so shares can exceed caps. This is on purpose:
    unused connection is offered to everyone, in case wind rose."""
    caps = np.asarray(caps, float); weights = np.asarray(weights, float)
    if caps.sum() <= K:
        return caps + (K - caps.sum()) * weights / weights.sum()
    lo, hi = 0.0, float((caps / weights).max())
    for _ in range(60):
        lam = 0.5 * (lo + hi)
        if np.minimum(caps, lam * weights).sum() > K:
            hi = lam
        else:
            lo = lam
    return np.minimum(caps, lo * weights)


def _weibull_from_ar1(rng, shape, phi, c, k):
    """Weibull wind speeds that persist in time: an AR(1) Gaussian series
    (lag-1 correlation phi) mapped to a Weibull(c, k) distribution."""
    T = shape[0]
    z = np.zeros(shape)
    z[0] = rng.standard_normal(shape[1:])
    for t in range(1, T):
        z[t] = phi * z[t - 1] + np.sqrt(1 - phi**2) * rng.standard_normal(shape[1:])
    erf = np.frompyfunc(math.erf, 1, 1)
    p = 0.5 * (1 + erf(z / np.sqrt(2)).astype(float))      # uniform in (0, 1)
    p = np.clip(p, 1e-12, 1 - 1e-12)
    return c * (-np.log(1 - p)) ** (1 / k)


def synthetic_wind(n_owners, hours, r, nameplate, seed=0, persistence=0.95):
    # persistence = coefficient of a hidden Gaussian AR(1) series (see below)
    """Correlated synthetic wind, following the recipe in Andoni et al. (2017),
    sources/04, p. 7:
        u_i = c_r * u_ref + (1 - c_r) * u_rand_i,  c_r = arccos(1 - 2r) / pi
    with Weibull wind speeds (scale 9 m/s, shape 1.8), then a simple power curve.
    r = 0 means independent wind, r = 1 means identical wind.

    Our addition: 'persistence' is the coefficient of a hidden Gaussian AR(1)
    series that drives each wind speed, so wind persists from hour to hour.
    Andoni et al. draw each hour independently (persistence = 0).
    Notes: (1) after the Weibull mapping and the power curve, the hour-to-hour
    correlation of POWER is close to, but not equal to, 'persistence';
    (2) the mix of two Weibull speeds is not exactly Weibull; (3) the
    correlation of POWER between owners is close to r, not equal.
    The scripts print the measured values."""
    rng = np.random.default_rng(seed)
    c, k = 9.0, 1.8
    u_ref = _weibull_from_ar1(rng, (hours,), persistence, c, k)
    u_rand = _weibull_from_ar1(rng, (hours, n_owners), persistence, c, k)
    cr = np.arccos(1 - 2 * r) / np.pi
    u = cr * u_ref[:, None] + (1 - cr) * u_rand
    # generic power curve: 0 below 3 m/s, cubic up to 12 m/s, flat to 25, 0 above
    cf = np.clip((u**3 - 3**3) / (12**3 - 3**3), 0, 1)
    cf[u > 25] = 0.0
    return cf * np.asarray(nameplate, float)[None, :]

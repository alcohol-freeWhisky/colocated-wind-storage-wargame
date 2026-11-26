"""Deterministic forecast comparison with private owner histories.

Forecasting policies receive own wind/SOC and inferred past aggregate requests.
Only the ORACLE rollout and the evaluator receive private rival trajectories.
"""
from __future__ import annotations

from dataclasses import dataclass
import itertools
import numpy as np
from scipy.optimize import minimize


@dataclass
class Day:
    date: str
    W: np.ndarray
    price: np.ndarray


@dataclass
class Plant:
    names: list[str]
    N: np.ndarray
    P: np.ndarray
    E: np.ndarray
    K: float
    eta_c: float
    eta_d: float
    deg: float
    eps: float
    dt: float = 1.0


def policies(prices, config):
    levels = np.quantile(prices, config['price_quantiles'])
    return np.asarray([(a, b, beta) for a, b in itertools.combinations_with_replacement(levels, 2)
                       for beta in config['beta_grid']] + [(np.inf, np.inf, np.inf)])


def features(hour, origin, price, wind, soc_fraction, last, age, scale=100):
    return np.asarray([1, np.sin(2*np.pi*hour/24), np.cos(2*np.pi*hour/24),
                       price/scale, wind, soc_fraction, last, min(age, 168)/24,
                       (hour-origin)/24], dtype=float)


def action(W, price, soc, P, E, forecast, policy, K, ec, ed, remaining_charge, target):
    """Vectorized feasible actions; all information belongs to the acting owner.

    remaining_charge is the owner's perfect-foresight maximum future wind charge.
    Projection retains the same terminal return requirement for every treatment.
    """
    lo, hi, beta = policy[..., 0], policy[..., 1], policy[..., 2]
    fallback = np.isinf(beta)
    safe_beta = np.where(fallback, 0, beta)
    cap = np.maximum(K-safe_beta*forecast, 0)
    c = np.where(price <= lo, np.minimum(np.minimum(P, W), np.maximum(E-soc, 0)/ec), 0)
    d = np.where(price > hi, np.minimum(np.minimum(P, ed*soc), cap), 0)
    # Next SOC must leave the original return target reachable.
    floor = np.maximum(0, target-ec*remaining_charge)
    c = np.maximum(c, np.maximum(floor-soc, 0)/ec)
    c = np.minimum(np.minimum(c, P), np.minimum(W, np.maximum(E-soc, 0)/ec))
    d = np.where(c > 1e-10, 0, np.minimum(d, ed*np.maximum(soc-floor, 0)))
    r = np.minimum(W-c, np.maximum(W-c+d-cap, 0))
    # Return fallback charges only toward the target and exports nothing.
    fc = np.minimum(np.minimum(P, W), np.maximum(target-soc, 0)/ec)
    c = np.where(fallback, fc, c)
    d = np.where(fallback, 0, d)
    r = np.where(fallback, W-c, r)
    return c, d, r


def realize(W, soc, c, d, r, plant):
    """Batch equivalent of realize_hour for feasible, cycle-free input requests."""
    q = W-c-r+d
    total = q.sum(axis=-1, keepdims=True)
    cut = np.maximum(total-plant.K, 0)*q/np.maximum(total, 1e-30)
    wind_cut = np.minimum(cut, np.maximum(W-r, 0))
    pre = soc+plant.eta_c*c-d/plant.eta_d
    dc = np.minimum(np.minimum(np.maximum(cut-wind_cut, 0), d),
                    plant.eta_d*np.maximum(plant.E-pre, 0))
    spill = np.maximum(cut-wind_cut-dc, 0)
    rd = d-dc
    rr = r+wind_cut
    accepted = W-c-rr+rd-spill
    nxt = soc+plant.eta_c*c-rd/plant.eta_d
    return accepted, nxt, rd, rr, spill, q


def observe(last, age, q, accepted, plant, initial=0.5):
    """Only own request/acceptance enter this update. Zero requests reveal nothing."""
    total_names = plant.N.sum()-plant.N
    exact = (q > 1e-6) & (accepted > 1e-6) & (q-accepted > 1e-6)
    value = np.maximum(plant.K*q/np.maximum(accepted, 1e-30)-q, 0)/total_names
    return np.where(exact, value, last), np.where(exact, 0, np.minimum(age+1, 168))


class Forecaster:
    def __init__(self, theta, plant, config):
        self.theta, self.plant, self.config = theta, plant, config

    def predict(self, i, h, day, soc, last, age):
        total = self.plant.N.sum()-self.plant.N[i]
        result = []
        for t in range(h, 24):
            theta = self.theta[i, t-h]
            x = features(t, h, day.price[t], day.W[i, t]/self.plant.N[i],
                         soc/self.plant.E[i], last, age, self.config['price_scale'])
            pred = last if np.isnan(theta).any() else x@theta
            result.append(np.clip(total*pred, 0, (self.plant.N+self.plant.P).sum()
                                  -self.plant.N[i]-self.plant.P[i]))
        return np.asarray(result)


def fit_models(samples, plant, ridge, minimum=24):
    """Squared exact error plus squared upper-bound exceedance; no hidden labels."""
    theta = np.full((5, 24, 9), np.nan)
    for i in range(5):
        for k in range(24):
            data = [s for s in samples if s['i'] == i and s['lead'] == k]
            if len(data) < minimum:
                continue
            X = np.asarray([s['x'] for s in data]); y = np.asarray([s['label'] for s in data])
            exact = np.asarray([s['exact'] for s in data]); n = len(y)
            def loss(b):
                err = X@b-y
                err = np.where(exact, err, np.maximum(err, 0))
                penalty = b.copy(); penalty[0] = 0
                return float(err@err/n+ridge*(penalty@penalty)), 2*X.T@err/n+2*ridge*penalty
            init = np.zeros(9); init[0] = .5
            res = minimize(loss, init, jac=True, method='L-BFGS-B', options={'maxiter': 1000})
            if not res.success:
                raise RuntimeError(f'Forecast fit failed: {res.message}')
            theta[i, k] = res.x
    return theta


def candidate_rollouts(day, plant, h, focal, soc, last, age, candidates, reference,
                       prediction, oracle=False):
    """Own forecast rollouts, or candidate-conditional full-state oracle rollouts."""
    C = len(candidates)
    if oracle:
        state = np.broadcast_to(soc, (C, 5)).copy()
        hist = np.broadcast_to(last, (C, 5)).copy(); ages = np.broadcast_to(age, (C, 5)).copy()
        pol = np.broadcast_to(reference, (C, 5, 3)).copy(); pol[:, focal] = candidates
        score = np.zeros(C)
        for t in range(h, 24):
            remaining = np.minimum(day.W[:, t+1:], plant.P[:, None]).sum(axis=1)
            pred = hist*(plant.N.sum()-plant.N)
            c,d,r = action(day.W[:, t], day.price[t], state, plant.P, plant.E,
                           pred, pol, plant.K, plant.eta_c, plant.eta_d, remaining, .5*plant.E)
            accepted, nxt, rd, rr, spill, q = realize(day.W[:, t], state,c,d,r,plant)
            score += day.price[t]*accepted[:,focal]-plant.deg*rd[:,focal] \
                     -plant.eps*(c[:,focal]+d[:,focal]+r[:,focal])
            hist,ages = observe(hist,ages,q,accepted,plant); state=nxt
        return score
    # The predictor path is fixed at the information available at forecast origin.
    i=focal; state=np.full(C,soc[i]); score=np.zeros(C)
    for t in range(h,24):
        future = np.minimum(day.W[i,t+1:],plant.P[i]).sum()
        c,d,r=action(day.W[i,t],day.price[t],state,plant.P[i],plant.E[i],prediction[t-h],
                      candidates,plant.K,plant.eta_c,plant.eta_d,future,.5*plant.E[i])
        q=day.W[i,t]-c-r+d
        total=q+prediction[t-h]
        cut=np.maximum(total-plant.K,0)*q/np.maximum(total,1e-30)
        wc=np.minimum(cut,np.maximum(day.W[i,t]-r,0))
        pre=state+plant.eta_c*c-d/plant.eta_d
        dc=np.minimum(np.minimum(np.maximum(cut-wc,0),d),plant.eta_d*np.maximum(plant.E[i]-pre,0))
        spill=np.maximum(cut-wc-dc,0)
        rd=d-dc; acc=day.W[i,t]-c-r-wc+rd-spill
        score+=day.price[t]*acc-plant.deg*rd-plant.eps*(c+d+r)
        state=state+plant.eta_c*c-rd/plant.eta_d
    return score


def simulate(day, plant, reference, last, age, *, focal=None, method='REFERENCE',
             candidates=None, forecaster=None, collect=False):
    soc=.5*plant.E.copy(); rows=[]; origins=[]
    total_names=plant.N.sum()-plant.N
    for h in range(24):
        remaining=np.minimum(day.W[:,h+1:],plant.P[:,None]).sum(axis=1)
        pred=last*total_names
        pol=np.broadcast_to(reference,(5,3)).copy()
        focal_path=None
        if focal is not None:
            if method=='ZERO': focal_path=np.zeros(24-h)
            elif method=='FIT': focal_path=forecaster.predict(focal,h,day,soc[focal],last[focal],age[focal])
            else: focal_path=np.full(24-h,pred[focal])
            score=candidate_rollouts(day,plant,h,focal,soc,last,age,candidates,reference,
                                     focal_path,oracle=method=='ORACLE')
            pol[focal]=candidates[int(np.argmax(score))]
            if method!='ORACLE': pred[focal]=focal_path[0]
        if collect:
            for i in range(5):
                for t in range(h,24):
                    origins.append(dict(i=i,origin=h,target=t,lead=t-h,
                        x=features(t,h,day.price[t],day.W[i,t]/plant.N[i],soc[i]/plant.E[i],last[i],age[i])))
        c,d,r=action(day.W[:,h],day.price[h],soc,plant.P,plant.E,pred,pol,plant.K,
                     plant.eta_c,plant.eta_d,remaining,.5*plant.E)
        # ORACLE must implement the first action used in its winning rollout.
        # That action uses the same current persistence signal for the focal policy.
        acc,nxt,rd,rr,spill,q=realize(day.W[:,h],soc,c,d,r,plant)
        if np.any(nxt < -1e-6) or np.any(nxt>plant.E+1e-6) or acc.sum()>plant.K+1e-6:
            raise RuntimeError('Physical feasibility failure')
        if np.any(c*rd>1e-7) or np.any(c+rr>day.W[:,h]+1e-6):
            raise RuntimeError('Wind-only or simultaneous-operation failure')
        for i in range(5):
            exact=q[i]>1e-6 and acc[i]>1e-6 and q[i]-acc[i]>1e-6
            bound=q[i]>1e-6 and not exact
            label=(plant.K*q[i]/acc[i]-q[i])/total_names[i] if exact else max(plant.K-q[i],0)/total_names[i]
            true=q.sum()-q[i]
            fp=pred[i] if i!=focal or method=='ORACLE' else focal_path[0]
            rows.append(dict(day=day.date,hour=h,i=i,method=method,focal=-1 if focal is None else focal,
                W=day.W[i,h],price=day.price[h],soc_start=soc[i],soc=nxt[i],q_requested=q[i],q=acc[i],
                c=c[i],d=rd[i],r=rr[i],spill=spill[i],rival_request=true,forecast=fp,
                forecast_used=method!='ORACLE' or i!=focal,
                forecast_path=(focal_path.tolist() if i==focal and method!='ORACLE' else None),
                observable=exact or bound,exact=exact,label=label,
                J=day.price[h]*acc[i]-plant.deg*rd[i],overflow=max(q.sum()-plant.K,0),
                last=last[i],age=age[i]))
        last,age=observe(last,age,q,acc,plant);soc=nxt
    if np.any(soc < .5*plant.E-1e-6): raise RuntimeError('Terminal return failure')
    samples=[]
    if collect:
        for entry in origins:
            outcome=rows[entry['target']*5+entry['i']]
            if outcome['observable']:
                samples.append({**entry,'label':outcome['label'],'exact':outcome['exact'],'day':day.date})
    return rows,last,age,samples

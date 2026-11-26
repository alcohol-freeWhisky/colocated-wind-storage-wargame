"""Physical equivalence, censored information, and dispatch isolation checks."""
import numpy as np
from wargame.learning.experiment import (Plant,Day,realize,observe,action,candidate_rollouts,fit_models)
from wargame.model.env import Episode
from wargame.solvers.realize import realize_hour


def setup():
    ep=Episode.from_arrays(np.ones((5,24))*10,nameplates=np.ones(5)*10,
        cfg={'battery':{'p_ratio':.29,'duration_h':1.5}})
    p=Plant([a.name for a in ep.agents],ep.nameplates,
        np.array([a.battery.P for a in ep.agents]),np.array([a.battery.E for a in ep.agents]),
        ep.K,.922,.922,10,.001)
    return ep,p


def test_realization_matches_existing_with_congestion_and_discharge():
    ep,p=setup();rng=np.random.default_rng(9)
    for _ in range(50):
        s=rng.uniform(.1,.9,5)*p.E; W=rng.uniform(0,15,5)
        d=np.minimum(np.minimum(rng.uniform(0,3,5),p.P),.922*s);c=np.zeros(5);r=W*rng.uniform(0,.5,5)
        result=realize(W,s,c,d,r,p)
        old=realize_hour(W,c,d,r,ep.agents,s,p.K)
        for a,b in [(result[0],old[0]),(result[1],old[4]),(result[2],old[2]),(result[3],old[3])]:
            np.testing.assert_allclose(a,b,atol=1e-8)


def test_observation_inversion_and_nonbinding_censoring():
    _,p=setup();q=np.array([12.,10.,8.,7.,6.]);acc=q*p.K/q.sum()
    last,age=observe(np.full(5,.5),np.ones(5),q,acc,p)
    np.testing.assert_allclose(last,(q.sum()-q)/(p.N.sum()-p.N))
    np.testing.assert_allclose(age,0)
    x,a=observe(last,age,np.ones(5),np.ones(5),p)
    np.testing.assert_allclose(x,last);np.testing.assert_allclose(a,1)


def test_hidden_rival_state_cannot_change_nonoracle_scores():
    _,p=setup();W=np.ones((5,24))*8;day=Day('test',W,np.linspace(-10,100,24))
    candidates=np.array([[0,50,0],[0,50,1],[np.inf,np.inf,np.inf]])
    s=p.E*.5;last=np.full(5,.5);age=np.ones(5);pred=np.ones(24)*20
    a=candidate_rollouts(day,p,0,0,s,last,age,candidates,candidates[0],pred)
    W2=W.copy();W2[1:]*=.1;s2=s.copy();s2[1:]*=.1
    b=candidate_rollouts(Day('test',W2,day.price),p,0,0,s2,last,age,candidates,candidates[0],pred)
    np.testing.assert_allclose(a,b)


def test_terminal_viability_projection():
    _,p=setup();s=p.E*.5;W=np.zeros(5)
    c,d,r=action(W,100,s,p.P,p.E,np.zeros(5),np.tile([0,50,0],(5,1)),
                   p.K,.922,.922,np.zeros(5),.5*p.E)
    np.testing.assert_allclose(d,0)


def test_censored_fit_uses_bound_without_turning_it_into_exact_label():
    _,p=setup();samples=[]
    for _ in range(30):
        samples.append(dict(i=0,lead=0,x=np.array([1.,0,0,0,0,0,0,0,0]),label=.8,exact=True))
        samples.append(dict(i=0,lead=0,x=np.array([1.,0,0,0,0,0,0,0,0]),label=1.,exact=False))
    theta=fit_models(samples,p,.01)
    assert abs(theta[0,0,0]-.8)<1e-4


def test_oracle_rollout_matches_executed_reference_when_candidate_is_reference():
    from wargame.learning.experiment import simulate
    _,p=setup();rng=np.random.default_rng(23)
    day=Day('test',rng.uniform(0,15,(5,24)),np.linspace(-20,120,24))
    ref=np.array([20.,70.,1.]);last=np.full(5,.5);age=np.full(5,168.)
    score=candidate_rollouts(day,p,0,2,.5*p.E,last,age,ref[None,:],ref,None,oracle=True)[0]
    rows,_,_,_=simulate(day,p,ref,last,age)
    own=[r for r in rows if r['i']==2]
    # The score charges planned activity; terminal projection removes cycles.
    # Reconstruct requested activity because realization may add curtailment.
    state=.5*p.E.copy();hist=last.copy();ages=age.copy();expected=0.
    for t in range(24):
        future=np.minimum(day.W[:,t+1:],p.P[:,None]).sum(axis=1)
        c,d,r=action(day.W[:,t],day.price[t],state,p.P,p.E,hist*(p.N.sum()-p.N),
            np.tile(ref,(5,1)),p.K,p.eta_c,p.eta_d,future,.5*p.E)
        acc,nxt,rd,rr,spill,q=realize(day.W[:,t],state,c,d,r,p)
        expected+=day.price[t]*acc[2]-p.deg*rd[2]-p.eps*(c[2]+d[2]+r[2])
        hist,ages=observe(hist,ages,q,acc,p);state=nxt
    np.testing.assert_allclose(score,expected)
    np.testing.assert_allclose(sum(r['J'] for r in own),
        sum(day.price[r['hour']]*r['q']-p.deg*r['d'] for r in own))

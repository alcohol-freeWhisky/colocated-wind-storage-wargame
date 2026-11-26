import numpy as np
from test_learning import setup
from wargame.learning.experiment import Day
from wargame.learning.soc_filter import SOCFilter
from wargame.learning.simultaneous import run_day


def test_private_truth_is_evaluation_only():
    _,p=setup();cand=np.array([[0,40,0],[0,60,1],[np.inf,np.inf,np.inf]])
    a=SOCFilter(p,0,cand,11,particles=16);b=SOCFilter(p,0,cand,11,particles=16)
    a.diagnostics(p.E*.1);b.diagnostics(p.E*.9)
    w=np.ones(24)*8;price=np.linspace(-10,100,24)
    np.testing.assert_allclose(a.predict(w,price,0,.5*p.E[0],.5,168),
                               b.predict(w,price,0,.5*p.E[0],.5,168))


def test_filter_day_preserves_physics_and_normalized_weights():
    _,p=setup();cand=np.array([[0,40,0],[0,60,1],[np.inf,np.inf,np.inf]])
    filters=[SOCFilter(p,i,cand,11+i,particles=16) for i in range(5)]
    day=Day('test',np.ones((5,24))*8,np.linspace(-10,100,24))
    rows,paths,_,_,_,scores=run_day(day,p,cand,'SOC_FILTER',None,
        np.full(5,.5),np.full(5,168.),beliefs=filters)
    assert len(rows)==120 and len(scores)==120
    for f in filters:
        assert np.isclose(f.weights.sum(),1)
        assert (f.soc>=-1e-6).all() and (f.soc<=p.E+1e-6).all()
    for i in range(5):assert rows[-5+i]['soc']>=.5*p.E[i]-1e-6


def test_prior_does_not_condition_and_reset_ablation_resets_soc():
    _,p=setup();cand=np.array([[0,40,0],[0,60,1]])
    prior=SOCFilter(p,0,cand,11,particles=16,condition=False)
    reset=SOCFilter(p,0,cand,11,particles=16,reset_soc=True)
    w=np.ones(24)*8;price=np.ones(24)*100
    for f in [prior,reset]: f.update(w,price,0,.5*p.E[0],0,0,0,8,4,.5)
    np.testing.assert_allclose(prior.weights,np.full(16,1/16))
    np.testing.assert_allclose(reset.soc,np.tile(.5*p.E,(16,1)))

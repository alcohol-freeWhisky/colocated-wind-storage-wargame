import numpy as np
from wargame.learning.simultaneous import run_day
from wargame.learning.experiment import Forecaster,Day
from test_learning import setup


def test_joint_decisions_use_only_pre_action_history():
    _,p=setup();W=np.ones((5,24))*8;prices=np.linspace(-10,100,24)
    candidates=np.array([[0,50,0],[0,50,1],[np.inf,np.inf,np.inf]])
    def run(w):
        return run_day(Day('test',w,prices),p,candidates,'PERSIST',None,np.ones(5)*.5,np.ones(5)*168)[0]
    a=run(W);W2=W.copy();W2[1:]*=.1;b=run(W2)
    # Own current action is invariant to rivals' private wind before execution.
    np.testing.assert_allclose(a[0]['q_requested'],b[0]['q_requested'])
    assert len(a)==120
    assert sum(r['q'] for r in a[:5])<=p.K+1e-6
    for i in range(5): assert a[-5+i]['soc']>=.5*p.E[i]-1e-6

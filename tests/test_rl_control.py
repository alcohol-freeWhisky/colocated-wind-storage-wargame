import numpy as np
from test_learning import setup
from wargame.learning.experiment import Day
from wargame.learning.control import DQN,obs,direct_action,dp_action,run


def config():
    return dict(hidden=8,actions=[-1,0,1],batch_size=8,replay_capacity=100,warmup=8,
        learning_rate=.001,discount=1,target_interval=10,updates_per_hour=1)


def test_actor_observation_cannot_see_rival_private_wind_or_soc():
    _,p=setup();W=np.ones((5,24))*8;price=np.arange(24.)
    a=obs(Day('x',W,price),0,.5*p.E,np.ones(5)*.5,np.ones(5),p)
    W[1:]*=.1;s=.5*p.E;s[1:]=0
    b=obs(Day('x',W,price),0,s,np.ones(5)*.5,np.ones(5),p)
    np.testing.assert_allclose(a[0],b[0])


def test_dp_charges_for_later_price_increase():
    _,p=setup();W=np.zeros((5,24));W[:,22]=2
    price=np.zeros(24);price[22]=10;price[23]=100
    actions=np.array([-1.,0,1])
    a=dp_action(Day('x',W,price),22,0,.5*p.E[0],np.zeros(2),p,actions)
    assert actions[a]<0


def test_terminal_dqn_target_does_not_bootstrap():
    a=DQN(config(),1);b=DQN(config(),1)
    b.target=[np.ones_like(x)*10 for x in b.target]
    for _ in range(8):
        x=np.zeros((5,17));act=np.zeros(5,dtype=int);reward=np.ones(5)*.1
        a.remember(x,act,reward,x,True);b.remember(x,act,reward,x,True)
    a.update();b.update()
    for x,y in zip(a.params,b.params):np.testing.assert_allclose(x,y)


def test_rl_execution_preserves_terminal_and_physical_constraints():
    _,p=setup();day=Day('x',np.ones((5,24))*8,np.linspace(-20,120,24))
    model=DQN(config(),5)
    rows,*_=run(day,p,np.array([-1.,0,1]),'DQN',np.full(5,.5),np.full(5,168.),
        model=model,epsilon=1,train=True)
    for i in range(5):assert rows[-5+i]['soc']>=.5*p.E[i]-1e-6
    assert model.updates>0


def test_independent_q_function_has_no_cross_owner_features():
    model=DQN(config(),3);x=np.ones((5,1,17))
    a,_=model.forward(x,model.params)
    x[1:]=100
    b,_=model.forward(x,model.params)
    np.testing.assert_allclose(a[0],b[0])

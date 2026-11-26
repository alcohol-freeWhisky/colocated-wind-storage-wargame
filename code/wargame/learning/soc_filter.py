"""Latent rival SOC/policy filter using own metering and a wind proxy.

Private rival truth is accepted only by diagnostics, after prediction, and never
enters inference. Each filter belongs to one owner.
"""
import numpy as np
from scipy.special import log_ndtr
from .experiment import action,realize


class SOCFilter:
    def __init__(self,plant,owner,candidates,seed,particles=128,wind_sigma=.15,
                 observation_sigma=.05,condition=True,reset_soc=False,wind_ar=.8,policy_change_probability=.05):
        self.p=plant;self.i=owner;self.M=particles
        self.rng=np.random.default_rng(seed)
        self.candidates=candidates[~np.isinf(candidates[:,2])]
        self.soc=np.tile(.5*plant.E,(particles,1))
        self.policy=self.rng.integers(0,len(self.candidates),(particles,5))
        self.wind_error=np.zeros((particles,5));self.weights=np.full(particles,1/particles)
        self.wind_sigma=wind_sigma;self.observation_sigma=observation_sigma
        self.condition=condition;self.reset_soc=reset_soc;self.last_ess=float(particles)
        self.wind_ar=wind_ar;self.policy_change_probability=policy_change_probability

    def _step(self,ownwind,prices,t,state,error,policy,own_soc,last,actual_action=None):
        p=self.p;i=self.i
        error=self.wind_ar*error+np.sqrt(1-self.wind_ar**2)*self.wind_sigma*self.rng.normal(size=error.shape)
        wind=np.clip(ownwind[t]/p.N[i]+error,0,1.2)*p.N
        wind[:,i]=ownwind[t];state=state.copy();state[:,i]=own_soc
        future_cf=ownwind[t+1:]/p.N[i]
        future=np.minimum(np.clip(future_cf[:,None],0,1.2)*p.N,p.P).sum(axis=0)
        pred=last*(p.N.sum()-p.N)
        pol=self.candidates[policy]
        c,d,r=action(wind,prices[t],state,p.P,p.E,pred,pol,p.K,p.eta_c,p.eta_d,future,.5*p.E)
        if actual_action is not None:
            c[:,i],d[:,i],r[:,i]=actual_action
        acc,nxt,rd,rr,spill,q=realize(wind,state,c,d,r,p)
        return q.sum(axis=1)-q[:,i],nxt,error,q,acc

    def predict(self,ownwind,prices,h,own_soc,last,age):
        state=self.soc.copy();error=self.wind_error.copy();policy=self.policy.copy()
        result=[];own=np.full(self.M,own_soc)
        for t in range(h,24):
            q,nxt,error,requests,accepted=self._step(ownwind,prices,t,state,error,policy,own,last)
            result.append(float(self.weights@q));state=nxt;own=nxt[:,self.i]
        return np.asarray(result)

    def update(self,ownwind,prices,h,own_soc,c,d,r,own_request,own_accepted,last):
        p=self.p;i=self.i
        q,nxt,error,_,_=self._step(ownwind,prices,h,self.soc,self.wind_error,self.policy,
                                  own_soc,last,(c,d,r))
        if self.condition and own_request>1e-6:
            sigma=self.observation_sigma*(p.N.sum()-p.N[i])
            if own_request-own_accepted>1e-6 and own_accepted>1e-6:
                observation=p.K*own_request/own_accepted-own_request
                likelihood=-.5*((q-observation)/sigma)**2
            else:
                likelihood=log_ndtr((p.K-own_request-q)/sigma)
            logw=np.log(np.maximum(self.weights,1e-300))+likelihood
            w=np.exp(logw-logw.max());self.weights=w/w.sum()
        self.last_ess=float(1/(self.weights@self.weights))
        self.soc=nxt;self.wind_error=error
        if self.last_ess<self.M/2:
            u=(self.rng.random()+np.arange(self.M))/self.M
            indices=np.searchsorted(np.cumsum(self.weights),u).clip(max=self.M-1)
            self.soc=self.soc[indices].copy();self.wind_error=self.wind_error[indices].copy()
            self.policy=self.policy[indices].copy();self.weights.fill(1/self.M)
        # Unknown opponent policies may change between operating intervals.
        change=self.rng.random(self.policy.shape)<self.policy_change_probability
        replacement=self.rng.integers(0,len(self.candidates),self.policy.shape)
        self.policy=np.where(change,replacement,self.policy)
        if self.reset_soc:self.soc[:]=.5*p.E

    def diagnostics(self,truth):
        """Evaluator-only scoring; this method does not change the filter."""
        mask=np.arange(5)!=self.i
        estimate=self.weights@self.soc
        aggregate_est=float(estimate[mask].sum());aggregate_true=float(truth[mask].sum())
        return dict(aggregate_soc_estimate=aggregate_est,aggregate_soc_true=aggregate_true,
            aggregate_soc_error2=(aggregate_est-aggregate_true)**2,
            individual_soc_error2=float(np.mean((estimate[mask]-truth[mask])**2)),
            ess=self.last_ess)

"""Simultaneous decisions and delayed-label online forecast updates."""
import numpy as np
from .experiment import action, realize, observe, features, candidate_rollouts


def run_day(day, plant, candidates, method, forecaster, last, age, beliefs=None):
    """Choose all five actions from pre-action histories, then execute jointly."""
    soc=.5*plant.E.copy(); rows=[]; origins=[]; paths=[]; state_scores=[]
    for h in range(24):
        forecasts=[]; selected=[]
        for i in range(5):
            if method=='ZERO': path=np.zeros(24-h)
            elif method=='PERSIST': path=np.full(24-h,last[i]*(plant.N.sum()-plant.N[i]))
            elif beliefs is not None:
                path=beliefs[i].predict(day.W[i],day.price,h,soc[i],last[i],age[i])
                state_scores.append(dict(day=day.date,hour=h,owner=i,
                    **beliefs[i].diagnostics(soc)))
            else: path=forecaster.predict(i,h,day,soc[i],last[i],age[i])
            forecasts.append(path)
            score=candidate_rollouts(day,plant,h,i,soc,last,age,candidates,candidates[0],path)
            selected.append(candidates[np.argmax(score)])
            for t in range(h,24):
                origins.append(dict(i=i,origin=h,target=t,lead=t-h,
                    x=features(t,h,day.price[t],day.W[i,t]/plant.N[i],soc[i]/plant.E[i],last[i],age[i])))
        # No owner's decision is revealed until every owner has selected an action.
        forecast=np.array([x[0] for x in forecasts])
        rem=np.minimum(day.W[:,h+1:],plant.P[:,None]).sum(axis=1)
        c,d,r=action(day.W[:,h],day.price[h],soc,plant.P,plant.E,forecast,
            np.asarray(selected),plant.K,plant.eta_c,plant.eta_d,rem,.5*plant.E)
        acc,nxt,rd,rr,spill,q=realize(day.W[:,h],soc,c,d,r,plant)
        if (np.any(nxt < -1e-6) or np.any(nxt>plant.E+1e-6) or
            acc.sum()>plant.K+1e-6 or np.any(c*rd>1e-7) or np.any(c+rr>day.W[:,h]+1e-6)):
            raise RuntimeError('Physical feasibility failure')
        for i in range(5):
            exact=q[i]>1e-6 and acc[i]>1e-6 and q[i]-acc[i]>1e-6
            bound=q[i]>1e-6 and not exact
            norm=plant.N.sum()-plant.N[i]
            label=(plant.K*q[i]/acc[i]-q[i])/norm if exact else max(plant.K-q[i],0)/norm
            rows.append(dict(day=day.date,hour=h,i=i,method=method,price=day.price[h],W=day.W[i,h],
                soc_start=soc[i],soc=nxt[i],c=c[i],d=rd[i],r=rr[i],spill=spill[i],
                q_requested=q[i],q=acc[i],J=day.price[h]*acc[i]-plant.deg*rd[i],
                forecast=forecast[i],rival_request=q.sum()-q[i],exact=exact,
                observable=exact or bound,label=label,overflow=max(q.sum()-plant.K,0),
                policy_low=selected[i][0],policy_high=selected[i][1],policy_beta=selected[i][2]))
            for lead,pred in enumerate(forecasts[i]):
                paths.append(dict(day=day.date,method=method,i=i,origin=h,lead=lead,prediction=pred))
            if beliefs is not None:
                # The filter receives only this owner's action, wind, and metering.
                beliefs[i].update(day.W[i],day.price,h,soc[i],c[i],d[i],r[i],q[i],acc[i],last[i])
        soc=nxt;last,age=observe(last,age,q,acc,plant)
    if np.any(soc < .5*plant.E-1e-6): raise RuntimeError('Terminal return failure')
    samples=[]
    for o in origins:
        y=rows[o['target']*5+o['i']]
        if y['observable']: samples.append({**o,'day':day.date,'label':y['label'],'exact':y['exact']})
    for p in paths:
        y=rows[(p['origin']+p['lead'])*5+p['i']]
        p['actual']=y['rival_request']
    return rows,paths,samples,last,age,state_scores

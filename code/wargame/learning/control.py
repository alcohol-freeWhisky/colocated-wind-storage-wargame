"""Direct battery controls, forecast dynamic programming and independent DQN."""
import numpy as np
from .experiment import realize,observe


def direct_action(W, price, soc, P, E, command, ec, ed, remaining):
    """Positive command discharges, negative command charges; terminal-safe."""
    c=np.minimum(np.minimum(np.maximum(-command,0)*P,W),np.maximum(E-soc,0)/ec)
    floor=np.maximum(.5*E-ec*remaining,0)
    c=np.maximum(c,np.maximum(floor-soc,0)/ec)
    c=np.minimum(np.minimum(c,P),np.minimum(W,np.maximum(E-soc,0)/ec))
    d=np.where(c>1e-10,0,np.minimum(np.maximum(command,0)*P,ed*np.maximum(soc-floor,0)))
    r=np.where(price<0,W-c,0.)
    return c,d,r


def obs(day,h,soc,last,age,p):
    """One row per owner; each row contains only that owner's allowed inputs."""
    future=day.price[h:];near=day.price[h:min(h+6,24)]
    feats=[]
    for i in range(5):
        w=day.W[i,h:]/p.N[i]
        feats.append([h/24,soc[i]/p.E[i],day.W[i,h]/p.N[i],
            np.clip(day.price[h]/100,-5,5),np.mean(future)/100,np.max(future)/100,
            np.min(future)/100,np.mean(near)/100,np.max(near)/100,
            np.mean(w),np.max(w),last[i],min(age[i],168)/168,
            (24-h)/24, p.P[i]/p.N[i],
            (np.max(future)-day.price[h])/100,
            (day.price[h]-np.min(future))/100])
    return np.clip(np.asarray(feats),-5,5)


def own_realization(W,soc,c,d,r,rivals,p,i):
    q=W-c-r+d;total=q+rivals
    cut=np.maximum(total-p.K,0)*q/np.maximum(total,1e-30)
    wc=np.minimum(cut,np.maximum(W-r,0))
    pre=soc+p.eta_c*c-d/p.eta_d
    dc=np.minimum(np.minimum(np.maximum(cut-wc,0),d),p.eta_d*np.maximum(p.E[i]-pre,0))
    spill=np.maximum(cut-wc-dc,0)
    return q-cut,soc+p.eta_c*c-(d-dc)/p.eta_d,d-dc


def dp_action(day,h,i,soc,rivals,p,actions,points=81):
    """Backward finite-grid battery DP; fixed rival forecast, actual acceptance."""
    grid=np.linspace(0,p.E[i],points)
    value=np.where(grid>=.5*p.E[i]-1e-9,0.,-1e9)
    for t in range(23,h-1,-1):
        states=grid[:,None] if t>h else np.array([[soc]])
        rem=np.minimum(day.W[i,t+1:],p.P[i]).sum()
        c,d,r=direct_action(day.W[i,t],day.price[t],states,p.P[i],p.E[i],actions[None,:],
                            p.eta_c,p.eta_d,rem)
        acc,nxt,rd=own_realization(day.W[i,t],states,c,d,r,rivals[t-h],p,i)
        score=day.price[t]*acc-p.deg*rd-p.eps*(c+d+r)+np.interp(nxt,grid,value)
        if t==h:return int(np.argmax(score[0]))
        value=np.max(score,axis=1)


class DQN:
    """Five independent NumPy MLP Q functions with replay and Double-DQN targets."""
    def __init__(self,cfg,seed,nfeatures=17):
        self.cfg=cfg;self.rng=np.random.default_rng(seed);H=cfg['hidden'];A=len(cfg['actions'])
        self.w1=self.rng.normal(0,1/np.sqrt(nfeatures),(5,nfeatures,H));self.b1=np.zeros((5,H))
        self.w2=self.rng.normal(0,.01,(5,H,A));self.b2=np.zeros((5,A))
        self.params=[self.w1,self.b1,self.w2,self.b2]
        self.target=[x.copy() for x in self.params]
        self.m=[np.zeros_like(x) for x in self.params];self.v=[np.zeros_like(x) for x in self.params]
        self.replay=[];self.steps=0;self.updates=0

    @staticmethod
    def forward(x,weights):
        w,b,v,c=weights;z=np.tanh(np.einsum('ibf,ifh->ibh',x,w)+b[:,None,:])
        return np.einsum('ibh,iha->iba',z,v)+c[:,None,:],z

    def choose(self,x,epsilon=0):
        q,_=self.forward(x[:,None,:],self.params);a=np.argmax(q[:,0],axis=1)
        mask=self.rng.random(5)<epsilon
        return np.where(mask,self.rng.integers(0,len(self.cfg['actions']),5),a)

    def remember(self,x,a,r,nxt,done):
        transition=(x.copy(),a.copy(),r.copy(),nxt.copy(),done)
        if len(self.replay)<self.cfg['replay_capacity']:self.replay.append(transition)
        else:self.replay[self.steps%len(self.replay)]=transition
        self.steps+=1

    def update(self):
        if len(self.replay)<self.cfg['warmup']:return None
        B=self.cfg['batch_size'];items=[self.replay[k] for k in self.rng.integers(0,len(self.replay),B)]
        x=np.stack([t[0] for t in items],axis=1);a=np.stack([t[1] for t in items],axis=1)
        r=np.stack([t[2] for t in items],axis=1);nxt=np.stack([t[3] for t in items],axis=1)
        done=np.asarray([t[4] for t in items])
        q,z=self.forward(x,self.params);online,_=self.forward(nxt,self.params)
        target,_=self.forward(nxt,self.target)
        idx=np.argmax(online,axis=-1)
        y=r+self.cfg['discount']*(1-done)[None,:]*np.take_along_axis(target,idx[:,:,None],axis=-1)[:,:,0]
        pred=np.take_along_axis(q,a[:,:,None],axis=-1)[:,:,0]
        err=pred-y;dq=np.zeros_like(q)
        np.put_along_axis(dq,a[:,:,None],np.clip(err,-1,1)[:,:,None]/B,axis=-1)
        gw2=np.einsum('ibh,iba->iha',z,dq);gb2=dq.sum(axis=1)
        dz=np.einsum('iba,iha->ibh',dq,self.w2)*(1-z*z)
        gw1=np.einsum('ibf,ibh->ifh',x,dz);gb1=dz.sum(axis=1)
        self.updates+=1
        for k,(param,grad) in enumerate(zip(self.params,[gw1,gb1,gw2,gb2])):
            grad=np.clip(grad,-5,5)
            self.m[k]=.9*self.m[k]+.1*grad;self.v[k]=.999*self.v[k]+.001*grad*grad
            param-=self.cfg['learning_rate']*(self.m[k]/(1-.9**self.updates))/(np.sqrt(self.v[k]/(1-.999**self.updates))+1e-8)
        if self.updates%self.cfg['target_interval']==0:self.target=[p.copy() for p in self.params]
        return float(np.mean(np.where(np.abs(err)<1,.5*err**2,np.abs(err)-.5)))

    def save(self,path):np.savez(path,**{f'p{k}':v for k,v in enumerate(self.params)})
    def load(self,path):
        with np.load(path) as f:
            for k,p in enumerate(self.params):p[:]=f[f'p{k}']
        self.target=[p.copy() for p in self.params]


def run(day,p,actions,method,last,age,model=None,epsilon=0,train=False,forecaster=None,points=81,blind=False):
    soc=.5*p.E.copy();rows=[];losses=[]
    for h in range(24):
        x=obs(day,h,soc,last,age,p)
        if blind:x[:,11:13]=0
        if model is not None:indices=model.choose(x,epsilon)
        else:
            indices=[]
            for i in range(5):
                path=forecaster.predict(i,h,day,soc[i],last[i],age[i]) if forecaster is not None else np.full(24-h,last[i]*(p.N.sum()-p.N[i]))
                indices.append(dp_action(day,h,i,soc[i],path,p,actions,points))
            indices=np.asarray(indices)
        rem=np.minimum(day.W[:,h+1:],p.P[:,None]).sum(axis=1)
        c,d,r=direct_action(day.W[:,h],day.price[h],soc,p.P,p.E,actions[indices],p.eta_c,p.eta_d,rem)
        acc,nxt,rd,rr,spill,q=realize(day.W[:,h],soc,c,d,r,p)
        if (np.any(nxt< -1e-6) or np.any(nxt>p.E+1e-6) or acc.sum()>p.K+1e-6 or
            np.any(c*rd>1e-7) or np.any(c+rr>day.W[:,h]+1e-6)):
            raise RuntimeError('Physical feasibility failure')
        reward=day.price[h]*acc-p.deg*rd
        newlast,newage=observe(last,age,q,acc,p)
        if train:
            nx=obs(day,h+1,nxt,newlast,newage,p) if h<23 else np.zeros_like(x)
            if blind:nx[:,11:13]=0
            # Exogenous baseline has no action dependence and preserves returns.
            baseline=day.price[h]*np.minimum(day.W[:,h],p.K*p.N/p.N.sum())
            shaped=(reward-baseline)/(100*p.N)
            model.remember(x,indices,shaped,nx,h==23)
            for _ in range(model.cfg['updates_per_hour']):
                loss=model.update()
                if loss is not None:losses.append(loss)
        for i in range(5):rows.append(dict(day=day.date,method=method,hour=h,i=i,soc=nxt[i],
            W=day.W[i,h],price=day.price[h],command=actions[indices[i]],c=c[i],d=rd[i],r=rr[i],
            q_requested=q[i],q=acc[i],J=reward[i],overflow=max(q.sum()-p.K,0)))
        soc=nxt;last,age=newlast,newage
    if np.any(soc<.5*p.E-1e-6):raise RuntimeError('Terminal return failure')
    return rows,last,age,float(np.mean(losses)) if losses else np.nan

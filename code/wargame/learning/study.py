"""Shared data loading, tables and report helpers for sequential studies."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd
from wargame.experiments.io import load_config,assess_complete_days,write_table
from wargame.model.env import build_episode
from .experiment import Plant,Day,simulate


def context():
    cfg=load_config(Path('config/base.yaml'),Path('config/learning.yaml'))
    names=cfg['data']['primary_agents'];dates,_=assess_complete_days(cfg,names)
    eps=[build_episode(d,names,cfg) for d in dates];e=eps[0]
    p=Plant(names,e.nameplates,np.array([a.battery.P for a in e.agents]),
        np.array([a.battery.E for a in e.agents]),e.K,.922,.922,10,.001)
    days=[Day(str(e.day),e.W,e.pi_RT) for e in eps]
    with np.load('results/learning/fitted_model.npz') as model:
        theta=model['theta'];candidates=model['candidates'];ref=model['reference']
    last=np.full(5,.5);age=np.full(5,168.);samples=[]
    for k,d in enumerate(days[:40]):
        _,last,age,obs=simulate(d,p,ref,last,age,collect=True)
        if k<30:samples.extend(obs)
    return cfg,p,days,candidates,theta,last,age,samples


def table(df):
    return '| '+' | '.join(df.columns)+' |\n| '+' | '.join(['---']*len(df.columns))+' |\n'+''.join(
        '| '+' | '.join(f'{x:.3f}' if isinstance(x,float) else str(x) for x in row)+' |\n'
        for row in df.itertuples(index=False,name=None))


def save(output,cfg,rows,paths,runtime,metadata,states=None):
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    tr=pd.DataFrame(rows);fp=pd.DataFrame(paths)
    fp['error2']=(fp.prediction-fp.actual)**2
    tr['error2']=(tr.forecast-tr.rival_request)**2
    daily=tr.groupby(['method','day']).agg(J=('J','sum'),overflow=('overflow','first')).reset_index()
    ov=tr.groupby(['method','day','hour']).overflow.first().groupby(['method','day']).sum()
    daily['overflow']=daily.set_index(['method','day']).index.map(ov)
    summary=daily.groupby('method').agg(system_J=('J','mean'),overflow_mwh=('overflow','mean')).reset_index()
    err=tr.groupby('method').error2.mean().pow(.5)
    summary['rmse_mw']=summary.method.map(err)
    base=daily[daily.method=='PERSIST'].set_index('day').J
    rng=np.random.default_rng(6974);contrasts=[]
    for method in summary.method:
        diff=(daily[daily.method==method].set_index('day').J-base).to_numpy()
        boot=rng.choice(diff,(1000,len(diff))).mean(axis=1)
        contrasts.append(dict(method=method,delta_system_J=diff.mean(),low=np.quantile(boot,.025),high=np.quantile(boot,.975)))
    ct=pd.DataFrame(contrasts)
    lead=fp.groupby(['method','lead']).error2.mean().pow(.5).rename('rmse_mw').reset_index()
    hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('code/wargame/learning').glob('*.py')}
    metadata.update(source_sha256=hashes,objective='accepted-export revenue; no overflow penalty',
        split={'training':'2025-03-01/2025-03-31','validation':'2025-04-01/2025-04-10','test':'2025-04-11/2025-04-30'},test_dates=sorted(set(tr.day)),seed=6974)
    for name,df in [('trajectories',tr),('forecast_paths',fp),('daily',daily),('summary',summary),
        ('contrasts',ct),('forecast_by_lead',lead)]:write_table(df,out/f'{name}.csv',cfg,runtime,**metadata)
    if states:write_table(pd.DataFrame(states),out/'soc_diagnostics.csv',cfg,runtime,**metadata)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(1,2,figsize=(10,3.5),layout='constrained')
    for method,g in lead.groupby('method'):ax[0].plot(g.lead,g.rmse_mw,label=method)
    ax[0].set(xlabel='Lead (h)',ylabel='Rival request RMSE (MW)');ax[0].legend(fontsize=7,frameon=False)
    ax[1].errorbar(ct.delta_system_J,range(len(ct)),xerr=np.vstack([ct.delta_system_J-ct.low,ct.high-ct.delta_system_J]),fmt='o')
    ax[1].set_yticks(range(len(ct)),ct.method,fontsize=7);ax[1].axvline(0,color='gray',lw=.8)
    ax[1].set_xlabel('System margin difference vs persistence ($/day)')
    fig.savefig(out/'comparison.png',dpi=180);plt.close(fig)
    return summary,ct

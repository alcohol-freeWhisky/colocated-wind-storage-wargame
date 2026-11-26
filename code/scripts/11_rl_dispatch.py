#!/usr/bin/env python3
"""Improve dispatch with battery DP and compare independent reward-trained DQN."""
import hashlib,json,time
from pathlib import Path
import numpy as np
import pandas as pd
import yaml
from wargame.learning.study import context,table
from wargame.learning.experiment import Forecaster,simulate
from wargame.learning.control import DQN,run
from wargame.experiments.io import write_table


def evaluate(days,p,actions,method,last,age,**kwargs):
    out=[]
    for day in days:
        rows,last,age,_=run(day,p,actions,method,last,age,**kwargs);out+=rows
    return out


def main():
    started=time.perf_counter();cfg,p,days,candidates,theta,testlast,testage,_=context()
    rc=yaml.safe_load(Path('config/rl.yaml').read_text())['rl'];cfg['rl']=rc
    out=Path(rc['output']);out.mkdir(parents=True,exist_ok=True)
    actions=np.asarray(rc['actions']);rows=[];learning=[];selection=[]
    # Validation starts from training-only observable history.
    with np.load('results/learning/fitted_model.npz') as f:reference=f['reference']
    vl=np.full(5,.5);va=np.full(5,168.)
    for day in days[:30]:_,vl,va,_=simulate(day,p,reference,vl,va)
    for method,forecaster in [('DP_PERSIST',None),('DP_FIT',Forecaster(theta,p,cfg['learning']))]:
        rs=evaluate(days[40:],p,actions,method,testlast.copy(),testage.copy(),
            forecaster=forecaster,points=rc['dp_soc_points'])
        for r in rs:r['seed']=-1
        rows+=rs;print('Completed retrospective evaluation',method,flush=True)
    for blind in [False,True]:
        method='DQN_NO_RIVAL' if blind else 'DQN_HISTORY'
        for seed in rc['seeds']:
            model=DQN(rc,seed);rng=np.random.default_rng(seed);best=-np.inf;bestep=None
            path=out/f'{method.lower()}_{seed}.npz'
            for episode in range(1,rc['episodes']+1):
                day=days[int(rng.integers(0,30))]
                epsilon=rc['epsilon_start']+(rc['epsilon_end']-rc['epsilon_start'])*episode/rc['episodes']
                rs,_,_,loss=run(day,p,actions,method,np.full(5,.5),np.full(5,168.),
                    model=model,epsilon=epsilon,train=True,blind=blind)
                learning.append(dict(method=method,seed=seed,episode=episode,training_day=day.date,
                    J=sum(r['J'] for r in rs),loss=loss,epsilon=epsilon))
                if episode%rc['validation_interval']==0:
                    val=evaluate(days[30:40],p,actions,method,vl.copy(),va.copy(),model=model,blind=blind)
                    value=sum(r['J'] for r in val)/10
                    selection.append(dict(method=method,seed=seed,episode=episode,validation_J=value))
                    if value>best:best=value;bestep=episode;model.save(path)
                    print(method,seed,episode,'validation J',round(value,2),flush=True)
            model.load(path)
            rs=evaluate(days[40:],p,actions,method,testlast.copy(),testage.copy(),model=model,blind=blind)
            for r in rs:r['seed']=seed
            rows+=rs
            print('Selected',method,seed,bestep,best,flush=True)
    tr=pd.DataFrame(rows)
    # Original persistence threshold controller is an external reference, not a same-action-class control.
    old=pd.read_csv('results/learning_simultaneous/trajectories.csv')
    old=old[old.method=='PERSIST'].copy();old['method']='THRESHOLD_PERSIST';old['seed']=-1
    tr=pd.concat([tr,old],ignore_index=True)
    daily=tr.groupby(['method','seed','day']).agg(J=('J','sum')).reset_index()
    dailymean=daily.groupby(['method','day']).J.mean().unstack('method')
    summary=dailymean.mean().rename('system_J').reset_index()
    rng=np.random.default_rng(6974);contrasts=[]
    for method in dailymean.columns:
        for ref in ['THRESHOLD_PERSIST','DP_PERSIST']:
            diff=(dailymean[method]-dailymean[ref]).to_numpy()
            boot=rng.choice(diff,(1000,len(diff))).mean(axis=1)
            contrasts.append(dict(method=method,reference=ref,delta_J=diff.mean(),low=np.quantile(boot,.025),high=np.quantile(boot,.975)))
    ct=pd.DataFrame(contrasts);runtime=time.perf_counter()-started
    source=list(Path('code/wargame/learning').glob('*.py'))+[Path(__file__)]
    meta=dict(source_sha256={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in source},
        evaluation_status='retrospective; April 11–30 reused in prior studies',
        training='March complete days only',validation='April 1–10',evaluation='April 11–30',
        objective='individual accepted-export operating margin; no overflow charge',failed_days=0)
    for name,df in [('trajectories',tr),('daily',daily),('summary',summary),('contrasts',ct),
        ('training',pd.DataFrame(learning)),('checkpoint_selection',pd.DataFrame(selection))]:
        write_table(df,out/f'{name}.csv',cfg,runtime,**meta)
    report=f'''# Dispatch Improvement and Reinforcement Learning

## Algorithms

The earlier controllers used regression/filter forecasts and threshold-policy
rollouts. This study adds finite-grid battery dynamic programming (DP) and
independent Double DQN. Five owners act simultaneously with private execution.
Each DQN receives only its own SOC, wind, permitted future own wind/prices, and
past inferred aggregate rival requests. DQN_NO_RIVAL masks the last-request and
observation-age fields. It retains the same architecture and training budget.

DP uses {rc['dp_soc_points']} energy grid points and {len(actions)} battery commands.
It optimizes accepted revenue, executed discharge degradation and the same
activity tie-break cost. DP_PERSIST and DP_FIT differ only in the rival forecast.
DQN uses the same commands and feasibility projection, with actual individual
operating margin as reward. Negative-price wind can be curtailed freely.

DQN subtracts an action-independent, own-wind energy-revenue baseline and scales
rewards by 100 times owner nameplate. This changes neither daily policy ranking
nor the monetary evaluation. Episodes reset at midnight; discount is 1. Targets
use online action selection with a separate target network. Training replay
contains March simulated transitions only. All five independent Q functions
train together; execution reveals no contemporaneous rival actions or SOC.

There are {rc['episodes']} training episodes per seed and ablation. Checkpoints
are selected on April 1–10 only. April 11–30 has appeared in prior experiments,
so results below are retrospective evaluation, not a fresh holdout claim.
Hyperparameters are fixed in config/rl.yaml. Seeds: {rc['seeds']}.

## Mean system margin ($/day)

{table(summary)}
## Paired differences ($/day)

Seeds are averaged within day before bootstrapping 20 paired day blocks.
THRESHOLD_PERSIST is the earlier controller; DP_PERSIST is the stronger
same-command-set planning baseline. Intervals use 1,000 draws, seed 6974.

{table(ct)}

## Artifacts

The result directory contains per-owner hourly dispatch, per-seed daily values,
March reward/loss traces, validation checkpoint scores, selected model weights,
source hashes and the effective configuration. Physical battery bounds, wind-only
charging, terminal return and the shared POI limit are checked during every run.
'''
    (out/'report.md').write_text(report)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(8,4),layout='constrained')
    g=ct[ct.reference=='THRESHOLD_PERSIST']
    ax.errorbar(g.delta_J,np.arange(len(g)),xerr=np.vstack([g.delta_J-g.low,g.high-g.delta_J]),fmt='o',capsize=3)
    ax.set_yticks(np.arange(len(g)),g.method);ax.axvline(0,color='gray',lw=.8)
    ax.set_xlabel('System margin change vs threshold persistence ($/day)')
    fig.savefig(out/'comparison.png',dpi=180);plt.close(fig)
    print(summary.to_string(index=False));print('Runtime',runtime,flush=True)

if __name__=='__main__':main()

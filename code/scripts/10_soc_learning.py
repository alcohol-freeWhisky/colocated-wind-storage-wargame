#!/usr/bin/env python3
"""Stage 2: latent rival SOC inference, after simultaneous learning."""
import time
from pathlib import Path
import numpy as np
import pandas as pd
import yaml
from wargame.learning.study import context,save,table
from wargame.learning.experiment import Forecaster
from wargame.learning.simultaneous import run_day
from wargame.learning.soc_filter import SOCFilter


def main():
    if not Path('results/learning_simultaneous/report.md').exists():
        raise RuntimeError('Complete stage 1 before running the SOC comparison')
    started=time.perf_counter();cfg,p,days,candidates,theta,last0,age0,_=context()
    sc=yaml.safe_load(Path('config/soc_learning.yaml').read_text())['soc_learning']
    cfg['soc_learning']=sc;rows=[];paths=[];states=[];byseed=[]
    # Fixed model settings are declared before the test run; no test selection.
    for seed in sc['seeds']:
        for method in sc['treatments']:
            last,age=last0.copy(),age0.copy()
            for day_index,d in enumerate(days[40:]):
                beliefs=None
                if method.startswith('SOC_'):
                    beliefs=[SOCFilter(p,i,candidates,seed+1000*day_index+100*i,
                        particles=sc['particles'],wind_sigma=sc['wind_sigma'],
                        observation_sigma=sc['observation_sigma'],condition=method!='SOC_PRIOR',
                        reset_soc=method=='SOC_RESET',wind_ar=sc['wind_ar'],
                        policy_change_probability=sc['policy_change_probability']) for i in range(5)]
                rs,ps,_,last,age,ss=run_day(d,p,candidates,method,
                    Forecaster(theta,p,cfg['learning']),last,age,beliefs=beliefs)
                for r in rs:r['seed']=seed
                for r in ps:r['seed']=seed
                for r in ss:r['seed']=seed;r['method']=method
                rows+=rs;paths+=ps;states+=ss
            print('Completed SOC study',seed,method,flush=True)
    # Preserve seed-level records; paired-day summaries average seeds first.
    tr=pd.DataFrame(rows);fp=pd.DataFrame(paths)
    output=Path(sc['output']);output.mkdir(parents=True,exist_ok=True)
    from wargame.experiments.io import write_table
    meta=dict(stage='2 SOC inference under simultaneous dispatch',failed_days=0,seeds=sc['seeds'],
        wind_model='own wind capacity factor plus bounded AR(1) latent rival deviations',
        particle_settings=sc,policy_information='own wind/actions/metering only')
    write_table(tr,output/'trajectories_by_seed.csv',cfg,time.perf_counter()-started,**meta)
    write_table(fp,output/'forecast_paths_by_seed.csv',cfg,time.perf_counter()-started,**meta)
    # save() aggregates records into daily system sums: average owner-hour seeds first.
    numeric=[c for c in tr.select_dtypes(include='number') if c not in ['seed','hour','i']]
    averaged=tr.groupby(['method','day','hour','i'])[numeric].mean().reset_index()
    pn=[c for c in fp.select_dtypes(include='number') if c not in ['seed','i','origin','lead']]
    avgpaths=fp.groupby(['method','day','i','origin','lead'])[pn].mean().reset_index()
    s,c=save(output,cfg,averaged.to_dict('records'),avgpaths.to_dict('records'),
        time.perf_counter()-started,meta,states)
    # Error averages must be computed before averaging predictions across seeds.
    fp['error2']=(fp.prediction-fp.actual)**2
    tr['error2']=(tr.forecast-tr.rival_request)**2
    rmse=tr.groupby('method').error2.mean().pow(.5)
    s['rmse_mw']=s.method.map(rmse)
    write_table(s,output/'summary.csv',cfg,time.perf_counter()-started,**meta)
    lead=fp.groupby(['method','lead']).error2.mean().pow(.5).rename('rmse_mw').reset_index()
    write_table(lead,output/'forecast_by_lead.csv',cfg,time.perf_counter()-started,**meta)
    # Replot using seed-level RMSE, not errors of seed-averaged predictions.
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(1,2,figsize=(10,3.5),layout='constrained')
    for method,g in lead.groupby('method'):ax[0].plot(g.lead,g.rmse_mw,label=method)
    ax[0].set(xlabel='Lead (h)',ylabel='Rival request RMSE (MW)');ax[0].legend(fontsize=7,frameon=False)
    ax[1].errorbar(c.delta_system_J,range(len(c)),xerr=np.vstack([c.delta_system_J-c.low,c.high-c.delta_system_J]),fmt='o')
    ax[1].set_yticks(range(len(c)),c.method,fontsize=7);ax[1].axvline(0,color='gray',lw=.8)
    ax[1].set_xlabel('System margin vs persistence ($/day)')
    fig.savefig(output/'comparison.png',dpi=180);plt.close(fig)
    daily=pd.DataFrame(rows).groupby(['method','seed','day']).J.sum().groupby(['method','day']).mean().unstack('method')
    extra=[];rng=np.random.default_rng(6974)
    for reference in ['SOC_PRIOR','SOC_RESET']:
        diff=(daily.SOC_FILTER-daily[reference]).to_numpy()
        b=rng.choice(diff,(1000,len(diff))).mean(axis=1)
        extra.append(dict(method='SOC_FILTER',reference=reference,delta_system_J=diff.mean(),low=np.quantile(b,.025),high=np.quantile(b,.975)))
    extra=pd.DataFrame(extra)
    write_table(extra,output/'soc_contrasts.csv',cfg,time.perf_counter()-started,**meta)
    stat=pd.DataFrame(states)
    scores=stat[stat.hour>0].groupby('method').agg(aggregate_mse=('aggregate_soc_error2','mean'),
        individual_mse=('individual_soc_error2','mean'),ess=('ess','mean')).reset_index()
    scores['aggregate_rmse_mwh']=np.sqrt(scores.pop('aggregate_mse'))
    scores['individual_rmse_mwh']=np.sqrt(scores.pop('individual_mse'))
    write_table(scores,output/'soc_summary.csv',cfg,time.perf_counter()-started,**meta)
    report=f'''# Stage 2: Hidden Rival SOC Inference

## Setup

All five owners act simultaneously. The farm data, battery parameters, shared
connection, actual-revenue objective and terminal controller match stage 1.
Test dates are April 11–30, 2025. Three declared Monte Carlo seeds are used.
Own generation and prices have perfect foresight; rival generation and SOC are
hidden. Each owner sees only its own requests, accepted exports and past history.

The particle state contains rival SOC, wind deviations, and threshold-policy
indices. Initial SOC is known at the prescribed daily reset. Rival wind uses the
owner's wind capacity factor as a proxy plus bounded AR(1) errors. The wind-error
standard deviation is {sc['wind_sigma']}; observation-model error is
{sc['observation_sigma']} times rival nameplate. Each owner has {sc['particles']}
particles. The likelihood uses aggregate request inferred from proportional cuts,
or the upper bound from full acceptance. No rival truth enters filtering.

SOC_PRIOR propagates particles without observation conditioning. SOC_FILTER
conditions on metering and propagates inferred SOC. SOC_RESET applies the same
conditioning but resets rival SOC to 50% each interval, testing the contribution
of retaining a latent energy state. FIT_FROZEN and PERSIST are stage-1 controls.
Filter settings are fixed experiment parameters, not fitted rival telemetry.
Private truth is used only after prediction for scoring.

Particles use a stationary threshold-policy library with 5% interval-wise policy
changes to approximate adaptive opponents. This is a specified inference model;
aggregate observations need not identify individual SOC. Forecast rollouts use
that model rather than private future states. The model includes no reserve
monitor or SOC violations; this study concerns hidden rival storage states.

## Operating and prediction results

System margins are dollars/day, averaged across seeds within each day.
RMSE is computed from individual seed predictions before seed averaging.

{table(s)}
## Paired system margin relative to persistence

Intervals bootstrap the 20 day blocks after seed averaging. Common seeds are
used across particle treatments. The deterministic controls repeat identically.

{table(c)}
## Filter ablations: paired system margin

{table(extra)}

![Forecast and system-margin comparisons](comparison.png)

## SOC estimation (hours 1–23)

The known initial SOC at hour 0 is excluded. Aggregate RMSE scores the sum of
four rival SOC values; individual RMSE averages the four separate errors.

{table(scores)}

The PRIOR and RESET controls distinguish observation conditioning from carrying
SOC forward. Results are conditional on the proxy wind and policy library.
Seed-level trajectories, SOC errors, and forecast paths are saved separately.
'''
    (output/'report.md').write_text(report)
    print(s.to_string(index=False));print(scores.to_string(index=False))

if __name__=='__main__':main()

#!/usr/bin/env python3
"""Run the first deterministic aggregate-forecast comparison."""
from __future__ import annotations
import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import time
import numpy as np
import pandas as pd
from wargame.experiments.io import load_config, assess_complete_days, write_table
from wargame.model.env import build_episode
from wargame.learning.experiment import (Day, Plant, policies, simulate, fit_models, Forecaster)


def state():
    return np.full(5,.5),np.full(5,168.)


def run_focal(task):
    focal,days,plant,reference,candidates,theta,config,initial_last,initial_age=task
    out=[]
    for method in config['treatments']:
        last,age=initial_last.copy(),initial_age.copy()
        for day in days:
            rows,last,age,_=simulate(day,plant,reference,last,age,focal=focal,method=method,
                candidates=candidates,forecaster=Forecaster(theta,plant,config))
            out.extend(rows)
        print(f'Completed focal={plant.names[focal]} method={method} days={len(days)}',flush=True)
    return out


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--config',default='config/base.yaml')
    parser.add_argument('--scenario',default='config/learning.yaml')
    parser.add_argument('--workers',type=int,default=4)
    args=parser.parse_args(); started=time.perf_counter()
    cfg=load_config(Path(args.config),Path(args.scenario)); lc=cfg['learning']
    names=cfg['data']['primary_agents']; dates,skipped=assess_complete_days(cfg,names)
    if len(dates)!=sum(lc[k] for k in ['train_days','validation_days','test_days']):
        raise ValueError('Configured split must cover all complete days')
    episodes=[build_episode(d,names,cfg) for d in dates]; ep=episodes[0]
    plant=Plant(names,ep.nameplates,np.array([a.battery.P for a in ep.agents]),
        np.array([a.battery.E for a in ep.agents]),ep.K,cfg['battery']['eta_c'],
        cfg['battery']['eta_d'],cfg['battery']['c_deg_usd_per_mwh'],
        cfg['battery']['eps_tiebreak_usd_per_mwh'])
    days=[Day(str(e.day),e.W,e.pi_RT) for e in episodes]
    n=lc['train_days']; nv=lc['validation_days']
    train,val,test=days[:n],days[n:n+nv],days[n+nv:]
    candidates=policies(np.concatenate([d.price for d in train]),lc)
    # Fixed policy selection, without current rival states or actions.
    validation=[]
    for k,ref in enumerate(candidates):
        last,age=state(); score=0
        for day in val:
            rows,last,age,_=simulate(day,plant,ref,last,age)
            score+=sum(r['J'] for r in rows)
        validation.append(dict(candidate=k,p_low=ref[0],p_high=ref[1],beta=ref[2],J=score))
    ref_index=int(np.argmax([r['J'] for r in validation])); reference=candidates[ref_index]
    print(f'Selected fixed reference: {reference.tolist()}',flush=True)
    train_samples=[]; val_samples=[]; pilot=[];last,age=state()
    for k,day in enumerate(train+val):
        rows,last,age,samples=simulate(day,plant,reference,last,age,collect=True)
        pilot.extend(rows)
        if k<n: train_samples.extend(samples)
        else: val_samples.extend(samples)
    test_last,test_age=last.copy(),age.copy()
    fitted=[]; fit_scores=[]
    for ridge in lc['ridge_grid']:
        theta=fit_models(train_samples,plant,ridge,lc['minimum_samples'])
        losses=[]
        for sample in val_samples:
            b=theta[sample['i'],sample['lead']]
            pred=sample['x'][6] if np.isnan(b).any() else sample['x']@b
            err=pred-sample['label']
            losses.append(err**2 if sample['exact'] else max(err,0)**2)
        fit_scores.append(dict(ridge=ridge,validation_censored_mse=float(np.mean(losses))))
        fitted.append(theta)
        print(f'Fitted ridge={ridge}: validation loss={np.mean(losses):.6g}',flush=True)
    best=int(np.argmin([r['validation_censored_mse'] for r in fit_scores])); theta=fitted[best]
    tasks=[(i,test,plant,reference,candidates,theta,lc,test_last,test_age) for i in range(5)]
    if args.workers==1: results=[run_focal(t) for t in tasks]
    else:
        with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as pool:
            results=list(pool.map(run_focal,tasks))
    trajectory=pd.DataFrame([r for result in results for r in result])
    paths=[]
    for (method,fi,date), group in trajectory.groupby(['method','focal','day']):
        own=group[group.i==fi].sort_values('hour')
        actual=own.rival_request.to_numpy()
        for row in own.itertuples(index=False):
            if row.forecast_path is not None:
                for lead,pred in enumerate(row.forecast_path):
                    paths.append(dict(method=method,focal=fi,day=date,origin=row.hour,lead=lead,
                        prediction=pred,actual=actual[row.hour+lead]))
    trajectory=trajectory.drop(columns='forecast_path')
    forecast_paths=pd.DataFrame(paths)
    forecast_paths['squared_error']=(forecast_paths.prediction-forecast_paths.actual)**2
    lead_scores=forecast_paths.groupby(['method','lead']).agg(mse=('squared_error','mean'),
        observations=('actual','size')).reset_index()
    lead_scores['rmse_mw']=np.sqrt(lead_scores.pop('mse'))
    focal=trajectory[trajectory.i==trajectory.focal].copy()
    focal['error2']=(focal.forecast-focal.rival_request)**2
    focal.loc[~focal.forecast_used,'error2']=np.nan
    focal['reject']=focal.q_requested-focal.q
    focal['throughput']=focal.c+focal.d
    focal['observed_error2']=focal.error2.where(focal.exact)
    daily=focal.groupby(['method','focal','day']).agg(J=('J','sum'),
        overflow=('overflow','sum'),rejected=('reject','sum'),throughput=('throughput','sum'),
        forecast_mse=('error2','mean'),observable_mse=('observed_error2','mean'),
        exact_hours=('exact','sum')).reset_index()
    total=trajectory.groupby(['method','focal','day']).J.sum().rename('system_J').reset_index()
    daily=daily.merge(total,on=['method','focal','day'])
    summary=daily.groupby('method').agg(J=('J','mean'),system_J=('system_J','mean'),
        attempted_overflow_mwh=('overflow','mean'),rejected_mwh=('rejected','mean'),
        throughput_mwh=('throughput','mean'),forecast_mse=('forecast_mse','mean'),
        exact_hours=('exact_hours','mean')).reset_index()
    summary['forecast_rmse_mw']=np.sqrt(summary.pop('forecast_mse'))
    paired=daily.groupby(['method','day']).J.mean().unstack('method')
    rng=np.random.default_rng(cfg['seed']); contrasts=[]
    for method in lc['treatments']:
        diff=(paired[method]-paired.PERSIST).to_numpy()
        means=np.mean(rng.choice(diff,size=(lc['bootstrap_samples'],len(diff)),replace=True),axis=1)
        contrasts.append(dict(method=method,reference='PERSIST',mean_delta_J=diff.mean(),
            ci_low=np.quantile(means,.025),ci_high=np.quantile(means,.975),days=len(diff)))
    output=Path(lc['output']);output.mkdir(parents=True,exist_ok=True)
    elapsed=time.perf_counter()-started
    source_files=list(Path('code/wargame/learning').glob('*.py'))+[Path(__file__)]
    source_hash={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files}
    meta=dict(split={'train':[d.date for d in train],'validation':[d.date for d in val],
        'test':[d.date for d in test]},source_sha256=source_hash,objective='realized revenue; no overflow charge',
        fitted_mode='frozen training coefficients; treatment-specific observable test histories',
        selected_reference=reference.tolist(),selected_ridge=lc['ridge_grid'][best],
        candidates=len(candidates),failed_days=0)
    for name,frame in [('trajectories',trajectory),('daily',daily),('summary',summary),
        ('forecast_paths',forecast_paths),('forecast_by_lead',lead_scores),
        ('contrasts',pd.DataFrame(contrasts)),('reference_selection',pd.DataFrame(validation)),
        ('ridge_selection',pd.DataFrame(fit_scores)),('training_observations',pd.DataFrame(pilot)),
        ('skipped_days',skipped)]:
        write_table(frame,output/f'{name}.csv',cfg,elapsed,**meta)
    np.savez(output/'fitted_model.npz',theta=theta,candidates=candidates,reference=reference)
    write_report(output,summary,pd.DataFrame(contrasts),meta,elapsed)
    plot_results(output,lead_scores,pd.DataFrame(contrasts))
    print(summary.to_string(index=False));print(f'Runtime {elapsed:.1f}s; output={output}',flush=True)


def write_report(output,summary,contrasts,meta,elapsed):
    def table(df):
        return '| '+' | '.join(df.columns)+' |\n| '+' | '.join(['---']*len(df.columns))+' |\n'+''.join(
            '| '+' | '.join(f'{x:.3f}' if isinstance(x,float) else str(x) for x in row)+' |\n'
            for row in df.itertuples(index=False,name=None))
    fitrow=contrasts.set_index('method').loc['FIT']
    fitrmse=summary.set_index('method').loc['FIT','forecast_rmse_mw']
    persistrmse=summary.set_index('method').loc['PERSIST','forecast_rmse_mw']
    text=f'''# Aggregate Rival Forecasting: First Simulation

## Design

Five focal-owner rotations, four fixed persistence-policy opponents, 20 test days,
and four focal treatments: ZERO, PERSIST, FIT, ORACLE. All use the same candidate
controller, wind-only batteries, actual accepted-export revenue, degradation,
and terminal-return requirement. Overflow charges are zero. Own wind and prices
have perfect foresight. Coefficients are fitted on the first 30 complete days;
the next 10 select the reference policy and ridge parameter. Test dates are
April 11–30, 2025. The physical initial SOC resets daily; observable forecast
histories continue across days. All treatments start from the same pilot history.

The controller projects actions onto terminal-reachable SOC before realization:

$$
s_{{i,t+1}}^{{plan}}\\ge
\\left[s_{{i0}}-\\eta_c\\sum_{{u=t+1}}^{{23}}\\min(P_i,W_{{iu}})\\right]_+.
$$

This common adjustment preserves the original return requirement. It is an
implementation refinement to the threshold controller in model_formulation.md.
The candidate score uses the original activity cost; reported J excludes it.

Current actions are simultaneous. Only own request and acceptance update the
past aggregate estimate. Binding positive exports identify past rival total
requests; nonbinding observations supply an upper bound. Censored regression
uses both. FIT coefficients remain frozen during testing. The initial forecast
is 0.5 times total rival nameplate, and the initial observation age is 168 hours.

ORACLE evaluates candidate-conditional opponent trajectories with their private
wind and SOC, then implements its selected first action. Its forecast RMSE is
undefined because it uses simulator rollouts rather than an observable predictor.
The first run covers deterministic forecasts (M=1); scenario sampling and
simultaneous adaptation are separate experiments.

Selected reference [low threshold, high threshold, beta]: {meta['selected_reference']}.
Selected ridge: {meta['selected_ridge']}. Candidates: {meta['candidates']}.
Runtime: {elapsed:.1f} seconds. Physical, wind-only, simultaneous-operation, and
terminal-return checks passed for every executed interval/day.

## Mean daily results

J is the focal owner's operating margin in dollars/day. system_J sums all five
owners within that rotation. Forecast errors use evaluator-only private truth;
that truth never enters ZERO, PERSIST, or FIT actions. exact_hours counts hours
where own metering identifies rival total requests.

{table(summary)}
## Paired focal margin relative to persistence

Average across five focal rotations within each day, then bootstrap the 20 day
blocks (1,000 draws, seed 6974). Intervals are descriptive paired-day bootstrap
intervals for this test window.

{table(contrasts)}
## Interpretation

The fitted current-hour predictor reduces RMSE from {persistrmse:.2f} MW to
{fitrmse:.2f} MW. Its mean focal operating-margin difference from persistence is
{fitrow['mean_delta_J']:.2f} dollars/day, with a paired-day interval of
[{fitrow['ci_low']:.2f}, {fitrow['ci_high']:.2f}]. This test does not establish a
positive economic gain from the fitted model. The ideal-information controller
also yields a small mean improvement within this threshold-policy class.

The fixed reference selected beta=0 and a high discharge threshold. These
opponents do not strategically respond to congestion forecasts, although their
battery states and later requests respond physically to export curtailment.
Conclusions apply to this reference behavior, candidate policy class, and test
window. Joint adaptive operation remains a separate comparison.

![Forecast error and operating-margin contrasts](comparison.png)

## Artifacts

- trajectories.csv: every owner's hourly request, acceptance, SOC, actions,
  forecasts, and observation availability for each focal treatment.
- daily.csv: focal and system outcomes by day and rotation.
- forecast_paths.csv and forecast_by_lead.csv: forecasts made at each origin and
  evaluator-only errors against subsequently executed rival requests, by horizon.
- reference_selection.csv and ridge_selection.csv: validation selections.
- training_observations.csv: common pilot histories for training and validation.
- fitted_model.npz: coefficients and candidate controllers.
- CSV metadata: exact splits, source hashes, objective and configuration hash.
'''
    (output/'report.md').write_text(text)


def plot_results(output, lead_scores, contrasts):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(10,3.7),layout='constrained')
    for method,g in lead_scores.groupby('method'):
        axes[0].plot(g.lead,g.rmse_mw,label=method)
    axes[0].set(xlabel='Forecast lead (hours)',ylabel='Aggregate request RMSE (MW)')
    axes[0].legend(frameon=False)
    c=contrasts[contrasts.method!='PERSIST'].reset_index(drop=True)
    axes[1].errorbar(c.mean_delta_J,range(len(c)),
        xerr=np.vstack([c.mean_delta_J-c.ci_low,c.ci_high-c.mean_delta_J]),fmt='o',capsize=4)
    axes[1].set_yticks(range(len(c)),c.method)
    axes[1].axvline(0,color='gray',linewidth=.8)
    axes[1].set(xlabel='Focal margin change vs persistence ($/day)')
    for ax in axes:
        ax.spines[['top','right']].set_visible(False)
    fig.savefig(output/'comparison.png',dpi=180)
    plt.close(fig)


if __name__=='__main__': main()

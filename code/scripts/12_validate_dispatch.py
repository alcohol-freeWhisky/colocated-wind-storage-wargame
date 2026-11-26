#!/usr/bin/env python3
"""Validation-only algorithm ranking and paired information ablations."""
import hashlib,json,time
from pathlib import Path
import numpy as np
import pandas as pd
import yaml
from wargame.learning.study import context,table
from wargame.learning.experiment import Forecaster,simulate
from wargame.learning.control import DQN
from wargame.learning.simultaneous import run_day
from wargame.experiments.io import write_table
from importlib.util import spec_from_file_location,module_from_spec


def main():
    start=time.perf_counter();cfg,p,days,candidates,theta,_,_,_=context()
    rc=yaml.safe_load(Path('config/rl.yaml').read_text())['rl'];cfg['rl']=rc
    spec=spec_from_file_location('rl_runner','code/scripts/11_rl_dispatch.py')
    runner=module_from_spec(spec);spec.loader.exec_module(runner)
    out=Path(rc['output']);actions=np.asarray(rc['actions'])
    with np.load('results/learning/fitted_model.npz') as f:reference=f['reference']
    last=np.full(5,.5);age=np.full(5,168.)
    for d in days[:30]:_,last,age,_=simulate(d,p,reference,last,age)
    validation=[]
    for method,fc in [('DP_PERSIST',None),('DP_FIT',Forecaster(theta,p,cfg['learning']))]:
        rows=runner.evaluate(days[30:40],p,actions,method,last.copy(),age.copy(),
            forecaster=fc,points=rc['dp_soc_points'])
        validation.append(dict(method=method,seed=-1,validation_J=sum(r['J'] for r in rows)/10))
    for method in ['DQN_HISTORY','DQN_NO_RIVAL']:
        for seed in rc['seeds']:
            model=DQN(rc,seed);model.load(out/f'{method.lower()}_{seed}.npz')
            rows=runner.evaluate(days[30:40],p,actions,method,last.copy(),age.copy(),
                model=model,blind=method=='DQN_NO_RIVAL')
            validation.append(dict(method=method,seed=seed,validation_J=sum(r['J'] for r in rows)/10))
    l,a=last.copy(),age.copy();rs=[]
    for day in days[30:40]:
        r,_,_,l,a,_=run_day(day,p,candidates,'PERSIST',None,l,a);rs+=r
    validation.append(dict(method='THRESHOLD_PERSIST',seed=-1,validation_J=sum(r['J'] for r in rs)/10))
    vf=pd.DataFrame(validation);ranking=vf.groupby('method').validation_J.mean().sort_values(ascending=False).reset_index()
    daily=pd.read_csv(out/'daily.csv').groupby(['method','day']).J.mean().unstack('method')
    rng=np.random.default_rng(6974);pairs=[]
    for method,reference in [('DQN_HISTORY','DQN_NO_RIVAL'),('DP_FIT','DP_PERSIST')]:
        diff=(daily[method]-daily[reference]).to_numpy();b=rng.choice(diff,(1000,len(diff))).mean(axis=1)
        pairs.append(dict(method=method,reference=reference,delta_J=diff.mean(),low=np.quantile(b,.025),high=np.quantile(b,.975)))
    pairs=pd.DataFrame(pairs)
    meta=dict(source_sha256={str(Path(__file__)):hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
        selection_data='April 1–10 only',evaluation_status='April 11–30 retrospective',
        selected_algorithm=ranking.iloc[0]['method'])
    for name,df in [('validation_policies',vf),('validation_ranking',ranking),('information_contrasts',pairs)]:
        write_table(df,out/f'{name}.csv',cfg,time.perf_counter()-start,**meta)
    summary=pd.read_csv(out/'summary.csv').set_index('method').system_J
    base=summary.THRESHOLD_PERSIST
    text=f'''\n## Validation-only algorithm ranking

Selected models are evaluated on April 1–10 with a training-only initial history.
Algorithm-family values average the three selected checkpoints where applicable.
The highest validation value selects {ranking.iloc[0]['method']}.

{table(ranking)}
## Value of rival information

These contrasts retain the same battery command set within each pair.

{table(pairs)}
## Findings

The previous threshold controller earns {base:.2f} dollars/system-day in the
retrospective window. DP with fitted forecasts earns {summary.DP_FIT:.2f},
a change of {100*(summary.DP_FIT/base-1):.2f}%. DQN with rival history earns
{summary.DQN_HISTORY:.2f}, a change of {100*(summary.DQN_HISTORY/base-1):.2f}%.

The dominant measured improvement comes from battery control. The information
contrasts above do not isolate a clear additional economic gain when their day
intervals include zero. DQN improves on the old threshold controller but does not
outperform the DP baseline at this training budget. Validation ranking supports
using the DP controller as the next working baseline.

![Retrospective operating-margin differences](comparison.png)

## Reproduction

```bash
PYTHONPATH=code OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python code/scripts/11_rl_dispatch.py
PYTHONPATH=code OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python code/scripts/12_validate_dispatch.py
```
'''
    report=out/'report.md';body=report.read_text().split('\n## Validation-only algorithm ranking')[0]
    report.write_text(body+text)
    print(ranking.to_string(index=False));print(pairs.to_string(index=False))

if __name__=='__main__':main()

#!/usr/bin/env python3
"""Stage 1: five simultaneous forecasting owners; frozen and online regression."""
import time
from pathlib import Path
import numpy as np
from wargame.learning.study import context,save,table
from wargame.learning.experiment import Forecaster,fit_models
from wargame.learning.simultaneous import run_day


def main():
    start=time.perf_counter();cfg,p,days,candidates,theta,last0,age0,initial=context()
    lc=cfg['learning'];allrows=[];allpaths=[];updates=[]
    import json
    ridge=json.loads(Path('results/learning/summary.meta.json').read_text())['selected_ridge']
    for method in ['ZERO','PERSIST','FIT_FROZEN','FIT_ONLINE']:
        last,age=last0.copy(),age0.copy();training=list(initial);model=theta.copy()
        for d in days[40:]:
            if method=='FIT_ONLINE':
                model=fit_models(training,p,ridge,lc['minimum_samples'])
                assert max(x['day'] for x in training)<d.date
                updates.append(dict(method=method,decision_day=d.date,last_label_day=max(x['day'] for x in training),samples=len(training)))
            rows,paths,samples,last,age,_=run_day(d,p,candidates,method,Forecaster(model,p,lc),last,age)
            allrows+=rows;allpaths+=paths
            if method=='FIT_ONLINE':training+=samples
        print('Completed simultaneous',method,flush=True)
    meta=dict(stage='1 simultaneous aggregate learning',fit_updates=updates,
        primary_split='March training; April 1–10 validation; April 11–30 test',failed_days=0)
    s,c=save('results/learning_simultaneous',cfg,allrows,allpaths,time.perf_counter()-start,meta)
    report=f'''# Stage 1: Simultaneous Aggregate Learning

All five owners choose dispatch simultaneously from their own pre-action histories.
Own wind and prices have perfect foresight. Batteries, POI, terminal return,
actual-revenue objective and candidate controller match the focal-owner study.
No overflow penalty is charged. No current rival request or SOC enters a policy.

ZERO and PERSIST use fixed forecasting rules. FIT_FROZEN uses the original
training coefficients. FIT_ONLINE refits the censored regression once per day,
using the common training history plus its own completed test-day observations.
Current and future test-day labels are excluded. Validation selects the ridge
and threshold grid before testing. All methods start with the same pilot history.
SOC resets daily; observable histories carry forward. Each method runs 20 test
days, giving 80 joint operating days and 9,600 owner-hour observations.

## Results

{table(s)}
## Paired system margin versus persistence

The unit is dollars per system-day. Intervals bootstrap 20 paired day blocks,
1,000 draws, seed 6974. These are adaptive dispatch comparisons; the output does
not certify a dynamic-game equilibrium.

{table(c)}
![Forecast and payoff comparisons](comparison.png)

Hourly actions, forecast paths by lead, daily outcomes, fitted-update timestamps,
and source hashes are stored with the result tables. The next study separately
adds a hidden-SOC filter.
'''
    Path('results/learning_simultaneous/report.md').write_text(report)
    print(s.to_string(index=False));print(c.to_string(index=False))

if __name__=='__main__':main()

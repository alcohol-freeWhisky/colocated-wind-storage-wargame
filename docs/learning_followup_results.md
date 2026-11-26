# Sequential Learning Studies

## 1. Five owners adapting simultaneously

All five owners select hourly actions from their own observation histories.
The study compares fixed forecast rules, frozen fitted coefficients, and daily
online refitting. Test days are April 11–30, 2025; the preceding 30/10 complete
days supply training and validation. No current rival requests or SOC are public.

| Forecast | Mean system margin ($/day) | Difference from persistence ($/day) | Paired 95% interval |
|---|---:|---:|---|
| ZERO | 64,634.66 | -526.68 | [-828.13, -247.33] |
| PERSIST | 65,161.34 | 0 | — |
| FIT_FROZEN | 65,014.50 | -146.84 | [-300.60, -17.19] |
| FIT_ONLINE | 65,069.89 | -91.46 | [-219.83, 17.95] |

Fitted forecasts reduce request-prediction error. The fitted controllers do not
improve average system margin over persistence in this test. Online updating
recovers part of the frozen model's margin loss. The sample comprises 80 joint
operating days and 9,600 owner-hour records.

[Stage 1 report](../results/learning_simultaneous/report.md)

## 2. Hidden rival SOC inference

The second study adds a particle model of rival SOC, wind and operating policies.
Each owner uses only its own wind and metering. All five owners adapt, using the
same physical system and threshold-controller class as stage 1. Three declared
Monte Carlo seeds give 300 joint operating days and 36,000 owner-hour records.

| Forecast | Mean system margin ($/day) | Current request RMSE (MW) |
|---|---:|---:|
| PERSIST | 65,161.34 | 71.39 |
| FIT_FROZEN | 65,014.50 | 39.39 |
| SOC_PRIOR | 64,740.73 | 61.58 |
| SOC_FILTER | 64,963.35 | 31.06 |
| SOC_RESET | 65,040.41 | 30.26 |

SOC_PRIOR propagates latent states without conditioning on metering. SOC_FILTER
uses the observed aggregate request or upper bound to update particle weights.
SOC_RESET performs that conditioning but resets modeled rival SOC to 50% each
interval.

| SOC_FILTER comparison | Difference in system margin ($/day) | Paired 95% interval |
|---|---:|---|
| Versus SOC_PRIOR | +222.62 | [104.27, 366.67] |
| Versus SOC_RESET | -77.06 | [-163.83, -2.94] |
| Versus PERSIST | -198.00 | [-451.94, 15.21] |

Conditioning on observations improves on the unconditioned model. Carrying
inferred SOC forward does not improve the controller over the reset ablation.
Aggregate rival SOC RMSE improves from 29.21 MWh under the prior to 27.30 MWh
under filtering; individual-rival SOC RMSE increases from 8.87 to 9.39 MWh.
The aggregate observations provide limited identification of individual storage
states in this proxy model.

Intervals resample 20 paired day blocks, after averaging the three seeds within
each day. Results concern the specified policy library and wind proxy. They do
not establish a benefit from more complex SOC inference over simple forecasting.

[Stage 2 report](../results/learning_soc/report.md)

## Reproduction

```bash
PYTHONPATH=code OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python code/scripts/09_simultaneous_learning.py
PYTHONPATH=code OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python code/scripts/10_soc_learning.py
PYTHONPATH=code .venv/bin/python -m pytest -q
```

The physical and information checks cover wind-only charging, battery bounds,
terminal return, simultaneous decisions, POI acceptance, delayed online labels,
and separation of private truth from SOC inference. The full suite passes 38 tests.

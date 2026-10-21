Implemented Task B end to end.

Created:

- Physical model and episode loading: [physics.py](/Users/ziqiwei/6.974_wargame/code/wargame/model/physics.py), [env.py](/Users/ziqiwei/6.974_wargame/code/wargame/model/env.py)
- Central, agent, game, MPC, and realization solvers under [solvers](/Users/ziqiwei/6.974_wargame/code/wargame/solvers)
- Metrics and regime runner under [experiments](/Users/ziqiwei/6.974_wargame/code/wargame/experiments)
- Synthetic tests: [test_physics.py](/Users/ziqiwei/6.974_wargame/tests/test_physics.py), [test_solvers.py](/Users/ziqiwei/6.974_wargame/tests/test_solvers.py), [test_realize.py](/Users/ziqiwei/6.974_wargame/tests/test_realize.py)
- Defensive realization edge case documented in [DEVIATIONS.md](/Users/ziqiwei/6.974_wargame/docs/DEVIATIONS.md)

Validation:

```bash
.venv/bin/python -m pytest tests/ -q
```

Result: `16 passed` in 2.27 seconds.

Performance:

- Synthetic N=5, T=24, all six regimes: 1.91 seconds
- Processed-data N=5, T=24 episode: 1.93 seconds
- All realized exports remained within `K + 1e-6`.

Not run: the complete 61-day sensitivity grids.
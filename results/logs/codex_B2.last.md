Implemented both targeted solver changes. No new files or DESIGN deviations were needed.

### Verification

Full offline suite:

```text
.venv/bin/python -m pytest tests/ -q
19 passed, 3 warnings in 3.93s
```

The warnings are CVXPY’s existing SCIPY canonicalization fallback.

Real Anchor episode, original implementation:

| Regime | System profit ($) | Under-delivery (MWh) | Overflow hours | Simultaneous c/d hours |
|---|---:|---:|---:|---:|
| R1 | 48,000.403 | 0.000 | 0 | 0 |
| R2 | 47,774.872 | 0.084 | 4 | 0 |
| R3a | 47,954.953 | 0.000 | 0 | 15 |
| R3b | 47,954.953 | 0.000 | 0 | 15 |
| R4a | 28,636.020 | 78.391 | 0 | 0 |
| R4b | 28,655.208 | 78.391 | 0 | 0 |

Final implementation:

| Regime | System profit ($) | Under-delivery (MWh) | Overflow hours | Simultaneous c/d hours |
|---|---:|---:|---:|---:|
| R1 | 48,000.403 | 0.000 | 0 | 0 |
| R2 | 47,774.872 | 0.084 | 4 | 0 |
| R3a | 47,958.730 | 0.000 | 0 | 0 |
| R3b | 47,958.711 | 0.000 | 0 | 0 |
| R4a | 47,705.863 | 0.000 | 0 | 0 |
| R4b | 47,701.049 | 0.000 | 0 | 0 |
| R4a_f | 28,636.020 | 78.391 | 0 | 0 |
| R4b_f | 28,655.208 | 78.391 | 0 | 0 |

The old R4 results are reproduced exactly by the new `_f` regimes. In a controlled epsilon-only comparison, the maximum profit change was **0.00788%**, below the requested 0.01%.

| Gap | Before | After |
|---|---:|---:|
| strategic_gap | 225.531 | 225.531 |
| info_gap | 19,138.852 | 69.010 |
| signal_value | -19.187 | 4.813 |
| forecast_gap | — | 19,069.843 |
| PoA | 1.004721 | 1.004721 |

### Modified files

- MPC information controls: [mpc.py](/Users/ziqiwei/6.974_wargame/code/wargame/solvers/mpc.py:12)
- LP tie-breaks: [central.py](/Users/ziqiwei/6.974_wargame/code/wargame/solvers/central.py:105), [agent_lp.py](/Users/ziqiwei/6.974_wargame/code/wargame/solvers/agent_lp.py:112)
- Damped-game cycle canonicalization: [game.py](/Users/ziqiwei/6.974_wargame/code/wargame/solvers/game.py:54)
- Eight-regime execution and gaps: [run_episode.py](/Users/ziqiwei/6.974_wargame/code/wargame/experiments/run_episode.py:36), [metrics.py](/Users/ziqiwei/6.974_wargame/code/wargame/experiments/metrics.py:79)
- Defaults and documentation: [base.yaml](/Users/ziqiwei/6.974_wargame/config/base.yaml:35), [DESIGN.md](/Users/ziqiwei/6.974_wargame/docs/DESIGN.md:82)
- Synthetic coverage: [test_solvers.py](/Users/ziqiwei/6.974_wargame/tests/test_solvers.py:74)

Run using `run_all_regimes(build_episode(...), cfg)` or the pytest command above. Nothing remains unverified.
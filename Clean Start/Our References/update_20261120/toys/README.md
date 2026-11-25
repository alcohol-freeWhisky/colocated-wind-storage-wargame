# Toy scripts (run offline, no data, no internet)

Each script is short, prints its own explanation, and runs in under 20 seconds. They need only **numpy**; **matplotlib** is optional (for the figures).

```bash
cd "Clean Start/Our References/update_20261120/toys"
python toy01_two_owners.py
python toy02_lying_rule.py
python toy03_rules_synthetic_wind.py
python toy04_learning_vs_equilibrium.py
python toy05_battery_basics.py
```

Change the numbers in the block marked `numbers you can change` at the top of each file, and run again.

| Script | Question it answers | What you should see | Proposal section |
|---|---|---|---|
| `toy01_two_owners.py` | Does an owner gain by over-reporting? What are the equilibria? | Example B table. Truth is **not** an equilibrium. In all equilibria owner 1 reports the cap and owner 2 reports 8–10 MW. | 5.1, 5.2 |
| `toy02_lying_rule.py` | When does lying stop paying? | The rule \(\alpha f \ge v K (Q - a_i)/Q^2\) agrees with brute force in 3000 of 3000 random cases. A table of fine vs. smallest inspection probability. | 5.3 |
| `toy03_rules_synthetic_wind.py` | Which sharing rule loses least, and when? | Fixed shares (= everyone lies) lose up to ~19% when wind is unrelated and 0% when identical. Meter feedback loses less here, but it depends strongly on wind persisting hour to hour (set `PERSISTENCE = 0.0` to see it fail). | 6.1, 6.2, Q4 |
| `toy04_learning_vs_equilibrium.py` | Do learning owners (EXP3) reach the equilibrium? | No fine: equilibrium = all "cap"; learners lie a lot. Fine ≥ 1×: equilibrium = all truth; learners mostly tell the truth but keep some small lies. | 6.3, 6.4 |
| `toy05_battery_basics.py` | Where does the battery enter? | How available power = wind + what the battery can discharge, under a fixed battery rule; stored vs. spilled wind; Example A payoff table (both store, $95 instead of $115). | 4.3, App. A |

`toy_common.py` holds the shared pieces: the pro-rata rule, the meter-feedback fill, and the synthetic wind generator. The generator follows Andoni et al. (2017), `sources/04`, p. 7, plus our hour-to-hour persistence.

## Notes

- **Synthetic wind is not real data.** For the real-data results (ERCOT, Anchor Wind), run `../sims/simplified_sims.py` from the repository root. It needs the repository's `data/processed` files, which are already on your disk.
- **Toy numbers differ from the real-data numbers.** The toys show the **direction** of each effect and let you test ideas quickly. The proposal's numbers come from `sims/`.
- **Learning is slow** in toy 4. It takes tens of thousands of simulated days. A bigger fine also makes EXP3 slower, because rewards are scaled to [0, 1] using the worst-case fine. This is a known property of EXP3, not a bug.

## Exercises for an offline afternoon

1. In `toy01`, set `a = [8, 2]`. Is lying worth more or less per MW for the smaller owner? (Hint: the formula in toy02. With 8 and 4 it is 0.50 MWh per MW; with 8 and 2 it is 0.72.) Then try `a = [8, 1]`: total power equals K, so owner 2 already sends all its 1 MW; a bigger report cannot help it and only wastes owner 1's capacity.
2. In `toy02`, find the fine that makes 20% inspections enough for Example B.
3. In `toy03`, change `KAPPA` to 0.4 (a stress day). Which rule suffers most?
4. In `toy04`, set `FINES = [0.3, 0.6]`. Is there a fine where the equilibrium is a "small lie"?
5. In `toy05`, give the battery more energy `E`. How much less wind is spilled?

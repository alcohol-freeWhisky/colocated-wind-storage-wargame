# Decision Log and Reproduction

*Companion to "Wargame Project - Simplified Proposal.md". It records who suggested each modeling choice and what we decided, so the main document can stay short.*

## 1. Decisions: independent reviewer, Codex, and our final choice

| Topic | Independent reviewer | Codex | **Our decision** |
|---|---|---|---|
| Central game | Reporting + inspection | Agrees | **Reporting + inspection.** Battery timing is an extension. |
| What is reported | Three options, choose one | Committed export request, fixed battery behavior | **Committed request; truth = available power under a fixed battery rule** (Proposal 4.4) |
| Equilibrium claim | Asks for one | "Cap" is weakly dominant and always an equilibrium, but not unique | **Stated with the multiplicity** (Proposal 5.2) |
| Harm | Separate transfer and waste | Agrees | **Both measured.** On real data, transfers are large and waste is small (Proposal 6.1). |
| Meter feedback (R6) | Mentions reallocation | "Essential benchmark; may beat report rules" | **Included and shown honestly** |
| Fine definition | Flat $200 in the example | Inconsistent with "per MW" | **Per MWh over-reported everywhere** |
| Negative prices | Not discussed | Breaks the dominance claim | **Assumption A2, with the 38% figure** |
| "Only inspection can detect" | - | Overstated | **Reworded:** the meter alone cannot detect the best lie |
| Gaussian screening, theorems | Level 3 | Later | **Postponed.** The targeted checker uses real forecast errors instead. |
| Game results without batteries | - | Round 2: biggest issue | **Agreed.** Labeled (Proposal 6, scope note); battery game is task 1. |
| Stress claim | - | Round 2: needed inspection rate does not rise | **Agreed and corrected** (Proposal 6.5) |
| Learning reward scaling | - | Round 2: rewards were not bounded in [0, 1] | **Fixed** and re-run; conclusions unchanged, learning slower |
| "Learners reach the equilibria" | - | Rounds 2–3: overclaim | **Softened** to "in our runs" |
| ERCOT HSL / CAISO wording | - | Rounds 2–3: narrow the claims | **Narrowed** (Proposal 2.1) |
| Literature section (round 3, P1) | - | Modify: "only number" is too strong | **Added 2.3** with "metered output does not show curtailed potential" |
| CAISO 67/33 example (P2) | - | Modify: an example, not proof | **Used as an example of R1** |
| "Game in one box" (P3) | - | Agree | **Added 4.0** |
| R6 and wind persistence (P4) | - | Modify: toy-specific; gaming R6 is plausible, not shown | **Stated as toy result + analogy** |
| Checker realism (P5) | - | Modify: screening is imperfect | **Added to 4.7 as imperfect screening** |
| Concision (P6) | - | Agree | **This file created**; glossary absorbs old Section 3.3 |
| Free reports vs. paid bids (P7) | - | Modify: all-cap is one equilibrium | **Added to 5.2 with that wording** |
| Numerical check of the rule (P8) | - | Agree: a check, not a proof | **Added to 5.3** |
| Battery "plan" (round 3) | - | The battery reacts to the share, so it is a rule, not a fixed schedule | **Renamed "fixed battery rule" everywhere** |
| Toy README exercise (round 3) | - | Claimed owner 2 can gain with a = (8, 1), K = 9 | **Kept our version.** Owner 2 already sends all its 1 MW, so it cannot gain (checked with toy01). |

## 2. Reproduction

Real-data results (from the repository root; about 1 minute):

```bash
python "Clean Start/Our References/update_20261120/sims/simplified_sims.py"
```

This writes all figures to `figures/` and prints every number in the proposal, except the averages quoted from Workshop 1. The printed output is saved in `sims/simplified_sims_output.txt`.

Toy scripts (no data, numpy only):

```bash
cd "Clean Start/Our References/update_20261120/toys" && python toy01_two_owners.py
```

See `toys/README.md` for all five toys.

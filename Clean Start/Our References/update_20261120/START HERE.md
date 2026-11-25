# START HERE: offline work package (Nov 21, 2026)

Everything in this folder works **without internet**.

## What is in this folder

| Item                                       | What it is                                                                                 | Time to use   |
| ------------------------------------------ | ------------------------------------------------------------------------------------------ | ------------- |
| `Wargame Project - Simplified Proposal.md` | **The main document**: setting, questions, the game step by step, results, plan            | 60 min        |
| `sources/`                                 | 12 downloaded papers and official documents (PDF)                                          | hours         |
| `sources/README - Reading Guide.md`        | One card per source: key idea, what matches our setting, what does not, pages to read      | 20 min        |
| `toys/`                                    | 5 small scripts (numpy only) that rebuild each idea from scratch                           | 5–15 min each |
| `sims/simplified_sims.py`                  | The script behind every number and figure in the proposal (real ERCOT data from the repo)  | 1 min to run  |
| `figures/`                                 | The 6 figures used in the proposal                                                         | -             |
| `Decision Log.md`                          | Who suggested each modeling choice (reviewer, Codex) and what we decided; how to reproduce | 10 min        |
| `Wargame Project - The Game.md`            | The older, more complicated draft (kept for reference only)                                | -             |
| `Course Info - 6.S974.pdf`                 | Course requirements (Workshop 2 on Dec 10)                                                 | 10 min        |

## Suggested order for a 4–5 hour offline session

1. **Read the proposal, Sections 1–5** (40 min). Stop after the small examples.
2. **Run `toys/toy01` and `toys/toy02`** (15 min). Change the numbers. Make sure you can explain every line of output.
3. **Read sources 02 and 01** (40 min). See what a real "report" (HSL) and a real shared connection limit look like.
4. **Read the proposal, Sections 6–7** (20 min), then **run `toys/toy03` and `toys/toy04`** (20 min).
5. **Read sources 05 and 04** (60 min): how curtailment is shared in practice and in research.
6. **Read source 10, Sections 1, 3.3 and 5** (45 min): inspection games.
7. Do the exercises at the end of `toys/README.md`.

## The project in five lines

1. Several wind–battery owners share **one grid connection** that is smaller than what they can produce together.
2. Each hour, each owner **reports** how much power it can send; the connection is split **in proportion to the reports**.
3. When the connection is congested, the meter shows only what each owner was **allowed** to send. So reports cannot be checked from the meter, and owners have a reason to **over-report**.
4. A **checker** with a few inspections per day can fine liars.
5. We study when lying pays (Q1), whether owners learn it (Q2), which checks stop it (Q3), and which sharing rule works best, also on stress days (Q4).

## How to run things

```bash
# toys: from this folder
cd toys && python toy01_two_owners.py

# real-data simulations: from the repository root (needs data/processed, already on disk)
python "Clean Start/Our References/update_20261120/sims/simplified_sims.py"
```

Python 3 with numpy, pandas and matplotlib is enough. The toys need only numpy.

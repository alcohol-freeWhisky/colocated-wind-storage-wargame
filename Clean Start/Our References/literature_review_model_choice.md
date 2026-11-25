# Literature review and model choice

Review of the reporting and inspection game in `game_setting_notes.md`.

**Verdict.** The basic structure is right and well supported in the literature: a split of the shared connection based on reports, plus costly and imperfect audits. It is not yet the simplest realistic version. The main problems are the timing assumptions and the decision to treat the allocation rule as fixed rather than chosen.

> References are cited from memory and were not looked up. Verify the details before citing them.

## 1. Related literature

| Strand | Key references | What it does that we don't |
|---|---|---|
| **Allocation with costly verification** | Ben-Porath, Dekel & Lipman (2014, *AER*); Mylovanov & Zapechelnyuk (2017, *AER*, bounded penalties) | Allocates a scarce good based on reports, with no payments, where the principal can check reports at a cost. It finds the *best allocation rule and audit policy together*. Our setup is the same problem, but we fix the proportional rule in advance. |
| **Costly state verification / optimal auditing** | Townsend (1979); Border & Sobel (1987); Mookherjee & Png (1989) | Audit probability depends on the report itself. The optimal policy is randomized and often makes truth-telling the best response by design. |
| **Inspector leadership (commitment)** | Maschler (1966); Avenhaus, von Stengel & Zamir (2002) | Treats commitment as the *standard* case. Our no-commitment result (Prop. 8: zero audits) is a known artifact of giving the inspector no benefit from a proven case. |
| **Audit games / security games** | Blocki et al. (2013, "Audit games"); Tambe's Stackelberg security games | Leader-follower games with a budget and a choice of how hard to punish. Mature computational methods for whom to audit. |
| **Proportional sharing with bids** | Kelly (1997); Johari & Tsitsiklis (2004); Tullock contests | Kelly's mechanism allocates in proportion to *paid bids*, with at most 25% efficiency loss. Our rule has no payments, so it is proportional rationing, not Kelly, and the 25% bound does not apply. Relevant to the PRICE regime. |
| **Uniform rule** | Sprumont (1991); Ching & Serizawa (1998) | With single-peaked or single-plateaued preferences (ours are), the uniform rule $k_i=\min\{\ell_i,\lambda\}$ is strategy-proof and efficient. When capability is known at reporting time, it removes the incentive to inflate without audits. See `setup_step_by_step.md`. |
| **Report inflation under proportional rationing** | Cachon & Lariviere (1999) | The same incentive in supply chains. Their fix is to change the rule (e.g. allocate by past sales), not to audit. |
| **Curtailment sharing for non-firm connections** | Kane & Ault (2014); Andoni et al. (2017) | In practice, curtailment is shared pro rata on *nameplate capacity* or by last-in-first-off order, not on self-reports. |
| **Forecast elicitation** | Gneiting & Raftery (2007), proper scoring rules | When reports are forecasts (Remark 7), truth is induced by scoring the forecast against realized output, with no audits. |
| **Detection that evades statistical tests** | Liu, Ning & Reiter (2009); Xie, Mo & Sinopoli (2011); Hardt et al. (2016, strategic classification) | Bad-data detection, and agents adjusting their inputs to fool a classifier. This supports our χ² screen and stealth findings. |
| **Enforcement economics** | Becker (1968); Stigler (1970); Polinsky & Shavell (2000) | Tradeoff between audit probability and fine size, maximal fines, and marginal deterrence. Background for Thm. 12 and Prop. 13. |

## 2. Pros and cons of our setting

**Pros**

- It captures what is new here: one report is both a grab for capacity and a change to the evidence the monitor sees.
- It has clean closed-form results: the stealth bound $\bar d_i$, the gain $G_i(d)$, the deterrence threshold $\alpha_i^\ast$, and the rat race $d^\ast$.
- The meter makes large lies visible automatically, so only small "stealth" lies need statistical screening. That matches how metering and telemetry actually work.
- The correlated-error results (camouflage, ranking reversals) are new and tied to wind.

**Cons**

1. **The allocation rule is assumed, not justified.** Nameplate pro rata needs no reports and is current practice. A congestion price (the PRICE regime) also avoids misreporting. Reports are worth using only if they put capacity where it can be used, so that benefit has to be weighed against the cost of inflation. The costly-verification literature is built around that tradeoff.
2. **Capability is known before reporting.** This is wrong for wind (Remark 7) and for storage, where available export depends on the owner's own dispatch. With forecasts, $x_i<k_i$ no longer proves inflation, and the stealth results lose their sharpness.
3. **Without commitment the result is trivial.** With $B_i\equiv0$ the monitor never audits (Prop. 8). Most of the literature starts from commitment.
4. **The harm measure makes undetected inflation mostly a transfer.** On the stealth set the harm is redistribution only. With identical owners it is zero, so there is nothing for the monitor to protect (Cor. 17). Real harm would come from wasted headroom, reliability, or unfairness, and the model needs at least one of these to give monitoring a reason.
5. **Two separate models.** The operating game (with batteries) and the inspection game are not yet linked.

## 3. The simplest model that is still realistic

The full dynamic Bayesian game with a budget is more than the research questions need. Proposed reduction:

1. **One period, repeated i.i.d.** (no dynamic budget). The budget becomes a per-period audit probability, which avoids the fragile last-audit problem behind Prop. 14.
2. **Commitment as the baseline.** The monitor announces report-dependent audit probabilities $\alpha_i(\ell)$.
3. **Owners who differ** (at least two capability levels). This is the minimum for monitoring to matter (Cor. 17).
4. **Reports are forecasts.** The report is $\ell_i$ and realized capability is $h_i=\widehat h_i+e_i$. Evidence comes from realized output when it isn't curtailed, plus audits.
5. **The allocation rule is a design choice.** Compare three rules on the same harm measure:
   - nameplate pro rata (no reports);
   - report pro rata plus audits (the current model);
   - congestion price.

This is a Ben-Porath–Dekel–Lipman-style problem: allocation with bounded penalties and costly verification. It is solvable, it connects directly to established theory, it can be simulated on the Anchor Wind data, and it answers the practical question of whether report-based allocation is worth the audits it needs.

**What to keep from the current note:** the stealth bound, the gain formula, the deterrence threshold $\alpha_i^\ast$, and the correlated-error results (Props. 18–21). They carry over as building blocks.

## 4. Suggested next steps

1. Verify the references above.
2. Write the reduced model (Section 3) with the same notation and color key as `game_setting_notes.md`.
3. Simulate the three allocation rules on Anchor Wind data, measuring utilization, redistribution, and the audit rate needed for truthful reporting.

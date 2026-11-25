# Setup, step by step

Each step gives the **definition**, the **assumptions** it needs, and a check of each assumption: realistic or not, why, source, and confidence. Points that were not obvious were checked with Codex (marked *Codex*). Results derived here are marked **Claim** and come with a short proof.

Legend: ✅ realistic · ⚠️ approximation or modeling choice that must be stated · ❌ not realistic, replace it.

---

## Step 1. Players and the shared limit

**Definition.** Owners $i=1,\dots,N$ (wind, optionally with storage) export through one point of interconnection (POI) with limit $K$. A monitor checks reports. The ISO is not a player.

| # | Assumption | Check | Why / source |
|---|---|---|---|
| S1 | Several owners share one POI limit $K$ | ✅ | Co-located and hybrid resources under CAISO's Aggregate Capability Constraint; cable pooling (RAP 2024); non-firm connections (Kane & Ault 2014). |
| S2 | Total export cannot exceed $K$: $\sum_i x_i\le K$ | ✅ | Physical or contractual interconnection limit. |
| S3 | Exports $x_i$ are metered exactly | ✅ | Revenue metering and telemetry at the POI (PJM, CAISO practice). |
| S4 | Owners are price takers | ✅ | A 262 MW site in an ERCOT system of roughly 80 GW. |
| S5 | All owners face the same nodal price $p$ | ✅ | They sit at one node, so they see one locational price. |

## Step 2. Private information: what each owner knows

**Definition.** Owner $i$'s capability $h_i$ is the MW it could export now. The owner knows it (or a forecast of it); the monitor does not.

| # | Assumption | Check | Why / source |
|---|---|---|---|
| I1 | **Real-time reports:** $h_i$ is approximately known when reporting | ⚠️ | ERCOT wind resources telemeter their HSL (current capability) every 4 s, and it feeds 5-min SCED. "Known" means wind persists over 5 min; when output is curtailed, capability is itself an estimate (*Codex*, medium). |
| I2 | **Forecast reports:** reports precede $h_i$, with $h_i\sim G_i$ | ✅ | Day-ahead and hour-ahead plans (ERCOT COP). |
| I3 | Capability is exogenous | ⚠️ / ❌ | True for wind only. With storage, available export depends on the owner's own state of charge and its decisions. |
| I4 | Values per MWh are equal across owners | ⚠️ | One nodal price (S5), but net values differ through PPAs, tax-credit eligibility, and battery opportunity cost (*Codex*, high). Acceptable for wind-only owners with similar contracts. |

**Consequence.** I1 and I2 are different problems and must be modeled separately. Storage breaks I3 and I4.

## Step 3. The report

**Definition.** Owner $i$ submits $\ell_i\ge0$ before the interval.

| # | Assumption | Check | Why / source |
|---|---|---|---|
| R1 | The report is the owner's capability (wind) | ✅ | Mirrors ERCOT's HSL, which must equal current net output capability. |
| R2 | For a hybrid, the report is the owner's *desired export* (or a bid), not capability | ✅ | A battery may legitimately export less than it can, so "capability" is not the economically relevant quantity (*Codex*, high). |
| R3 | No reporting cost | ✅ | Telemetry and scheduling submissions are routine. |

## Step 4. Allocation rule — the key design choice

**Definition.** When reports exceed $K$, a rule maps reports to headroom $k_i$, and export is $x_i=\min\{h_i,k_i\}$.

| Rule | $k_i$ under congestion | Status |
|---|---|---|
| **P** proportional | $K\ell_i/\sum_j\ell_j$ | Our current model. Real-world use is **not documented**: no ERCOT tie-break rule was found, CAISO's constraint is bid-based, and private agreements vary (*Codex*, medium). ⚠️ Treat P as a stylized contractual rule. |
| **U** uniform | $\min\{\ell_i,\lambda\}$ with $\sum_i\min\{\ell_i,\lambda\}=K$ | The standard truthful rule for dividing a fixed amount (Sprumont 1991; Ching & Serizawa 1998). Cachon & Lariviere (1999) find P inflates and U does not. |
| Nameplate share | $K\bar h_i/\sum_j\bar h_j$ | Needs no report, but leaves headroom unused when some owners are below their share. |
| LIFO priority | by connection order | Common in UK active network management (Kane & Ault 2014). Needs no report. |
| Bids / price | from offers | CAISO's Aggregate Capability Constraint; needed when values differ (I4). |

**Claim 1 (known capability, I1).** Under U, reporting $\ell_i=h_i$ is weakly dominant, and truthful reports use all of $K$ when $\sum_i h_i\ge K$.
*Proof.* With others' reports fixed, $k_i=\min\{\ell_i,a_i\}$, where the cap $a_i$ does not depend on $\ell_i$. Export $\min\{h_i,\ell_i,a_i\}$ is maximized at any $\ell_i\ge h_i$, including $\ell_i=h_i$. ∎
*Caveat (Codex):* not strictly dominant. An owner already capped at $a_i$ can over-report at no cost.

**Claim 2 (P is manipulable).** Under P with $\sum_j h_j>K$, inflation pays. With truthful rivals the gain is
$$G_i(d)=\frac{pK(Q-h_i)\,d}{Q(Q+d)},\qquad Q=\sum_j h_j$$
(Lemma 6 in `main.pdf`).

**Claim 3 (forecasts, I2; own result, verified by Codex).** Add a charge $c$ per MWh of unused allocation $(k_i-x_i)^+$. The owner's expected payoff is
$$V(k)=p\,\mathbb E\min\{h,k\}-c\,\mathbb E(k-h)^+,\qquad V'(k)=p-(p+c)G_i(k),$$
so the best allocation is the quantile $q_i=G_i^{-1}\!\big(p/(p+c)\big)$; $c=p$ gives the median.
- Under U, $k_i=\min\{\ell_i,a_i\}$ again, so reporting $q_i$ is weakly dominant.
- Under P, the best report depends on rivals' total $S$: $\ell_i=q_iS/(K-q_i)$. Truthful reporting is not dominant.
- Without the charge ($c=0$), both rules invite over-reporting.

**Conclusion of Step 4.** With known capability and equal values, U needs no audits. Audits are necessary only when (a) the rule is P, (b) reports are forecasts and there is no calibrated charge, or (c) the report cannot be checked against outcomes.

## Step 5. Evidence

**Definition.** The meter gives $x_i$. When output is curtailed, the monitor estimates capability: $\widehat h_i=h_i+\varepsilon_i$ with $\varepsilon\sim N(0,\Sigma)$, giving the residual $z=\widehat h-\ell$.

| # | Assumption | Check | Why / source |
|---|---|---|---|
| E1 | $x_i<k_i$ reveals $h_i=x_i$ (and A2 sanctions it) | ⚠️ / ❌ | Holds only for wind with no voluntary curtailment. It fails with storage (a battery may choose to under-export) and with negative-price curtailment (*Codex*, high). |
| E2 | When curtailed, capability is estimated from weather and turbine data | ✅ | This is how curtailed output is valued in practice, e.g. German Redispatch 2.0 power-curve methods; ERCOT HSL is defined as uncurtailed potential. |
| E3 | Gaussian estimation error with known $\Sigma$ | ⚠️ | A standard approximation. Real forecast errors are heavy-tailed and correlated across nearby units; $\Sigma$ must be estimated. |
| E4 | Errors are positively correlated across owners | ✅ | Neighbouring units share weather. This drives the camouflage results (Props. 18–21); related to Kattwinkel (2020). |

## Step 6. Monitor, audits, and sanctions

**Definition.** The monitor audits $i$ with probability $\alpha_i$. An audit proves a lie with probability $\eta(d)$. A proof triggers a fine $F\le\bar F$.

| # | Assumption | Check | Why / source |
|---|---|---|---|
| M1 | The monitor is the facility operator or an auditor named in the contract; the ISO/IMM/PUCT oversee wholesale-market conduct | ✅ | *Codex*, medium; Potomac Economics as ERCOT's IMM. |
| M2 | The monitor commits to an audit policy | ✅ | Inspector leadership (Maschler 1966); audit games (Blocki et al. 2013); published penalty guidelines. |
| M3 | Fines are bounded | ✅ | Legal caps; Becker (1968); Polinsky & Shavell (2000); Mylovanov & Zapechelnyuk (2017). |
| M4 | Imperfect proof, $\eta(d)<1$ | ✅ | Avenhaus, von Stengel & Zamir (2002) on inspection with detection errors. |
| M5 | Monitor's direct benefit from a proof: $B=0$ | ⚠️ | FERC and Ofgem order repayment of gains (disgorgement), but that does not go to a private monitor (*Codex*). Set $B>0$ only if the contract provides restitution. With $B=0$, commitment (M2) is required; otherwise there are no audits (Prop. 8). |
| M6 | Misreporting capability is sanctioned in practice | ✅ | FERC 18 CFR §35.41(b) cases (Dynegy, Terra-Gen, AES, GenOn); Ofgem fined InterGen in 2020 for false Stable Export Limits. |

## Step 7. Timing and solution concept

Each interval:
1. The monitor has already announced audit probabilities $\alpha$ and fine $F$ (commitment).
2. Owners observe $h_i$ (or $G_i$) and report $\ell_i$.
3. The rule allocates $k_i$, and owners export $x_i$.
4. The meter records $x$; the monitor estimates $\widehat h$ when output was curtailed.
5. Audits and fines are applied.

**Solution concept:** Bayesian Nash equilibrium among owners given the committed policy (Stackelberg leader–followers). Periods are treated as independent, with a per-period audit probability instead of a dynamic budget. ✅ This is the standard simplification; the dynamic budget (Dresher 1962; von Stengel 2016) is an extension.

---

## Simplest realistic game

| Layer | Setting | What it answers |
|---|---|---|
| **Benchmark** | Real time, wind only, known $h$, equal values. Compare **P vs U**. | U is truthful without audits (Claim 1). P needs audit probability $\alpha\ge\alpha^\ast$ (Thm. 12). Answers: *is the rule or the audit the cheaper fix?* |
| **Main** | Forecast reports (I2), capability estimated when curtailed (E2), correlated errors (E4), committed audits. Compare P and U with a charge $c$ on unused allocation. | Claim 3: U plus the charge is truthful for the target quantile. Under P, audits and fines are needed; correlated errors weaken detection (camouflage). |
| **Extension** | Storage (I3, I4, R2): reports are desired export or bids. | Values differ, so allocation needs bids (the PRICE regime). Link to the operating game. |

**Assumptions to drop or replace from `main.pdf`:**
- E1 / A2 (metered self-incrimination): replace it with E2 whenever storage or voluntary curtailment is present.
- $B=0$ without commitment: use commitment as the baseline.
- The dynamic public budget: use a per-period audit probability.
- Rule P as given: present it as a stylized contractual rule and compare it with U.

---

## Sources

- Allocation rules: [Cachon & Lariviere 1999 (summary)](https://www.researchgate.net/publication/226227618_An_equilibrium_analysis_of_linear_proportional_and_uniform_allocation_of_scarce_capacity); Sprumont 1991 and Ching & Serizawa 1998 ([survey](https://core.ac.uk/download/36014178.pdf), [domain extension](https://ddd.uab.cat/pub/artpub/2001/143790/gamecobeh_a2001v37n2p367iENG.pdf)).
- Verification and limited penalties: [Ben-Porath, Dekel & Lipman 2014](https://econpapers.repec.org/RePEc:aea:aecrev:v:104:y:2014:i:12:p:3779-3813); [Mylovanov & Zapechelnyuk 2017](https://research-repository.st-andrews.ac.uk/bitstream/10023/11657/1/Zapechelnyuk_2017_AER_ExpostVerification_AAM.pdf); [Li 2020](https://economics.sas.upenn.edu/sites/default/files/filevault/SSRN%2016_009%20third%20version.pdf); [Kattwinkel 2020](https://ideas.repec.org/p/bon/boncrc/crctr224_2020_227.html).
- Inspection and audit games: [von Stengel 2016](https://arxiv.org/pdf/1412.0129); [Blocki et al. 2013](https://arxiv.org/abs/1409.4503).
- Proportional sharing with bids: [Johari & Tsitsiklis 2004](https://www.mit.edu/people/jnt/Papers/J097-04-joh-ncgame.pdf).
- Shared connections: [Kane & Ault 2014](https://econpapers.repec.org/RePEc:eee:enepol:v:72:y:2014:i:c:p:67-77); [LIFO vs. pro rata](https://arxiv.org/pdf/1908.10313); [non-firm connections (arXiv 2606.03887)](https://arxiv.org/pdf/2606.03887); [RAP/ERRA 2024](https://www.raponline.org/wp-content/uploads/2024/10/RAP-ERRA-Power-grid-report-October-2024.pdf); [CAISO Market Operations BPM](https://bpmcm.caiso.com/BPM%20Document%20Library/Market%20Operations/BPM_for_Market%20Operations_V99_Redline.pdf).
- ERCOT practice: [WGR HSL expectations](https://www.ercot.com/files/docs/2011/07/07/wind_powered_generation_resource_telemetered_hsl___expectati.doc); [GREDP example](https://www.ercot.com/files/docs/2011/01/05/wind_gredp_example.doc); [ERCOT IMM](https://potomaceconomics.com/markets-monitored/ercot/).
- Curtailed-output estimation: [Redispatch 2.0 settlement methods](https://synertics.io/blog/243/redispatch-20-for-renewable-assets-understanding-the-three-settlement-methods).
- Enforcement: [FERC outage-reporting settlements](https://www.thompsoncoburn.com/insights/avoiding-enforcement-risk-outage-reporting-lessons-from-recent-ferc-settlements-102m1om/); [FERC §35.41(b) cases](https://www.jdsupra.com/legalnews/ferc-settlements-reflect-enforcement-6192853/); [Ofgem InterGen](https://ofgem.gov.uk/publications/ofgem-requires-intergen-pay-ps37m-over-energy-market-abuse).

# Reading Guide: 12 Sources for the Wind–Storage Wargame

*All files are in this folder and can be read offline. Page numbers below are **PDF page numbers** (what your PDF viewer shows), not the printed journal page numbers.*

**How to use this guide.** Each source has a short card with:
- what it is;
- the one idea to take from it;
- what **matches** our setting;
- what does **not** match;
- which pages to read.

The table right below tells you which source supports which part of our project.

---

## 1. Map: which source supports what

| # | Source | Type | Supports | Our section |
|---|---|---|---|---|
| 01 | CAISO (2021), *Aggregate Capability Constraint* | Market rule (real practice) | Several resources share one connection limit; fixed split vs. joint limit | Setting, R1 |
| 02 | Texas RE & ERCOT (2016), *Wind Operations Issues* | Operator training slides (real practice) | The report (HSL) and how operators check it | Report, checker |
| 03 | CAISO (2020), *High Sustainable Limit white paper* | Market rule (real practice) | How HSL is computed and checked | Report, checker |
| 04 | Andoni et al. (2017), *Applied Energy* | Research: game theory + curtailment | Curtailment rules (pro-rata, LIFO); wind correlation | Rules, Q4 |
| 05 | Kane & Ault (2014), *Energy Policy* | Research: review of real schemes | How UK schemes share curtailment in practice | Rules, realism |
| 06 | Simshauser & Newbery (2023), EPRG WP | Research: economics, Australia | Pro-rata (non-firm) vs. priority access at scale | Rules, Q4 |
| 07 | Mahuze et al. (2026), *Applied Energy* | Research: mechanism design | Beyond pro-rata: trading curtailment; truthful bids | Q4, extensions |
| 08 | Johari & Tsitsiklis (2004), *Math. of OR* | Research: game theory | Proportional sharing as a game; efficiency loss | Q1 |
| 09 | Cachon & Lariviere (1999), *Mgmt. Science* | Research: game theory, supply chains | Allocation based on past sales can be gamed too | R6, Q4 |
| 10 | Avenhaus, von Stengel & Zamir (2002), *Handbook of GT* | Research: inspection games | Inspector vs. inspectee; commitment; data verification | Q3 |
| 11 | Korzhyk et al. (2011), *JAIR* | Research: security games | Stackelberg (commit first) vs. Nash | Q3 |
| 12 | Auer et al. (2002), *SIAM J. Comput.* | Research: learning | The EXP3 learning rule we use | Q2 |

**Reading order for one offline afternoon (about 3–4 hours):**
1. **02** (20 min): see what a real "report" (HSL) looks like and how operators check it.
2. **01** (20 min): see a real multi-resource connection limit.
3. **05** (30 min): see how real schemes share curtailment.
4. **04** (40 min): the closest research paper to our setting.
5. **10** (45 min): the theory of inspections.
6. **08** (30 min): the theory of proportional sharing.
7. **12** (20 min): the learning rule.
8. Skim **03, 06, 07, 09, 11** as needed.

---

## 2. Real-world practice (what exists today)

### 01. CAISO (2021). *Aggregate Capability Constraint – Implementation* (final proposal). 9 pages.
`01_CAISO_2021_ACC_CoLocated_FinalProposal.pdf`

- **What it is:** the California grid operator's rule for several resources (for example, solar + battery, or several projects) behind **one point of interconnection**.
- **Key idea:** the market dispatches all co-located resources so that their **sum** stays below the interconnection limit. This is the "aggregate capability constraint" (ACC).
- **Matches our setting:**
  - Developers split projects among different buyers ("disaggregate those projects among off-takers", p. 2). So several commercial parties behind one connection is a real situation.
  - **An example of fixed shares.** On p. 4, CAISO describes how such resources were traditionally modeled: a 100 MW and a 50 MW resource behind a 100 MW limit were registered as 67 MW and 33 MW. This is an example of our rule **R1 (fixed shares in proportion to size)**. CAISO says this approach "limits the total amount of dispatch available from each individual resource", which is one reason for the ACC. (It is one example, not proof that all plants used this split.)
  - CAISO says it has "no liability if co-located resources do not comply with dispatch instructions and infringe on interconnection capacity for use by other co-located resources" (p. 2). This is about non-compliance with dispatch, but it shows that co-located parties can affect each other's use of the shared limit.
- **Does not match:** in CAISO, the market decides the split (using offers and the resources' telemetry). There is no owner-to-owner pro-rata rule and no inspection with fines.
- **Read:** pp. 2–5.

### 02. Texas RE & ERCOT (2016). *Texas RE and ERCOT Wind Operations Issues* (training slides). 48 pages.
`02_TexasRE_ERCOT_2016_Wind_Operations_HSL.pdf`

- **What it is:** slides from the Texas reliability entity and ERCOT for wind plant operators.
- **Key idea:** each wind unit sends a live number called **HSL (High Sustained Limit)**: the power it could produce now.
- **Matches our setting (this is the real-world version of our "report" and "checker"):**
  - "When under curtailment a WGR's HSL must represent **actual power generation potential**" (pp. 45–46). During curtailment, the meter alone cannot show this potential, so the dispatch relies on the owner's number. This is our report \(\ell\). (Independent forecasts, below, can give a second, noisier estimate.)
  - "When a WGR is **uncurtailed** its MW and HSL values should be exactly the same" (pp. 43–44). This is the meter check: outside curtailment, the report can be compared with the meter.
  - ERCOT makes its own wind forecast (STWPF) from site data, meteorological towers and turbine power curves (pp. 7–8). This is the checker's **independent estimate** \(\hat a\).
- **Does not match:** ERCOT dispatch is centralized (SCED with offers). It does not split a private connection pro-rata between owners. The slides are about honest data errors, not strategic lying.
- **Read:** pp. 7–9 and 42–48.

### 03. CAISO (2020). *High Sustainable Limit (HSL)* white paper. 16 pages.
`03_CAISO_HSL_WhitePaper_HybridPhase2.pdf`

- **What it is:** CAISO's proposal to require the HSL telemetry for wind and solar parts of hybrid and co-located plants.
- **Key idea:** HSL is computed at the site from wind speed, wind direction, number of available turbines and the power curve (p. 12).
- **Matches our setting:**
  - How the operator checks HSL (p. 15): "During times of non-dispatch, the HSL will be very similar to the MW telemetry. The CAISO can **compare these two values**." It also plots HSL against wind speed to see whether it is reasonable. This is a real, simple version of our **inspection**.
  - It discusses "overbuilt" plants (for example, 150 MW solar + 50 MW battery behind a 100 MW connection, p. 14). This is our \(K < \sum L_i\).
- **Does not match:** no penalties for strategic over-reporting are discussed; the checks are about data quality.
- **Read:** pp. 4–7, 12, 14–16.

### 05. Kane & Ault (2014). *A review and analysis of renewable energy curtailment schemes and Principles of Access*. *Energy Policy* 72: 67–77. 11 pages, open access.
`05_Kane_Ault_2014_Curtailment_Principles_of_Access.pdf`

- **What it is:** a review of real UK "Active Network Management" schemes, where many generators share a congested network under "non-firm" connections.
- **Key idea:** the sharing rule is called the **Principle of Access (PoA)**. The main options are:
  - **LIFO** (last in, first off);
  - **pro-rata**;
  - market-based rules.
- **Matches our setting:**
  - Pro-rata "divides the required curtailment equally between all [non-firm generators]... based on the ratio of **rated or actual** [generator] output" (p. 4). A real project (Flexible Plug and Play) chose pro-rata with a cap on how much capacity can connect.
  - The criteria used to compare rules (efficiency, certainty, simplicity, fairness) match our metrics.
- **Does not match (important):** in these schemes, pro-rata uses **rated capacity** (= our fixed shares R1) or **measured output** (close to our meter feedback R6). It does **not** use self-reports. Our report-based rule rests on a different fact: during curtailment, metered output does not show the curtailed potential. Operators then rely on owner estimates like HSL (sources 02, 03), possibly checked against independent forecasts.
- **Read:** pp. 1–5 (review and PoA definitions), then the conclusions.

### 06. Simshauser & Newbery (2023). *Non-Firm vs. Priority Access: on the Long Run Average and Marginal Cost of Renewables in Australia*. EPRG Working Paper 2322. 31 pages.
`06_Simshauser_Newbery_2023_NonFirm_vs_Priority_Access.pdf`

- **What it is:** an economics paper on Australian Renewable Energy Zones (REZ), where many wind and solar plants share network capacity.
- **Key idea:** the existing regime gives "equal dispatch rights for all connected generators in a REZ with **production-weighted pro-rata sharing** of curtailment" (p. 20). The alternative is **priority access** (LIFO). The authors show that the gap between **marginal** and **average** curtailment matters a lot for investment.
- **Matches our setting:** pro-rata sharing of a congested connection among independent owners is a real regime at very large scale (GW). Their marginal-curtailment idea is close to our "first small step of lying" formula: a new or extra MW is curtailed more than the average MW.
- **Does not match:** the focus is investment and long-run cost, not hourly reporting or lying.
- **Read:** abstract, Section 1, and pp. 18–22.
- *Note:* the related paper by Newbery & Biggar (2024, *Energy Policy* 191) could not be downloaded here; this working paper covers the same ideas.

---

## 3. Research on sharing rules (game theory and mechanism design)

### 04. Andoni, Robu, Früh & Flynn (2017). *Game-theoretic modeling of curtailment rules and network investments with distributed generation*. *Applied Energy* 201: 174–187. 21 pages (arXiv version).
`04_Andoni_2017_Curtailment_Rules_Game_Theory.pdf`

- **What it is:** the closest research paper to our setting. Wind generators share a line; the line investor and the generators play a **Stackelberg game**.
- **Key ideas:**
  1. It compares curtailment rules: LIFO, rotation, **pro-rata**, and a new fair rule (FRR). Pro-rata can be "according to rated capacity or power output" (table, p. 6).
  2. **Wind correlation matters:** "most generators responsible for a particular grid constraint have geographical proximity and therefore correlated power outputs" (p. 2). Total curtailment rises with correlation (Fig. 1c).
- **Matches our setting:** shared line, pro-rata, real hourly wind data, game theory. Our Figure 6 (honest reports matter less when wind is similar) is in the same spirit as their correlation study.
- **Does not match:** generators do not report anything, so there is no lying and no inspection. The game is about **investment** (how much capacity to build), not hourly operation. This gap is where our project adds something.
- **Useful for coding:** a simple recipe to make correlated synthetic wind (p. 7): \(u_i = c_r u_{\text{ref}} + (1 - c_r) u_{\text{rand},i}\), with \(c_r = \arccos(1 - 2r)/\pi\) and Weibull wind speeds. We use it in `toys/toy03_rules_synthetic_wind.py`.
- **Read:** pp. 1–8 (rules and correlation), skim the Stackelberg part.

### 08. Johari & Tsitsiklis (2004). *Efficiency Loss in a Network Resource Allocation Game*. *Mathematics of Operations Research* 29(3). 35 pages (preprint).
`08_Johari_Tsitsiklis_2004_Proportional_Allocation_Game.pdf`

- **What it is:** a classic paper on **proportional sharing** of a congested resource as a game. Users submit **bids** (money). Each gets a share in proportion to its bid (the "Kelly mechanism").
- **Key result:** with strategic users, total value is at least **3/4** of the best possible (p. 1). This is a "price of anarchy" result.
- **Matches our setting:** same mathematical form as our rule \(k_i = \ell_i K / \sum_j \ell_j\). The way they compute best responses and equilibria is the same idea as our Section 5.
- **Does not match:** their users **pay** for their bids, so a larger bid costs money. Our reports are **free** unless inspected. So in our game, without checks, reporting the cap is weakly dominant and "everyone at the cap" is an equilibrium (not always the only one), while theirs has a well-behaved, unique equilibrium. An expected fine for over-reporting plays a role similar to their price, but it is paid only when caught, and only on the false part of the report.
- **Read:** pp. 1–6 (model and the single-resource result).

### 09. Cachon & Lariviere (1999). *Capacity Allocation Using Past Sales: When to Turn-and-Earn*. *Management Science* 45(5): 685–703. 19 pages.
`09_Cachon_Lariviere_TurnAndEarn_Allocation_Past_Sales.pdf`

- **What it is:** a supplier with fixed capacity gives it to retailers based on their **past sales** ("turn-and-earn", used by car makers).
- **Key result:** retailers inflate their sales when demand is low, to earn a bigger allocation later. This helps the supplier but can hurt the whole chain when capacity is very tight (p. 1).
- **Matches our setting:** this is the economics of our **meter feedback rule (R6)**: allocation based on past metered delivery. By analogy, such rules may also be gamed: an owner might discharge its battery just to keep a large share. (This is a plausible incentive suggested by the analogy, not a result of the paper for our setting.)
- **Also relevant:** their companion paper (*Management Science* 45(8), 1999, "Capacity choice and allocation", not downloadable here) shows that **proportional allocation of orders makes buyers inflate orders**. This is the supply-chain twin of our over-reporting result.
- **Does not match:** no inspections; retailers sell real goods (the "inflation" is real sales, not false reports).
- **Read:** pp. 1–4 (model and main insight).

### 07. Mahuze, Gressel, Amadeh & Zhang (2026). *The Potential Welfare Gains from Curtailment Trading Under Non-Firm Interconnection*. *Applied Energy* (arXiv v5). 68 pages.
`07_Curtailment_Trading_NonFirm_Interconnection_2026.pdf`

- **What it is:** a very recent mechanism-design paper. Loads with "non-firm" connections can **trade** curtailment obligations.
- **Key results:** pro-rata ignores how much each party values its energy. A trading market with VCG payments makes truthful bidding a dominant strategy, and welfare is 1.41–1.83 times the pro-rata level in their tests (p. 3). They also find that simpler pricing is **manipulable** (p. 3).
- **Matches our setting:** it treats pro-rata as the baseline to beat, and it cares about truthful reporting. This is the "advanced" direction for our Q4.
- **Does not match:** the parties are **loads** (for example, data centers), not wind owners. Values differ a lot across parties, while in our model all MWh have the same value. VCG needs money transfers and can need subsidies.
- **Read:** abstract (p. 3) and the introduction; skip the proofs.

---

## 4. Research on inspections, security, and learning

### 10. Avenhaus, von Stengel & Zamir (2002). *Inspection Games*. Chapter 51 in *Handbook of Game Theory*, Vol. 3. 40 pages (2001 preprint).
`10_Avenhaus_vonStengel_Zamir_2001_Inspection_Games.pdf`

- **What it is:** the standard survey of **inspection games**. An inspector with limited resources checks whether an inspectee follows the rules.
- **Key ideas:**
  1. **Data verification** (Section 3.3, p. 18): the inspectee **reports data** and the inspector compares it with his own noisy measurements. This is our checker exactly.
  2. **Inspector leadership** (Section 5, p. 29): the inspector gains by **announcing and committing** to an inspection strategy ("commitment power"). This is our committed checker (Stackelberg).
  3. Applications to auditing and tax inspection (Section 2.2, p. 5).
- **Matches our setting:** limited budget, strategic violations, reports vs. own measurements, commitment.
- **Does not match:** usually one inspectee. We have several owners who also compete with **each other** through the shared connection, so one owner's lie hurts the others, not only the inspector.
- **Read:** pp. 2–6 (introduction and applications), p. 18 onward (data verification), pp. 29–31 (leadership).

### 11. Korzhyk, Yin, Kiekintveld, Conitzer & Tambe (2011). *Stackelberg vs. Nash in Security Games*. *JAIR* 41: 297–327. 31 pages.
`11_Korzhyk_2011_Stackelberg_vs_Nash_Security_Games.pdf`

- **What it is:** a key paper on **security games**: a defender with limited resources protects targets; an attacker picks a target.
- **Key results:** under a natural restriction on security games, any "commit first" (Stackelberg) strategy of the defender is also a Nash equilibrium strategy (abstract, p. 1). So, in those games, the defender does not need to know whether the attacker can observe its strategy. With attackers that can hit several targets, this can fail.
- **Matches our setting:** our checker is the defender, the owners are the attackers, and the "targets" are owners or hours to inspect. It supports using a **committed** inspection rule.
- **Does not match:** security games usually have one attacker and zero-sum-like payoffs. Our owners are many, and their lies also hurt each other.
- **Read:** pp. 1–6 (abstract, introduction, model).

### 12. Auer, Cesa-Bianchi, Freund & Schapire (2002). *The Nonstochastic Multiarmed Bandit Problem*. *SIAM J. Computing* 32(1): 48–77. 30 pages.
`12_Auer_2002_EXP3_Nonstochastic_Bandit.pdf`

- **What it is:** the paper that introduced **EXP3**, the learning rule our owners use.
- **Key idea:** a player picks one of \(K\) options each round and sees only the payoff of the option it played. EXP3:
  1. mixes "play good options more" with a little random exploration;
  2. divides each observed payoff by the probability of the option played, so that the estimates are fair.

  It needs payoffs in [0, 1] and works even if the environment (other owners) changes adversarially.
- **Matches our setting:** our owners see only their own profit and face other learning owners, which is an "adversarial" environment.
- **Does not match:** the guarantee (low regret) is for one player. When all players use EXP3, the theory does not promise convergence to a Nash equilibrium. That is why our learning results are reported as simulations, not theorems.
- **Read:** pp. 1–3 (problem) and pp. 5–7 (the EXP3 algorithm, Figure 1, and its first regret bound).

---

## 5. What the literature has, and what is new in our project

| Topic | What exists | What we add |
|---|---|---|
| Sharing a congested connection | Pro-rata, LIFO, market rules are used and studied (04, 05, 06, 07) | A sharing rule that relies on **unverifiable reports**, and its weakness to lying |
| Reported available power | HSL exists and is checked for data quality (02, 03) | Treat HSL-type reports as **strategic** |
| Proportional sharing as a game | Well studied when bids cost money (08) or are real orders (09) | **Free** reports plus **fines**, so inspections replace prices |
| Inspection games | Mature theory, usually one inspectee (10, 11) | Several inspectees who **compete for the same connection** |
| Learning in games | EXP3 and no-regret learning (12) | Learning owners in a real-data wargame; learners can pick the "small hidden lie" equilibrium |

**Honest limits of this list:** we did not find a paper that studies exactly "pro-rata curtailment based on self-reported availability, with inspections". This is a gap that our project fills, but it may also mean the setting is uncommon in practice. Section 2 of the proposal explains why we think it is realistic: during curtailment, metered output does not show the curtailed potential, so operators rely on owner estimates such as HSL (02, 03).

**Already in the repository, related:**
- `docs/references/LBNL_Hybrid_Plant_Tracking_2025.pdf`: statistics on hybrid plants and their connection limits.
- `Clean Start/Our References/literature_review_model_choice.md`: earlier notes on audit games, strategic classification and stealthy attacks.

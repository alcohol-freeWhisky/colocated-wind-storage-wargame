
# 1. Research Setup and Question

**What is the exact setup here?** "Strategic" use of limited interconnection capacity under imperfect monitoring, for a market with independent generators that have the option to use wind–battery scheduling, each day/period.
- Maybe something like: _"Strategic Generation Capacity Allocation and Monitoring in Shared Wind–Storage Facilities"_

The central question can be something like:

> How should a shared export connection be allocated among independently operated wind–battery resources when owners have private information about their capacities, may strategically exaggerate (or fake) their claims, and a coordinator has limited ability to verify each of them?

This is focused enough to formulate as a game and rich enough to support the course's learning, security, and resilience components.

**Some research questions (not the central one)**

- **(Strategic inefficiency)** Under shared export constraints, when does decentralized operating or reporting behavior lead to inefficient allocations, and when is truthful or coordinated behavior an equilibrium?
- **(Monitoring and deterrence)** How do inspection budgets, imperfect evidence, and penalties change equilibrium reporting? Can an adaptive monitor outperform fixed or random inspections?
- **(Resilient mechanism design)** Which allocation rules are least vulnerable to strategic reporting, and what efficiency or fairness trade-offs do more robust rules impose?

We have a clear progression then:
- 1st understand strategic behavior, 
- 2nd analyze enforcement, 
- 3rd redesign the rules/policies.


## **4. Define the game in layers**

Rather than immediately solving one enormous dynamic stochastic game, I recommend the following architecture.

**Layer A — Physical and operating system**

Wind, batteries, energy prices, storage dynamics, shared export limit

**Layer B — Strategic allocation game**

Private export capabilities → strategic reports → connection allocations → realized delivery

**Layer C — Inspection and adaptation game**

Noisy signals → limited audits → sanctions → updated strategies and beliefs

The layers describe a common environment, but we can analyze a restricted game at each stage. This is how we avoid claiming an equilibrium of the full dynamic game when we have actually computed an equilibrium of only one component.

### **4.1 The common physical system**

We have \(N\) independently controlled resources, indexed by \(i\), sharing a point of interconnection with capacity \(K\).

For each one-hour period \(t\):

- \(W_{it}\): wind available to owner \(i\).
    
- \(s_{it}\): battery state of charge.
    
- \(c_{it},d_{it},r_{it}\): charging, discharging, and curtailment decisions.
    
- \(q_{it}\): requested net export.
    
- \(x_{it}\): actual export accepted through the shared connection.
    
- \(\pi_t\): exogenous market price.
    

The operational equations begin with

\[ q_{it}=W_{it}-r_{it}-c_{it}+d_{it} \]

and

\[ s_{i,t+1} =s_{it}+\eta_i^c c_{it} -\frac{\widetilde d_{it}}{\eta_i^d}. \]

Here \(\widetilde d_{it}\) is **executed**, not merely requested, battery discharge. This is important because energy that could not pass through the connection should not mysteriously disappear from the battery.

The basic physical requirement is

\[ 0\leq\sum_i x_{it}\leq K. \]

The owner is paid for actual delivered energy, subject to degradation costs. Day-ahead financial positions can be included if desired, but fixed positions contribute constants to the operating decision when market prices are exogenous.

### **4.2 The reporting game: the first one we should solve rigorously**

For this first game, freeze the operating decisions within a period. Let \(h_i\) be the export capability established by the operating layer before reports are submitted.

Initially, assume \(h_i\) is known to owner \(i\), but not directly to the coordinator. The owner reports \(\ell_i\).

The coordinator allocates capacity proportionally to reports:

\[ k_i(\ell)= \ell_i\min\left\{1,\frac{K}{\sum_j\ell_j}\right\}. \]

Under the simplifying assumption that resources export all they can up to their allocations,

\[ x_i=\min\{h_i,k_i(\ell)\}. \]

With no inspections and a common positive energy price \(p\), the payoff is

\[ u_i(\ell_i,\ell_{-i})=p\,x_i. \]

This is a genuine simultaneous-move game: one owner's report changes the connection share available to everyone else.

The simplest equilibrium question is whether there exists a profile \(\ell^*\) such that

\[ u_i(\ell_i^*,\ell_{-i}^*) \ge u_i(\ell_i,\ell_{-i}^*) \quad\forall i,\ell_i. \]

Crucially, this minimal game does **not** yet pretend to solve strategic battery scheduling, forecasting, and inspections simultaneously.

### **4.3 Add a monitor with a well-defined information problem**

The monitor does not know \(h_i\). It observes reports, accepted exports, and independent diagnostic evidence.

An initial statistical model could be

\[ z_t=\widehat h_t-\ell_t, \qquad \widehat h_t=h_t+\varepsilon_t, \qquad \varepsilon_t\sim\mathcal N(0,\Sigma). \]

Here \(\Sigma\) represents correlated estimation errors.

At each period, the monitor selects a set \(A_t\) of owners to investigate. Across the experiment, it has a hard inspection budget \(M\):

\[ \sum_{t=1}^{T}|A_t|\le M. \]

If an investigation establishes a contractual violation, a pre-announced fine may apply.

A reporting owner's expected period payoff becomes

\[ u_{it}=p_t x_{it} -\Pr(i\text{ audited})\, \eta_i(d_{it})F_i(d_{it}), \]

where \(d_{it}=(\ell_{it}-h_{it})^+\) and \(\eta_i\) is the conditional probability of proving a violation.

For the first solved example, I would use perfect verification conditional on an audit. Only afterward should we introduce imperfect verification, noisy statistical screening, and strategic audit targeting.

I would also use a **committed inspection policy** in the main model. The monitor announces a policy before owners report, and owners optimize against that policy. Without commitment or a direct ex-post enforcement benefit, the monitor's current audit cost can make inspections sequentially irrational once reports and allocations are already determined. This is precisely the issue your newer manuscript identifies.

### **4.4 A necessary distinction about capability**

The definition above makes \(h_i\) a frozen, physically feasible export quantity. That assumption is essential for the initial proof.

In the full wind–battery model, however, owners can deliberately preserve storage energy or curtail wind. A low observed export therefore need not reveal the maximum amount they could have supplied.

We must eventually choose a contractual reporting interpretation: a declaration of current verified capability, a committed export offer, or a forecast-based reservation. Each leads to different evidence and violation rules.

My recommended sequence is to **solve the frozen-capability game first and explicitly label it as a reporting subgame**. Then add endogenous operating choices and forecast errors as extensions. This avoids building a sophisticated inspection model around an unobservable quantity whose meaning changes from one section to another.

## **5. Two small games that should anchor the whole project**

These are more valuable than immediately running another large experimental design.

### **Example A — Why decentralized storage operation can be inefficient**

The two-owner, two-hour example in the original submission is worth preserving.

Both owners initially have 1 MWh of wind and can either sell it now or store it for the second hour. The connection has capacity 1 MW, prices are $20 and $100/MWh, and battery wear costs $5 per MWh discharged. This illustrative example assumes perfect storage efficiency and no terminal energy requirement.

Payoff matrix — dollars (Owner 1, Owner 2)

||Owner 2: Charge|Owner 2: Sell|
|---|---|---|
|**Owner 1: Charge**|**(47.5, 47.5)**|(95, 20)|
|**Owner 1: Sell**|(20, 95)|(10, 10)|

Both charging is the unique Nash equilibrium in this restricted two-action game: charging is a strictly dominant strategy for each owner.

Decentralized equilibrium

# **$95**

Joint realized payoff

Coordinated solution

# **$115**

Joint realized payoff

The equilibrium is less efficient because both owners crowd the high-price period.

This proves something about the **restricted two-strategy example**, not about equilibrium of the entire continuous 24-hour battery game. That limitation should be stated.

### **Example B — Why strategic reporting creates a different problem**

Now isolate the reporting decision.

Suppose there are two owners, with actual capabilities

\[ h_1=8,\qquad h_2=4,\qquad K=9. \]

The energy price is $100/MWh, and each period is one hour. Owner 1 reports truthfully, \(\ell_1=8\). Owner 2 considers inflating its report.

The numbers below follow directly from the proposed allocation rule.
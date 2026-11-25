This repository implements a dynamic shared-resource coordination game—not a strategic bidding or market-power game.

I also created a visual mathematical companion you can open beside the chat: Fundamental Game Analysis (/Users/nacevedo/.cursor/projects/Users-nacevedo-Documents-Github-colocated-wind-storage-wargame/canvases/fundamental-game.canvas.tsx). I chose a canvas because the game’s physical, informational, and equilibrium layers are easier to inspect as one durable model.

The fundamental game is:

> Several independently controlled wind-plus-battery operators share one constrained export cable (the POI). They earn the same exogenous real-time electricity price, but their individually chosen injections jointly create congestion and can cause a shared delivery shortfall.

## Players, horizon, and market

There are N agents. In the base case, N=5 wind units at Anchor Wind, each paired with a fixed co-located battery.

An episode is a 24-hour operating day. Electricity is sold at the observed ERCOT real-time hub price πₜ. Crucially, agents are price takers:

πₜ  is exogenous; agents neither submit bids nor affect price.

So this is not Cournot, Bertrand, or a two-settlement bidding game. It is a dynamic congestion/common-pool game with intertemporal storage.

The common infrastructure is the point of interconnection:

    N
Qₜ= ∑  q_{i,t},
   i=1

where q_{i,t} is agent i's net injection. The desired system envelope is

Dₜ ≤ Qₜ ≤ K.

Here K is the shared export limit and Dₜ is a shared minimum-delivery target constructed from day-ahead awards or wind forecasts.

## Strategies: what each player chooses

At each hour, agent i selects a charging, discharging, and curtailment plan:

a_{i,t}=(c_{i,t},d_{i,t},r_{i,t}).

Its net injection is

q_{i,t}=W_{i,t}-r_{i,t}-c_{i,t}+d_{i,t},

where W_{i,t} is available wind.

Battery state evolves as

                                    d_{i,t}
s_{i,t+1} = s_{i,t} +η_{c} c_{i,t} -───────,
                                     η_{d}

subject to

0≤ s_{i,t}≤ Eᵢ,  0≤ c_{i,t},d_{i,t}≤ Pᵢ,  0≤ r_{i,t}≤ W_{i,t}.

The battery starts at 50% state of charge and, in the base case, must return to that level at the end of the day. Thus the strategic choice is really an entire 24-hour dispatch path, not an isolated hourly action.

Grid charging is allowed, so q_{i,t} may be negative.

## Why the game is strategic

An extra MWh exported by one player has two effects:

1. It earns that player πₜ.
2. It uses scarce shared POI headroom and changes the shared shortfall/congestion cost for all players.

Storage makes this intertemporal. Charging at hour t sacrifices current export capacity but can create discharge capacity for a later high-price hour. If several agents see the same high-price opportunity—or have correlated wind—they may all want to discharge through the same constrained POI at once.

The main strategic tension is therefore:

private value of export  vs.  social cost imposed through the shared POI.

Tighter K, more correlated wind, and more flexible batteries intensify that tension.

## Payoffs

The basic operating profit is

Uᵢ⁰ = ∑ [ πₜ q_{i,t} - Cᵢᵈᵉᵍd_{i,t} ].
      t

Discharging has a degradation cost; charging and curtailment have a tiny tie-breaking cost in the LP implementation.

For the decentralized game, each player also bears an allocated share of the common penalties:

Uᵢ = Uᵢ⁰ -βᵢ⁻λ⁻∑[Dₜ-Qₜ]⁺ -βᵢ⁺λ⁺ ∑[Qₜ-K]⁺ - ∑ μₜ q_{i,t}.
               t                t          t

In the baseline full-information selfish game, the shares are capacity shares:

\[
\beta_i^-=\beta_i^+
=
\frac{\text{nameplate}_i}{\sum_j\text{nameplate}_j}.
\]

The base penalties are λ⁻=250 dollars/MWh for under-delivery and λ⁺=100 dollars/MWh for planned POI overflow.

This creates a public-good problem. When the system is short, an additional injection by i reduces the total shortfall, but i captures only βᵢ of that benefit. When the POI is overloaded, i internalizes only βᵢ of the marginal overflow cost.

## The central benchmark

The central planner solves

\[
\max_{\{a_i\}}
\sum_i U_i^0
-\lambda^-\sum_t[D_t-Q_t]^+
\]

subject to the battery constraints and the hard POI constraint

Qₜ≤ K.

This is regime R1. It is the first-best operational benchmark conditional on realized wind, prices, fixed asset sizes, and the model’s delivery target.

It is not an equilibrium: one controller owns the full decision vector and internalizes all system consequences.

## The selfish equilibrium: R2

R2 is the project’s main game-theoretic object. Each agent sees the full state—everybody’s wind, state of charge, prices, and planned actions—and chooses a best response to the other agents’ plans:

\[
a_i^* \in
\arg\max_{a_i\in\mathcal A_i}
U_i(a_i,a_{-i}^*).
\]

The code computes this using damped Gauss–Seidel best responses over the whole daily path. It calls the outcome converged only when both:

\[
\max_{i,t}\frac{\left|BR_{q,i,t}-q_{i,t}\right|}{\sum_j N_j}
\le 10^{-5},
\]

and the largest final unilateral gain is at most $1.

So R2 is an approximate pure-strategy Nash equilibrium of the implemented soft-penalty planning game. It is not a proof of uniqueness or a closed-form equilibrium. The implementation reports non-convergence; roughly 11% of the reported best-response runs do not meet the strict convergence criterion.

Mathematically, each player has a convex physical feasible set and a payoff that is concave in its own dispatch conditional on rivals, which supports the use of best responses. But the common penalty creates coupled incentives, multiple equilibria are possible, and the numerical solver need not find one in every instance.

## A subtle but important implementation distinction

The decentralized planning game permits intended overflow:

[Qₜ-K]⁺>0.

But a physical realization layer then enforces

Qₜʳᵉᵃˡⁱᶻᵉᵈ≤ K

by pro-rata curtailment of positive exporters. Therefore:

- R2 equilibrium is an equilibrium of the announced, soft-penalty dispatch-planning game.
- Realized profit is evaluated after a physical gatekeeper prevents impossible export.
- Attempted overflow is a strategic diagnostic, while realized overflow is zero by construction.

That means the model is intentionally testing whether the incentive system prevents agents from planning infeasible congestion, even though physics ultimately protects the POI.

## Coordination mechanisms: R3a and R3b

R3a changes the penalties so that every player internalizes the full shared cost:

βᵢ⁻=βᵢ⁺=1.

Then a unilateral change by player i changes its payoff by

Δ Uᵢ = Δ Uᵢ⁰-Δ C_{shared}.

This aligns the player’s marginal incentive with the planner’s soft shared-cost objective. It is the cleanest mechanism in the repository: agents remain independent, but they no longer underweight the common consequence of their action.

R3b adds the central planner’s POI shadow price μₜ:

-μₜ q_{i,t}.

This is intended as a congestion price. However, the implementation does not rebate that payment, so it acts as an extra tax on export. The results show that R3a recovers about 93.5% of the average R1–R2 strategic gap, while R3b recovers only about 45.9%.

## Limited-information cases are not equilibrium solutions

R4a and R4b are decentralized receding-horizon control policies, not Bayesian-Nash or Markov-perfect equilibria.

- R4a: each agent sees its own state plus a lagged aggregate headroom signal.
- R4b: each agent sees only its own state and assumes a fixed capacity-share POI budget.

Each agent solves a private MPC problem using forecasts or realized own information, but does not model opponent beliefs or iterate to a fixed point. Thus the R2-to-R4 gap is partly an information loss and partly a policy-architecture loss.

This is especially important because R4 replaces the system-wide delivery requirement with private delivery commitments:

D_{i,t}=δ_{D} b_{i,t}.

Even when the POI does not bind, private commitments can create an “information gap” because agents cannot pool delivery flexibility.

## What the results imply

For the base case—60 operating days, κ_{K}=0.6—the reported realized system objective is

J = realized energy profit -λ⁻×realized under-delivery.

Key comparisons are:

- Centralization vs. selfish equilibrium:
  \[
    J_{\mathrm{R1}}-J_{\mathrm{R2}}
    \approx \$724/\text{day}
    \]
  on average, about 1.5% of R1. This is heavy-tailed: the median is only $193/day, but stressed days can be much worse.
- Full information vs. aggregate-information MPC:
  \[
    J_{\mathrm{R2}}-J_{\mathrm{R4a}}
    \approx \$2{,}459/\text{day}.
    \]
  In this setup, limited information/policy design costs more than selfishness under full information.
- Perfect foresight vs. forecast operation:
  \[
    J_{\mathrm{R1}}-J_{\mathrm{R1_f}}
    \approx \$6{,}613/\text{day}.
    \]
  Forecast error is the largest modeled source of value loss.

## The monitoring game is a second, preliminary game

The repository also begins an enforcement problem. A monitor observes

y_{i,t}=m_{i,t}+ε_{i,t},

where m_{i,t} is deliberate withholding and ε_{i,t} is wind/forecast/measurement noise.

The monitor sanctions when y_{i,t}>τ, producing:

\[
q_0=\Pr(\text{sanction}\mid m=0),
\qquad
q_1=\Pr(\text{sanction}\mid m>0).
\]

For a one-shot deviation gain g, discount factor δ, and enforcement delay d, the required fine is

           δ⁻ᵈ-q₁
F^{*} = g  ──────.
           q₁-q₀

This is an inspection/deterrence calculation: noisy renewable output makes small strategic withholding difficult to distinguish from innocent forecast error. It is not yet a live repeated game coupled to the dispatch equilibrium; withholding, adaptive monitoring, attacks, and resilience are explicitly future work.

## Bottom line

The core game is best described as:

┌────────────────────────────────────────────────────────────────────────┐
│  a finite-horizon, price-taking, dynamic congestion game with storage  │
└────────────────────────────────────────────────────────────────────────┘

or, less formally:

┌────────────────────────────────────────────────────────────────┐
│  a common-pool shared-wire game with intertemporal batteries.  │
└────────────────────────────────────────────────────────────────┘

Its central question is not “who can move the electricity price?” It is:

> When independently owned hybrid resources share a physical export bottleneck, can individually rational battery dispatch reproduce coordinated operation—and how much do information, incentives, and imperfect monitoring matter when it cannot?

The main source material is DESIGN.md (docs/DESIGN.md), proposal.tex (docs/proposal.tex), Workshop 1 report (docs/workshop1/report.md), and the implemented solvers in game.py (code/wargame/solvers/game.py), agent_lp.py (code/wargame/solvers/agent_lp.py), central.py (code/wargame/solvers/central.py), and realize.py (code/wargame/solvers/realize.py).
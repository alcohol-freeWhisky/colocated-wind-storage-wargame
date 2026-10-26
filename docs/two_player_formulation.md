# Minimal two-player formulation

The smallest version of the model that still contains the mechanism the experiments measure has two co-located wind-storage units sharing one point of interconnection (POI), a per-hour delivery obligation, and penalties for falling short of the obligation or exceeding the POI. It is the model in `DESIGN.md` with N = 2. Section 4 reduces it further to a two-hour example that can be solved by hand and that reproduces the strategic loss observed in the simulations.

## 1. Primitives

Players i ∈ {1, 2}. Hours t ∈ {1, …, T}.

Exogenous data, known to both players under perfect foresight (factor F2 = P) or replaced by day-ahead forecasts for hours after the current one (F2 = F):

- $W_{it} \ge 0$: available wind power of unit i in hour t (MW, hourly energy in MWh).
- $\pi_t$: real-time price ($/MWh), taken as given.
- $b_{it}$: day-ahead baseline of unit i; the system delivery obligation is $D_t = \delta_D (b_{1t} + b_{2t})$.
- $K$: POI export limit (MW).
- $\lambda^-$, $\lambda^+$: shortfall and overflow penalty rates ($/MWh).

Battery of unit i: energy capacity $E_i$, power limit $P_i$, charging and discharging efficiencies $\eta_c, \eta_d$, degradation cost $C_{\mathrm{deg}}$ per MWh discharged, initial state of charge $s_{i,1} = s_i^0$.

## 2. Decisions, physics, and payoffs

Decisions of unit i in hour t: curtailment $r_{it}$, charging $c_{it}$, discharging $d_{it}$, all non-negative.

Net injection and aggregate:

$$q_{it} = W_{it} - r_{it} - c_{it} + d_{it}, \qquad Q_t = q_{1t} + q_{2t}.$$

Battery dynamics and bounds:

$$s_{i,t+1} = s_{it} + \eta_c c_{it} - d_{it}/\eta_d, \quad 0 \le s_{it} \le E_i, \quad 0 \le c_{it}, d_{it} \le P_i, \quad 0 \le r_{it} \le W_{it}, \quad s_{i,T+1} \ge s_i^0 .$$

System violations:

$$V_t^- = (D_t - Q_t)^+, \qquad V_t^+ = (Q_t - K)^+ .$$

Allocation of the penalties to players (factor F3):

- Equal split (EQ): each player pays half of each system penalty, $\lambda^- V_t^-/2$ and $\lambda^+ V_t^+/2$.
- Causal split (INJ): the overflow penalty is shared in proportion to positive injection, $w^+_{it} = q_{it}^+ / (q_{1t}^+ + q_{2t}^+)$ (1/2 when nobody injects), and each player pays the shortfall rate on its own deficit relative to its own commitment, $\lambda^- (D_{it} - q_{it})^+$ with $D_{it} = \delta_D b_{it}$.

Payoff of player i for a joint plan $(q_1, q_2)$ under INJ:

$$u_i = \sum_{t=1}^{T} \Big[ \pi_t q_{it} - C_{\mathrm{deg}} d_{it} - \lambda^- (D_{it} - q_{it})^+ - \lambda^+ w^+_{it} V_t^+ \Big],$$

and under EQ the last two terms are replaced by $\lambda^- V_t^-/2 + \lambda^+ V_t^+/2$.

The overflow shares sum to one, so the overflow charges add up to the system overflow penalty under either rule. Under EQ the shortfall charges also add up to the system shortfall penalty. Under INJ the sum of own-deficit charges is at least the system shortfall penalty (it exceeds it only when one player over-delivers while the other falls short) and never a multiple of it.

## 3. Solution concepts

Centralized benchmark (F1 = C). One planner chooses both units' decisions to maximize $U$ subject to the physics and to $Q_t \le K$ as a hard constraint. This is a linear program. Its POI multiplier $\mu_t \ge 0$ is the shadow price of POI capacity in hour t.

Decentralized game (F1 = D). Player i chooses its own $(r_i, c_i, d_i)$ to maximize $u_i$, taking the other player's plan as given. The POI limit is not a constraint of player i; it enters only through the overflow penalty term. A pure-strategy Nash equilibrium is a pair of plans in which neither player can gain by changing its own plan alone.

Information (F4):

- FULL: player i knows $q_{jt}$ for all remaining hours when it best-responds (sequential adjustment until a fixed point).
- PRICE: player i sees only $\mu_t$; it maximizes $\sum_t [(\pi_t - \mu_t) q_{it} - C_{\mathrm{deg}} d_{it} - \lambda^- w^-_{it} (D_{it} - q_{it})^+]$ with no overflow term; a coordinator who observes only $Q_t$ raises $\mu_t$ while $Q_t > K$ and lowers it toward zero otherwise.
- NONE: player i sees nothing about j and limits itself to the fixed share $q_{it} \le K N_i/(N_1 + N_2)$.

Realization. After plans are fixed, each hour is executed. If $Q_t > K$ the excess is removed pro rata to positive injections, first from wind (additional curtailment), then from discharge (energy returned to the battery). Realized aggregate injection therefore never exceeds K. The realized system objective is

$$J = \sum_t \Big[ \pi_t \tilde Q_t - C_{\mathrm{deg}}(\tilde d_{1t} + \tilde d_{2t}) - \lambda^- \tilde V_t^- \Big],$$

where tildes denote realized quantities. The overflow penalty does not appear in J because overflow cannot physically occur; it is a planning signal only. The strategic gap is $J^{\mathrm{C}} - J^{\mathrm{D}}$ and the price of anarchy is $J^{\mathrm{C}} / J^{\mathrm{D}}$.

## 4. A two-hour example solvable by hand

Set T = 2, no delivery obligation ($D_t = 0$), and ignore efficiency losses and degradation ($\eta_c = \eta_d = 1$, $C_{\mathrm{deg}} = 0$) so that only the POI mechanism remains.

- Hour 1: high price $\pi_1$. Wind exactly fills the POI, $W_{11} + W_{21} = K$.
- Hour 2: low price $\pi_2 < \pi_1$, no wind, $W_{12} = W_{22} = 0$.
- Each battery holds dischargeable energy $e_i \le P_i$ at the start, and is not required to return to its initial level (one-shot example).

Each player has one real decision: how much of $e_i$ to discharge in hour 1, $d_{i1} \in [0, e_i]$, with the remainder $e_i - d_{i1}$ discharged in hour 2.

Central optimum. Discharging in hour 1 adds nothing to realized export (the POI is already full with wind) and displaces wind that would otherwise be sold. The planner therefore sets $d_{11} = d_{21} = 0$ and sells all stored energy in hour 2:

$$J^{\mathrm{C}} = \pi_1 K + \pi_2 (e_1 + e_2).$$

Decentralized equilibrium (FULL information, EQ shares). Suppose player j discharges $d_{j1}$ in hour 1. Player i's planned payoff from discharging $d_{i1}$ is

$$\pi_1 (W_{i1} + d_{i1}) + \pi_2 (e_i - d_{i1}) - \tfrac{1}{2}\lambda^+ (d_{i1} + d_{j1}),$$

because $Q_1 - K = d_{11} + d_{21}$. The marginal value of one more MWh in hour 1 is $\pi_1 - \pi_2 - \lambda^+/2$, independent of $d_{j1}$. Hence:

- if $\pi_1 - \pi_2 > \lambda^+/2$, the dominant strategy is $d_{i1} = e_i$ for both players;
- if $\pi_1 - \pi_2 < \lambda^+/2$, the dominant strategy is $d_{i1} = 0$ and the equilibrium coincides with the central optimum.

In the first case the planned aggregate is $K + e_1 + e_2$. The realization layer removes the excess pro rata and takes it from wind first, so $e_1 + e_2$ MWh of wind is curtailed, both batteries are empty after hour 1, and nothing is sold in hour 2:

$$J^{\mathrm{D}} = \pi_1 K, \qquad J^{\mathrm{C}} - J^{\mathrm{D}} = \pi_2 (e_1 + e_2), \qquad \mathrm{PoA} = 1 + \frac{\pi_2 (e_1 + e_2)}{\pi_1 K}.$$

With the base-case parameters ($\lambda^+ = 100$ $/MWh) the inefficient equilibrium appears whenever the hour-1 premium over hour 2 exceeds 50 $/MWh, which happens on the high-price days that dominate the simulated strategic gap.

Causal shares (INJ). Player i's anticipated overflow charge becomes $\lambda^+ \, \frac{q_{i1}}{Q_1} (Q_1 - K)$ with $q_{i1} = W_{i1} + d_{i1}$ (all injections are positive here, so $Q_1 = q_{11} + q_{21}$). Its marginal charge is $\lambda^+ \big(1 - K q_{j1}/Q_1^2\big)$, which equals $\lambda^+/2$ in the symmetric case at $Q_1 = K$ and rises toward $\lambda^+$ as player i's injection comes to dominate. Causal shares therefore deter the player who contributes most to the overflow more strongly than equal shares do, but the threshold for the first unit of overflow is the same. The charge is convex in the player's own injection, so the best response remains a convex program (the simulations use this exact form; see `DESIGN.md`).

Price coordination (PRICE). A coordinator who sees $Q_1 > K$ raises $\mu_1$. Player i stops discharging in hour 1 once $\pi_1 - \mu_1 \le \pi_2$. The fixed point is $\mu_1^* = \pi_1 - \pi_2$, at which both players are indifferent and any split with $d_{11} + d_{21} = 0$ is supported; the central optimum is recovered without either player observing the other. This is the shadow price of the central LP in this example: one more MW of POI capacity in hour 1 would allow one more MWh of stored energy to be sold at $\pi_1$ instead of $\pi_2$.

Fixed share (NONE). Each player caps itself at $q_{i1} \le K N_i/(N_1 + N_2)$. If wind is proportional to nameplate this cap equals $W_{i1}$, so neither player discharges in hour 1 and the central optimum is recovered by the rule, with no information exchanged. If wind is not proportional to nameplate, the cap binds asymmetrically: one player curtails wind it could have sold while the other has unused room, which is the information loss measured by the FULL − NONE contrast.

## 5. What the example leaves out and the full model adds

- The delivery obligation $D_t$ and the shortfall penalty, which create the mirror-image free-riding problem (each player would rather let the other cover a low-price hour).
- Battery dynamics across 24 hours, efficiency losses and degradation, which make the central allocation of discharge across hours non-trivial.
- Forecast error (F2 = F), under which the players' plans and the coordinator's prices are built from day-ahead information and realized against real-time wind and prices.
- Five units with heterogeneous size and real ERCOT wind series, which determine how often and how severely the hour-1 condition above is met.

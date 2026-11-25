# Defining the game: findings and decisions

This document records the starting point for defining the game. Assumptions are proposals until confirmed.

## 1. Physical setting

Several wind and battery assets may share a point of interconnection with the grid. NREL describes multiple hybrid-plant configurations, including arrangements with a shared substation and a plant controller. The actual ownership and control arrangements depend on the site. [NREL: Renewable Energy and Storage](https://www.nrel.gov/docs/fy24osti/89921.pdf)

Let $i\in\{1,\ldots,N\}$ index owners, and $t$ index time periods. If $x_{i,t}$ is owner $i$'s actual export in MW and $K$ is the site's export limit in MW, then

$$
\sum_{i=1}^N x_{i,t}\leq K.
$$

This is a physical or contractual limit on aggregate export. For now, it does not specify how the site handles imports or losses; those details need to be defined later.

## 2. Who makes decisions?

- **Independent owners:** Each owner controls its own assets and values its own payoff. Their choices can interact through the shared connection. This can be modeled as a game.
- **One controlling entity:** One decision maker controls all assets to maximize a common objective. This gives a centralized optimization problem. A game would require another source of conflicting interests.

The current project assumes five independent wind–battery owners. That is a modeling assumption; the references reviewed so far do not establish that it describes Anchor Wind's actual ownership, shared connection, or operating agreement. Until verified, call the case a **hypothetical site inspired by the available data**.

## 3. The connection rule is a separate choice

The limit $\sum_i x_{i,t}\leq K$ alone does not say how headroom is divided. A site controller or agreement must specify the rule, including what happens when a participant cannot use its allocation.

The existing model proposes allocation in proportion to reported capability. This is an illustrative mechanism; it has not been verified as Anchor Wind's rule or as ERCOT's market-clearing rule. Other rules, such as fixed shares with reallocation of unused capacity, are possible benchmarks.

## 4. Proposed first model

Begin with **two independent owners**, each with wind and a battery, sharing one export limit. Two owners are enough to study strategic interaction; later simulations can use five units if the data support that choice.

For the first model, determine in order:

1. Which physical actions each owner controls and what the controller observes.
2. How shared headroom is allocated and whether unused capacity is reassigned.
3. Each owner's revenue, costs, and information.
4. When owners act and what equilibrium means.
5. Only then, whether a report can be manipulated and how monitoring works.

## 5. Decision to confirm

Should the project begin with a **hypothetical two-owner site**, or is reproducing **Anchor Wind's actual ownership and operating arrangement** essential? If the latter, obtain evidence on ownership, control, metering, interconnection rights, and the allocation agreement before treating them as facts.

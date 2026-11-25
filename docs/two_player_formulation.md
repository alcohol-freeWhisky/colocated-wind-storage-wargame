# Minimal Two-Owner Formulation

Two wind-battery owners share one export connection of capacity `K`. Owner `i`
chooses curtailment `r_it`, charging `c_it`, and discharging `d_it`:

```text
q_it = W_it - r_it - c_it + d_it
s_i,t+1 = s_it + eta_c c_it - d_it / eta_d
```

Wind-only charging, battery power/energy limits, and a terminal state-of-charge
condition apply. There is no minimum-delivery target.

Let `Q_t = q_1t + q_2t` and `V_t = [Q_t - K]+`. Owner `i` receives its own
energy revenue, pays its battery degradation cost, and receives one allocation
of the fixed overflow charge:

```text
U_i = sum_t pi_t q_it - c_deg,i sum_t d_it
      - lambda_plus sum_t w_it V_t
```

Equal allocation uses `w_1t = w_2t = 1/2`. Causal allocation uses each owner's
share of positive injection. Under either rule, owner charges add to
`lambda_plus * V_t`.

The Nash profile is a fixed point of owner best responses. The planner instead
maximizes joint energy margin subject to `Q_t <= K`. Comparing their common
realized system value isolates the cost of separate decisions.

## Two-hour intuition

Each owner has 1 MWh of wind in hour 1, a 1 MWh initially empty battery, and no
wind in hour 2. Prices are 20 and 100 $/MWh, discharge wear is 5 $/MWh, and the
shared connection is 1 MW. If both store for hour 2, each exports 0.5 MWh there
and joint profit is 95 dollars. Coordinating one owner to sell in hour 1 and the
other to store produces 115 dollars. This isolates congestion timing; it is not
a computed equilibrium of every continuous-game instance.

# Design and Implementation Contract

## 1. Experimental unit

One episode is one complete 24-hour ERCOT operating day. The base site contains
five Anchor Wind resources, each represented as a wind-battery owner. All cells
use the same physical parameters, POI limit, realization rule, and evaluation
metric.

## 2. Input contract

| Field | Meaning | Use |
|---|---|---|
| `W_avail` | Realized available wind, hourly SCED HSL | Current truth and perfect foresight |
| `What_cop` | COP HSL forecast | Future wind in forecast cells |
| `pi_RT` | Hourly RT settlement-point price | Realized revenue and perfect foresight |
| `pi_DA` | Hourly DA settlement-point price | Future price forecast in forecast cells |
| `b_dam` | Disclosed resource-level DAM award | Provenance only; not used by the operating game |
| `N_i` | Calibrated wind nameplate | Battery and POI scaling |

COP is never substituted for a missing DAM award. There is no constructed
`b_baseline`, minimum-delivery target, or shortfall charge.

## 3. Physics

For owner `i` and hour `t`:

```text
g_it = W_it - c_it - r_it
q_it = g_it + d_it
0 <= c_it, d_it <= P_i
0 <= r_it, c_it + r_it <= W_it
s_i,t+1 = s_it + eta_c c_it - d_it / eta_d
0 <= s_it <= E_i
s_i,T >= s_i,0
```

The base case is wind-only charging. A small activity tie-break and an exact
cycle-removal transformation eliminate simultaneous charge/discharge without
changing injection or state-of-charge evolution.

The central planner has the hard planning constraint `sum_i q_it <= K`. Owner
plans may attempt to exceed `K`; their payoff includes a fixed attempted-
overflow charge. Physical realization applies one common factor to wind export
and battery discharge when aggregate requested export exceeds `K`. Unaccepted
wind is spilled and unexecuted discharge stays in storage.

## 4. Objectives

The central planner maximizes `sum_t pi_t q_total,t` less discharge degradation.
Owner `i` maximizes the same private energy margin less its allocated share:

```text
U_i = sum_t pi_t q_it - c_deg,i sum_t d_it
      - lambda_plus sum_t w_it [sum_j q_jt - K]+
```

`lambda_plus` is fixed at 100 $/MWh in every owner cell.

- `EQ`: `w_it = 1/N`.
- `INJ`: `w_it = q_it+ / sum_j q_jt+`, with an equal fallback only when all
  positive injections are zero.

Both rules allocate the same total attempted-overflow charge. The exact causal
owner term is solved as a convex DPP problem with Clarabel.

The common ex-post metric is realized energy margin. Overflow charges are
internal incentives and are not part of system value.

## 5. Matched ablation matrix

| Factor | Levels | Controlled comparison |
|---|---|---|
| F1 control | planner / owners | Central versus owners at fixed foresight |
| F2 foresight | perfect / forecast | `P - F` with other factors fixed |
| F3 allocation | causal / equal | `INJ - EQ` with other factors fixed |
| F4 information | full / aggregate / none | Pairwise contrasts with other factors fixed |

The slide-compatible `PRICE` ID denotes aggregate information:

- `FULL`: owner-level rival plans are available and converted to aggregate net
  and positive rival injection.
- `PRICE`: only aggregate net and positive injection are provided.
- `NONE`: no current rival signal is provided; the owner solves against zero
  rivals without a private POI quota.

FULL and PRICE use identical sequential best-response updates, damping, warm
starts, tolerances, payoffs, and constraints. Since the payoff is aggregative,
they may coincide; this tests whether identities add value beyond sufficient
aggregate information.

## 6. Foresight and receding horizon

Every policy replans hourly and implements only its first hour. Perfect cells
use realized remaining wind and RT prices. Forecast cells use current truth,
then COP wind and DA price. Realized state of charge becomes the next initial
condition. If wind-only charging makes the original return target unreachable
under the current information view, the target is capped at the maximum
physically reachable terminal SOC. The same rule applies to planner and owners.

## 7. Completion gates

Owner cells are accepted only when the maximum unilateral payoff improvement is
no greater than one dollar (a one-dollar epsilon-Nash criterion). The undamped
best-response residual is retained as a diagnostic but is not a rejection rule,
because non-unique best responses can remain far apart in dispatch space while
having negligible payoff difference. Formal runs also reject realized POI
overflow and planned or realized simultaneous charge/discharge.

## 8. Output contract

`07_design_matrix.py` writes daily rows, summaries, matched contrasts, figures,
and one representative-day trajectory per cell. CSV files have metadata
sidecars. `06_make_report.py` reads those artifacts and does not rerun models.

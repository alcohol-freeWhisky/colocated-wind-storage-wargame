"""TOY 5: where the battery enters (physics + Example A).

Part 1. One owner with wind + battery, behind a shared connection, over 6 hours.
        The battery follows a fixed RULE (not a fixed schedule): send as much
        as the share allows, wind first, then battery; store wind that cannot
        be sent. The rule reacts to the share.
        Shows: (a) available power = wind + what the battery can discharge;
               (b) the battery stores wind that the connection cannot take;
               (c) energy that could not be sent stays in the battery.
Part 2. Example A (Appendix A of the proposal): two owners choose WHEN to use
        the connection. Computes the 2 x 2 payoff table and the equilibrium.

Run:  python toy05_battery_basics.py
"""
import numpy as np

print("=" * 70)
print("PART 1. One owner, wind + battery, fixed simple rule")
print("=" * 70)
# ---- numbers you can change ---------------------------------------------
wind = np.array([20.0, 30.0, 30.0, 10.0, 5.0, 0.0])   # wind available each hour (MW)
share = np.array([15.0, 15.0, 15.0, 15.0, 15.0, 15.0])  # share given each hour (MW)
P, E, ETA = 10.0, 20.0, 0.92       # battery power (MW), energy (MWh), one-way efficiency
soc = 5.0                          # energy stored at the start (MWh)
# -------------------------------------------------------------------------
print(f"{'hour':>4} {'wind':>5} {'avail a':>8} {'share':>6} {'sent x':>7} {'from batt':>9} "
      f"{'charged':>8} {'spilled':>8} {'stored after':>12}")
for t in range(len(wind)):
    dis_max = min(P, soc * ETA)                 # what the battery can deliver now
    a = wind[t] + dis_max                       # AVAILABLE POWER this hour
    x = min(a, share[t])                        # sent: limited by a and by the share
    wind_used = min(wind[t], x)
    dis = x - wind_used                         # battery covers the rest
    leftover = wind[t] - wind_used              # wind that could not be sent
    ch = min(P, leftover, (E - soc) / ETA)      # store what fits
    spill = leftover - ch
    soc = soc - dis / ETA + ch * ETA            # battery changes only with ACTUAL flows
    print(f"{t:4d} {wind[t]:5.1f} {a:8.1f} {share[t]:6.1f} {x:7.1f} {dis:9.1f} "
          f"{ch:8.1f} {spill:8.1f} {soc:12.1f}")
print("""
Read the table:
 - 'avail a' is what the owner can really send (wind + battery). This is the
   true value its report should match.
 - In windy hours the share is the limit: the battery stores the extra wind,
   and only what does not fit is spilled.
 - In calm hours the battery fills the share. Energy is never lost from the
   battery because the connection was busy: it simply stays stored.
 - The battery follows a FIXED RULE (send as much as allowed, store the
   rest). The rule is the same in every hour and for every owner, so
   'available power' has one clear meaning: wind now + the most the battery
   can discharge now. The owner does not choose its battery strategy here;
   that is the Example A game below.""")

print("=" * 70)
print("PART 2. Example A: two owners choose WHEN to use the connection")
print("=" * 70)
K, p1, p2, wear = 1.0, 20.0, 100.0, 5.0      # 1 MW connection, prices $20 then $100
# each owner has 1 MWh of wind in hour 1: Sell now (S) or Store for hour 2 (C)


def payoff(s1, s2):
    now = [s == "S" for s in (s1, s2)]
    n_now, n_later = sum(now), 2 - sum(now)
    out = []
    for sells_now in now:
        if sells_now:
            out.append(p1 * min(1, K / n_now))
        else:
            out.append((p2 - wear) * min(1, K / n_later))
    return tuple(out)


print(f"{'':16}{'owner 2: Store':>18}{'owner 2: Sell now':>20}")
for s1, lab in (("C", "owner 1: Store"), ("S", "owner 1: Sell now")):
    print(f"{lab:16}{str(payoff(s1, 'C')):>18}{str(payoff(s1, 'S')):>20}")
best = max(sum(payoff(a, b)) for a in "CS" for b in "CS")
print(f"""
Storing is better for each owner whatever the other does: if the other
stores, 47.5 > 20; if the other sells now, 95 > 10.
So both store, earn {sum(payoff('C', 'C')):.0f} in total, and crowd hour 2.
Best joint plan earns {best:.0f}: one sells early, one stores.
This is the battery-timing game. On real data its loss was small (about 0.24%),
so it is an extension, not the main game.""")

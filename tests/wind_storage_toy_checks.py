"""Reproducible toy examples for the wind-storage wargame (Levels 1--3).

Run: python wind_storage_toy_checks.py
Uses only the Python standard library. This is NOT the full ERCOT simulator.
"""

from math import isclose


def proportional(requests, capacity=1.0):
    """Allocate a nonnegative shared export capacity pro rata to requests."""
    assert capacity >= 0 and all(q >= 0 for q in requests)
    total = sum(requests)
    scale = min(1.0, capacity / total) if total > 0 else 1.0
    delivered = tuple(q * scale for q in requests)
    assert sum(delivered) <= capacity + 1e-9
    return delivered


def operating_game():
    """Level 1: two players, two hours; C=charge, S=sell now."""
    payoffs = {}
    for a in ("C", "S"):
        for b in ("C", "S"):
            actions = (a, b)
            sold_now = proportional([1.0 if x == "S" else 0.0 for x in actions])
            discharged = proportional([1.0 if x == "C" else 0.0 for x in actions])
            # Hour 1 price = $20; hour 2 price = $100; degradation = $5/MWh.
            payoffs[actions] = tuple(
                20.0 * sold_now[i] + 95.0 * discharged[i]
                for i in range(2)
            )

    assert payoffs["S", "S"] == (10.0, 10.0)
    assert payoffs["C", "S"] == (95.0, 20.0)
    assert payoffs["S", "C"] == (20.0, 95.0)
    assert payoffs["C", "C"] == (47.5, 47.5)

    equilibria = []
    for (a, b), (u1, u2) in payoffs.items():
        if all(u1 >= payoffs[other, b][0] - 1e-9 for other in ("C", "S")) and all(
            u2 >= payoffs[a, other][1] - 1e-9 for other in ("C", "S")
        ):
            equilibria.append((a, b))
    assert equilibria == [("C", "C")]
    optimum = max(sum(values) for values in payoffs.values())
    assert optimum == 115.0
    return payoffs, equilibria, optimum


def reporting_game():
    """Level 2: false export nominations under shared-capacity allocation."""
    feasible = (0.2, 1.0)
    truthful = proportional(feasible)
    inflated_rights = proportional((1.5, 1.0))
    inflated_delivery = tuple(min(feasible[i], inflated_rights[i]) for i in range(2))
    price = 100.0
    private_gain = price * (inflated_delivery[0] - truthful[0])
    lost_total_revenue = price * (sum(truthful) - sum(inflated_delivery))
    assert isclose(private_gain, 10 / 3, abs_tol=1e-8)
    assert isclose(lost_total_revenue, 40.0, abs_tol=1e-8)
    return truthful, inflated_delivery, private_gain, lost_total_revenue


def noisy_inspection(private_gain, inspection_probability=0.10, fine=40.0):
    """Level 2.5: fine-only expected gains; no fine for compliant reports."""
    return {
        detection_probability: private_gain - inspection_probability * detection_probability * fine
        for detection_probability in (1.0, 0.5)
    }


def dynamic_inspection(g=4.0, fine=20.0, harm=20.0, audit_cost=2.0,
                       q1=0.5, n_max=2):
    """Level 3: fine-only recursive inspection game.

    One audit uses one budget unit. A detected violation incurs a fine and
    terminates the inspection episode. Undetected violations earn g and harm
    the inspector by harm. q0=0, no false-alarm cost, no disgorgement.

    Assumes an interior mixed equilibrium at each evaluated state. For other
    parameters, boundary/pure equilibria must be computed separately.
    """
    V = {(0, m): 0.0 for m in range(n_max + 1)}
    I = {(0, m): 0.0 for m in range(n_max + 1)}
    mixed = {}

    for n in range(1, n_max + 1):
        V[n, 0], I[n, 0] = n * g, -n * harm
        for m in range(1, n + 1):
            vk, ik = V[n - 1, min(m, n - 1)], I[n - 1, min(m, n - 1)]
            vu, iu = V[n - 1, m - 1], I[n - 1, m - 1]
            p = g / (q1 * (fine + vu))
            r = (audit_cost + ik - iu) / (q1 * (harm - iu))
            if not (0 < p < 1 and 0 < r < 1):
                raise ValueError(f"No interior equilibrium at {(n, m)}: p={p}, r={r}")
            V[n, m] = p * vu + (1 - p) * vk
            I[n, m] = ik - r * harm
            mixed[n, m] = (p, r)

    assert isclose(mixed[1, 1][0], 0.4)
    assert isclose(mixed[1, 1][1], 0.2)
    assert isclose(mixed[2, 1][0], 1 / 3)
    assert isclose(mixed[2, 1][1], 0.9)
    return mixed


def main():
    payoffs, equilibria, optimum = operating_game()
    print("Level 1: payoffs", payoffs)
    print(f"  Nash equilibria: {equilibria}; Nash total $95.00; joint optimum ${optimum:.2f}")

    truthful, inflated, gain, loss = reporting_game()
    print(f"Level 2: truthful deliveries={truthful}, inflated-report deliveries={inflated}")
    print(f"  Private gain ${gain:.2f}; reduction in total revenue ${loss:.2f}")

    outcomes = noisy_inspection(gain)
    print("Level 2.5: net gains from misreporting:",
          {f"q1={q1:.0%}": round(value, 2) for q1, value in outcomes.items()})

    mixed = dynamic_inspection()
    print("Level 3: (audit probability, violation probability):")
    for state in ((1, 1), (2, 1)):
        print(f"  {state}: {tuple(round(v, 3) for v in mixed[state])}")
    print("All tests passed.")


if __name__ == "__main__":
    main()

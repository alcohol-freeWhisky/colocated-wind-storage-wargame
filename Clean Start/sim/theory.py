"""Closed-form results of spec Section 9, used to check the simulation against the math.

Notation: a = K S / L^2, with S = sum of rivals' reports and L = total reports (congested hour, rule R).
p_hat = value of one more MWh exported now: p if it displaces curtailment, p - V_s if it displaces charging.
"""
from __future__ import annotations


def a_coef(K: float, S: float, L: float) -> float:
    return K * S / L**2


def V_s(eta_c: float, eta_d: float, p_tilde: float, wear: float) -> float:
    """Value of one MWh of surplus wind stored instead of exported now: eta_c eta_d (p_tilde - wear)."""
    return eta_c * eta_d * (p_tilde - wear)


def P1_marginal(rule: str, lam: float, p_hat: float, a: float = 0.0) -> float:
    """dU/dl under S0 (hide): C -> lam; R -> lam (1 - a) + p_hat a."""
    return lam if rule == "C" else lam * (1 - a) + p_hat * a


def P2_marginal(rule: str, lam: float, p: float, a: float, displaces: str, Vs: float = 0.0) -> float:
    """dU/dl under S2 (fixed trigger, non-binding cap). C -> 0.
    R, displaces curtailment: (p - lam) a. R, displaces charging: (p - V_s) a."""
    if rule == "C":
        return 0.0
    return (p - lam) * a if displaces == "curtailment" else (p - Vs) * a


def P3_alpha_star(rule: str, lam: float, f: float, z: float, p: float = 0.0, a: float = 0.0) -> float:
    """Smallest random-audit probability that deters a small inflation (S1, beyond tolerance,
    curtailment case): C -> lam / (z (lam + f)); R -> (lam + (p - lam) a) / (z (lam + f))."""
    num = lam if rule == "C" else lam + (p - lam) * a
    return num / (z * (lam + f))


def P4_relabel_gain(lam_q: float, lam_c: float) -> float:
    return lam_q - lam_c

"""Hidráulica de tuberías a presión: Colebrook-White + Darcy-Weisbach."""
import math

G = 9.81


def velocity(Q: float, D: float) -> float:
    """V = 4Q/(πD²). Q en m³/s, D en m."""
    return 4.0 * Q / (math.pi * D**2)


def reynolds(V: float, D: float, nu: float) -> float:
    return V * D / nu


def friction_factor(Re: float, rel_rough: float) -> float:
    """Colebrook-White resuelto por punto fijo. Laminar si Re<2300."""
    if Re <= 0:
        return 0.0
    if Re < 2300:
        return 64.0 / Re
    f = 0.02
    for _ in range(100):
        rhs = -2.0 * math.log10(rel_rough / 3.7 + 2.51 / (Re * math.sqrt(f)))
        f_new = (1.0 / rhs) ** 2
        if abs(f_new - f) < 1e-12:
            return f_new
        f = f_new
    return f


def hf_darcy(f: float, L: float, D: float, V: float) -> float:
    """Pérdidas por fricción Darcy-Weisbach [m]."""
    return f * (L / D) * V**2 / (2.0 * G)


def hl_local(sum_km: float, V: float) -> float:
    """Pérdidas locales ΣKm·V²/2g [m]."""
    return sum_km * V**2 / (2.0 * G)

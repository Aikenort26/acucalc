"""Método clásico de Allievi para el golpe de ariete por maniobra de válvula en
una conducción simple sin fricción (ecuaciones encadenadas), con Joukowsky y
Michaud como cotas cerradas. Sirve de segundo motor para validar el MOC.

Referencias: Allievi (1925); Wylie, Streeter y Suo (1993)."""
import math
from typing import Callable

G = 9.81


def joukowsky(a: float, dV: float) -> float:
    """Sobrepresión por cambio instantáneo de velocidad: ΔH = a·ΔV/g [m]."""
    return a * dV / G


def michaud(L: float, V0: float, Tc: float) -> float:
    """ΔH = 2·L·V0/(g·Tc) para reducción lineal de la velocidad en Tc ≥ 2L/a."""
    return 2 * L * V0 / (G * Tc)


def tiempo_critico(a: float, L: float) -> float:
    """Periodo de ida y vuelta de la onda: 2L/a [s]."""
    return 2 * L / a


def clasificar(Tc: float, a: float, L: float) -> str:
    """Maniobra rápida (Tc ≤ 2L/a: rige Joukowsky) o lenta (rige Michaud)."""
    return "rápida" if Tc <= tiempo_critico(a, L) else "lenta"


def longitud_critica(Tc: float, a: float) -> float:
    """Longitud a partir de la cual una maniobra de duración Tc es rápida: a·Tc/2."""
    return a * Tc / 2


def rho(a: float, V0: float, H0: float) -> float:
    """Constante de Allievi ρ = a·V0/(2·g·H0), con H0 la carga neta en la válvula."""
    return a * V0 / (2 * G * H0)


def cierre_instantaneo(t: float) -> float:
    return 1.0 if t <= 0 else 0.0


def cierre_lineal(Tc: float) -> Callable[[float], float]:
    return lambda t: 1.0 if t <= 0 else max(0.0, 1 - t / Tc)


def cierre_potencial(Tc: float, Em: float) -> Callable[[float], float]:
    """τ = (1 − t/Tc)^Em: Em > 1 cierra rápido al inicio y lento al final."""
    return lambda t: 1.0 if t <= 0 else max(0.0, 1 - t / Tc) ** Em


def apertura_lineal(Ta: float) -> Callable[[float], float]:
    return lambda t: 0.0 if t <= 0 else min(1.0, t / Ta)


def cadena(tau: Callable[[float], float], a: float, L: float, V0: float, H0: float,
           Hd: float, dt: float, n_pasos: int) -> list:
    """Cabeza en la válvula en t = n·dt por las ecuaciones encadenadas de Allievi.
    Con h = H − Hd, v = V/V0 y T = 2L/a:
        h_t + h_{t−T} − 2·h0 = (a·V0/g)·(v_{t−T} − v_t),   v_t = τ_t·√(h_t/h0),
    que con ζ² = h/h0 y ρ = a·V0/(2g·h0) es la forma clásica
        ζ_t² + ζ_{t−T}² − 2 = 2ρ(τ_{t−T}·ζ_{t−T} − τ_t·ζ_t).
    Con la válvula cerrada (τ = 0) la relación es lineal y admite h < 0. Si con
    la válvula abierta h resultaría negativo (flujo inverso) se devuelve NaN.
    Antes de t = 0 rige el régimen permanente (h = h0, v = 1)."""
    T = tiempo_critico(a, L)
    rezago = round(T / dt)
    if abs(rezago * dt - T) > 1e-9 * T:
        raise ValueError("2L/a debe ser múltiplo entero de dt")
    h0 = H0 - Hd
    k = a * V0 / G
    h = [h0] * (n_pasos + 1)
    v = [1.0] * (n_pasos + 1)
    for n in range(1, n_pasos + 1):
        m = n - rezago
        h_m, v_m = (h[m], v[m]) if m > 0 else (h0, 1.0)
        S = 2 * h0 - h_m + k * v_m
        tau_n = tau(n * dt)
        if tau_n <= 0:
            h[n], v[n] = S, 0.0
            continue
        r = rho(a, V0, h0) * tau_n
        K = S / h0
        if K < 0 or math.isnan(S):
            h[n] = v[n] = float("nan")
            continue
        zeta = -r + math.sqrt(r * r + K)
        h[n], v[n] = h0 * zeta * zeta, tau_n * zeta
    return [Hd + hn for hn in h]

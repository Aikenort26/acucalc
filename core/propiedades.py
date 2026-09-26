"""Propiedades del agua y de la atmósfera para NPSH y transitorios.

- Presión de vapor: IAPWS-IF97, región 4, ecuación de saturación (IAPWS
  R7-97(2012), ec. 30), válida de 273.15 K a 647.096 K.
- Presión atmosférica: atmósfera estándar ISA (ISO 2533), troposfera."""
import math

G0 = 9.80665                 # m/s², gravedad estándar

_N = (0.11670521452767e4, -0.72421316703206e6, -0.17073846940092e2,
      0.12020824702470e5, -0.32325550322333e7, 0.14915108613530e2,
      -0.48232657361591e4, 0.40511340542057e6, -0.23855557567849,
      0.65017534844798e3)

# ISA troposfera
_P0, _T0, _L = 101325.0, 288.15, 0.0065        # Pa, K, K/m
_M, _R = 0.0289644, 8.31446                     # kg/mol, J/(mol·K)
_EXP = G0 * _M / (_R * _L)                      # ≈ 5.2559


def presion_vapor_pa(t_c: float) -> float:
    """Presión de saturación del agua [Pa] a la temperatura t_c [°C]."""
    t = t_c + 273.15
    if not 273.15 <= t <= 647.096:
        raise ValueError(f"Temperatura fuera del rango de IF97 región 4: {t_c} °C")
    n = _N
    th = t + n[8] / (t - n[9])
    a = th * th + n[0] * th + n[1]
    b = n[2] * th * th + n[3] * th + n[4]
    c = n[5] * th * th + n[6] * th + n[7]
    return (2 * c / (-b + math.sqrt(b * b - 4 * a * c))) ** 4 * 1e6


def presion_atmosferica_pa(z_m: float) -> float:
    """Presión atmosférica estándar [Pa] a la altitud z_m [m s.n.m.]
    (troposfera, hasta 11 km)."""
    return _P0 * (1 - _L * z_m / _T0) ** _EXP


def carga_m(p_pa: float, rho: float) -> float:
    """Presión [Pa] expresada en metros de columna del fluido de densidad rho."""
    return p_pa / (rho * G0)

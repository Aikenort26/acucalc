"""Proyección de población: tasas y métodos RAS/Res 0330."""
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class RateRow:
    year: int
    aritmetica: float
    geometrica: float
    exponencial: float
    wappaus: float


@dataclass(frozen=True)
class GrowthRates:
    aritmetica: float
    geometrica: float
    exponencial: float
    wappaus: float


def growth_rate_rows(censo: list[tuple[int, int]]) -> list[RateRow]:
    """Tasa por fila del censo. Aritmética/geométrica/Wappaus contra el año
    final; exponencial entre pares consecutivos (convención memoria Salado)."""
    if len(censo) < 2:
        raise ValueError("Se requieren al menos 2 registros censales")
    censo = sorted(censo)
    tf, pf = censo[-1]
    rows = []
    for i, (t, p) in enumerate(censo[:-1]):
        n = tf - t
        arit = ((pf - p) / p) / n
        geom = (pf / p) ** (1.0 / n) - 1.0
        t2, p2 = censo[i + 1]
        expo = math.log(p2 / p) / (t2 - t)
        wapp = 2.0 * (pf - p) / (n * (pf + p))
        rows.append(RateRow(t, arit, geom, expo, wapp))
    return rows


def growth_rates(censo: list[tuple[int, int]]) -> GrowthRates:
    rows = growth_rate_rows(censo)
    n = len(rows)
    return GrowthRates(
        aritmetica=sum(r.aritmetica for r in rows) / n,
        geometrica=sum(r.geometrica for r in rows) / n,
        exponencial=sum(r.exponencial for r in rows) / n,
        wappaus=sum(r.wappaus for r in rows) / n,
    )


@dataclass(frozen=True)
class Projection:
    series: dict[str, list[tuple[int, float]]]
    deviations: dict[str, float]   # vs promedio en el año horizonte


def project(p0: float, year0: int, horizon_year: int, rates: GrowthRates,
            tasa_res0844: float = 0.005) -> Projection:
    """Proyecta P0 desde year0 hasta horizon_year por los 5 métodos."""
    years = list(range(year0, horizon_year + 1))
    k, r, e, w = rates.aritmetica, rates.geometrica, rates.exponencial, rates.wappaus
    series = {
        "aritmetico":  [(t, p0 * (1 + k * (t - year0))) for t in years],
        "geometrico":  [(t, p0 * (1 + r) ** (t - year0)) for t in years],
        "exponencial": [(t, p0 * math.exp(e * (t - year0))) for t in years],
        "wappaus":     [(t, p0 * (2 + w * (t - year0)) / (2 - w * (t - year0))) for t in years],
        "res0844":     [(t, p0 * (1 + tasa_res0844) ** (t - year0)) for t in years],
    }
    finals = {m: s[-1][1] for m, s in series.items()}
    mean = sum(finals.values()) / len(finals)
    deviations = {m: (v - mean) / mean for m, v in finals.items()}
    return Projection(series, deviations)


def suggest_method(proj: Projection) -> str:
    """Método con menor desviación absoluta respecto al promedio de los 5
    métodos en el año horizonte (comportamiento más cercano al promedio)."""
    return min(proj.deviations, key=lambda m: abs(proj.deviations[m]))

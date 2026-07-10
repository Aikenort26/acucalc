"""Digitalización de curvas de bomba: calibración de ejes y ajustes.
Funcionalidad tipo WebPlotDigitizer (automeris.io); implementación propia."""
import math
from dataclasses import dataclass

import numpy as np
from scipy.optimize import brentq


@dataclass(frozen=True)
class AxisCalibration:
    px1: float
    val1: float
    px2: float
    val2: float
    log: bool = False

    def __post_init__(self):
        if self.px1 == self.px2:
            raise ValueError("Los dos puntos de calibración tienen el mismo pixel")
        if self.log and (self.val1 <= 0 or self.val2 <= 0):
            raise ValueError("Escala log requiere valores > 0")

    def to_data(self, px: float) -> float:
        f = (px - self.px1) / (self.px2 - self.px1)
        if self.log:
            lv = math.log10(self.val1) + f * (math.log10(self.val2) - math.log10(self.val1))
            return 10.0 ** lv
        return self.val1 + f * (self.val2 - self.val1)


def pixel_to_data(px_xy: tuple[float, float], cal_x: AxisCalibration,
                  cal_y: AxisCalibration) -> tuple[float, float]:
    return cal_x.to_data(px_xy[0]), cal_y.to_data(px_xy[1])


@dataclass(frozen=True)
class CurveFit:
    coeffs: tuple[float, ...]   # numpy polyfit, mayor grado primero
    r2: float
    q_min: float
    q_max: float

    def __call__(self, q: float) -> float:
        return float(np.polyval(self.coeffs, q))


def fit_curve(points: list[tuple[float, float]], degree: int = 2) -> CurveFit:
    """Ajuste polinómico Q→Y por mínimos cuadrados, con R²."""
    if len(points) < degree + 1:
        raise ValueError(f"Se requieren ≥{degree + 1} puntos para grado {degree}")
    q = np.array([p[0] for p in points], dtype=float)
    y = np.array([p[1] for p in points], dtype=float)
    coeffs = np.polyfit(q, y, degree)
    pred = np.polyval(coeffs, q)
    ss_res = float(np.sum((y - pred) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 1.0
    return CurveFit(tuple(coeffs), r2, float(q.min()), float(q.max()))


@dataclass(frozen=True)
class BEP:
    q: float
    e: float


def best_efficiency_point(points_qe: list[tuple[float, float]], degree: int = 2) -> BEP:
    """Máximo de la curva de eficiencia ajustada, dentro del rango de datos."""
    fit = fit_curve(points_qe, degree)
    qs = np.linspace(fit.q_min, fit.q_max, 500)
    es = np.polyval(fit.coeffs, qs)
    i = int(np.argmax(es))
    return BEP(float(qs[i]), float(es[i]))


def operating_point(pump_fit: CurveFit,
                    system_points: list[tuple[float, float]]) -> tuple[float, float] | None:
    """Intersección H_bomba(Q) − H_sistema(Q) = 0 por brentq sobre el rango común.
    Devuelve (Q, H) o None si no hay cruce."""
    sq = np.array([p[0] for p in system_points], dtype=float)
    sh = np.array([p[1] for p in system_points], dtype=float)

    def diff(q: float) -> float:
        return pump_fit(q) - float(np.interp(q, sq, sh))

    lo = max(pump_fit.q_min, float(sq.min()))
    hi = min(pump_fit.q_max, float(sq.max()))
    if lo >= hi:
        return None
    qs = np.linspace(lo, hi, 200)
    vals = [diff(q) for q in qs]
    for a, b, fa, fb in zip(qs, qs[1:], vals, vals[1:]):
        if fa == 0.0:
            return float(a), pump_fit(float(a))
        if fa * fb < 0:
            q_op = brentq(diff, a, b)
            return float(q_op), pump_fit(float(q_op))
    return None


def detect_curve_by_color(img_rgb, target_rgb: tuple[int, int, int],
                          tolerance: int = 40, n_points: int = 30) -> list[tuple[float, float]]:
    """Extrae puntos (px_x, px_y) de la curva cuyo color ≈ target_rgb.
    img_rgb: array HxWx3 uint8 (RGB). Devuelve ≤ n_points ordenados por x
    (mediana de y por banda de x). Lista vacía si no hay pixeles del color."""
    img = np.asarray(img_rgb, dtype=np.int16)
    dist = np.abs(img - np.array(target_rgb, dtype=np.int16)).sum(axis=2)
    mask = dist <= tolerance * 3
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return []
    x_min, x_max = xs.min(), xs.max()
    bands = np.linspace(x_min, x_max + 1, n_points + 1)
    pts = []
    for a, b in zip(bands, bands[1:]):
        sel = (xs >= a) & (xs < b)
        if sel.any():
            pts.append((float(np.median(xs[sel])), float(np.median(ys[sel]))))
    return pts

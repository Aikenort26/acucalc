"""Digitalización de curvas de bomba: calibración de ejes y ajustes.
Implementación propia: calibración de ejes por pixel, ajuste polinómico,
punto de operación y detección de curva por color."""
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
                          tolerance: int = 40, n_points: int = 30,
                          bbox: tuple[int, int, int, int] | None = None,
                          mask_extra=None) -> list[tuple[float, float]]:
    """Extrae puntos (px_x, px_y) de la curva cuyo color ≈ target_rgb, estilo
    WebPlotDigitizer/automeris. Devuelve ≤ n_points ordenados por x.

    Correcciones vs. la versión vieja (que tomaba "puntos aleatorios"):
    - **Distancia euclidiana en RGB** (no L1 cruda): un umbral en L1 de ~180
      hacía match con grises y ejes; la euclidiana con `tolerance` acota mucho
      mejor la vecindad del color objetivo.
    - **Restricción al rectángulo `bbox`** (x0, y0, x1, y1) del área de la
      gráfica — típicamente el rectángulo calibrado. Fuera de ahí quedan ejes,
      texto y leyenda que contaminaban la máscara.
    - **`mask_extra`**: máscara booleana HxW opcional ("pen") para limitar la
      búsqueda a la zona pintada por el usuario.
    - **Clustering por conectividad en cada banda** en vez de la mediana global:
      si en una banda de x coexisten la curva y una línea de rejilla, la mediana
      caía ENTRE ambas (un punto que no está en ninguna). Ahora se toma el
      cluster contiguo de y más grande (la curva es la traza más densa) y se
      devuelve su centro.

    img_rgb: array HxWx3 uint8 (RGB). Lista vacía si no hay pixeles del color."""
    img = np.asarray(img_rgb, dtype=np.float32)
    target = np.array(target_rgb, dtype=np.float32)
    dist = np.sqrt(((img - target) ** 2).sum(axis=2))
    mask = dist <= float(tolerance)
    if bbox is not None:
        x0, y0, x1, y1 = bbox
        x0, x1 = sorted((max(int(x0), 0), min(int(x1), mask.shape[1])))
        y0, y1 = sorted((max(int(y0), 0), min(int(y1), mask.shape[0])))
        recorte = np.zeros_like(mask)
        recorte[y0:y1, x0:x1] = True
        mask &= recorte
    if mask_extra is not None:
        mask &= np.asarray(mask_extra, dtype=bool)
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return []
    x_min, x_max = xs.min(), xs.max()
    bands = np.linspace(x_min, x_max + 1, n_points + 1)
    pts = []
    for a, b in zip(bands, bands[1:]):
        sel = (xs >= a) & (xs < b)
        if not sel.any():
            continue
        ys_band = np.sort(ys[sel])
        y_centro = _cluster_y_dominante(ys_band)
        x_centro = float(np.median(xs[sel]))
        pts.append((x_centro, y_centro))
    return pts


def _cluster_y_dominante(ys_sorted, gap: int = 5) -> float:
    """Centro del cluster contiguo de y más grande (la traza de la curva es más
    densa que una línea de rejilla aislada). `gap`: separación en px que corta
    un cluster del siguiente."""
    inicio = 0
    mejor_ini, mejor_fin = 0, 0
    for i in range(1, len(ys_sorted) + 1):
        if i == len(ys_sorted) or ys_sorted[i] - ys_sorted[i - 1] > gap:
            if (i - inicio) > (mejor_fin - mejor_ini):
                mejor_ini, mejor_fin = inicio, i
            inicio = i
    cluster = ys_sorted[mejor_ini:mejor_fin]
    return float(np.mean(cluster))


def suggest_n2(qh: list[tuple[float, float]], qe: list[tuple[float, float]],
               n1_nominal: float, n_unidades: int, arreglo: str,
               sys_lps: list[tuple[float, float]],
               q_objetivo: float | None = None,
               h_objetivo: float | None = None) -> float | None:
    """Sugiere N₂ (rpm/Hz) tal que el punto de operación de la bomba
    transformada (afinidad N1→N2, luego arreglo ×n_unidades) contra la curva
    de sistema `sys_lps` caiga en `q_objetivo` O `h_objetivo` (exactamente
    uno de los dos, no ambos). Es solo una sugerencia — el llamador decide si
    aplicarla a `PumpData.n2_objetivo`; esta función NO modifica nada.

    Busca la raíz por `brentq` sobre r = N2/N1 en el bracket [0.3, 3.0]
    (afinidad físicamente razonable para el mismo rodete). Devuelve None si
    no se puede evaluar (menos de 3 puntos, N1 <= 0) o si no hay raíz
    acotada en el bracket (el objetivo está fuera de lo alcanzable variando
    N2 solo)."""
    if (q_objetivo is None) == (h_objetivo is None):
        raise ValueError("Debes dar exactamente uno de q_objetivo o h_objetivo")
    if n1_nominal <= 0 or len(qh) < 3:
        return None

    def _objetivo(r: float) -> float | None:
        n2 = n1_nominal * r
        qh_t, _ = apply_pump_transform(qh, qe, n1_nominal, n2, n_unidades, arreglo)
        try:
            fit = fit_curve(qh_t, 2)
        except ValueError:
            return None
        op = operating_point(fit, sys_lps)
        if op is None:
            return None
        return op[0] - q_objetivo if q_objetivo is not None else op[1] - h_objetivo

    lo, hi = 0.3, 3.0
    f_lo, f_hi = _objetivo(lo), _objetivo(hi)
    if f_lo is None or f_hi is None:
        # barrido fino para encontrar un sub-intervalo bracketable, en vez de
        # rendirse ante un solo None en los extremos (ej. r bajo sin cruce)
        rs = np.linspace(lo, hi, 40)
        vals = [_objetivo(r) for r in rs]
        for a, b, fa, fb in zip(rs, rs[1:], vals, vals[1:]):
            if fa is None or fb is None:
                continue
            if fa == 0.0:
                return float(n1_nominal * a)
            if fa * fb < 0:
                r_root = brentq(lambda r: _objetivo(r), a, b)
                return float(n1_nominal * r_root)
        return None
    if f_lo == 0.0:
        return float(n1_nominal * lo)
    if f_lo * f_hi < 0:
        r_root = brentq(lambda r: _objetivo(r), lo, hi)
        return float(n1_nominal * r_root)
    return None


def scale_points(points: list[tuple[float, float]], r: float) -> list[tuple[float, float]]:
    """Leyes de afinidad para el mismo rodete (r = N2/N1): Q → Q·r, H → H·r²."""
    return [(q * r, h * r ** 2) for q, h in points]


def combine_parallel(points: list[tuple[float, float]], n: int) -> list[tuple[float, float]]:
    """n bombas iguales en paralelo: mismo H, Q se multiplica por n."""
    if n < 1:
        raise ValueError("n debe ser ≥ 1")
    return [(q * n, h) for q, h in points]


def combine_series(points: list[tuple[float, float]], n: int) -> list[tuple[float, float]]:
    """n bombas iguales en serie: mismo Q, H se multiplica por n."""
    if n < 1:
        raise ValueError("n debe ser ≥ 1")
    return [(q, h * n) for q, h in points]


def apply_pump_transform(qh: list[tuple[float, float]], qe: list[tuple[float, float]],
                         n1_nominal: float, n2_objetivo: float, n_unidades: int,
                         arreglo: str) -> tuple[list, list]:
    """Aplica afinidad (n1_nominal→n2_objetivo, si ambos > 0 y distintos) y
    luego arreglo (paralelo/serie ×n_unidades, si n_unidades > 1) a puntos
    Q-H/Q-η digitalizados. La eficiencia se desplaza en Q, no en valor.

    Fuente única de la transformación — usada tanto por la UI (página 6,
    comparación interactiva) como por el reporte (`core/report_ctx.build`),
    para que ambos flujos nunca puedan desincronizarse."""
    qh, qe = list(qh), list(qe)
    if n1_nominal > 0 and n2_objetivo > 0 and n2_objetivo != n1_nominal:
        r = n2_objetivo / n1_nominal
        qh = scale_points(qh, r)
        qe = [(q * r, e) for q, e in qe]
    if n_unidades > 1:
        combinar = combine_parallel if arreglo == "paralelo" else combine_series
        qh = combinar(qh, n_unidades)
        if arreglo == "paralelo":
            qe = [(q * n_unidades, e) for q, e in qe]
    return qh, qe

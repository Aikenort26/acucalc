"""Catálogo de bombas candidatas desde Excel (base de datos de curvas).

Formato largo: columnas `Bomba | Q [L/s] | H [m] | eta` (eta opcional),
una fila por punto de curva, filas agrupadas por nombre de bomba."""
import io

import numpy as np
import pandas as pd

from core import curves as cv
from core.project import PumpData

COLS = {"bomba", "q [l/s]", "h [m]"}
N_EXPORT = 10   # nº de puntos de la grilla normalizada de exportación (WP-3d)


def template_xlsx() -> bytes:
    """Plantilla de ejemplo descargable."""
    df = pd.DataFrame({
        "Bomba": ["Ejemplo A"] * 4 + ["Ejemplo B"] * 4,
        "Q [L/s]": [10, 20, 30, 40, 15, 25, 35, 45],
        "H [m]": [52, 48, 41, 30, 60, 55, 46, 33],
        "eta": [0.55, 0.72, 0.78, 0.70, 0.50, 0.68, 0.76, 0.71],
    })
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    return buf.getvalue()


def export_xlsx(bombeos: list) -> bytes:
    """Exporta todas las bombas de todos los sistemas de bombeo en formato
    largo compatible con `parse()` (columnas extra se ignoran al reimportar;
    sirven como referencia).

    WP-3d — corrige un bug real: la versión anterior exportaba la grilla
    digitalizada NOMINAL (`puntos_qh` crudos), ignorando la afinidad
    (N1→N2) y el arreglo (paralelo/serie ×n_unidades) configurados para la
    bomba — es decir, exportaba una curva que la app nunca usó para el punto
    de operación del sistema. Ahora se aplica `cv.apply_pump_transform`
    primero (misma fuente única que usa la comparación interactiva de la
    página 6 y `core/report_ctx.build`) y LUEGO se resamplea a `N_EXPORT`
    puntos equiespaciados en Q sobre el rango de la curva transformada,
    evaluando H y η con los polinomios ajustados (no por interpolación
    lineal de los puntos digitalizados crudos).

    Solo se incluyen bombas con ≥3 puntos Q-H (mismo criterio que
    `core/report_ctx.build` usa para decidir qué bombas entran al reporte —
    fuente de la elección: <3 puntos no alcanza para un ajuste de grado 2).

    Cada fila lleva, además de Q/H/eta, las columnas de los coeficientes del
    polinomio H(Q)=A·Q²+B·Q+C y η(Q)=D·Q²+E·Q+F (con su R²) — repetidas en
    las N_EXPORT filas de la misma bomba en vez de una hoja de resumen
    aparte: mantiene el archivo de una sola hoja/tabla, más simple de leer
    con `pandas.read_excel` sin tener que unir dos hojas."""
    rows = []
    for s in bombeos:
        for b in s.bombas:
            if len(b.puntos_qh) < 3:
                continue
            qh_t, qe_t = cv.apply_pump_transform(
                b.puntos_qh, b.puntos_qe, b.n1_nominal, b.n2_objetivo,
                b.n_unidades, b.arreglo)
            fit_h = cv.fit_curve(qh_t, 2)
            fit_e = cv.fit_curve(qe_t, 2) if len(qe_t) >= 3 else None
            A, B, C = fit_h.coeffs
            if fit_e is not None:
                D, E, F, r2_e = (*fit_e.coeffs, fit_e.r2)
            else:
                D = E = F = r2_e = None
            q_grid = (np.linspace(fit_h.q_min, fit_h.q_max, N_EXPORT)
                     if fit_h.q_max > fit_h.q_min else np.full(N_EXPORT, fit_h.q_min))
            for q in q_grid:
                rows.append({
                    "Sistema": s.nombre, "Bomba": b.nombre,
                    "Q [L/s]": float(q), "H [m]": fit_h(float(q)),
                    "eta": fit_e(float(q)) if fit_e is not None else None,
                    "H: A": A, "H: B": B, "H: C": C, "H: R2": fit_h.r2,
                    "eta: D": D, "eta: E": E, "eta: F": F, "eta: R2": r2_e,
                })
    df = pd.DataFrame(rows, columns=[
        "Sistema", "Bomba", "Q [L/s]", "H [m]", "eta",
        "H: A", "H: B", "H: C", "H: R2", "eta: D", "eta: E", "eta: F", "eta: R2"])
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    return buf.getvalue()


def parse(file) -> list[PumpData]:
    """Lee el Excel/CSV del catálogo y devuelve una PumpData por bomba.

    Lanza ValueError con mensaje claro si faltan columnas o alguna bomba
    tiene menos de 3 puntos."""
    df = (pd.read_csv(file) if getattr(file, "name", str(file)).lower()
          .endswith(".csv") else pd.read_excel(file))
    df.columns = [str(c).strip().lower() for c in df.columns]
    if not COLS <= set(df.columns):
        raise ValueError(f"Faltan columnas requeridas: {COLS - set(df.columns)} "
                         "(formato: Bomba | Q [L/s] | H [m] | eta)")
    tiene_eta = "eta" in df.columns
    bombas = []
    for nombre, g in df.groupby("bomba", sort=False):
        g = g.dropna(subset=["q [l/s]", "h [m]"]).sort_values("q [l/s]")
        if len(g) < 3:
            raise ValueError(f"La bomba '{nombre}' tiene {len(g)} puntos Q-H "
                             "(mínimo 3 para la regresión)")
        qh = [(float(r["q [l/s]"]), float(r["h [m]"])) for _, r in g.iterrows()]
        qe = []
        if tiene_eta:
            ge = g.dropna(subset=["eta"])
            qe = [(float(r["q [l/s]"]), float(r["eta"])) for _, r in ge.iterrows()]
            if 0 < len(qe) < 3:
                qe = []          # muy pocos puntos de eficiencia: se descartan
        bombas.append(PumpData(nombre=str(nombre), puntos_qh=qh, puntos_qe=qe))
    if not bombas:
        raise ValueError("El catálogo no contiene bombas")
    return bombas

"""Catálogo de bombas candidatas desde Excel (base de datos de curvas).

Formato largo: columnas `Bomba | Q [L/s] | H [m] | eta` (eta opcional),
una fila por punto de curva, filas agrupadas por nombre de bomba."""
import io

import pandas as pd

from core.project import PumpData

COLS = {"bomba", "q [l/s]", "h [m]"}


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
    largo compatible con `parse()` (la columna extra 'Sistema' se ignora al
    reimportar; sirve como referencia de origen)."""
    rows = []
    for s in bombeos:
        for b in s.bombas:
            eta_por_q = dict(b.puntos_qe)
            for q, h in b.puntos_qh:
                rows.append({"Sistema": s.nombre, "Bomba": b.nombre,
                            "Q [L/s]": q, "H [m]": h, "eta": eta_por_q.get(q)})
    df = pd.DataFrame(rows, columns=["Sistema", "Bomba", "Q [L/s]", "H [m]", "eta"])
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

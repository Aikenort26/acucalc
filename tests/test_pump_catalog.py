import io

import pandas as pd
import pytest

from core import curves as cv
from core import pump_catalog as pc
from core.project import PumpSystemData, PumpData


def _xlsx(df):
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    buf.seek(0)
    buf.name = "catalogo.xlsx"
    return buf


def test_parse_ok():
    df = pd.DataFrame({
        "Bomba": ["A"] * 3 + ["B"] * 4,
        "Q [L/s]": [10, 20, 30, 5, 15, 25, 35],
        "H [m]": [50, 45, 35, 60, 55, 45, 30],
        "eta": [0.6, 0.75, 0.7, None, 0.55, 0.7, 0.65],
    })
    bombas = pc.parse(_xlsx(df))
    assert [b.nombre for b in bombas] == ["A", "B"]
    assert bombas[0].puntos_qh == [(10.0, 50.0), (20.0, 45.0), (30.0, 35.0)]
    assert len(bombas[0].puntos_qe) == 3
    assert len(bombas[1].puntos_qe) == 3      # el None se descarta


def test_parse_template():
    buf = io.BytesIO(pc.template_xlsx())
    buf.name = "plantilla.xlsx"
    assert [b.nombre for b in pc.parse(buf)] == ["Ejemplo A", "Ejemplo B"]


def test_parse_columnas_faltantes():
    df = pd.DataFrame({"Bomba": ["A"], "Q": [1]})
    with pytest.raises(ValueError, match="Faltan columnas"):
        pc.parse(_xlsx(df))


def test_parse_pocos_puntos():
    df = pd.DataFrame({"Bomba": ["A", "A"], "Q [L/s]": [1, 2], "H [m]": [5, 4]})
    with pytest.raises(ValueError, match="mínimo 3"):
        pc.parse(_xlsx(df))


def test_export_xlsx_roundtrip():
    """WP-3d: el export ya no vuelca los puntos crudos digitalizados — resamplea
    N_EXPORT=10 puntos equiespaciados en Q sobre la curva AJUSTADA. El roundtrip
    conserva la bomba y sus 10 puntos siguen cayendo sobre la parábola original
    (los puntos de entrada son exactos para un ajuste de grado 2 con 3 puntos)."""
    s1 = PumpSystemData(nombre="Sistema 1")
    s1.bombas = [PumpData(nombre="Bomba A",
                          puntos_qh=[(10.0, 50.0), (20.0, 45.0), (30.0, 35.0)],
                          puntos_qe=[(10.0, 0.6), (20.0, 0.75), (30.0, 0.7)])]
    s2 = PumpSystemData(nombre="Sistema 2")
    s2.bombas = [PumpData(nombre="Bomba B",
                          puntos_qh=[(5.0, 60.0), (15.0, 55.0), (25.0, 45.0)])]
    data = pc.export_xlsx([s1, s2])
    buf = io.BytesIO(data)
    buf.name = "export.xlsx"
    bombas = pc.parse(buf)
    assert {b.nombre for b in bombas} == {"Bomba A", "Bomba B"}
    a = next(b for b in bombas if b.nombre == "Bomba A")
    assert len(a.puntos_qh) == pc.N_EXPORT
    assert a.puntos_qh[0][0] == pytest.approx(10.0, abs=1e-6)
    assert a.puntos_qh[-1][0] == pytest.approx(30.0, abs=1e-6)
    fit_a = cv.fit_curve([(10.0, 50.0), (20.0, 45.0), (30.0, 35.0)], 2)
    for q, h in a.puntos_qh:
        assert h == pytest.approx(fit_a(q), abs=1e-6)
    assert len(a.puntos_qe) == pc.N_EXPORT


def test_export_xlsx_qh_qe_grillas_independientes():
    # puntos_qh y puntos_qe con Q's muestreados de forma independiente
    # (caso real: digitalizador/tabla manual), como la bomba WKL 125 de
    # scripts/demo_sanjacinto.py — casi nunca comparten valores exactos de Q.
    s = PumpSystemData(nombre="Sistema 1")
    s.bombas = [PumpData(
        nombre="WKL 125",
        puntos_qh=[(25.0, 60.0), (40.0, 55.0), (50.0, 50.0),
                   (63.0, 42.0), (75.0, 33.0), (85.0, 20.0)],
        puntos_qe=[(25.0, 0.5), (35.0, 0.65), (45.0, 0.75),
                   (55.0, 0.72), (63.0, 0.68)])]
    data = pc.export_xlsx([s])
    buf = io.BytesIO(data)
    buf.name = "export.xlsx"
    bombas = pc.parse(buf)
    b = next(x for x in bombas if x.nombre == "WKL 125")
    assert b.puntos_qe != []


def test_export_xlsx_aplica_transformada_n2_y_arreglo():
    """WP-3d — el bug real: antes se exportaba la curva NOMINAL cruda,
    ignorando N2/afinidad y arreglo. Con n_unidades=2 en paralelo, el Q
    exportado debe reflejar el caudal DOBLADO (mismo H), no el Q nominal."""
    s = PumpSystemData(nombre="Sistema 1")
    b = PumpData(nombre="Doble", puntos_qh=[(10.0, 50.0), (20.0, 45.0), (30.0, 35.0)],
                puntos_qe=[], n_unidades=2, arreglo="paralelo")
    s.bombas = [b]
    data = pc.export_xlsx([s])
    df = pd.read_excel(io.BytesIO(data))
    fila = df[df["Bomba"] == "Doble"]
    assert len(fila) == pc.N_EXPORT
    # arreglo paralelo: mismo H, Q multiplicado por n_unidades=2 -> rango
    # de Q exportado debe ir de 20 a 60 (=2×[10,30]), no de 10 a 30 (nominal).
    assert fila["Q [L/s]"].min() == pytest.approx(20.0, abs=1e-6)
    assert fila["Q [L/s]"].max() == pytest.approx(60.0, abs=1e-6)
    assert fila["H [m]"].max() == pytest.approx(50.0, abs=1e-6)
    assert fila["H [m]"].min() == pytest.approx(35.0, abs=1e-6)


def test_export_xlsx_incluye_columnas_de_coeficientes():
    """Columnas de los coeficientes H(Q)=A·Q²+B·Q+C y η(Q)=D·Q²+E·Q+F + R²
    de cada bomba, presentes y consistentes en todas sus filas."""
    s = PumpSystemData(nombre="Sistema 1")
    s.bombas = [PumpData(nombre="A",
                         puntos_qh=[(10.0, 50.0), (20.0, 45.0), (30.0, 35.0)],
                         puntos_qe=[(10.0, 0.6), (20.0, 0.75), (30.0, 0.7)])]
    data = pc.export_xlsx([s])
    df = pd.read_excel(io.BytesIO(data))
    for col in ("H: A", "H: B", "H: C", "H: R2", "eta: D", "eta: E", "eta: F", "eta: R2"):
        assert col in df.columns
    assert len(df) == pc.N_EXPORT
    assert df["H: A"].nunique() == 1     # mismo coeficiente repetido en las 10 filas


def test_export_xlsx_menos_de_3_puntos_se_omite():
    s = PumpSystemData(nombre="Sistema 1")
    s.bombas = [PumpData(nombre="Incompleta", puntos_qh=[(10.0, 50.0), (20.0, 45.0)])]
    data = pc.export_xlsx([s])
    df = pd.read_excel(io.BytesIO(data))
    assert "Incompleta" not in set(df.get("Bomba", []))


def test_parse_tolera_columnas_extra_de_un_export_nuevo():
    """Un archivo exportado con el formato nuevo (columnas de coeficientes)
    debe seguir siendo importable — extra columns se ignoran al leer."""
    s = PumpSystemData(nombre="Sistema 1")
    s.bombas = [PumpData(nombre="A",
                         puntos_qh=[(10.0, 50.0), (20.0, 45.0), (30.0, 35.0)])]
    data = pc.export_xlsx([s])
    buf = io.BytesIO(data)
    buf.name = "export.xlsx"
    bombas = pc.parse(buf)
    assert [b.nombre for b in bombas] == ["A"]

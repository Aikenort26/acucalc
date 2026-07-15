import io

import pandas as pd
import pytest

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
    assert a.puntos_qh == [(10.0, 50.0), (20.0, 45.0), (30.0, 35.0)]
    assert len(a.puntos_qe) == 3

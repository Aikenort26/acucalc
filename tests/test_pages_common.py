from pathlib import Path

import pandas as pd

from core.project import Project
from pages_common import f_num, fila_incompleta, i_num, resolve_save_path, s_txt


def test_resolve_vacio_devuelve_none():
    assert resolve_save_path(Project(nombre="X")) is None


def test_resolve_archivo_json_se_usa_tal_cual():
    p = Project(nombre="X", ruta_guardado=r"C:\d\mi_proyecto.acucalc.json")
    assert resolve_save_path(p) == Path(r"C:\d\mi_proyecto.acucalc.json")


def test_resolve_carpeta_agrega_nombre_slug():
    p = Project(nombre="San Jacinto", ruta_guardado=r"C:\d\Proyectos")
    assert resolve_save_path(p) == Path(r"C:\d\Proyectos") / "San_Jacinto.acucalc.json"


def test_resolve_quita_comillas_envolventes():
    p = Project(nombre="X", ruta_guardado='"C:\\d\\p.acucalc.json"')
    assert resolve_save_path(p) == Path(r"C:\d\p.acucalc.json")


# ---------- guardas NaN de las tablas editables ----------

def test_or_no_protege_nan_pero_i_num_si():
    """El bug reportado: `int(r["Suministro desde [h]"] or 0)` reventaba porque
    `bool(float('nan')) is True` → `NaN or 0` es NaN → `int(NaN)` lanza
    ValueError. Este test fija el comportamiento correcto."""
    nan = float("nan")
    assert bool(nan) is True                 # la razón por la que `or` no servía
    assert (nan or 0) is nan                 # el `or` viejo dejaba pasar el NaN
    assert i_num(nan, 0) == 0                # la guarda nueva sí lo atrapa
    assert i_num(nan, 23) == 23


def test_i_num_y_f_num_casos_vacios():
    for vacio in (None, float("nan"), "", "   "):
        assert f_num(vacio, 2.5) == 2.5
        assert i_num(vacio, 7) == 7


def test_f_num_conserva_cero_legitimo():
    """Q=0 es un punto válido de una curva de bomba: no puede tratarse como vacío."""
    assert f_num(0.0, 9.9) == 0.0
    assert i_num(0, 9) == 0


def test_f_num_valores_normales_y_basura():
    assert f_num(3.5, 0.0) == 3.5
    assert f_num("4.25", 0.0) == 4.25
    assert i_num(2.6, 0) == 3                # redondea, no trunca
    assert f_num("no es un número", 1.0) == 1.0


def test_celda_vacia_de_pandas_es_nan_no_none():
    """La razón por la que la guarda vieja era código muerto: pandas nunca
    devuelve None en una columna numérica, siempre NaN."""
    df = pd.DataFrame([{"Cantidad": 1}, {"Cantidad": None}])
    celda = df.iloc[1]["Cantidad"]
    assert celda is not None
    assert i_num(celda, 1) == 1


def test_fila_incompleta_detecta_celdas_vacias():
    df = pd.DataFrame([{"Nombre": "T1", "Cantidad": 1, "Altura": 2.5},
                       {"Nombre": "T2", "Cantidad": None, "Altura": None}])
    assert fila_incompleta(df.iloc[1], ["Cantidad", "Altura"]) is True
    assert fila_incompleta(df.iloc[0], ["Cantidad", "Altura"]) is False


def test_s_txt_nan_no_produce_literal_nan():
    """El bug visto en pantalla: `NaN or "circular"` devuelve NaN (NaN es
    truthy) y `str(NaN)` produce el literal "nan", que terminaba como forma
    y tipo constructivo del tanque, en la tabla y en el reporte."""
    nan = float("nan")
    assert str(nan or "circular") == "nan"      # el bug viejo
    assert s_txt(nan, "circular") == "circular"  # la guarda nueva
    assert s_txt(None, "superficial") == "superficial"
    assert s_txt("", "circular") == "circular"
    assert s_txt("   ", "circular") == "circular"
    assert s_txt("nan", "circular") == "circular"   # pandas ya lo stringificó
    assert s_txt("rectangular", "circular") == "rectangular"
    assert s_txt("  T1  ") == "T1"

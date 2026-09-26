import base64
import io

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import pytest
from PIL import Image

from core import estudios as es, project as pj


def _png(w=40, h=30):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (10, 120, 200)).save(buf, "PNG")
    return buf.getvalue()


def _pdf():
    fig, ax = plt.subplots(figsize=(3, 2))
    ax.plot([0, 1], [0, 1])
    buf = io.BytesIO()
    fig.savefig(buf, format="pdf")
    plt.close(fig)
    return buf.getvalue()


def test_tabla_desde_csv_y_excel():
    t = es.tabla_de_archivo("suelos.csv", "Sondeo,Profundidad [m],Clasificación\n"
                                          "S-1,1.5,CL\nS-2,3.0,SM\n".encode("utf-8"))
    df = es.tabla_df(t)
    assert list(df.columns) == ["Sondeo", "Profundidad [m]", "Clasificación"] and len(df) == 2
    buf = io.BytesIO()
    pd.DataFrame({"Año": [2018, 2023], "Hogares": [510, 560]}).to_excel(buf, index=False)
    t2 = es.tabla_de_archivo("hogares.xlsx", buf.getvalue())
    assert es.tabla_df(t2)["Hogares"].tolist() == [510, 560]


def test_tabla_demasiado_ancha_es_error():
    csv = ",".join(f"c{i}" for i in range(10)) + "\n" + ",".join("1" * 10) + "\n"
    with pytest.raises(ValueError, match="columnas"):
        es.tabla_de_archivo("ancha.csv", csv.encode())


def test_figura_desde_imagen_y_desde_pdf():
    img = Image.open(io.BytesIO(base64.b64decode(es.figura_de_archivo("foto.png", _png()))))
    assert img.size == (40, 30)
    pag = Image.open(io.BytesIO(base64.b64decode(es.figura_de_archivo("plano.pdf", _pdf()))))
    assert pag.format == "PNG" and pag.width > 100          # primera página rasterizada
    with pytest.raises(ValueError):
        es.figura_de_archivo("nada.png", b"no es imagen")


def _estudio():
    e = pj.EstudioPrevio(id="a1", tipo="topografia", titulo="",
                         texto="Levantamiento con GNSS al 50% & #1 {x} [@res0330].\n\n"
                               "Segundo párrafo sin citas [@inexistente].")
    e.tablas = [pj.TablaEstudio("Puntos de control", "Punto,Norte,Este\nGPS-1,1500.25,980.10\n")]
    e.figuras = [pj.FiguraEstudio("Plano topográfico", base64.b64encode(_png()).decode(),
                                  "Levantamiento 2025")]
    return e


def test_contexto_escapa_cita_y_separa_parrafos(tmp_path):
    guardadas = {}

    def guardar(b64, nombre):
        guardadas[nombre] = b64
        return nombre + ".png"
    ctx, faltantes = es.contexto([_estudio()], {"res0330"}, guardar)
    c = ctx[0]
    assert c["titulo"] == "Topografía"                     # sin título usa el del tipo
    assert len(c["parrafos"]) == 2
    assert r"50\% \& \#1 \{x\}" in c["parrafos"][0] and r"\cite{res0330}" in c["parrafos"][0]
    assert r"\cite{inexistente}" not in c["parrafos"][1] and faltantes == ["inexistente"]
    tab = c["tablas"][0]
    assert tab["encabezados"] == ["Punto", "Norte", "Este"]
    assert tab["filas"] == [["GPS-1", "1500.25", "980.10"]]
    assert tab["alineacion"] == ["l", "r", "r"]            # columnas numéricas a la derecha
    fig = c["figuras"][0]
    assert fig["archivo"] == "estudio_a1_1.png" and "estudio_a1_1" in guardadas
    assert fig["leyenda"] == "Plano topográfico"
    assert fig["fuente"] == "Levantamiento 2025"


def test_estudio_fuera_del_informe_o_vacio_no_entra():
    e = _estudio()
    e.en_informe = False
    vacio = pj.EstudioPrevio(id="b2", tipo="social")
    assert es.contexto([e, vacio], set(), lambda b64, n: n)[0] == []

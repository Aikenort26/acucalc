import math

import numpy as np
import pandas as pd
import pytest

from core.transients import perfil as pf


@pytest.mark.parametrize("txt,valor", [("K0+120.50", 120.5), ("k1+005", 1005.0),
                                       ("0+250", 250.0), (340, 340.0), ("12.5", 12.5)])
def test_abscisas_formato_colombiano(txt, valor):
    assert pf.abscisa(txt) == pytest.approx(valor)


def test_carga_con_cota_eje_y_longitud_real():
    df = pd.DataFrame({"Abscisa": ["K0+000", "K0+300", "K0+400"],
                       "Cota terreno": [100.0, 140.0, 140.0],
                       "Cota clave": [99.0, 139.0, 139.0]})
    p = pf.cargar(df)
    assert p.longitud == pytest.approx(math.hypot(300, 40) + 100)
    assert p.z_en_x(np.array([0.0, p.longitud]))[-1] == pytest.approx(139.0)


def test_sin_cota_eje_usa_cobertura_y_diametro():
    df = pd.DataFrame({"abscisa (m)": [0, 100], "Cota de terreno [m]": [50.0, 60.0]})
    p = pf.cargar(df, cobertura=1.2, D_m=0.2)
    assert p.z_eje == pytest.approx((50 - 1.3, 60 - 1.3))


def test_sin_cota_eje_ni_cobertura_es_error():
    with pytest.raises(ValueError, match="cobertura"):
        pf.cargar(pd.DataFrame({"Abscisa": [0, 10], "Terreno": [1.0, 2.0]}))


def test_abscisas_no_crecientes_es_error():
    with pytest.raises(ValueError, match="crecientes"):
        pf.cargar(pd.DataFrame({"Abscisa": [0, 10, 10], "Terreno": [1, 2, 3],
                                "Eje": [0, 1, 2]}))


def test_puntos_altos_locales():
    df = pd.DataFrame({"Abscisa": [0, 100, 200, 300, 400], "Terreno": [0, 10, 5, 12, 3],
                       "Eje": [0, 10, 5, 12, 3]})
    assert pf.cargar(df).puntos_altos() == [100.0, 300.0]


def test_recto_desde_longitud_y_desnivel():
    p = pf.recto(500.0, 10.0, 60.0)
    assert p.longitud == pytest.approx(math.hypot(500 * math.cos(math.asin(50 / 500)), 50))


@pytest.mark.parametrize("valor,txt", [(0.0, "K0+000.00"), (120.5, "K0+120.50"),
                                       (1234.5, "K1+234.50"), (999.999, "K1+000.00"),
                                       (12003.2, "K12+003.20")])
def test_formato_abscisa_ida_y_vuelta(valor, txt):
    assert pf.formato_abscisa(valor) == txt
    assert pf.abscisa(txt) == pytest.approx(round(valor, 2))


def test_abscisa_de_x_sobre_la_tuberia():
    p = pf.Perfil((0.0, 300.0, 700.0), (10.0, 50.0, 20.0), (9.0, 49.0, 19.0))
    x = p.x_vertices()
    assert p.abscisa_de_x(x[1]) == pytest.approx(300.0)
    assert p.abscisa_de_x((x[1] + x[2]) / 2) == pytest.approx(500.0)

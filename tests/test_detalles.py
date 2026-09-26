import math

import matplotlib
matplotlib.use("Agg")
import pytest

from core import detalles as dt, project as pj, storage


def _zanja(**kw):
    z = pj.ZanjaConfig(d_ext_mm=200.0, ancho_fondo=0.60, profundidad=1.40, talud=0.25,
                       cama=0.10, atraque=0.30, pavimento=0.0,
                       mat_cama="Arena", mat_atraque="Material seleccionado",
                       mat_relleno="Material de excavación")
    for k, v in kw.items():
        setattr(z, k, v)
    return z


def _textos(fig):
    # los rótulos se parten en varias líneas: se comparan con espacios simples
    return [" ".join(t.get_text().split()) for ax in fig.axes for t in ax.texts]


def test_zanja_completa_genera_figura_con_cotas():
    z = _zanja()
    assert dt.validar_zanja(z) == []
    fig = dt.fig_zanja(z)
    txt = " ".join(_textos(fig))
    assert "0.60 m" in txt and "1.40 m" in txt              # ancho de fondo y profundidad
    assert "1.10 m" in txt                                   # cobertura = 1.40 − 0.10 − 0.20
    assert "Arena" in txt and "Material seleccionado" in txt
    assert dt.cobertura(z) == pytest.approx(1.10)
    assert dt.ancho_superior(z) == pytest.approx(0.60 + 2 * 0.25 * 1.40)


@pytest.mark.parametrize("campo,valor,mensaje", [
    ("ancho_fondo", 0.0, "ancho"), ("profundidad", 0.0, "profundidad"),
    ("d_ext_mm", 0.0, "diámetro"), ("ancho_fondo", 0.15, "no cabe"),
    ("atraque", 1.5, "superan la profundidad"),
])
def test_zanja_incompleta_o_incoherente_no_genera_figura(campo, valor, mensaje):
    z = _zanja(**{campo: valor})
    assert any(mensaje in e for e in dt.validar_zanja(z))
    assert dt.fig_zanja(z) is None


def test_zanja_con_pavimento_lo_descuenta_del_relleno():
    z = _zanja(pavimento=0.25)
    assert dt.validar_zanja(z) == []
    assert "0.25 m" in " ".join(_textos(dt.fig_zanja(z)))
    assert dt.validar_zanja(_zanja(pavimento=1.0)) != []


def test_niveles_del_tanque_son_volumen_sobre_area():
    t = pj.TankSpec("T", "elevado", "circular", 100.0, 2.5, cantidad=1, borde_libre=0.3)
    n = dt.niveles_tanque(t, frac_incendio=0.15)
    ct = storage.dimensioned_tank(100.0, 2.5, "circular")
    area = math.pi / 4 * ct.diametro ** 2
    assert n.area == pytest.approx(area)
    assert n.h_max == pytest.approx(100.0 / area)
    assert n.h_incendio == pytest.approx(100.0 * 0.15 / 1.15 / area)
    assert n.h_muro == pytest.approx(ct.altura + 0.3)


def test_niveles_por_unidad_cuando_hay_varias():
    t = pj.TankSpec("T", "bajo", "rectangular", 300.0, 3.0, ratio=2.0, cantidad=3)
    n = dt.niveles_tanque(t, frac_incendio=0.0)
    ct = storage.dimensioned_tank(100.0, 3.0, "rectangular", 2.0)
    assert n.area == pytest.approx(ct.ancho * ct.largo)
    assert n.h_max == pytest.approx(100.0 / n.area) and n.h_incendio == 0.0


def test_figura_del_tanque_rotula_los_niveles():
    t = pj.TankSpec("Elevado", "elevado", "circular", 100.0, 2.5, tipo_constructivo="elevado",
                    borde_libre=0.3)
    fig = dt.fig_tanque(t, 0.15)
    txt = " ".join(_textos(fig))
    assert "Nivel máximo" in txt and "incendio" in txt and "Borde libre" in txt
    sin_bl = " ".join(_textos(dt.fig_tanque(pj.TankSpec("T", volumen=50.0, altura=2.0), 0.15)))
    assert "Borde libre" not in sin_bl


def test_tanque_sin_volumen_no_genera_figura():
    assert dt.fig_tanque(pj.TankSpec("T", volumen=0.0), 0.15) is None


def _sistema(tipo_bomba="superficie"):
    s = pj.PumpSystemData(nombre="Captación", tipo_bomba=tipo_bomba, he=25.0)
    s.tramos = [pj.SegmentData("Succión", "succion", 6.0, 102.2, "PVC"),
                pj.SegmentData("Impulsión", "impulsion", 300.0, 79.5, "PEAD")]
    s.accesorios = [pj.AccessoryData("Entrada boca acampanada", 1, "Succión"),
                    pj.AccessoryData("Codo radio medio", 2, "Succión"),
                    pj.AccessoryData("Válvula de cheque", 1, "Impulsión"),
                    pj.AccessoryData("Válvula de compuerta", 1, "Impulsión"),
                    pj.AccessoryData("Salida", 1, "Impulsión")]
    return s


def test_estacion_de_bombeo_dibuja_sus_accesorios():
    fig = dt.fig_estacion(_sistema())
    txt = " ".join(_textos(fig))
    for tipo in ("Entrada boca acampanada", "2× Codo radio medio", "Válvula de cheque",
                 "Válvula de compuerta", "Salida"):
        assert tipo in txt
    assert "Bomba de superficie" in txt and "Succión" in txt and "Impulsión" in txt


def test_estacion_sumergible_y_sin_tramos():
    assert "Bomba sumergible" in " ".join(_textos(dt.fig_estacion(_sistema("sumergible"))))
    assert dt.fig_estacion(pj.PumpSystemData(nombre="Vacío")) is None


def test_orden_de_accesorios_por_lado():
    lados = dt.accesorios_por_lado(_sistema())
    assert [a.tipo for a in lados["succion"]] == ["Entrada boca acampanada", "Codo radio medio"]
    assert [a.tipo for a in lados["impulsion"]][-1] == "Salida"

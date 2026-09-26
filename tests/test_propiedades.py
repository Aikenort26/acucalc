import pytest

from core import propiedades as pr


@pytest.mark.parametrize("t_k,ps_mpa", [
    # IAPWS R7-97(2012), Tabla 35: valores de verificación de la ecuación (30)
    (300.0, 0.353658941e-2),
    (500.0, 0.263889776e1),
    (600.0, 0.123443146e2),
])
def test_presion_vapor_if97_tabla_35(t_k, ps_mpa):
    assert pr.presion_vapor_pa(t_k - 273.15) == pytest.approx(ps_mpa * 1e6, rel=1e-8)


def test_presion_vapor_agua_fria_crece_con_t():
    ps = [pr.presion_vapor_pa(t) for t in (5, 15, 25, 35)]
    assert ps == sorted(ps) and 800 < ps[0] < 900       # ~0.87 kPa a 5 °C


def test_presion_atmosferica_isa():
    assert pr.presion_atmosferica_pa(0.0) == pytest.approx(101325.0, abs=1e-6)
    # ISO 2533: tropopausa (11 km geopotencial) = 22 632 Pa
    assert pr.presion_atmosferica_pa(11000.0) == pytest.approx(22632.06, abs=1.0)


def test_presion_atmosferica_decrece_con_altitud():
    assert pr.presion_atmosferica_pa(2600) < pr.presion_atmosferica_pa(1000) < 101325


def test_carga_de_presion():
    assert pr.carga_m(98066.5, rho=1000.0) == pytest.approx(10.0)


def test_presion_vapor_fuera_de_rango():
    with pytest.raises(ValueError):
        pr.presion_vapor_pa(-5.0)

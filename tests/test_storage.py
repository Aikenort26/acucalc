from core import storage

QMD_M3D = 185.098344
FACTORES = [0.6,0.7,0.8,0.9,1,1.2,1.6,1.2,1,1.1,1.1,1.2,1.1,1.1,1,1.1,1.2,1.1,0.9,0.9,0.9,0.8,0.8,0.7]
SUPPLY = [1 if 5 <= h <= 14 else 0 for h in range(24)]


def test_metodo_art81():
    r = storage.volume_art81(QMD_M3D, frac_regulacion=1/3, frac_incendio=0.15, dias_reserva=1)
    assert abs(r.v_regulacion - 61.6994) < 1e-3
    assert abs(r.v_incendio - 9.2549) < 1e-3
    assert r.v_total_redondeado == 75


def test_curva_integral():
    r = storage.volume_curva_integral(QMD_M3D, FACTORES, SUPPLY, frac_incendio=0.15, dias_reserva=1)
    assert abs(r.frac_regulacion - 0.516667) < 1e-4
    assert abs(r.v_regulacion - 95.6341) < 1e-2
    assert r.v_total_redondeado == 110


def test_volumen_final_maximo():
    a = storage.volume_art81(QMD_M3D, 1/3, 0.15, 1)
    b = storage.volume_curva_integral(QMD_M3D, FACTORES, SUPPLY, 0.15, 1)
    assert storage.final_volume(a, b) == 110


def test_factores_no_suman_24():
    import pytest
    with pytest.raises(ValueError):
        storage.volume_curva_integral(QMD_M3D, [1.0] * 23, SUPPLY[:23], 0.15, 1)


def test_predimensionado_tanque():
    t = storage.tank_dimensions(volumen=60, altura=2.5)
    assert abs(t.diametro - 5.53) < 0.03        # cilíndrico: D=sqrt(4V/(pi·h))
    assert abs(t.lado - 4.899) < 0.01           # cuadrado: L=sqrt(V/h)


def test_predimensionado_rectangular():
    t = storage.tank_dimensions(volumen=60, altura=2.5, ratio=2.0)
    assert abs(t.ancho - (60 / (2.5 * 2.0)) ** 0.5) < 1e-9   # ancho=sqrt(V/(h·ratio))
    assert abs(t.largo - 2.0 * t.ancho) < 1e-9
    assert abs(t.ancho * t.largo * t.altura - 60) < 1e-9


def test_balance_curve_equivale_curva_integral():
    # el refactor debe reproducir el 51.67% del golden Bolívar
    supply = [s / sum(SUPPLY) for s in SUPPLY]
    demand = [f / sum(FACTORES) for f in FACTORES]
    frac, difs = storage.balance_curve(supply, demand)
    assert abs(frac - 0.516667) < 1e-4
    assert len(difs) == 24


def test_tank_balance_check_cumple():
    """Volumen asignado ≥ el requerido por el balance interno → cumple=True."""
    chk = storage.tank_balance_check("T1", QMD_M3D, SUPPLY, FACTORES, v_asignado=200,
                                     frac_incendio=0.15, dias_reserva=1)
    assert chk.cumple is True
    assert abs(chk.frac_balance - 0.516667) < 1e-4
    assert chk.horas_suministro == 10          # SUPPLY: horas 5-14
    assert chk.horas_salida == 24              # FACTORES: 24 horas con consumo
    assert chk.v_asignado == 200


def test_tank_balance_check_no_cumple():
    """Volumen asignado insuficiente → cumple=False y v_balance_req exacto.
    v_req = frac·QMD·(1+incendio)·días, con frac de balance_curve sobre las
    ventanas normalizadas (mismo golden 51.67% del Bolívar)."""
    supply = [s / sum(SUPPLY) for s in SUPPLY]
    demand = [f / sum(FACTORES) for f in FACTORES]
    frac, _ = storage.balance_curve(supply, demand)
    v_req_esperado = frac * QMD_M3D * (1 + 0.15) * 1
    chk = storage.tank_balance_check("T1", QMD_M3D, SUPPLY, FACTORES, v_asignado=50,
                                     frac_incendio=0.15, dias_reserva=1)
    assert chk.cumple is False
    assert abs(chk.v_balance_req - v_req_esperado) < 1e-6
    assert abs(chk.v_balance_req - 109.979) < 1e-2


def test_round_up_step():
    assert storage.round_up_step(5.53, 0.1) == 5.6
    assert storage.round_up_step(5.50, 0.1) == 5.5           # exacto no sube
    assert storage.round_up_step(2.401, 0.1) == 2.5


def test_dimensioned_tank_circular():
    ct = storage.dimensioned_tank(60, 2.5, "circular")
    assert ct.diametro == 5.6                                 # 5.53 → 5.6
    assert ct.altura == 2.5
    assert ct.volumen_real >= 60
    import math
    assert abs(ct.volumen_real - math.pi / 4 * 5.6**2 * 2.5) < 1e-9


def test_dimensioned_tank_rectangular_siempre_alcanza_volumen():
    for v in (30, 110, 430, 2225):
        ct = storage.dimensioned_tank(v, 2.5, "rectangular", ratio=1.5)
        assert ct.volumen_real >= v
        assert abs(ct.ancho * 10 - round(ct.ancho * 10)) < 1e-6
        assert abs(ct.largo * 10 - round(ct.largo * 10)) < 1e-6

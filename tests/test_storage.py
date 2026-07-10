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

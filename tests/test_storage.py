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


def test_tank_chain_golden():
    """Cadena captación→bajo→bombeo→elevado→red. Elevado reproduce el 51.67%
    (bombeo 10 h vs factores Bolívar); bajo: captación 24 h vs bombeo 10 h,
    verificado por acumulados manuales."""
    ventana_capta = [1] * 24                         # captación continua
    ventana_bombeo = SUPPLY                          # bombeo 10 h (horas 5-14)
    r = storage.tank_chain(QMD_M3D, FACTORES, ventana_capta, ventana_bombeo,
                           frac_incendio=0.15, dias_reserva=1)
    assert abs(r.elevado.frac_regulacion - 0.516667) < 1e-4
    # bajo: suministro uniforme 1/24 por hora; demanda 1/10 por hora en 5..14.
    # acumulado diff: sube 5/24 (h0-4), baja (1/24-1/10)/h ×10h → min = 5/24-10*(7/120)
    acum, difs = 0.0, []
    for h in range(24):
        acum += 1 / 24 - (1 / 10 if 5 <= h <= 14 else 0.0)
        difs.append(acum)
    esperado = max(difs) - min(difs)
    assert abs(r.bajo.frac_regulacion - esperado) < 1e-9
    assert r.elevado.v_total_redondeado == 110       # coherente con golden v1
    assert r.total_redondeado == r.bajo.v_total_redondeado + r.elevado.v_total_redondeado


def test_tank_chain_ventanas_invalidas():
    import pytest
    with pytest.raises(ValueError):
        storage.tank_chain(QMD_M3D, FACTORES, [0] * 24, SUPPLY, 0.15, 1)


def test_tank_train_equivale_a_chain():
    """El tren de 2 tanques reproduce exactamente la cadena bajo/elevado."""
    entradas = [("Tanque bajo", [1] * 24), ("Tanque elevado", SUPPLY)]
    tren = storage.tank_train(QMD_M3D, entradas, FACTORES, 0.15, 1)
    chain = storage.tank_chain(QMD_M3D, FACTORES, [1] * 24, SUPPLY, 0.15, 1)
    assert abs(tren[0].frac_regulacion - chain.bajo.frac_regulacion) < 1e-12
    assert abs(tren[1].frac_regulacion - chain.elevado.frac_regulacion) < 1e-12
    assert tren[1].v_total_redondeado == 110          # golden Bolívar 10 h
    assert abs(tren[1].frac_regulacion - 0.516667) < 1e-4
    # caudal del bombeo intermedio que alimenta al elevado: QMD·24/10
    assert abs(tren[1].q_entrada_lps - (QMD_M3D / 86.4) * 2.4) < 1e-6
    assert tren[1].horas_entrada == 10


def test_tank_train_tres_tanques():
    entradas = [("T1", [1] * 24),
                ("T2", [1 if 5 <= h <= 14 else 0 for h in range(24)]),
                ("T3", [1 if 6 <= h <= 17 else 0 for h in range(24)])]
    tren = storage.tank_train(QMD_M3D, entradas, FACTORES, 0.15, 1)
    assert len(tren) == 3
    assert tren[2].horas_entrada == 12
    assert all(t.v_total_redondeado % 5 == 0 for t in tren)


def test_tank_train_vacio():
    import pytest
    with pytest.raises(ValueError):
        storage.tank_train(QMD_M3D, [], FACTORES, 0.15, 1)

"""Casos analíticos del MOC (Wylie–Streeter) y del método de Allievi."""
import math

import numpy as np
import pytest

from core.transients import allievi, moc

G = moc.G
L, A_ONDA, D = 1200.0, 1200.0, 0.30
AREA = math.pi * D ** 2 / 4
Q0 = 0.08
V0 = Q0 / AREA
H_RES = 100.0


def _valvula(tau, f=0.0, t_fin=12.0, N=24, H_d=20.0):
    cfg = moc.Config(tuberias=[moc.Tuberia(L, D, A_ONDA, f)], aguas_arriba=moc.Embalse(H_RES),
                     aguas_abajo=moc.Valvula(tau, H_d), Q0=Q0, N_min=N, t_fin=t_fin)
    return moc.run(cfg)


def test_sin_perturbacion_cabeza_constante_con_friccion():
    r = _valvula(lambda t: 1.0, f=0.02, t_fin=10 * 4 * L / A_ONDA)
    assert np.max(np.abs(r.H_abajo - r.H_abajo[0])) < 1e-9
    assert np.max(np.abs(r.Q_abajo - Q0)) < 1e-12


def test_cierre_instantaneo_onda_cuadrada_joukowsky():
    r = _valvula(allievi.cierre_instantaneo)
    dh = A_ONDA * V0 / G
    T = 2 * L / A_ONDA
    for t, h in zip(r.t, r.H_abajo):
        fase = (t % (2 * T)) / T
        if 1e-9 < t and 0.02 < fase < 0.98:
            assert h - H_RES == pytest.approx(dh, abs=1e-9)
        elif 1.02 < fase < 1.98:
            assert h - H_RES == pytest.approx(-dh, abs=1e-9)
    assert allievi.joukowsky(A_ONDA, V0) == pytest.approx(dh)


@pytest.mark.parametrize("tau", [allievi.cierre_lineal(3.0),
                                 allievi.cierre_potencial(3.0, 1.5),
                                 allievi.cierre_lineal(0.9)])
def test_moc_sin_friccion_igual_a_cadena_de_allievi(tau):
    r = _valvula(tau, t_fin=15.0)
    h_all = allievi.cadena(tau, A_ONDA, L, V0, H_RES, 20.0, r.dt, len(r.t) - 1)
    assert np.max(np.abs(r.H_abajo - h_all)) < 1e-9 * H_RES


def test_caudal_lineal_prescrito_maximo_de_michaud():
    Tc = 6.0                                           # ≥ 2L/a = 2 s
    cfg = moc.Config(tuberias=[moc.Tuberia(L, D, A_ONDA, 0.0)], aguas_arriba=moc.Embalse(H_RES),
                     aguas_abajo=moc.CaudalPrescrito(lambda t: Q0 * max(0.0, 1 - t / Tc)),
                     Q0=Q0, N_min=20, t_fin=12.0)
    r = moc.run(cfg)
    assert r.H_abajo.max() - H_RES == pytest.approx(allievi.michaud(L, V0, Tc), rel=1e-9)


def _bomba(modo, H_succion=10.0, **kw):
    bomba = moc.Bomba(H_succion=H_succion, modo=modo, **kw)
    cfg = moc.Config(tuberias=[moc.Tuberia(L, D, A_ONDA, 0.0)], aguas_arriba=bomba,
                     aguas_abajo=moc.Embalse(H_RES), Q0=Q0, N_min=24, t_fin=1.9 * L / A_ONDA)
    return moc.run(cfg)


def test_parada_instantanea_de_bomba_depresion_joukowsky():
    r = _bomba("parada_instantanea")
    assert r.H_arriba[1:].min() - H_RES == pytest.approx(-A_ONDA * V0 / G, abs=1e-9)


def test_dos_tuberias_en_serie_coeficiente_de_transmision():
    t1 = moc.Tuberia(3000.0, 0.40, 1000.0, 0.0)          # recibe la onda
    t2 = moc.Tuberia(1000.0, 0.25, 1000.0, 0.0)          # tramo de la válvula
    cfg = moc.Config(tuberias=[t1, t2], aguas_arriba=moc.Embalse(H_RES),
                     aguas_abajo=moc.Valvula(allievi.cierre_instantaneo, 20.0), Q0=Q0,
                     N_min=10, t_fin=2.5, monitor=[2900.0])
    r = moc.run(cfg)
    B1, B2 = t1.a / (G * t1.area), t2.a / (G * t2.area)
    h_inc = B2 * Q0
    s = 2 * B1 / (B1 + B2)
    serie = r.monitor[2900.0] - r.monitor[2900.0][0]
    # la onda llega a x = 2900 m en (1000 + 100)/1000 = 1.1 s y la reflejada en el
    # embalse vuelve en > 5 s: entre 1.2 y 2.5 s solo está la transmitida
    ventana = (r.t > 1.2) & (r.t < 2.5)
    assert np.allclose(serie[ventana], s * h_inc, atol=1e-9)


def test_line_packing_con_friccion():
    r = _valvula(allievi.cierre_instantaneo, f=0.03, t_fin=2 * L / A_ONDA)
    h = r.H_abajo[(r.t > 0) & (r.t < 2 * L / A_ONDA - 1e-9)]
    # con Courant = 1 la malla se desacopla en dos sub-mallas: la cabeza sube en
    # escalones cada 2·dt (no decreciente) por el empaquetamiento de la línea
    assert np.all(np.diff(h) >= -1e-9) and h[-1] - h[0] > 1.0


def _curva(h_suc=10.0):
    # curva por 3 puntos con H(Q0) = H_RES − h_suc (sin fricción): punto de operación Q0
    h = H_RES - h_suc
    return moc.CurvaBomba.por_puntos([(0.0, h + 20.0), (Q0, h), (2 * Q0, h - 50.0)])


def test_parada_con_inercia_tiende_a_instantanea_con_I_pequena():
    # succión baja: con la bomba ya detenida no pasa agua desde la succión, que es
    # lo que supone la parada instantánea (Q = 0)
    r = _bomba("parada_inercia", H_succion=-60.0, curva=_curva(-60.0), n_rpm=1750,
               inercia=1e-7, eta=0.75)
    ref = _bomba("parada_instantanea", H_succion=-60.0)
    assert r.H_arriba[1:].min() == pytest.approx(ref.H_arriba[1:].min(), abs=0.01 * A_ONDA * V0 / G)
    assert np.all(np.diff(r.alpha) <= 1e-15) and r.alpha.min() >= 0


def test_parada_con_inercia_real_amortigua_la_depresion():
    r = _bomba("parada_inercia", curva=_curva(), n_rpm=1750, inercia=5.0, eta=0.75)
    ref = _bomba("parada_instantanea")
    assert r.H_arriba[1:].min() > ref.H_arriba[1:].min() + 1.0


def test_hidroneumatico_infinito_se_comporta_como_embalse():
    vaso = moc.Hidroneumatico(V_aire0=1e9, n=1.2, C_orificio=0.0, z=0.0, H_bar=10.33)
    r = _bomba("parada_instantanea", hidroneumatico=vaso)
    assert np.max(np.abs(r.H_arriba - r.H_arriba[0])) < 1e-3


def test_hidroneumatico_real_reduce_la_depresion():
    vaso = moc.Hidroneumatico(V_aire0=2.0, n=1.2, C_orificio=0.0, z=0.0, H_bar=10.33)
    r = _bomba("parada_instantanea", hidroneumatico=vaso)
    ref = _bomba("parada_instantanea")
    assert r.H_arriba.min() > ref.H_arriba[1:].min() + 5.0
    assert np.all(np.diff(r.V_aire[:5]) >= 0)            # el aire se expande al entregar agua


def test_cavitacion_se_detecta_con_perfil():
    r = moc.run(moc.Config(tuberias=[moc.Tuberia(L, D, A_ONDA, 0.0)],
                           aguas_arriba=moc.Bomba(H_succion=10.0, modo="parada_instantanea"),
                           aguas_abajo=moc.Embalse(H_RES), Q0=Q0, N_min=24, t_fin=4.0,
                           z_de_x=lambda x: np.full_like(x, 95.0), h_vapor_rel=-9.8))
    t_cav, x_cav = r.cavitacion
    assert 0 < t_cav < 0.1 and x_cav == pytest.approx(0.0)


def test_clasificacion_y_longitud_critica():
    assert allievi.clasificar(1.0, A_ONDA, L) == "rápida"
    assert allievi.clasificar(5.0, A_ONDA, L) == "lenta"
    assert allievi.longitud_critica(5.0, A_ONDA) == pytest.approx(3000.0)


def test_ajuste_de_celeridad_reportado():
    cfg = moc.Config(tuberias=[moc.Tuberia(1000.0, 0.3, 1000.0, 0.0),
                               moc.Tuberia(333.0, 0.3, 1000.0, 0.0)],
                     aguas_arriba=moc.Embalse(H_RES), aguas_abajo=moc.Valvula(lambda t: 1.0, 20.0),
                     Q0=Q0, N_min=3, t_fin=1.0)
    r = moc.run(cfg)
    assert 0 < r.ajuste_a_pct < 5

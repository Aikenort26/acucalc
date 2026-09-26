import pytest

from core import epanet_engine as ee
from core import project as pj
from core import red_diseno as rd
from tests.test_epanet_engine import INP_1, INP_TANQUE

requiere_epanet = pytest.mark.skipif(not ee.disponible(), reason="EPANET no disponible")


def _res(presiones, velocidades):
    return ee.SteadyResult({}, {}, velocidades, {}, 1, True, presiones=presiones,
                           avisos=[], motor="x")


def test_resumen_estatico_extremos_y_violaciones():
    r = rd.resumen_estatico(_res({"A": 8.0, "B": 30.0, "C": 75.0},
                                 {"P1": 0.2, "P2": -2.5, "P3": 7.0}),
                            p_min=15, p_max=70, v_max=6)
    assert (r.p_min, r.nodo_p_min) == (8.0, "A")
    assert (r.p_max, r.nodo_p_max) == (75.0, "C")
    assert (r.v_max, r.tubo_v_max) == (7.0, "P3")
    assert r.bajo_p_min == ["A"] and r.sobre_p_max == ["C"] and r.sobre_v_max == ["P3"]
    assert not r.cumple


def test_k2_vs_pico_del_patron():
    assert rd.aviso_pico_vs_k2([1.0] * 23 + [1.6], 1.6) is None
    msg = rd.aviso_pico_vs_k2([1.0] * 23 + [1.8], 1.5)
    assert msg and "1.80" in msg and "1.50" in msg


def test_curvas_de_bombas_del_proyecto_usa_la_seleccionada_transformada():
    s = pj.PumpSystemData(nombre="Rebombeo")
    s.bombas = [pj.PumpData("B1", puntos_qh=[(0, 40), (5, 35), (10, 20)], n_unidades=2,
                            arreglo="paralelo"),
                pj.PumpData("B2", puntos_qh=[(0, 10), (5, 8), (10, 2)])]
    s.bomba_seleccionada = "B1"
    p = pj.Project(bombeos=[s])
    curvas = rd.curvas_bombas(p)
    assert list(curvas) == ["Rebombeo · B1"]
    assert curvas["Rebombeo · B1"][1] == (10, 35)          # 2 en paralelo: Q×2


def test_cambios_red_multiplicador_y_bombas_conectadas():
    s = pj.PumpSystemData(nombre="S")
    s.bombas = [pj.PumpData("B", puntos_qh=[(0, 40), (5, 35), (10, 20)])]
    s.bomba_seleccionada = "B"
    p = pj.Project(bombeos=[s], red_conexiones={"S · B": ["J0", "J0B"]})
    c = rd.cambios_red(p, k2=1.5)
    assert c.multiplicador == 1.5 and c.bombas[0].nodo1 == "J0"
    assert rd.cambios_red(p, k2=1.5, patron=[1.0] * 24).multiplicador == 1.0   # EPS
    p.red_aplicar_k2 = False
    assert rd.cambios_red(p, k2=1.5).multiplicador == 1.0
    p.red_conexiones = {"S · B": ["", "J0B"]}          # conexión incompleta: no se usa
    assert rd.cambios_red(p, k2=1.5).bombas == []


@requiere_epanet
def test_resumen_eps_minimos_por_nodo_y_tanques():
    patron = [0.6] * 6 + [1.6] + [1.0] * 17
    eps = ee.correr_eps(INP_TANQUE, ee.Cambios(patron=patron))
    r = rd.resumen_eps(eps, p_min=15)
    assert r.p_min == pytest.approx(min(min(v) for v in eps.presiones.values()))
    assert eps.presiones[r.nodo_critico][r.hora_critica] == pytest.approx(r.p_min)
    t = r.tanques["T1"]
    assert t["min"] <= t["max"]


@requiere_epanet
def test_resumen_estatico_con_epanet():
    res = ee.correr_estatico(INP_1)
    r = rd.resumen_estatico(res, p_min=15, p_max=70, v_max=6)
    assert r.cumple and r.nodo_p_min in {"J1", "J2"}

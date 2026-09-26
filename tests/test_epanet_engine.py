import math
import tempfile
from pathlib import Path

import pytest

from core import epanet_engine as ee
from core import network as net

pytestmark = pytest.mark.skipif(not ee.disponible(), reason="epyt/EPANET no disponible")

FT, IN, GPM = 0.3048, 25.4, 0.0630901964

INP_1 = """[JUNCTIONS]
J1 10 0
J2 8 5.5

[RESERVOIRS]
R1 50

[PIPES]
P1 R1 J1 200 150 130
P2 J1 J2 150 100 130

[OPTIONS]
Units LPS
Headloss H-W

[END]
"""


def _hw(q_lps, L, d_mm, c=130.0):
    return 10.667 * L * (q_lps / 1000) ** 1.852 / (c ** 1.852 * (d_mm / 1000) ** 4.871)


def test_estatico_coincide_con_hazen_williams_analitico():
    r = ee.correr_estatico(INP_1)
    assert r.converged and r.motor.startswith("EPANET")
    h1 = 50 - _hw(5.5, 200, 150)
    h2 = h1 - _hw(5.5, 150, 100)
    assert r.heads["J1"] == pytest.approx(h1, rel=2e-3)
    assert r.presiones["J2"] == pytest.approx(h2 - 8, rel=2e-3)
    assert r.flows["P1"] == pytest.approx(5.5, rel=1e-6)
    assert r.hf["P2"] == pytest.approx(r.heads["J1"] - r.heads["J2"], abs=1e-6)
    v = 5.5e-3 / (math.pi * 0.1 ** 2 / 4)
    assert r.velocities["P2"] == pytest.approx(v, rel=1e-4)


def _inp_1_us():
    return f"""[JUNCTIONS]
J1 {10 / FT:.8f} 0
J2 {8 / FT:.8f} {5.5 / GPM:.8f}

[RESERVOIRS]
R1 {50 / FT:.8f}

[PIPES]
P1 R1 J1 {200 / FT:.8f} {150 / IN:.8f} 130
P2 J1 J2 {150 / FT:.8f} {100 / IN:.8f} 130

[OPTIONS]
Units GPM
Headloss H-W

[END]
"""


def test_mismo_resultado_en_lps_y_gpm():
    si, us = ee.correr_estatico(INP_1), ee.correr_estatico(_inp_1_us())
    for n in ("J1", "J2"):
        assert us.presiones[n] == pytest.approx(si.presiones[n], abs=1e-3)
    assert us.flows["P2"] == pytest.approx(si.flows["P2"], rel=1e-5)


def test_inp_sin_units_se_corre_como_lps():
    r = ee.correr_estatico(INP_1.replace("Units LPS\n", ""))
    assert r.flows["P1"] == pytest.approx(5.5, rel=1e-6)


def test_cambios_de_demanda_y_multiplicador():
    r = ee.correr_estatico(INP_1, ee.Cambios(demandas={"J1": 1.0, "J2": 2.0}, multiplicador=1.5))
    assert r.flows["P1"] == pytest.approx(4.5, rel=1e-6)
    assert r.flows["P2"] == pytest.approx(3.0, rel=1e-6)


def test_cambio_de_diametro_reduce_perdidas():
    base = ee.correr_estatico(INP_1)
    r = ee.correr_estatico(INP_1, ee.Cambios(diametros={"P2": 150.0}))
    assert r.hf["P2"] < base.hf["P2"]


def test_estatico_ignora_patron_del_inp():
    con_patron = INP_1.replace("J2 8 5.5", "J2 8 5.5 PAT1") .replace(
        "[OPTIONS]", "[PATTERNS]\nPAT1 0.2 0.2\n\n[OPTIONS]")
    r = ee.correr_estatico(con_patron)
    assert r.flows["P2"] == pytest.approx(5.5, rel=1e-6)


def test_nodo_inexistente_lanza_engine_error():
    malo = INP_1.replace("P2 J1 J2", "P2 J1 JX")
    with pytest.raises(ee.EngineError) as e:
        ee.correr_estatico(malo)
    assert e.value.codigo == 203


def test_presion_negativa_genera_aviso_6():
    alto = INP_1.replace("J2 8 5.5", "J2 80 5.5")
    r = ee.correr_estatico(alto)
    assert any("6" == str(a.codigo) for a in r.avisos)
    assert r.presiones["J2"] < 0


def test_no_deja_archivos_temporales():
    base = Path(tempfile.gettempdir())
    antes = set(base.glob("acucalc_epanet_*"))
    ee.correr_estatico(INP_1)
    assert set(base.glob("acucalc_epanet_*")) == antes


INP_TANQUE = """[JUNCTIONS]
J1 10 0
J2 5 4.0

[RESERVOIRS]
R1 40

[TANKS]
T1 30 3 0 6 60 0

[PIPES]
P1 R1 J1 500 150 130
P2 J1 T1 100 150 130
P3 T1 J2 300 100 130

[OPTIONS]
Units LPS
Headloss H-W

[END]
"""


def test_eps_balance_de_masa_del_tanque():
    patron = [0.6, 0.7, 0.8, 0.9, 1, 1.2, 1.6, 1.2, 1, 1.1, 1.1, 1.2,
              1.1, 1.1, 1, 1.1, 1.2, 1.1, 0.9, 0.9, 0.9, 0.8, 0.8, 0.7]
    r = ee.correr_eps(INP_TANQUE, ee.Cambios(patron=patron))
    assert r.horas == list(range(25))
    area = math.pi * 60 ** 2 / 4
    niveles = r.niveles["T1"]
    entra = [r.flows["P2"][k] - r.flows["P3"][k] for k in range(24)]
    dv = sum(q / 1000 * 3600 for q in entra)
    assert (niveles[24] - niveles[0]) * area == pytest.approx(dv, rel=1e-4)
    # la demanda de J2 sigue el patrón
    assert r.demandas["J2"][6] == pytest.approx(4.0 * 1.6, rel=1e-6)


def test_eps_con_patron_constante_igual_al_estatico():
    est = ee.correr_estatico(INP_1)
    eps = ee.correr_eps(INP_1, ee.Cambios(patron=[1.0] * 24))
    for k in (0, 12, 23):
        assert eps.presiones["J2"][k] == pytest.approx(est.presiones["J2"], abs=1e-6)


INP_BOMBA = """[JUNCTIONS]
J0 0 0
J0B 0 0
J1 10 0
J2 8 5.5

[RESERVOIRS]
R1 20

[PIPES]
P0 R1 J0 10 150 130
P1 J0B J1 200 150 130
P2 J1 J2 150 100 130

[OPTIONS]
Units LPS
Headloss H-W

[END]
"""


def test_bomba_conectada_eleva_la_cabeza():
    curva = [(0.0, 40.0), (5.5, 35.0), (11.0, 20.0)]
    r = ee.correr_estatico(INP_BOMBA, ee.Cambios(bombas=[ee.BombaINP("B", "J0", "J0B", curva)]))
    assert r.converged
    assert r.heads["J0B"] - r.heads["J0"] == pytest.approx(35.0, abs=0.05)


def test_leer_inp_resume_componentes():
    m = ee.leer_inp(INP_TANQUE)
    assert (m.n_nodos, m.n_tanques, m.n_reservorios, m.n_tuberias) == (2, 1, 1, 3)
    assert m.unidades == "LPS" and m.headloss == "H-W"


def test_como_network_result_para_optimizar():
    red = net.parse_inp(INP_1)
    solver = ee.solver_para(INP_1)
    r = solver(red)
    assert set(r.heads) >= {"J1", "J2"} and r.converged
    res = net.optimize_diameters(red, "PVC-U", "RDE 21", v_max=0.5, p_min=5, solver=solver)
    assert res.result.converged

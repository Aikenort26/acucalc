import pytest
from core import network as net

INP_MINIMO = """[JUNCTIONS]
;ID  Elev  Demand
J1   10.0  0
J2   8.0   5.5   ; nodo de consumo

[RESERVOIRS]
;ID  Head
R1   50.0

[PIPES]
;ID  Node1  Node2  Length  Diameter  Roughness  MinorLoss
P1   R1     J1     200     150       130        0
P2   J1     J2     150     100       130        0

[OPTIONS]
Units LPS
Headloss H-W
"""


def test_parse_inp_minimo():
    n = net.parse_inp(INP_MINIMO)
    assert set(n.junctions) == {"J1", "J2"}
    assert n.junctions["J2"].demand == 5.5
    assert set(n.sources) == {"R1"}
    assert n.sources["R1"].head == 50.0
    assert len(n.pipes) == 2
    assert n.pipes[0].node1 == "R1" and n.pipes[0].node2 == "J1"
    assert n.headloss == "H-W"


def test_parse_inp_sin_reservorios_falla():
    with pytest.raises(ValueError, match="RESERVOIRS"):
        net.parse_inp("[JUNCTIONS]\nJ1 10.0 0\n")


def test_write_inp_demands_preserva_el_resto():
    nuevo = net.write_inp_demands(INP_MINIMO, {"J1": 12.34, "J2": 5.5})
    assert "12.3400" in nuevo
    n2 = net.parse_inp(nuevo)
    assert n2.junctions["J1"].demand == 12.34
    assert "[RESERVOIRS]" in nuevo and "R1   50.0" in nuevo
    assert "; nodo de consumo" in nuevo


def test_write_inp_demands_preserva_columna_patron():
    inp_con_patron = "[JUNCTIONS]\nJ1   10.0  0       PAT1\n\n[RESERVOIRS]\nR1   50.0\n"
    nuevo = net.write_inp_demands(inp_con_patron, {"J1": 7.5})
    lineas = [l for l in nuevo.splitlines() if l.startswith("J1")]
    assert len(lineas) == 1
    assert "7.5000" in lineas[0]
    assert "PAT1" in lineas[0]


INP_LINEAL = """[JUNCTIONS]
J1 0 0
J2 0 0

[RESERVOIRS]
R1 50.0

[PIPES]
P1 R1 J1 100 150 130
P2 J1 J2 200 100 130

[OPTIONS]
Headloss H-W
"""


def test_asignar_demandas_por_longitud_aferente():
    n = net.parse_inp(INP_LINEAL)
    d = net.assign_demands_by_length(n, qmd_lps=30.0)
    # J1: mitad de P1 (50) + mitad de P2 (100) = 150 de 300 -> 50%
    assert abs(d["J1"] - 15.0) < 1e-9
    # J2: solo mitad de P2 (100) de 300 -> 33.33%
    assert abs(d["J2"] - 10.0) < 1e-9
    assert "R1" not in d


def test_asignar_demandas_sin_tuberias_falla():
    n = net.Network(junctions={"J1": net.Junction("J1", 0.0)},
                    sources={"R1": net.Source("R1", 50.0)}, pipes=[])
    with pytest.raises(ValueError, match="longitud"):
        net.assign_demands_by_length(n, 10.0)


def _r_hw(L, D_mm, C):
    D = D_mm / 1000.0
    return 10.67 * L / (C ** 1.852 * D ** 4.8704)


def test_solve_dos_tuberias_en_serie():
    n = net.Network(
        junctions={"J1": net.Junction("J1", 0.0, 0.0),
                   "J2": net.Junction("J2", 0.0, 50.0)},
        sources={"R": net.Source("R", 100.0)},
        pipes=[net.Pipe("P1", "R", "J1", 200.0, 150.0, 130.0),
               net.Pipe("P2", "J1", "J2", 150.0, 100.0, 130.0)],
        headloss="H-W")
    r1, r2 = _r_hw(200.0, 150.0, 130.0), _r_hw(150.0, 100.0, 130.0)
    Q0 = 0.05
    h_j2_esperado = 100.0 - (r1 + r2) * Q0 ** 1.852
    res = net.solve(n)
    assert res.converged
    assert abs(res.heads["J2"] - h_j2_esperado) < 1e-3
    assert abs(res.flows["P1"] - 50.0) < 1e-2
    assert abs(res.flows["P2"] - 50.0) < 1e-2


def test_solve_dos_tuberias_en_paralelo_iguales():
    n = net.Network(
        junctions={"J": net.Junction("J", 0.0, 50.0)},
        sources={"R": net.Source("R", 100.0)},
        pipes=[net.Pipe("P1", "R", "J", 200.0, 150.0, 130.0),
               net.Pipe("P2", "R", "J", 200.0, 150.0, 130.0)],
        headloss="H-W")
    r = _r_hw(200.0, 150.0, 130.0)
    Q0 = 0.05
    h_j_esperado = 100.0 - r * (Q0 / 2) ** 1.852
    res = net.solve(n)
    assert res.converged
    assert abs(res.heads["J"] - h_j_esperado) < 1e-3
    assert abs(res.flows["P1"] - 25.0) < 1e-2
    assert abs(res.flows["P2"] - 25.0) < 1e-2


def test_optimize_diameters_converge():
    n = net.Network(
        junctions={"J1": net.Junction("J1", 0.0, 0.0),
                   "J2": net.Junction("J2", 0.0, 30.0)},
        sources={"R": net.Source("R", 50.0)},
        pipes=[net.Pipe("P1", "R", "J1", 300.0, 50.0, 130.0),
               net.Pipe("P2", "J1", "J2", 300.0, 50.0, 130.0)],
        headloss="H-W")
    r = net.optimize_diameters(n, "PEAD PE100", "RDE 21", v_max=2.0, p_min=15.0, p_max=70.0)
    assert all(abs(v) <= 2.0 + 1e-6 for v in r.result.velocities.values())
    for jid, j in n.junctions.items():
        assert r.result.heads[jid] - j.elevation >= 15.0 - 1e-3
    assert r.dn_optimizado["P1"] >= r.dn_original["P1"]


def test_optimize_diameters_avisa_si_p_min_no_se_resuelve():
    n = net.Network(
        junctions={"J1": net.Junction("J1", 0.0, 0.0),
                   "J2": net.Junction("J2", 0.0, 30.0)},
        sources={"R": net.Source("R", 50.0)},
        pipes=[net.Pipe("P1", "R", "J1", 300.0, 50.0, 130.0),
               net.Pipe("P2", "J1", "J2", 300.0, 50.0, 130.0)],
        headloss="H-W")
    r = net.optimize_diameters(n, "PEAD PE100", "RDE 21", v_max=2.0,
                               p_min=1000.0, p_max=70.0)
    assert r.avisos
    assert any("J2" in aviso or "J1" in aviso for aviso in r.avisos)

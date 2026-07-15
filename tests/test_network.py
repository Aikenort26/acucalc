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

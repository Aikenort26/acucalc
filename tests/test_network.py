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

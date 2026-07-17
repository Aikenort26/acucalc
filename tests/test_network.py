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


# ---------- WP-4a: escritura de diámetros y rugosidad al INP ----------

INP_PIPES = """[JUNCTIONS]
J1   10.0  0
J2   8.0   5.5   ; consumo

[RESERVOIRS]
R1   50.0

[PIPES]
;ID  Node1  Node2  Length  Diameter  Roughness  MinorLoss
P1   R1     J1     200     150       130        0    ; tramo principal
P2   J1     J2     150     100       130        0

[OPTIONS]
Headloss H-W
"""


def test_write_inp_pipes_reescribe_diametro_y_rugosidad():
    # simula el resultado de la optimización: nuevos diámetros internos y C
    cambios = {"P1": (168.3, 150.0), "P2": (110.2, 150.0)}
    nuevo = net.write_inp_pipes(INP_PIPES, cambios)
    n2 = net.parse_inp(nuevo)
    p1 = next(p for p in n2.pipes if p.id == "P1")
    p2 = next(p for p in n2.pipes if p.id == "P2")
    assert abs(p1.diameter_mm - 168.3) < 1e-6
    assert abs(p1.roughness - 150.0) < 1e-6
    assert abs(p2.diameter_mm - 110.2) < 1e-6


def test_write_inp_pipes_preserva_todo_lo_demas():
    nuevo = net.write_inp_pipes(INP_PIPES, {"P1": (168.3, 150.0)})
    # otras secciones intactas
    assert "[RESERVOIRS]" in nuevo and "R1   50.0" in nuevo
    assert "; consumo" in nuevo                     # comentario de [JUNCTIONS]
    assert "; tramo principal" in nuevo             # comentario del propio tramo
    # tramo NO tocado conserva su diámetro original
    n2 = net.parse_inp(nuevo)
    assert next(p for p in n2.pipes if p.id == "P2").diameter_mm == 100.0
    # el minorloss del tramo tocado se preserva
    assert next(p for p in n2.pipes if p.id == "P1").minorloss == 0.0


def test_roundtrip_parse_optimize_write_parse():
    n = net.parse_inp(INP_PIPES)
    opt = net.optimize_diameters(n, "PEAD PE100", "RDE 21",
                                 v_max=2.0, p_min=5.0, p_max=200.0)
    c = net.coef_rugosidad("PEAD PE100", "H-W")
    cambios = {p.id: (opt.dn_optimizado[p.id], c) for p in n.pipes}
    nuevo = net.write_inp_pipes(INP_PIPES, cambios)
    n2 = net.parse_inp(nuevo)
    for p in n2.pipes:
        assert abs(p.diameter_mm - opt.dn_optimizado[p.id]) < 1e-6
        assert abs(p.roughness - c) < 1e-6


def test_coef_rugosidad_hw_y_dw():
    # H-W: coeficiente C (adimensional, plásticos altos)
    c_pead = net.coef_rugosidad("PEAD PE100", "H-W")
    assert 140 <= c_pead <= 155
    # D-W: rugosidad absoluta ks en mm (del catálogo)
    ks_pead = net.coef_rugosidad("PEAD PE100", "D-W")
    assert 0.0 < ks_pead < 0.1
    # material desconocido no revienta: devuelve un default razonable
    assert net.coef_rugosidad("Material inexistente", "H-W") > 0


# ---------- WP-8: transferir curvas de bomba al INP ----------

def test_write_inp_pump_curves_agrega_curves_y_pumps():
    curvas = {"Bomba A": [(0.0, 45.0), (10.0, 40.0), (20.0, 28.0)],
              "Bomba B": [(0.0, 60.0), (15.0, 50.0)]}
    nuevo = net.write_inp_pump_curves(INP_PIPES, curvas)
    assert "[CURVES]" in nuevo
    assert "[PUMPS]" in nuevo
    # los puntos Q-H de cada bomba aparecen
    assert "45" in nuevo and "28" in nuevo and "60" in nuevo
    # el nombre de la bomba queda como comentario/referencia
    assert "Bomba A" in nuevo and "Bomba B" in nuevo
    # el resto del archivo se preserva y sigue parseando
    n2 = net.parse_inp(nuevo)
    assert set(n2.junctions) == {"J1", "J2"}
    assert len(n2.pipes) == 2


def test_write_inp_pump_curves_vacio_no_cambia_nada():
    assert net.write_inp_pump_curves(INP_PIPES, {}) == INP_PIPES


def test_write_inp_pump_curves_preserva_curves_existente():
    inp_con_curves = INP_PIPES + "\n[CURVES]\n;ID X Y\nCEXIST 1 2\n"
    nuevo = net.write_inp_pump_curves(inp_con_curves, {"B1": [(0.0, 30.0)]})
    assert "CEXIST" in nuevo            # no se pierde la curva que ya existía
    assert "B1" in nuevo


# ---------- WP-7: coordenadas y tipo de fuente para el mapa ----------

INP_COORDS = """[JUNCTIONS]
J1 10 0
J2 8 5.5

[RESERVOIRS]
R1 50

[TANKS]
T1 30 5 0 10 5 100

[PIPES]
P1 R1 J1 200 150 130
P2 J1 J2 150 100 130

[COORDINATES]
;Node X Y
J1 100 200
J2 150 200
R1 0 200
T1 300 250

[OPTIONS]
Headloss H-W
"""


def test_parse_coordenadas_y_tipo_fuente():
    n = net.parse_inp(INP_COORDS)
    assert n.junctions["J1"].x == 100 and n.junctions["J1"].y == 200
    assert n.sources["R1"].tipo == "reservorio"
    assert n.sources["T1"].tipo == "tanque"
    assert n.sources["R1"].x == 0
    assert n.sources["T1"].x == 300


def test_parse_sin_coordenadas_no_rompe():
    n = net.parse_inp(INP_MINIMO)          # INP_MINIMO no tiene [COORDINATES]
    assert n.junctions["J1"].x is None


def test_mapa_con_y_sin_coordenadas():
    from core import network_map as nm
    n = net.parse_inp(INP_COORDS)
    assert nm.tiene_coordenadas(n) is True
    fig = nm.fig_red(n)
    assert fig is not None
    import matplotlib.pyplot as plt
    plt.close(fig)
    # sin coordenadas: usa layout automático, no revienta
    n2 = net.parse_inp(INP_MINIMO)
    assert nm.tiene_coordenadas(n2) is False
    fig2 = nm.fig_red(n2, net.solve(n2), colorear="presion")
    assert fig2 is not None
    plt.close(fig2)


def _areas_marcadores(escala):
    """Áreas (`s`) de los marcadores del mapa para una escala dada."""
    import matplotlib.pyplot as plt
    from core import network_map as nm
    fig = nm.fig_red(net.parse_inp(INP_COORDS), dark=False, escala=escala)
    areas = [float(c.get_sizes()[0]) for c in fig.axes[0].collections
             if hasattr(c, "get_sizes") and len(c.get_sizes())]
    plt.close(fig)
    return areas


def test_mapa_escala_de_iconos():
    """La escala controla el tamaño de nodos/fuentes y el grosor de tramos: en
    una red densa los marcadores por defecto se enciman y tapan la topología."""
    base, doble = _areas_marcadores(1.0), _areas_marcadores(2.0)
    assert base and len(base) == len(doble)
    # el área va con escala²: al doblar la escala, el área se cuadruplica
    for a, b in zip(base, doble):
        assert b == pytest.approx(a * 4.0)


@pytest.mark.parametrize("mala", [0.0, -3.0])
def test_mapa_escala_no_admite_cero_ni_negativa(mala):
    """Una escala <= 0 haría desaparecer los marcadores (`s=0`), y una negativa
    reaparecería con el tamaño equivocado al elevarla al cuadrado. Se acota por
    abajo a 0.1, así que ambas deben dar exactamente lo mismo que 0.1."""
    assert _areas_marcadores(mala) == pytest.approx(_areas_marcadores(0.1))

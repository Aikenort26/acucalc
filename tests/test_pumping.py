from core import pumping as pu


def _sistema_salado():
    tramos = [pu.Segment(nombre="Impulsión", tipo="impulsion", L=284.8,
                         D=0.0795, material="PEAD")]
    accesorios = [
        pu.Accessory("Válvula de mariposa", 1, "Impulsión"),
        pu.Accessory("Válvula de cheque", 1, "Impulsión"),
        pu.Accessory("Válvula de compuerta", 1, "Impulsión"),
        pu.Accessory("Codo radio corto", 4, "Impulsión"),
        pu.Accessory("Codo radio medio", 1, "Impulsión"),
        pu.Accessory("Unión", 5, "Impulsión"),
        pu.Accessory("Salida", 1, "Impulsión"),
    ]
    return pu.PumpSystem(tramos=tramos, accesorios=accesorios, he=69.8,
                         temperatura=20.0, eficiencia=0.73413)


def test_q_bombeo():
    assert abs(pu.q_bombeo(qmd_lps=2.142342, horas=10) - 5.141621) < 1e-4


def test_perdidas_por_tramo():
    # ν(20°C) del catálogo físico estándar (ρ=998.29, μ=0.001003 → ν≈1.0047e-6)
    # da un Re/f/hf algo distintos del Excel de El Salado (que implica
    # ν≈8.74e-7, más cercano a ~26°C). Se prioriza la propiedad física
    # correcta a 20°C sobre replicar el número exacto del Excel.
    sys = _sistema_salado()
    r = pu.solve(sys, Q=5.141621e-3)
    tr = r.tramos[0]
    assert abs(tr.V - 1.0358) < 2e-3
    assert abs(tr.hf - 3.756) < 0.01
    assert abs(tr.sum_km - 14.6) < 1e-9
    assert abs(tr.hl - 14.6 * tr.V**2 / 19.62) < 1e-6


def test_hd_y_potencia():
    sys = _sistema_salado()
    r = pu.solve(sys, Q=5.141621e-3)
    assert abs(r.hd - 74.354) < 0.01
    assert abs(r.potencia_kw - 5.100) < 0.01
    assert abs(r.potencia_hp - r.potencia_kw * 1000 / 745.7) < 1e-6


def test_multiples_tramos_suman():
    """Dos tramos distintos (materiales/diámetros) acumulan pérdidas — el caso
    que el Excel no podía manejar."""
    tramos = [
        pu.Segment("Succión", "succion", L=10, D=0.1034, material="PVC"),
        pu.Segment("Impulsión 1", "impulsion", L=150, D=0.0795, material="PEAD"),
        pu.Segment("Impulsión 2", "impulsion", L=134.8, D=0.0704, material="HD"),
    ]
    sys = pu.PumpSystem(tramos=tramos, accesorios=[], he=69.8,
                        temperatura=20.0, eficiencia=0.7)
    r = pu.solve(sys, Q=5.141621e-3)
    assert len(r.tramos) == 3
    assert abs(sum(t.hf for t in r.tramos) - r.hf_total) < 1e-9
    assert r.hd > 69.8 + r.hf_total - 1e-9


def test_velocidad_fuera_de_norma_alerta():
    tramos = [pu.Segment("Imp", "impulsion", L=100, D=0.25, material="PVC")]
    sys = pu.PumpSystem(tramos, [], he=10, temperatura=20, eficiencia=0.7)
    r = pu.solve(sys, Q=5e-3)   # V ≈ 0.10 m/s < 0.5
    assert any("Art. 56" in i for i in r.issues)


def test_bresse():
    assert abs(pu.bresse_continuo(Q=5.141621e-3, K=0.9643) - 0.06913) < 2e-4
    d_nc = pu.bresse_no_continuo(Q=5.141621e-3, horas=10)
    assert abs(d_nc - 1.3 * (10/24)**0.25 * (5.141621e-3)**0.5) < 1e-9


def test_curva_sistema():
    sys = _sistema_salado()
    pts = pu.system_curve(sys, q_max=5.784323e-3, n=10)
    assert len(pts) == 10
    assert abs(pts[0][1] - 69.8) < 1e-9        # Q=0 → H=He
    assert pts[-1][1] > pts[0][1]              # creciente


def test_celeridad_y_sobrepresion():
    c = pu.celeridad(D=0.3374, e=0.0062, k_elast=18.0)
    assert abs(c - 308.795) < 0.5
    assert abs(pu.sobrepresion_ariete(c, V=1.08) - 33.996) < 0.05
    c2 = pu.celeridad(D=0.0795, e=0.0052941, k_elast=111.11)
    assert abs(c2 - 238.932) < 0.5


def test_npsh_disponible():
    n = pu.npsh_disponible(patm_m=10.33, h_succion=3.0, perdidas_succion=0.5,
                           presion_vapor_m=0.24)
    assert abs(n - (10.33 - 0.24 - 3.0 - 0.5)) < 1e-9


def test_arreglo_bombas():
    par = pu.arreglo_bombas(10.0, 80.0, 2, "paralelo")
    assert par.q_unit_lps == 5.0 and par.h_unit == 80.0
    ser = pu.arreglo_bombas(10.0, 80.0, 2, "serie")
    assert ser.q_unit_lps == 10.0 and ser.h_unit == 40.0
    import pytest
    with pytest.raises(ValueError):
        pu.arreglo_bombas(10, 80, 2, "mixto")


def test_leyes_de_afinidad():
    q2, h2, p2 = pu.afinidad(q1=10.0, h1=80.0, p1=7.0, n1=3500, n2=1750)
    assert abs(q2 - 5.0) < 1e-9        # Q ∝ N
    assert abs(h2 - 20.0) < 1e-9       # H ∝ N²
    assert abs(p2 - 0.875) < 1e-9      # P ∝ N³
    assert abs(pu.frecuencia_para_caudal(5.0, 10.0, 60.0) - 30.0) < 1e-9


def test_paneles():
    r = pu.paneles_solares(potencia_kw=5.138662, panel_w=710, fs=3, area_panel_m2=2.9768)
    assert r.cantidad == 22
    assert abs(r.area_total - 65.4896) < 1e-3

import pytest
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




# ---------- golpe de ariete: factor de seguridad / uso / margen (WP-2c) ----------
def test_celeridad_y_sobrepresion_valores_conocidos():
    # PEAD DN90 RDE21: D≈0.0795 m, e≈0.0043 m, k_elast=111.11.
    c = pu.celeridad(0.0795, 0.0043, 111.11)
    assert abs(c - 215.9) < 1.0           # 9900/√(48.3 + 111.11·0.0795/0.0043)
    dh = pu.sobrepresion_ariete(c, 1.0)   # V = 1 m/s → ΔH = C·V/g
    assert abs(dh - c / 9.81) < 1e-6


def test_ariete_tramo_fs_uso_margen_coherentes():
    # Se calcula primero h_total con las mismas fórmulas y se fija PN = 2·h_total
    # para verificar la aritmética del FS de forma exacta: FS=2, uso=50%, margen=50%.
    c = pu.celeridad(0.0795, 0.0043, 111.11)
    dh = pu.sobrepresion_ariete(c, 1.2)
    hd = 74.0
    h_total = hd + dh
    r = pu.ariete_tramo("Impulsión", 0.0795, 0.0043, 111.11, 1.2, hd, 2 * h_total)
    assert abs(r.h_total - h_total) < 1e-6
    assert abs(r.dh - dh) < 1e-9
    assert abs(r.fs - 2.0) < 1e-9
    assert abs(r.uso_pct - 50.0) < 1e-9
    assert abs(r.margen_pct - 50.0) < 1e-9
    assert r.cumple is True
    # relaciones internas siempre válidas
    assert abs(r.fs * r.uso_pct - 100.0) < 1e-9
    assert abs(r.margen_pct - (100.0 - r.uso_pct)) < 1e-9


def test_ariete_tramo_no_cumple_cuando_supera_pn():
    r = pu.ariete_tramo("T", 0.0795, 0.0043, 111.11, 2.0, 74.0, pn=80.0)
    assert r.h_total > 80.0
    assert r.fs < 1.0
    assert r.uso_pct > 100.0
    assert r.margen_pct < 0.0
    assert r.cumple is False


def test_ariete_tramo_pn_cero_no_revienta():
    r = pu.ariete_tramo("Manual sin PN", 0.0795, 0.0043, 111.11, 1.5, 74.0, pn=0.0)
    assert r.c > 0 and r.dh > 0 and r.h_total > 0   # sí se calcula la hidráulica
    assert r.fs is None and r.uso_pct is None
    assert r.margen_pct is None and r.cumple is None


def test_ariete_tramo_frozen():
    import dataclasses
    r = pu.ariete_tramo("T", 0.0795, 0.0043, 111.11, 1.0, 50.0, 150.0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.fs = 9.0


# --- WP5 v9: NPSH disponible del sistema -------------------------------------

from core import propiedades as _pr


def _sistema_con_succion(he=20.0):
    return pu.PumpSystem(
        tramos=[pu.Segment("Succión", "succion", 6.0, 0.1022, "PVC"),
                pu.Segment("Impulsión", "impulsion", 300.0, 0.0795, "PEAD")],
        accesorios=[pu.Accessory("Entrada recta a tope", 1, "Succión"),
                    pu.Accessory("Codo radio corto", 2, "Succión")],
        he=he, temperatura=20.0, eficiencia=0.7)


def test_npsh_sistema_suma_solo_perdidas_de_succion():
    sist = _sistema_con_succion()
    r = pu.solve(sist, 0.008)
    n = pu.npsh_sistema(r, altitud_m=0.0, temperatura=20.0, z_succion=3.0)
    suc = r.tramos[0]
    assert n.perdidas_succion == pytest.approx(suc.hf + suc.hl)
    rho = 998.29
    assert n.patm_m == pytest.approx(_pr.carga_m(101325.0, rho))
    assert n.pv_m == pytest.approx(_pr.carga_m(_pr.presion_vapor_pa(20.0), rho))
    assert n.npsh_d == pytest.approx(n.patm_m - n.pv_m - 3.0 - n.perdidas_succion)
    assert 6.5 < n.npsh_d < 7.4          # ~10.35 − 0.24 − 3 − pérdidas
    assert n.cumple is None              # sin NPSHr no se verifica


def test_npsh_verifica_con_margen():
    r = pu.solve(_sistema_con_succion(), 0.008)
    n0 = pu.npsh_sistema(r, 0.0, 20.0, 3.0)
    assert pu.npsh_sistema(r, 0.0, 20.0, 3.0, npsh_r=n0.npsh_d - 1.0, margen=0.5).cumple is True
    assert pu.npsh_sistema(r, 0.0, 20.0, 3.0, npsh_r=n0.npsh_d - 1.0, margen=1.5).cumple is False


def test_npsh_baja_con_altitud_y_temperatura():
    r = pu.solve(_sistema_con_succion(), 0.008)
    base = pu.npsh_sistema(r, 0.0, 20.0, 3.0).npsh_d
    assert pu.npsh_sistema(r, 2600.0, 20.0, 3.0).npsh_d < base
    assert pu.npsh_sistema(r, 0.0, 35.0, 3.0).npsh_d < base


def test_succion_ahogada_aumenta_npsh():
    r = pu.solve(_sistema_con_succion(), 0.008)
    assert (pu.npsh_sistema(r, 0.0, 20.0, -2.0).npsh_d
            == pytest.approx(pu.npsh_sistema(r, 0.0, 20.0, 3.0).npsh_d + 5.0))

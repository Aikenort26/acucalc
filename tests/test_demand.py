from core import demand


def test_dotacion_por_altitud():
    assert demand.dotacion_altitud(150) == 140
    assert demand.dotacion_altitud(1500) == 130
    assert demand.dotacion_altitud(2600) == 120


def test_dotacion_por_usos():
    usos = [("Tomar", 5), ("Lavar ropa", 15), ("Cocinar", 4), ("Descarga de baño", 20),
            ("Aseo vivienda", 10), ("Ducha", 15), ("Lavado de loza", 11)]
    assert demand.dotacion_usos(usos) == 80


def test_dotacion_bruta_y_alerta_perdidas():
    r = demand.flows(pop=1601.813, dneta=80, perdidas=0.10, k1=1.3, k2=1.6)
    assert abs(r.dbruta - 88.8889) < 1e-3
    assert r.issues == []
    r2 = demand.flows(pop=1000, dneta=80, perdidas=0.30, k1=1.3, k2=1.6)
    assert any("25%" in i for i in r2.issues)   # Art. 44


def test_caudales_golden_salado():
    r = demand.flows(pop=1601.813, dneta=80, perdidas=0.10, k1=1.3, k2=1.6)
    assert abs(r.qmed_lps - 1.64796) < 1e-3
    assert abs(r.qmd_lps - 2.14234) < 1e-3
    assert abs(r.qmh_lps - 3.42775) < 1e-3


def test_caudales_componentes():
    r = demand.flows(pop=1601.813, dneta=80, perdidas=0.10, k1=1.3, k2=1.6)
    c = demand.design_flows_by_component(r)
    assert abs(c["Captación superficial"] - 2 * r.qmd_lps) < 1e-9
    assert abs(c["Captación subterránea"] - r.qmd_lps) < 1e-9
    assert abs(c["Red de distribución"] - r.qmh_lps) < 1e-9
    for comp in ("Desarenador", "Aducción", "Conducción", "Tanque"):
        assert abs(c[comp] - r.qmd_lps) < 1e-9

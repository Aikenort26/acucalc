from core import catalogs


def test_agua_interpolacion():
    w = catalogs.water_props(20.0)
    assert abs(w.rho - 998.29) < 0.5          # kg/m3 a 20 C
    assert abs(w.mu - 0.001003) < 5e-5        # kg/m-s a 20 C
    assert abs(w.nu - w.mu / w.rho) < 1e-12


def test_ks_materiales():
    ks = catalogs.roughness()
    assert abs(ks["PVC"] - 0.0015e-3) < 1e-9  # metros
    assert abs(ks["PEAD"] - 0.007e-3) < 1e-9


def test_km_accesorios():
    km = catalogs.minor_loss_coefficients()
    assert km["Válvula de mariposa"] == 5.0
    assert km["Válvula de cheque"] == 2.5
    assert km["Codo radio corto"] == 0.9


def test_dotaciones_referencias():
    d = catalogs.dotacion_references()
    alturas = {r["rango"]: r["dotacion"] for r in d["res0330_art43"]}
    assert alturas["<1000"] == 140
    assert alturas["1000-2000"] == 130
    assert alturas[">2000"] == 120
    ids = {r["id"] for r in d["otras_referencias"]}
    assert {"res0844_2018", "cra_conceptos", "minimo_vital"} <= ids

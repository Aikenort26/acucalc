import pytest
from core import pipes


def test_materiales_y_series():
    ms = pipes.materials()
    assert {"PEAD PE100", "PVC-U", "Hierro dúctil", "Acero comercial", "GRP"} <= set(ms)
    assert "RDE 21" in pipes.series("PEAD PE100")
    assert "RDE 21" in pipes.series("PVC-U")
    assert "K9" in pipes.series("Hierro dúctil")


def test_pead_110_rde21():
    s = pipes.pipe("PEAD PE100", "RDE 21", 110)
    assert abs(s.e_mm - 5.2) < 1e-9              # 110/21 = 5.24 → 5.2
    assert abs(s.id_mm - (110 - 2 * 5.2)) < 1e-9
    assert s.k_elast == 111.11
    assert s.ks_mm == 0.007 and s.pn_mca == 82 and s.largo_m == 12
    assert abs(s.dn_in - 110 / 25.4) < 1e-6


def test_propiedades_completas_pvc():
    s = pipes.pipe("PVC-U", "RDE 26", 6)
    assert s.pn_mca == 113 and s.ks_mm == 0.0015 and s.largo_m == 6
    assert abs(s.dn_mm - 6 * 25.4) < 1e-6


def test_pvc_4in_rde21():
    s = pipes.pipe("PVC-U", "RDE 21", 4)
    assert abs(s.od_mm - 114.3) < 1e-9
    assert abs(s.e_mm - 5.4) < 1e-9              # 114.3/21 = 5.44 → 5.4
    assert s.unidad_dn == "in"


def test_hd_k9_dn200():
    s = pipes.pipe("Hierro dúctil", "K9", 200)
    assert abs(s.e_mm - 6.3) < 1e-9              # 9·(0.5+0.2) = 6.3
    assert abs(s.id_mm - 200) < 1e-9             # base id: DN = interno nominal
    assert s.k_elast == 1.0


def test_hd_k9_minimo_6mm():
    assert pipes.pipe("Hierro dúctil", "K9", 50).e_mm == 6.0


def test_rango_dn_50_a_1200():
    for mat in pipes.materials():
        for ser in pipes.series(mat):
            dns = pipes.diameters(mat, ser)
            assert dns == sorted(dns)
    assert max(pipes.diameters("PEAD PE100", "RDE 11")) == 1200
    assert max(pipes.diameters("Hierro dúctil", "K9")) == 1200


def test_dn_inexistente():
    with pytest.raises(KeyError):
        pipes.pipe("PEAD PE100", "RDE 21", 999)


def test_suggest_dn():
    # San Jacinto: Qb ≈ 103 L/s → Bresse ≈ 385 mm → PEAD RDE21 DN 450 (ID 407)
    dn = pipes.suggest_dn("PEAD PE100", "RDE 21", 0.10317)
    spec = pipes.pipe("PEAD PE100", "RDE 21", dn)
    import math
    v = 4 * 0.10317 / (math.pi * (spec.id_mm / 1000) ** 2)
    assert spec.id_mm >= 1.2 * math.sqrt(0.10317) * 1000 * 0.999
    assert v <= 6.0
    # caudal pequeño: 5.14 L/s → Bresse 86 mm → DN 110 (ID 99.6)
    assert pipes.suggest_dn("PEAD PE100", "RDE 21", 5.1416e-3) == 110

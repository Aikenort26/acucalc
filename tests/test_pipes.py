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

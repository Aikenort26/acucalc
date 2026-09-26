import pytest

from core import pipeline, pipes, storage
from core import project as pj
from tests.test_e2e_pipeline import _proyecto_salado


def test_design_flows_golden_el_salado():
    d = pipeline.design_flows(_proyecto_salado())
    assert abs(d.pob_final - 1601.813) < 0.05
    assert abs(d.flows.qmd_lps - 2.14234) < 1e-3
    assert d.serie_total[-1] == (2051, d.pob_final)


def test_design_flows_aplica_poblacion_flotante():
    p = _proyecto_salado()
    base = pipeline.design_flows(p).pob_final
    p.poblacion.flotante_pct = 0.10
    assert pipeline.design_flows(p).pob_final == pytest.approx(base * 1.10)


@pytest.mark.parametrize("romper", [
    lambda p: setattr(p, "censo", p.censo[:1]),
    lambda p: setattr(p.poblacion, "p0", 0),
    lambda p: setattr(p.poblacion, "metodo", ""),
    lambda p: setattr(p.poblacion, "metodo", "inexistente"),
    lambda p: setattr(p.demanda, "dneta", 0.0),
])
def test_design_flows_none_si_faltan_datos(romper):
    p = _proyecto_salado()
    romper(p)
    assert pipeline.design_flows(p) is None


def test_k_elast_tramo_catalogo_trae_pn():
    spec = pipes.pipe("PEAD PE100", "RDE 21", 90)
    t = pj.SegmentData("Imp", "impulsion", 100, 79.5, "PEAD", cat_material="PEAD PE100",
                       cat_serie="RDE 21", cat_dn=90, e_mm=4.3)
    assert pipes.k_elast_tramo(t) == (spec.k_elast, spec.pn_mca)


def test_k_elast_tramo_manual_sin_pn():
    t = pj.SegmentData("Imp", "impulsion", 100, 79.5, "PEAD", e_mm=5.3)
    assert pipes.k_elast_tramo(t) == (111.11, None)
    t.material = "desconocido"
    assert pipes.k_elast_tramo(t) == (18.0, None)


def test_patron_por_defecto_suma_24():
    assert len(storage.DEFAULT_PATTERN) == 24
    assert sum(storage.DEFAULT_PATTERN) == pytest.approx(24.0)

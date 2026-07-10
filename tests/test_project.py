import json
from core import project as pj


def _proyecto():
    p = pj.Project(nombre="El Salado", municipio="El Carmen de Bolívar",
                   departamento="Bolívar", corregimiento="El Salado",
                   consultor="Aiken Ortega", altitud=150, temperatura=20.0)
    p.censo = [(2018, 50848), (2019, 52021)]
    p.poblacion = pj.PopulationConfig(p0=1400, year0=2024, horizon_year=2051,
                                      tasa_res0844=0.005, metodo="res0844",
                                      justificacion="Retorno poblacional postconflicto",
                                      tipo="corregimiento", fuente="dane",
                                      dpto="Bolívar", mpio="El Carmen de Bolívar",
                                      area="Cabecera Municipal")
    p.demanda = pj.DemandConfig(modo="usos", dneta=80.0, perdidas=0.10, k1=1.3, k2=1.6,
                                usos=[("Tomar", 5.0)], referencia="", justificacion="")
    p.tramos = [pj.SegmentData("Impulsión", "impulsion", 284.8, 79.5, "PEAD")]
    p.accesorios = [pj.AccessoryData("Válvula de cheque", 1, "Impulsión")]
    p.bombas = [pj.PumpData(nombre="Bomba A", puntos_qh=[(2.9, 33.2), (4.0, 31.9), (5.1, 30.2)],
                            puntos_qe=[], imagen_b64="", cal=None)]
    return p


def test_roundtrip_json(tmp_path):
    p = _proyecto()
    f = tmp_path / "salado.acucalc.json"
    pj.save(p, f)
    p2 = pj.load(f)
    assert p2.nombre == "El Salado"
    assert p2.censo == [(2018, 50848), (2019, 52021)]
    assert p2.poblacion.metodo == "res0844"
    assert p2.poblacion.tipo == "corregimiento"
    assert p2.poblacion.mpio == "El Carmen de Bolívar"
    assert p2.tramos[0].material == "PEAD"
    assert p2.bombas[0].puntos_qh[1] == (4.0, 31.9)
    raw = json.loads(f.read_text(encoding="utf-8"))
    assert raw["schema_version"] == 1


def test_version_desconocida(tmp_path):
    import pytest
    f = tmp_path / "x.json"
    f.write_text('{"schema_version": 99}', encoding="utf-8")
    with pytest.raises(pj.SchemaError):
        pj.load(f)


def test_proyecto_vacio_serializa(tmp_path):
    p = pj.Project(nombre="Nuevo")
    f = tmp_path / "n.json"
    pj.save(p, f)
    assert pj.load(f).nombre == "Nuevo"

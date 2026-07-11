import json
import pytest
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
                                      area="Cabecera Municipal", flotante_pct=0.1)
    p.demanda = pj.DemandConfig(modo="usos", dneta=80.0, perdidas=0.10, k1=1.3, k2=1.6,
                                usos=[("Tomar", 5.0)], referencia="", justificacion="")
    p.almacenamiento.tanques = [pj.TankSpec("T. elevado", "elevado", "circular", 60, 2.5)]
    sistema = pj.PumpSystemData(nombre="Captación→T.Bajo", horas=10, he=69.8,
                                eficiencia=0.73, tipo_bomba="sumergible")
    sistema.tramos = [pj.SegmentData("Impulsión", "impulsion", 284.8, 79.5, "PEAD",
                                     cat_material="PEAD PE100", cat_serie="RDE 21",
                                     cat_dn=90, e_mm=4.3)]
    sistema.accesorios = [pj.AccessoryData("Válvula de cheque", 1, "Impulsión")]
    sistema.bombas = [pj.PumpData(nombre="Bomba A",
                                  puntos_qh=[(2.9, 33.2), (4.0, 31.9), (5.1, 30.2)])]
    p.bombeos = [sistema]
    return p


def test_roundtrip_json_v2(tmp_path):
    p = _proyecto()
    f = tmp_path / "salado.acucalc.json"
    pj.save(p, f)
    p2 = pj.load(f)
    assert p2.nombre == "El Salado"
    assert p2.censo == [(2018, 50848), (2019, 52021)]
    assert p2.poblacion.metodo == "res0844"
    assert p2.poblacion.flotante_pct == 0.1
    assert p2.almacenamiento.tanques[0].forma == "circular"
    assert len(p2.bombeos) == 1
    s = p2.bombeos[0]
    assert s.nombre == "Captación→T.Bajo" and s.tipo_bomba == "sumergible"
    assert s.tramos[0].cat_serie == "RDE 21" and s.tramos[0].e_mm == 4.3
    assert s.bombas[0].puntos_qh[1] == (4.0, 31.9)
    raw = json.loads(f.read_text(encoding="utf-8"))
    assert raw["schema_version"] == 2


def test_migracion_v1(tmp_path):
    v1 = {
        "schema_version": 1,
        "project": {
            "nombre": "Viejo", "municipio": "X", "departamento": "Y",
            "corregimiento": "", "consultor": "", "fecha": "",
            "altitud": 100.0, "temperatura": 20.0,
            "censo": [[2018, 1000]],
            "poblacion": {"p0": 500, "year0": 2024, "horizon_year": 2049,
                          "tasa_res0844": 0.005, "metodo": "res0844",
                          "justificacion": ""},
            "demanda": {"modo": "altitud", "dneta": 140.0, "perdidas": 0.1,
                        "k1": 1.3, "k2": 1.6, "usos": [], "referencia": "",
                        "justificacion": ""},
            "almacenamiento": {"frac_regulacion": 0.333, "frac_incendio": 0.15,
                               "dias_reserva": 1.0, "factores_hora": [],
                               "suministro_hora": []},
            "bombeo": {"horas": 8.0, "he": 50.0, "sumar_5m_ras": True,
                       "eficiencia": 0.7, "espesor_mm": 5.3, "k_elast": 18.0,
                       "pn_mca": 100.0, "panel_w": 710.0, "panel_area": 2.98,
                       "panel_fs": 3.0},
            "tramos": [{"nombre": "Imp", "tipo": "impulsion", "L": 100.0,
                        "D_mm": 79.5, "material": "PEAD"}],
            "accesorios": [{"tipo": "Salida", "cantidad": 1, "tramo": "Imp"}],
            "bombas": [{"nombre": "B1", "puntos_qh": [[1, 10]], "puntos_qe": [],
                        "imagen_b64": "", "cal": None, "modelo": "", "fabricante": ""}],
            "bomba_seleccionada": "B1",
        },
    }
    f = tmp_path / "v1.json"
    f.write_text(json.dumps(v1), encoding="utf-8")
    p = pj.load(f)
    assert len(p.bombeos) == 1
    s = p.bombeos[0]
    assert s.nombre == "Bombeo 1"
    assert s.horas == 8.0 and s.he == 50.0 and s.sumar_5m_ras
    # los campos v1 pn_mca/panel_* ya no existen — deben ignorarse al cargar
    assert s.tramos[0].D_mm == 79.5 and s.tramos[0].e_mm == 0.0
    assert s.bombas[0].nombre == "B1" and s.bomba_seleccionada == "B1"
    assert p.poblacion.flotante_pct == 0.0     # default nuevo


def test_version_desconocida(tmp_path):
    f = tmp_path / "x.json"
    f.write_text('{"schema_version": 99}', encoding="utf-8")
    with pytest.raises(pj.SchemaError):
        pj.load(f)


def test_proyecto_vacio_serializa(tmp_path):
    p = pj.Project(nombre="Nuevo")
    f = tmp_path / "n.json"
    pj.save(p, f)
    assert pj.load(f).nombre == "Nuevo"

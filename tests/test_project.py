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


def test_tankspec_salida_roundtrip(tmp_path):
    """La ventana de salida (salida_ini/fin) persiste en el JSON y los flags
    respetan el wrap-around de medianoche."""
    p = _proyecto()
    p.almacenamiento.tanques = [pj.TankSpec("T1", "elevado", "circular", 60, 2.5,
                                            salida_ini=20, salida_fin=4)]
    f = tmp_path / "salida.acucalc.json"
    pj.save(p, f)
    t = pj.load(f).almacenamiento.tanques[0]
    assert t.salida_ini == 20 and t.salida_fin == 4
    # ventana que cruza medianoche: horas 20-23 y 0-4 activas
    flags = t.salida_flags()
    assert flags[20] == 1 and flags[23] == 1 and flags[4] == 1 and flags[10] == 0


def test_tankspec_salida_default_backward_compat(tmp_path):
    """Un TankSpec sin salida_ini/fin (JSON viejo) toma los defaults."""
    t = pj.TankSpec("T", "elevado", "circular", 60, 2.5)
    assert t.salida_ini == 6 and t.salida_fin == 22
    assert t.salida_flags()[6] == 1 and t.salida_flags()[22] == 1 and t.salida_flags()[0] == 0


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


def test_k_auto_persiste_en_json(tmp_path):
    p = _proyecto()
    p.demanda.k_auto = False
    p.demanda.k1, p.demanda.k2 = 1.15, 1.45
    f = tmp_path / "kmanual.acucalc.json"
    pj.save(p, f)
    p2 = pj.load(f)
    assert p2.demanda.k_auto is False
    assert p2.demanda.k1 == 1.15 and p2.demanda.k2 == 1.45


def test_red_inp_persiste_en_json(tmp_path):
    p = _proyecto()
    p.red_inp = "[JUNCTIONS]\nJ1 10 5\n"
    p.red_material, p.red_serie = "PEAD PE100", "RDE 21"
    p.red_vmax = 2.5
    f = tmp_path / "red.acucalc.json"
    pj.save(p, f)
    p2 = pj.load(f)
    assert p2.red_inp == "[JUNCTIONS]\nJ1 10 5\n"
    assert p2.red_material == "PEAD PE100" and p2.red_vmax == 2.5


def test_ruta_guardado_persiste_en_json(tmp_path):
    p = _proyecto()
    p.ruta_guardado = r"C:\Users\aiken\Proyectos\San_Jacinto"
    f = tmp_path / "ruta.acucalc.json"
    pj.save(p, f)
    assert pj.load(f).ruta_guardado == r"C:\Users\aiken\Proyectos\San_Jacinto"


def test_ruta_guardado_default_vacio(tmp_path):
    p = _proyecto()               # sin fijar ruta
    f = tmp_path / "sin_ruta.acucalc.json"
    pj.save(p, f)
    assert pj.load(f).ruta_guardado == ""


def test_save_atomico_no_deja_tmp(tmp_path):
    p = _proyecto()
    f = tmp_path / "atomic.acucalc.json"
    pj.save(p, f)
    assert f.exists()
    assert not (tmp_path / "atomic.acucalc.json.tmp").exists()  # tmp renombrado, no residual
    assert pj.load(f).nombre == p.nombre


def test_save_atomico_sobrescribe_sin_corromper(tmp_path):
    p = _proyecto()
    f = tmp_path / "over.acucalc.json"
    pj.save(p, f)
    original = f.read_text(encoding="utf-8")
    p.nombre = "Nombre Nuevo"
    pj.save(p, f)                 # sobrescritura vía os.replace
    assert pj.load(f).nombre == "Nombre Nuevo"
    assert f.read_text(encoding="utf-8") != original


def test_load_ignora_claves_desconocidas_en_almacenamiento(tmp_path):
    """Regresión: un proyecto guardado por una versión anterior (v5, con el
    campo `usar_cadena` que v6 eliminó de StorageConfig) debe seguir
    cargando, no reventar con TypeError por un kwarg inesperado."""
    p = _proyecto()
    f = tmp_path / "viejo.acucalc.json"
    pj.save(p, f)
    raw = json.loads(f.read_text(encoding="utf-8"))
    raw["project"]["almacenamiento"]["usar_cadena"] = True   # campo v5, ya no existe
    f.write_text(json.dumps(raw), encoding="utf-8")
    p2 = pj.load(f)                # no debe lanzar TypeError
    assert p2.nombre == p.nombre
    assert p2.almacenamiento.tanques[0].forma == "circular"

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
    assert raw["schema_version"] == pj.SCHEMA_VERSION


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


def test_red_en_informe_default_true_y_persiste_false(tmp_path):
    p = _proyecto()
    assert p.red_en_informe is True
    p.red_en_informe = False
    f = tmp_path / "red_off.acucalc.json"
    pj.save(p, f)
    assert pj.load(f).red_en_informe is False


def test_red_en_informe_backward_compat_json_viejo(tmp_path):
    """Un proyecto guardado ANTES de que existiera red_en_informe (sin la
    clave) debe cargar con el default True, no reventar."""
    import json
    f = tmp_path / "viejo.acucalc.json"
    data = {"schema_version": pj.SCHEMA_VERSION,
            "project": {"nombre": "Viejo", "red_inp": "algo"}}
    f.write_text(json.dumps(data), encoding="utf-8")
    p = pj.load(f)
    assert p.red_en_informe is True
    assert p.red_inp == "algo"


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


def test_migrate_pump_cal_esquema_plano_viejo_a_qh_qe():
    """WP-B2: el esquema plano viejo {X1,X2,Y1,Y2} (una calibración
    compartida) migra a {'qh': <la vieja calibración>, 'qe': {}} — Q-η queda
    sin calibrar porque la calibración compartida ya era incorrecta para él."""
    viejo = {"X1": {"px": 10, "val": 0.0}, "X2": {"px": 500, "val": 40.0},
             "Y1": {"px": 300, "px_x": 5, "val": 0.0},
             "Y2": {"px": 20, "px_x": 5, "val": 60.0}}
    migrado = pj.migrate_pump_cal(viejo)
    assert migrado == {"qh": viejo, "qe": {}}


def test_migrate_pump_cal_none_o_vacio():
    assert pj.migrate_pump_cal(None) == {"qh": {}, "qe": {}}
    assert pj.migrate_pump_cal({}) == {"qh": {}, "qe": {}}


def test_migrate_pump_cal_esquema_nuevo_es_idempotente():
    nuevo = {"qh": {"X1": {"px": 1, "val": 0.0}}, "qe": {"Y1": {"px": 2, "val": 1.0}}}
    assert pj.migrate_pump_cal(nuevo) == nuevo
    assert pj.migrate_pump_cal({"qh": {"X1": {}}}) == {"qh": {"X1": {}}, "qe": {}}


def test_load_migra_cal_plano_de_proyecto_viejo(tmp_path):
    """Un proyecto guardado con el esquema plano viejo de `cal` (antes de
    WP-B2/WP-3a) debe cargar con `cal` ya migrado al esquema v7 vigente:
    {'x': {X1,X2}, 'qh': {}, 'qe': {}}."""
    p = _proyecto()
    f = tmp_path / "cal_viejo.acucalc.json"
    pj.save(p, f)
    raw = json.loads(f.read_text(encoding="utf-8"))
    raw["project"]["bombeos"][0]["bombas"][0]["cal"] = {
        "X1": {"px": 10, "val": 0.0}, "X2": {"px": 500, "val": 40.0}}
    f.write_text(json.dumps(raw), encoding="utf-8")
    p2 = pj.load(f)
    assert p2.bombeos[0].bombas[0].cal == {
        "x": {"X1": {"px": 10, "val": 0.0}, "X2": {"px": 500, "val": 40.0}},
        "qh": {}, "qe": {}}


# ---------- WP-3a: migración a esquema v7 (eje X único compartido) ----------

def test_migrate_pump_cal_v7_desde_v5_plano():
    """v5 plano (una sola calibración compartida) -> X va a 'x', Y1/Y2 a 'qh'
    (Q-H es la curva principal, la que siempre existió en v5) y 'qe' vacío."""
    viejo = {"X1": {"px": 10, "val": 0.0}, "X2": {"px": 500, "val": 40.0},
             "Y1": {"px": 300, "px_x": 5, "val": 0.0},
             "Y2": {"px": 20, "px_x": 5, "val": 60.0}}
    migrado = pj.migrate_pump_cal_v7(viejo)
    assert migrado == {
        "x": {"X1": {"px": 10, "val": 0.0}, "X2": {"px": 500, "val": 40.0}},
        "qh": {"Y1": {"px": 300, "px_x": 5, "val": 0.0},
               "Y2": {"px": 20, "px_x": 5, "val": 60.0}},
        "qe": {}}


def test_migrate_pump_cal_v7_desde_v6():
    """v6 (calibración independiente por curva, X duplicado en qh y qe) -> X
    final se toma de qh (elección documentada), Y1/Y2 de cada curva se
    conservan."""
    v6 = {
        "qh": {"X1": {"px": 10, "val": 0.0}, "X2": {"px": 500, "val": 40.0},
               "Y1": {"px": 300, "val": 0.0}, "Y2": {"px": 20, "val": 60.0}},
        "qe": {"X1": {"px": 12, "val": 0.0}, "X2": {"px": 498, "val": 40.0},
               "Y1": {"px": 310, "val": 0.0}, "Y2": {"px": 25, "val": 0.85}},
    }
    migrado = pj.migrate_pump_cal_v7(v6)
    assert migrado == {
        "x": {"X1": {"px": 10, "val": 0.0}, "X2": {"px": 500, "val": 40.0}},
        "qh": {"Y1": {"px": 300, "val": 0.0}, "Y2": {"px": 20, "val": 60.0}},
        "qe": {"Y1": {"px": 310, "val": 0.0}, "Y2": {"px": 25, "val": 0.85}},
    }


def test_migrate_pump_cal_v7_desde_v6_sin_x_en_qh_usa_qe():
    """Si 'qh' no tiene X calibrado (caso raro, ej. calibración parcial) se
    usa el X de 'qe' en su lugar — mejor que perder la calibración X."""
    v6 = {"qh": {"Y1": {"px": 300, "val": 0.0}},
          "qe": {"X1": {"px": 12, "val": 0.0}, "X2": {"px": 498, "val": 40.0}}}
    migrado = pj.migrate_pump_cal_v7(v6)
    assert migrado["x"] == {"X1": {"px": 12, "val": 0.0}, "X2": {"px": 498, "val": 40.0}}
    assert migrado["qh"] == {"Y1": {"px": 300, "val": 0.0}}
    assert migrado["qe"] == {}


def test_migrate_pump_cal_v7_desde_v7_es_idempotente():
    v7 = {"x": {"X1": {"px": 1, "val": 0.0}, "X2": {"px": 2, "val": 1.0}},
          "qh": {"Y1": {"px": 3, "val": 0.0}}, "qe": {"Y2": {"px": 4, "val": 1.0}}}
    assert pj.migrate_pump_cal_v7(v7) == v7
    assert pj.migrate_pump_cal_v7(pj.migrate_pump_cal_v7(v7)) == v7


def test_migrate_pump_cal_v7_none_o_vacio():
    assert pj.migrate_pump_cal_v7(None) == {"x": {}, "qh": {}, "qe": {}}
    assert pj.migrate_pump_cal_v7({}) == {"x": {}, "qh": {}, "qe": {}}


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


def test_load_proyecto_viejo_sin_nivel_riesgo(tmp_path):
    """Regresión WP-2b: un proyecto guardado ANTES de existir `nivel_riesgo`
    solo trae `frac_incendio` en `almacenamiento`. Debe cargar sin reventar,
    conservar su `frac_incendio` y quedar con el nivel vacío ('' =
    personalizado/legado)."""
    p = _proyecto()
    f = tmp_path / "sin_nivel.acucalc.json"
    pj.save(p, f)
    raw = json.loads(f.read_text(encoding="utf-8"))
    # Simula exactamente la forma vieja: sin la clave nivel_riesgo, con un
    # frac_incendio no estándar que debe preservarse tal cual.
    raw["project"]["almacenamiento"].pop("nivel_riesgo", None)
    raw["project"]["almacenamiento"]["frac_incendio"] = 0.18
    f.write_text(json.dumps(raw), encoding="utf-8")
    p2 = pj.load(f)
    assert p2.almacenamiento.frac_incendio == 0.18
    assert p2.almacenamiento.nivel_riesgo == ""     # personalizado/legado


def test_nivel_riesgo_persiste_en_json(tmp_path):
    p = _proyecto()
    p.almacenamiento.nivel_riesgo = "medio"
    p.almacenamiento.frac_incendio = 0.20
    f = tmp_path / "nivel.acucalc.json"
    pj.save(p, f)
    p2 = pj.load(f)
    assert p2.almacenamiento.nivel_riesgo == "medio"
    assert p2.almacenamiento.frac_incendio == 0.20


# --- WP1 v9: carga genérica (_from_dict) y schema v3 -------------------------

import dataclasses as _dc


def _proyecto_completo():
    """Proyecto con TODOS los campos en valores distintos al default, para que
    un campo que `load()` olvide restaurar se note en el round-trip."""
    p = _proyecto()
    p.fecha = "2026-09-26"
    p.temperatura = 24.0
    p.poblacion.horizon_year = 2050
    p.poblacion.tasa_res0844 = 0.006
    p.poblacion.tipo, p.poblacion.fuente = "municipio", "manual"
    p.demanda.perdidas, p.demanda.k1, p.demanda.k2 = 0.15, 1.2, 1.5
    p.bombeos[0].horas = 12.0
    p.logo_cliente_b64 = "iVBORw0KGgoCLIENTE"
    p.logo_consultor_b64 = "iVBORw0KGgoCONSULTOR"
    p.poblacion.year0 = 2025
    p.demanda.k_auto = False
    p.demanda.referencia = "res0844"
    p.demanda.justificacion = "Uso institucional"
    st = p.almacenamiento
    st.frac_regulacion = 0.30
    st.frac_incendio = 0.20
    st.nivel_riesgo = "medio"
    st.dias_reserva = 1.5
    st.factores_hora = [1.0] * 24
    st.suministro_hora = [1] * 12 + [0] * 12
    st.ventana_captacion = [0] * 24
    st.tanques = [pj.TankSpec("T1", "bajo", "rectangular", 90, 3.0, 2.0, 4, 16, 2,
                              "enterrado", 5, 21)]
    s = p.bombeos[0]
    s.sumar_5m_ras = True
    s.bomba_seleccionada = "Bomba A"
    b = s.bombas[0]
    b.puntos_qe = [(2.9, 0.61), (4.0, 0.70)]
    b.imagen_b64 = "iVBORw0KGgoCURVA"
    b.cal = {"x": {"X1": {"px": 10, "val": 0}}, "qh": {"Y1": {"px": 5, "val": 20}},
             "qe": {}}
    b.modelo, b.fabricante = "M-1", "Fab"
    b.n_unidades, b.arreglo = 2, "serie"
    b.n1_nominal, b.n2_objetivo = 3500.0, 3200.0
    p.red_inp = "[JUNCTIONS]\n"
    p.red_material, p.red_serie = "PVC-U", "RDE 21"
    p.red_vmax, p.red_pmin, p.red_pmax = 3.0, 10.0, 60.0
    p.red_en_informe = False
    p.ruta_guardado = "/tmp/x"
    return p


def _defaults(cls):
    return {f.name: (f.default if f.default is not _dc.MISSING else f.default_factory())
            for f in _dc.fields(cls)
            if f.default is not _dc.MISSING or f.default_factory is not _dc.MISSING}


@pytest.mark.parametrize("obtener,cls", [
    (lambda p: p, pj.Project),
    (lambda p: p.poblacion, pj.PopulationConfig),
    (lambda p: p.demanda, pj.DemandConfig),
    (lambda p: p.almacenamiento, pj.StorageConfig),
    (lambda p: p.almacenamiento.tanques[0], pj.TankSpec),
    (lambda p: p.bombeos[0], pj.PumpSystemData),
    (lambda p: p.bombeos[0].bombas[0], pj.PumpData),
])
def test_fixture_completo_cubre_todos_los_campos(obtener, cls):
    """Guarda del test de round-trip: si alguien agrega un campo nuevo sin
    darle valor no-default en `_proyecto_completo`, este test lo señala."""
    obj = obtener(_proyecto_completo())
    iguales = [k for k, v in _defaults(cls).items() if getattr(obj, k) == v]
    assert not iguales, f"campos de {cls.__name__} en default: {iguales}"


def test_roundtrip_todos_los_campos(tmp_path):
    p = _proyecto_completo()
    f = tmp_path / "full.acucalc.json"
    pj.save(p, f)
    assert _dc.asdict(pj.load(f)) == _dc.asdict(p)


def test_load_restaura_logos(tmp_path):
    """Regresión: load() no restauraba logo_cliente_b64/logo_consultor_b64."""
    p = _proyecto_completo()
    f = tmp_path / "logos.acucalc.json"
    pj.save(p, f)
    p2 = pj.load(f)
    assert p2.logo_cliente_b64 == "iVBORw0KGgoCLIENTE"
    assert p2.logo_consultor_b64 == "iVBORw0KGgoCONSULTOR"


def test_save_escribe_schema_actual(tmp_path):
    f = tmp_path / "v.acucalc.json"
    pj.save(_proyecto(), f)
    assert json.loads(f.read_text(encoding="utf-8"))["schema_version"] == 3 == pj.SCHEMA_VERSION


def test_migracion_v2_a_v3(tmp_path):
    p = _proyecto_completo()
    f = tmp_path / "v2.acucalc.json"
    pj.save(p, f)
    raw = json.loads(f.read_text(encoding="utf-8"))
    raw["schema_version"] = 2
    f.write_text(json.dumps(raw), encoding="utf-8")
    assert _dc.asdict(pj.load(f)) == _dc.asdict(p)


def test_version_futura_rechazada(tmp_path):
    """Una app vieja no debe cargar (y luego pisar con autosave) un archivo de
    una versión más nueva; esta app tampoco carga uno de una versión futura."""
    f = tmp_path / "futuro.json"
    f.write_text(json.dumps({"schema_version": pj.SCHEMA_VERSION + 1, "project": {}}),
                 encoding="utf-8")
    with pytest.raises(pj.SchemaError):
        pj.load(f)


def test_load_ignora_claves_desconocidas_en_todos_los_niveles(tmp_path):
    p = _proyecto_completo()
    f = tmp_path / "extra.acucalc.json"
    pj.save(p, f)
    raw = json.loads(f.read_text(encoding="utf-8"))
    d = raw["project"]
    d["campo_raro"] = 1
    d["poblacion"]["x"] = 1
    d["demanda"]["x"] = 1
    d["almacenamiento"]["tanques"][0]["x"] = 1
    d["bombeos"][0]["x"] = 1
    d["bombeos"][0]["tramos"][0]["x"] = 1
    d["bombeos"][0]["accesorios"][0]["x"] = 1
    d["bombeos"][0]["bombas"][0]["x"] = 1
    f.write_text(json.dumps(raw), encoding="utf-8")
    assert _dc.asdict(pj.load(f)) == _dc.asdict(p)


def test_load_tipos_de_listas(tmp_path):
    """Las listas de pares vuelven como tuplas y las listas de dataclasses
    como instancias (no dicts)."""
    f = tmp_path / "t.acucalc.json"
    pj.save(_proyecto_completo(), f)
    p = pj.load(f)
    assert isinstance(p.censo[0], tuple) and isinstance(p.demanda.usos[0], tuple)
    assert isinstance(p.almacenamiento.tanques[0], pj.TankSpec)
    s = p.bombeos[0]
    assert isinstance(s, pj.PumpSystemData)
    assert isinstance(s.tramos[0], pj.SegmentData)
    assert isinstance(s.accesorios[0], pj.AccessoryData)
    assert isinstance(s.bombas[0], pj.PumpData)
    assert isinstance(s.bombas[0].puntos_qh[0], tuple)
    assert isinstance(s.bombas[0].puntos_qe[0], tuple)

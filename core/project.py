"""Modelo de proyecto ACUCALC y persistencia JSON (schema_version=2).

v2: el bombeo son N sistemas nombrados (`Project.bombeos`), cada uno un paquete
completo (tramos, accesorios, parámetros, bombas candidatas). Los proyectos
schema 1 se migran automáticamente al cargar (un sistema "Bombeo 1")."""
import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path

SCHEMA_VERSION = 2


class SchemaError(Exception):
    pass


@dataclass
class PopulationConfig:
    p0: float = 0.0
    year0: int = 2026
    horizon_year: int = 2051
    tasa_res0844: float = 0.005
    metodo: str = ""           # aritmetico|geometrico|exponencial|wappaus|res0844
    justificacion: str = ""
    tipo: str = "corregimiento"   # municipio|corregimiento
    fuente: str = "dane"          # dane|manual
    dpto: str = ""
    mpio: str = ""
    area: str = ""                # ÁREA GEOGRÁFICA del DANE
    flotante_pct: float = 0.0     # población flotante como fracción de la residente


@dataclass
class DemandConfig:
    modo: str = "altitud"      # altitud|usos|manual
    dneta: float = 0.0
    perdidas: float = 0.10
    k1: float = 1.3
    k2: float = 1.6
    k_auto: bool = True        # False = K1/K2 manuales, nunca se recalculan
    usos: list = field(default_factory=list)         # [(actividad, L/hab/d)]
    referencia: str = ""       # id de data/dotaciones.json (modo manual)
    justificacion: str = ""


@dataclass
class TankSpec:
    nombre: str = ""
    tipo: str = "elevado"       # bajo|elevado (rol hidráulico en la cadena)
    forma: str = "circular"     # circular|cuadrado|rectangular
    volumen: float = 0.0
    altura: float = 2.5
    ratio: float = 1.5          # largo/ancho (solo rectangular)
    entrada_ini: int = 5        # ventana de entrada/suministro (bombeo/gravedad que lo alimenta)
    entrada_fin: int = 14       # inclusive; si fin < ini, la ventana cruza medianoche
    cantidad: int = 1           # número de unidades constructivas de este tanque
    tipo_constructivo: str = "superficial"  # superficial|enterrado|semienterrado|elevado
    salida_ini: int = 6         # ventana de salida (consumo/bombeo hacia adelante)
    salida_fin: int = 22        # inclusive; si fin < ini, la ventana cruza medianoche

    def entrada_flags(self) -> list[int]:
        if self.entrada_fin >= self.entrada_ini:
            return [1 if self.entrada_ini <= h <= self.entrada_fin else 0
                    for h in range(24)]
        return [1 if (h >= self.entrada_ini or h <= self.entrada_fin) else 0
                for h in range(24)]

    def salida_flags(self) -> list[int]:
        if self.salida_fin >= self.salida_ini:
            return [1 if self.salida_ini <= h <= self.salida_fin else 0
                    for h in range(24)]
        return [1 if (h >= self.salida_ini or h <= self.salida_fin) else 0
                for h in range(24)]


@dataclass
class StorageConfig:
    frac_regulacion: float = 1 / 3
    frac_incendio: float = 0.15
    nivel_riesgo: str = ""     # bajo|medio|alto|personalizado ("" = personalizado/legado)
    dias_reserva: float = 1.0
    factores_hora: list = field(default_factory=list)
    suministro_hora: list = field(default_factory=list)   # ventana de bombeo bajo→elevado
    ventana_captacion: list = field(default_factory=list)
    tanques: list = field(default_factory=list)           # TankSpec


@dataclass
class SegmentData:
    nombre: str
    tipo: str                  # succion|impulsion
    L: float
    D_mm: float                # diámetro interno de cálculo
    material: str              # clave de data/ks.json (para fricción)
    cat_material: str = ""     # material del catálogo de tuberías ("" = manual)
    cat_serie: str = ""
    cat_dn: float = 0.0
    e_mm: float = 0.0          # espesor (del catálogo o manual) para ariete


@dataclass
class AccessoryData:
    tipo: str
    cantidad: int
    tramo: str


@dataclass
class AxisCalData:
    px1: float
    val1: float
    px2: float
    val2: float
    log: bool = False


@dataclass
class PumpData:
    nombre: str
    puntos_qh: list = field(default_factory=list)
    puntos_qe: list = field(default_factory=list)
    imagen_b64: str = ""
    cal: dict | None = None    # {"qh": {"X1": {...}, ...}, "qe": {"X1": {...}, ...}}
    modelo: str = ""
    fabricante: str = ""
    n_unidades: int = 1            # nº de bombas iguales en el arreglo
    arreglo: str = "paralelo"      # paralelo|serie (solo si n_unidades > 1)
    n1_nominal: float = 0.0        # rpm/Hz nominal de la curva digitalizada (0 = sin afinidad)
    n2_objetivo: float = 0.0       # rpm/Hz al que se quiere operar (0 = igual a n1_nominal)


@dataclass
class PumpSystemData:
    nombre: str = "Bombeo 1"
    tramos: list = field(default_factory=list)        # SegmentData
    accesorios: list = field(default_factory=list)    # AccessoryData
    horas: float = 10.0
    he: float = 0.0
    sumar_5m_ras: bool = False
    eficiencia: float = 0.70
    tipo_bomba: str = "superficie"    # superficie|sumergible
    bombas: list = field(default_factory=list)        # PumpData
    bomba_seleccionada: str = ""


@dataclass
class Project:
    nombre: str = ""
    municipio: str = ""
    departamento: str = ""
    corregimiento: str = ""
    consultor: str = ""
    fecha: str = ""
    altitud: float = 0.0
    temperatura: float = 20.0
    logo_cliente_b64: str = ""       # logo para la portada del informe
    logo_consultor_b64: str = ""
    censo: list = field(default_factory=list)
    poblacion: PopulationConfig = field(default_factory=PopulationConfig)
    demanda: DemandConfig = field(default_factory=DemandConfig)
    almacenamiento: StorageConfig = field(default_factory=StorageConfig)
    bombeos: list = field(default_factory=list)       # PumpSystemData
    red_inp: str = ""             # texto INP cargado (vacío = sin red)
    red_material: str = ""        # material del catálogo usado en la optimización
    red_serie: str = ""
    red_vmax: float = 6.0
    red_pmin: float = 15.0
    red_pmax: float = 70.0
    ruta_guardado: str = ""       # carpeta o archivo .acucalc.json del usuario (vacío = saves/ interno)


def save(p: Project, path: str | Path) -> None:
    """Guardado atómico: escribe a un `.tmp` y hace `os.replace` (atómico en el
    mismo volumen). Evita que un corte/kill a mitad de la escritura deje el
    único archivo del usuario truncado/corrupto — crítico ahora que el autosave
    escribe sobre el archivo canónico del proyecto cada ~30 s."""
    path = Path(path)
    data = {"schema_version": SCHEMA_VERSION, "project": asdict(p)}
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def _filtered(cls, d: dict) -> dict:
    """Descarta claves de un JSON viejo que ya no existen en `cls` (ej. un
    campo eliminado en una migración) — evita que `Cls(**d)` reviente con
    `TypeError: unexpected keyword argument` al cargar un proyecto guardado
    con una versión anterior de la app."""
    from dataclasses import fields as _fields
    validos = {f.name for f in _fields(cls)}
    return {k: v for k, v in d.items() if k in validos}


def migrate_pump_cal(cal: dict | None) -> dict:
    """Migra `PumpData.cal` del esquema plano viejo (una sola calibración
    compartida por la curva Q-H y la curva Q-η: `{"X1": {...}, "X2": {...},
    "Y1": {...}, "Y2": {...}}`) al esquema nuevo de calibraciones
    independientes `{"qh": {...}, "qe": {...}}` (WP-B2 — H y η se grafican en
    ejes Y distintos con escalas no relacionadas, una calibración compartida
    era incorrecta para η).

    Un proyecto viejo conserva su calibración de Q-H (la curva principal, la
    que siempre se usó para leer H); Q-η queda sin calibrar — la calibración
    compartida ya era incorrecta para η, así que no hay nada útil que migrar
    ahí; el usuario debe volver a calibrar esa curva.

    Idempotente: si `cal` ya viene en el esquema nuevo (tiene "qh"/"qe" como
    claves de nivel superior, sin "X1"), se devuelve tal cual (con defaults
    para las claves que falten)."""
    if not cal:
        return {"qh": {}, "qe": {}}
    if "X1" in cal:
        return {"qh": dict(cal), "qe": {}}
    return {"qh": cal.get("qh", {}), "qe": cal.get("qe", {})}


def _pump_system_from_dict(s: dict) -> PumpSystemData:
    from dataclasses import fields as _fields
    validos = {f.name for f in _fields(PumpSystemData)} - {"tramos", "accesorios", "bombas"}
    sys = PumpSystemData(**{k: v for k, v in s.items() if k in validos})
    sys.tramos = [SegmentData(**t) for t in s.get("tramos", [])]
    sys.accesorios = [AccessoryData(**a) for a in s.get("accesorios", [])]
    sys.bombas = []
    for b in s.get("bombas", []):
        pump = PumpData(**b)
        pump.puntos_qh = [tuple(x) for x in pump.puntos_qh]
        pump.puntos_qe = [tuple(x) for x in pump.puntos_qe]
        pump.cal = migrate_pump_cal(pump.cal)
        sys.bombas.append(pump)
    return sys


def _migrate_v1(d: dict) -> dict:
    """schema 1 → 2: tramos/accesorios/bombas sueltos pasan a un sistema único."""
    bombeo = d.pop("bombeo", {})
    sistema = {
        "nombre": "Bombeo 1",
        "tramos": d.pop("tramos", []),
        "accesorios": d.pop("accesorios", []),
        "bombas": d.pop("bombas", []),
        "bomba_seleccionada": d.pop("bomba_seleccionada", ""),
        "horas": bombeo.get("horas", 10.0),
        "he": bombeo.get("he", 0.0),
        "sumar_5m_ras": bombeo.get("sumar_5m_ras", False),
        "eficiencia": bombeo.get("eficiencia", 0.70),
    }
    d["bombeos"] = [sistema] if (sistema["tramos"] or sistema["bombas"]) else []
    return d


def load(path: str | Path) -> Project:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    version = raw.get("schema_version")
    if version not in (1, SCHEMA_VERSION):
        raise SchemaError(f"schema_version {version} no soportada "
                          f"(esperada 1 o {SCHEMA_VERSION})")
    d = raw["project"]
    if version == 1:
        d = _migrate_v1(d)
    p = Project(**{k: d.get(k, "") for k in ("nombre", "municipio", "departamento",
                                             "corregimiento", "consultor", "fecha")},
                altitud=d.get("altitud", 0.0), temperatura=d.get("temperatura", 20.0))
    p.censo = [tuple(x) for x in d.get("censo", [])]
    p.poblacion = PopulationConfig(**_filtered(PopulationConfig, d.get("poblacion", {})))
    p.demanda = DemandConfig(**_filtered(DemandConfig, d.get("demanda", {})))
    p.demanda.usos = [tuple(u) for u in p.demanda.usos]
    p.almacenamiento = StorageConfig(**_filtered(StorageConfig, d.get("almacenamiento", {})))
    p.almacenamiento.tanques = [TankSpec(**_filtered(TankSpec, t))
                                for t in p.almacenamiento.tanques]
    p.bombeos = [_pump_system_from_dict(s) for s in d.get("bombeos", [])]
    p.red_inp = d.get("red_inp", "")
    p.red_material = d.get("red_material", "")
    p.red_serie = d.get("red_serie", "")
    p.red_vmax = d.get("red_vmax", 6.0)
    p.red_pmin = d.get("red_pmin", 15.0)
    p.red_pmax = d.get("red_pmax", 70.0)
    p.ruta_guardado = d.get("ruta_guardado", "")
    return p

"""Modelo de proyecto ACUCALC y persistencia JSON (schema_version=2).

v2: el bombeo son N sistemas nombrados (`Project.bombeos`), cada uno un paquete
completo (tramos, accesorios, parámetros, bombas candidatas). Los proyectos
schema 1 se migran automáticamente al cargar (un sistema "Bombeo 1")."""
import json
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
    usos: list = field(default_factory=list)         # [(actividad, L/hab/d)]
    referencia: str = ""       # id de data/dotaciones.json (modo manual)
    justificacion: str = ""


@dataclass
class TankSpec:
    nombre: str = ""
    tipo: str = "elevado"       # bajo|elevado
    forma: str = "circular"     # circular|cuadrado|rectangular
    volumen: float = 0.0
    altura: float = 2.5
    ratio: float = 1.5          # largo/ancho (solo rectangular)


@dataclass
class StorageConfig:
    frac_regulacion: float = 1 / 3
    frac_incendio: float = 0.15
    dias_reserva: float = 1.0
    factores_hora: list = field(default_factory=list)
    suministro_hora: list = field(default_factory=list)   # ventana de bombeo bajo→elevado
    ventana_captacion: list = field(default_factory=list)
    usar_cadena: bool = True
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
    cal: dict | None = None    # {"X1": {...}, ...}
    modelo: str = ""
    fabricante: str = ""


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
    censo: list = field(default_factory=list)
    poblacion: PopulationConfig = field(default_factory=PopulationConfig)
    demanda: DemandConfig = field(default_factory=DemandConfig)
    almacenamiento: StorageConfig = field(default_factory=StorageConfig)
    bombeos: list = field(default_factory=list)       # PumpSystemData


def save(p: Project, path: str | Path) -> None:
    data = {"schema_version": SCHEMA_VERSION, "project": asdict(p)}
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=1),
                          encoding="utf-8")


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
    p.poblacion = PopulationConfig(**d.get("poblacion", {}))
    p.demanda = DemandConfig(**d.get("demanda", {}))
    p.demanda.usos = [tuple(u) for u in p.demanda.usos]
    p.almacenamiento = StorageConfig(**d.get("almacenamiento", {}))
    p.almacenamiento.tanques = [TankSpec(**t) for t in p.almacenamiento.tanques]
    p.bombeos = [_pump_system_from_dict(s) for s in d.get("bombeos", [])]
    return p

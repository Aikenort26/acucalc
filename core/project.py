"""Modelo de proyecto ACUCALC y persistencia JSON (schema_version=1)."""
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

SCHEMA_VERSION = 1


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
class StorageConfig:
    frac_regulacion: float = 1 / 3
    frac_incendio: float = 0.15
    dias_reserva: float = 1.0
    factores_hora: list = field(default_factory=list)
    suministro_hora: list = field(default_factory=list)


@dataclass
class SegmentData:
    nombre: str
    tipo: str
    L: float
    D_mm: float
    material: str


@dataclass
class AccessoryData:
    tipo: str
    cantidad: int
    tramo: str


@dataclass
class BombeoConfig:
    horas: float = 10.0
    he: float = 0.0
    sumar_5m_ras: bool = False
    eficiencia: float = 0.70
    # ariete / paneles
    espesor_mm: float = 0.0
    k_elast: float = 18.0
    pn_mca: float = 0.0
    panel_w: float = 710.0
    panel_area: float = 2.9768
    panel_fs: float = 3.0


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
    cal: dict | None = None    # {"x": AxisCalData dict, "y": ..., "e": ...}
    modelo: str = ""
    fabricante: str = ""


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
    bombeo: BombeoConfig = field(default_factory=BombeoConfig)
    tramos: list = field(default_factory=list)        # SegmentData
    accesorios: list = field(default_factory=list)    # AccessoryData
    bombas: list = field(default_factory=list)        # PumpData
    bomba_seleccionada: str = ""


def save(p: Project, path: str | Path) -> None:
    data = {"schema_version": SCHEMA_VERSION, "project": asdict(p)}
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=1),
                          encoding="utf-8")


def load(path: str | Path) -> Project:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if raw.get("schema_version") != SCHEMA_VERSION:
        raise SchemaError(f"schema_version {raw.get('schema_version')} no soportada "
                          f"(esperada {SCHEMA_VERSION})")
    d = raw["project"]
    p = Project(**{k: d[k] for k in ("nombre", "municipio", "departamento",
                                     "corregimiento", "consultor", "fecha",
                                     "altitud", "temperatura")})
    p.censo = [tuple(x) for x in d["censo"]]
    p.poblacion = PopulationConfig(**d["poblacion"])
    p.demanda = DemandConfig(**d["demanda"])
    p.demanda.usos = [tuple(u) for u in p.demanda.usos]
    p.almacenamiento = StorageConfig(**d["almacenamiento"])
    p.bombeo = BombeoConfig(**d["bombeo"])
    p.tramos = [SegmentData(**t) for t in d["tramos"]]
    p.accesorios = [AccessoryData(**a) for a in d["accesorios"]]
    p.bombas = []
    for b in d["bombas"]:
        pump = PumpData(**b)
        pump.puntos_qh = [tuple(x) for x in pump.puntos_qh]
        pump.puntos_qe = [tuple(x) for x in pump.puntos_qe]
        p.bombas.append(pump)
    p.bomba_seleccionada = d.get("bomba_seleccionada", "")
    return p

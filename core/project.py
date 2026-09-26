"""Modelo de proyecto ACUCALC y persistencia JSON (schema_version=3).

v2: el bombeo son N sistemas nombrados (`Project.bombeos`), cada uno un paquete
completo (tramos, accesorios, parámetros, bombas candidatas). Los proyectos
schema 1 se migran automáticamente al cargar (un sistema "Bombeo 1").

v3: carga genérica `_from_dict` (todos los campos, en todos los niveles). El
salto de versión existe para que una app v2 rechace un archivo v3 en vez de
cargarlo sin las secciones nuevas y pisarlo con el autosave."""
import json
import os
from dataclasses import dataclass, field, asdict, fields, is_dataclass
from pathlib import Path

SCHEMA_VERSION = 3


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
    usos: list = field(default_factory=list, metadata={"item": tuple})  # [(actividad, L/hab/d)]
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
    tanques: list = field(default_factory=list, metadata={"item": TankSpec})


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
    puntos_qh: list = field(default_factory=list, metadata={"item": tuple})
    puntos_qe: list = field(default_factory=list, metadata={"item": tuple})
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
    tramos: list = field(default_factory=list, metadata={"item": SegmentData})
    accesorios: list = field(default_factory=list, metadata={"item": AccessoryData})
    horas: float = 10.0
    he: float = 0.0
    sumar_5m_ras: bool = False
    eficiencia: float = 0.70
    tipo_bomba: str = "superficie"    # superficie|sumergible
    bombas: list = field(default_factory=list, metadata={"item": PumpData})
    bomba_seleccionada: str = ""
    z_succion: float = 0.0            # + eje de bomba sobre la lámina, − ahogada [m]
    npsh_r: float = 0.0               # NPSH requerido del fabricante al Q de diseño (0 = sin dato)
    margen_npsh: float = 0.0          # margen que define el proyectista [m]


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
    censo: list = field(default_factory=list, metadata={"item": tuple})
    poblacion: PopulationConfig = field(default_factory=PopulationConfig)
    demanda: DemandConfig = field(default_factory=DemandConfig)
    almacenamiento: StorageConfig = field(default_factory=StorageConfig)
    bombeos: list = field(default_factory=list, metadata={"item": PumpSystemData})
    red_inp: str = ""             # texto INP cargado (vacío = sin red)
    red_material: str = ""        # material del catálogo usado en la optimización
    red_serie: str = ""
    red_vmax: float = 6.0
    red_pmin: float = 15.0
    red_pmax: float = 70.0
    red_en_informe: bool = True   # incluir la sección de red en el reporte (si hay red cargada)
    red_motor: str = "auto"       # auto (EPANET si está disponible) | epanet | gga
    red_aplicar_k2: bool = True   # estático con QMH = K2·demanda base (Art. 47)
    red_conexiones: dict = field(default_factory=dict)   # bomba -> [nodo succión, nodo impulsión]
    ruta_guardado: str = ""       # carpeta o archivo .acucalc.json del usuario (vacío = saves/ interno)
    bibtex_usuario: str = ""      # referencias propias en BibTeX (se suman a la biblioteca base)


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
    validos = {f.name for f in fields(cls)}
    return {k: v for k, v in d.items() if k in validos}


def _valor(f, v):
    if v is None:
        return None
    item = f.metadata.get("item")
    if item is tuple:
        return [tuple(x) for x in v]
    if item is not None:
        return [_from_dict(item, x) for x in v]
    if isinstance(f.type, type) and is_dataclass(f.type) and isinstance(v, dict):
        return _from_dict(f.type, v)
    return v


def _from_dict(cls, d: dict):
    """Reconstruye `cls` desde un dict de JSON, recursivamente. Las claves
    ausentes toman el default del dataclass y las desconocidas se ignoran, en
    todos los niveles. Las listas se tipan con `field(metadata={"item": X})`."""
    kwargs = {f.name: _valor(f, d[f.name]) for f in fields(cls) if f.name in d}
    obj = cls(**kwargs)
    post = _POST_LOAD.get(cls)
    if post:
        post(obj)
    return obj


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


def migrate_pump_cal_v7(cal: dict | None) -> dict:
    """Migra `PumpData.cal` al esquema WP-3a: eje X **único y compartido** entre
    Q-H y Q-η (Q es la misma magnitud/escala para ambas curvas de la misma
    bomba — solo Y necesita calibración independiente por curva, ya que H y η
    viven en escalas no relacionadas). Esquema resultante:
    `{"x": {"X1": {...}, "X2": {...}}, "qh": {"Y1": {...}, "Y2": {...}},
      "qe": {"Y1": {...}, "Y2": {...}}}`.

    Acepta y migra correctamente TRES formas de entrada, sin reventar ni
    migrar dos veces:
    - **v5 plano**: `{"X1": {...}, "X2": {...}, "Y1": {...}, "Y2": {...}}`
      (una sola calibración compartida por Q-H y Q-η, la más vieja).
    - **v6**: `{"qh": {"X1":..,"X2":..,"Y1":..,"Y2":..}, "qe": {mismo esquema}}`
      (calibraciones independientes por curva, incluyendo X duplicado).
    - **v7 (ya migrado)**: se devuelve tal cual (con defaults para las claves
      de nivel superior que falten) — idempotente.

    v6→v7: el eje X final se toma de `qh.X1`/`qh.X2` (elección arbitraria
    pero consistente — Q-H es la curva principal, la que siempre se digitalizó
    primero; si `qh` no tiene X calibrado se prueba con `qe`). `qh.Y1/Y2` y
    `qe.Y1/Y2` se conservan tal cual."""
    if not cal:
        return {"x": {}, "qh": {}, "qe": {}}
    if "x" in cal:      # ya es v7 (marca de nivel superior única de este esquema)
        return {"x": dict(cal.get("x", {})), "qh": dict(cal.get("qh", {})),
                "qe": dict(cal.get("qe", {}))}
    v6 = migrate_pump_cal(cal)
    qh, qe = dict(v6.get("qh", {})), dict(v6.get("qe", {}))
    fuente_x = qh if ("X1" in qh or "X2" in qh) else qe
    x = {k: fuente_x[k] for k in ("X1", "X2") if k in fuente_x}
    qh_y = {k: v for k, v in qh.items() if k not in ("X1", "X2")}
    qe_y = {k: v for k, v in qe.items() if k not in ("X1", "X2")}
    return {"x": x, "qh": qh_y, "qe": qe_y}


def _post_pump(b: PumpData) -> None:
    b.cal = migrate_pump_cal_v7(b.cal)


_POST_LOAD = {PumpData: _post_pump}


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
    if version not in (1, 2, SCHEMA_VERSION):
        raise SchemaError(f"schema_version {version} no soportada "
                          f"(esperada 1 a {SCHEMA_VERSION})")
    d = raw["project"]
    if version == 1:
        d = _migrate_v1(d)
    return _from_dict(Project, d)


def huella(p: Project) -> str:
    """Hash del contenido del proyecto: cambia si y solo si cambia algún dato.
    Sirve de clave para no recalcular el reporte en cada rerun."""
    import hashlib
    blob = json.dumps(asdict(p), sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()

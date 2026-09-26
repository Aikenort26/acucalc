"""Motor hidráulico EPANET (biblioteca oficial vía epyt) con respaldo en el
solver propio de `core/network`.

Resultados siempre en SI (L/s, m, m/s) sin importar las unidades del INP:
tras abrir el archivo se fijan las unidades de caudal a LPS y EPANET
convierte todo lo demás. Cada corrida usa un directorio temporal privado que
se borra al terminar, y un candado global serializa las corridas (Streamlit
atiende sesiones en hilos distintos)."""
import ctypes
import re
import shutil
import tempfile
import threading
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Callable

from core import network as net

_LOCK = threading.Lock()
_TMP_APP = Path(__file__).resolve().parent.parent / ".epanet_tmp"
_PREFIJO = "acucalc_epanet_"
MOTOR_GGA = "Solver propio ACUCALC (GGA)"
PATRON_ID = "ACUCALC24"

# Constantes del toolkit de EPANET (epanet2_enums.h)
EN_ELEVATION, EN_BASEDEMAND, EN_DEMAND, EN_HEAD = 0, 1, 9, 10
EN_DIAMETER, EN_ROUGHNESS, EN_FLOW, EN_VELOCITY, EN_PUMP_HCURVE = 0, 2, 8, 9, 19
EN_NODECOUNT, EN_TANKCOUNT, EN_LINKCOUNT, EN_PATCOUNT, EN_CURVECOUNT = 0, 1, 2, 3, 4
EN_JUNCTION, EN_RESERVOIR, EN_TANK = 0, 1, 2
EN_CVPIPE, EN_PIPE, EN_PUMP = 0, 1, 2
EN_DURATION, EN_HYDSTEP, EN_PATTERNSTEP, EN_PATTERNSTART, EN_REPORTSTEP, EN_REPORTSTART = 0, 1, 3, 4, 5, 6
EN_DEMANDMULT, EN_LPS, EN_ITERATIONS = 4, 5, 0

AVISOS = {
    1: "Sistema hidráulicamente desequilibrado: no se alcanzó la convergencia",
    2: "Sistema posiblemente inestable (estados de bombas/válvulas oscilando)",
    3: "Sistema desconectado: hay nodos sin conexión a una fuente",
    4: "Las bombas no pueden entregar el caudal o la altura requeridos",
    5: "Las válvulas no pueden entregar el caudal requerido",
    6: "Hay presiones negativas en el sistema",
}
# Avisos que invalidan la solución hidráulica (no solo la califican).
AVISOS_NO_CONVERGE = {1, 2, 3}


class EngineError(Exception):
    def __init__(self, codigo: int, mensaje: str):
        super().__init__(f"EPANET error {codigo}: {mensaje}" if codigo else mensaje)
        self.codigo = codigo
        self.mensaje = mensaje


@dataclass(frozen=True)
class Aviso:
    codigo: int
    hora: float
    texto: str


@dataclass(frozen=True)
class BombaINP:
    nombre: str
    nodo1: str               # succión
    nodo2: str               # impulsión
    curva_lps: list          # [(Q L/s, H m)], ya transformada (afinidad/arreglo)


@dataclass(frozen=True)
class Cambios:
    demandas: dict = field(default_factory=dict)     # nodo -> demanda base [L/s]
    diametros: dict = field(default_factory=dict)    # tubería -> diámetro interno [mm]
    rugosidad: dict = field(default_factory=dict)    # tubería -> C (H-W) o ks [mm] (D-W)
    bombas: list = field(default_factory=list)       # BombaINP
    patron: list | None = None                       # 24 factores horarios (solo EPS)
    multiplicador: float = 1.0                       # multiplicador global de demanda


@dataclass
class SteadyResult(net.NetworkResult):
    presiones: dict = field(default_factory=dict)    # nodo -> presión [m]
    avisos: list = field(default_factory=list)       # Aviso
    motor: str = ""


@dataclass(frozen=True)
class EpsResult:
    horas: list
    presiones: dict          # nodo -> [m por hora]
    heads: dict
    demandas: dict           # nodo -> [L/s por hora]
    flows: dict              # enlace -> [L/s por hora]
    velocities: dict
    niveles: dict            # tanque -> [nivel m por hora]
    avisos: list
    converged: bool
    motor: str


@dataclass(frozen=True)
class InpModel:
    unidades: str
    unidades_explicitas: bool
    headloss: str
    n_nodos: int
    n_reservorios: int
    n_tanques: int
    n_tuberias: int
    n_bombas: int
    n_valvulas: int
    n_patrones: int
    n_curvas: int
    duracion_h: float


# ---------------------------------------------------------------- API C

def _ruta_biblioteca() -> str:
    """La biblioteca nativa que empaqueta epyt (win/mac/linux)."""
    from epyt.src.epanetapi import _default_lib_path
    return str(_default_lib_path())


@lru_cache(maxsize=1)
def _lib():
    from ctypes import POINTER, c_char_p, c_double, c_int, c_long, c_void_p
    lib = ctypes.CDLL(_ruta_biblioteca())
    P, I, D, L, S = c_void_p, c_int, c_double, c_long, c_char_p
    firmas = {
        "EN_createproject": [POINTER(P)], "EN_deleteproject": [P],
        "EN_open": [P, S, S, S], "EN_close": [P], "EN_setflowunits": [P, I],
        "EN_getcount": [P, I, POINTER(I)], "EN_getnodeid": [P, I, S],
        "EN_getnodeindex": [P, S, POINTER(I)], "EN_getnodetype": [P, I, POINTER(I)],
        "EN_getlinkid": [P, I, S], "EN_getlinkindex": [P, S, POINTER(I)],
        "EN_getlinktype": [P, I, POINTER(I)], "EN_getlinknodes": [P, I, POINTER(I), POINTER(I)],
        "EN_getnodevalue": [P, I, I, POINTER(D)], "EN_getlinkvalue": [P, I, I, POINTER(D)],
        "EN_setlinkvalue": [P, I, I, D], "EN_getnumdemands": [P, I, POINTER(I)],
        "EN_setbasedemand": [P, I, I, D], "EN_setdemandpattern": [P, I, I, I],
        "EN_addpattern": [P, S], "EN_getpatternindex": [P, S, POINTER(I)],
        "EN_setpattern": [P, I, POINTER(D), I], "EN_addcurve": [P, S],
        "EN_getcurveindex": [P, S, POINTER(I)],
        "EN_setcurve": [P, I, POINTER(D), POINTER(D), I],
        "EN_addlink": [P, S, I, S, S, POINTER(I)], "EN_setoption": [P, I, D],
        "EN_settimeparam": [P, I, L], "EN_gettimeparam": [P, I, POINTER(L)],
        "EN_openH": [P], "EN_initH": [P, I], "EN_runH": [P, POINTER(L)],
        "EN_nextH": [P, POINTER(L)], "EN_closeH": [P],
        "EN_getstatistic": [P, I, POINTER(D)], "EN_saveinpfile": [P, S],
        "EN_geterror": [I, S, I], "EN_getversion": [POINTER(I)],
    }
    for nombre, args in firmas.items():
        fn = getattr(lib, nombre)
        fn.argtypes, fn.restype = args, c_int
    return lib


class _Proyecto:
    """Proyecto EPANET abierto (handle propio, doble precisión)."""

    def __init__(self, ruta: Path):
        self.lib = _lib()
        self.ph = ctypes.c_void_p()
        self.lib.EN_createproject(ctypes.byref(self.ph))
        rpt = ruta.with_suffix(".rpt")
        err = self.lib.EN_open(self.ph, str(ruta).encode(), str(rpt).encode(), b"")
        if err >= 100:
            self.cerrar()
            raise _error_de_reporte(err, rpt)

    def cerrar(self):
        if self.ph:
            self.lib.EN_close(self.ph)
            self.lib.EN_deleteproject(self.ph)
            self.ph = ctypes.c_void_p()

    def __call__(self, nombre: str, *args, accion: str = "") -> int:
        err = getattr(self.lib, nombre)(self.ph, *args)
        if err >= 100:
            raise EngineError(err, f"{accion or nombre}: {mensaje_error(err)}")
        return err

    def entero(self, nombre, *args, **kw) -> int:
        v = ctypes.c_int()
        self(nombre, *args, ctypes.byref(v), **kw)
        return v.value

    def real(self, nombre, *args) -> float:
        v = ctypes.c_double()
        self(nombre, *args, ctypes.byref(v))
        return v.value

    def texto(self, nombre, i) -> str:
        buf = ctypes.create_string_buffer(64)
        self(nombre, i, buf)
        return buf.value.decode("latin-1")

    def indice_nodo(self, nid: str) -> int:
        v = ctypes.c_int()
        if self.lib.EN_getnodeindex(self.ph, nid.encode(), ctypes.byref(v)):
            raise EngineError(203, f"el nodo '{nid}' no existe en la red")
        return v.value

    def indice_enlace(self, lid: str) -> int:
        v = ctypes.c_int()
        if self.lib.EN_getlinkindex(self.ph, lid.encode(), ctypes.byref(v)):
            raise EngineError(204, f"el enlace '{lid}' no existe en la red")
        return v.value


def mensaje_error(codigo: int) -> str:
    buf = ctypes.create_string_buffer(256)
    _lib().EN_geterror(codigo, buf, 255)
    return buf.value.decode("latin-1")


def _error_de_reporte(err: int, rpt: Path) -> EngineError:
    """El código de EN_open suele ser el genérico 200; el reporte trae el
    error específico y la línea del INP que lo causa."""
    texto = rpt.read_text(encoding="latin-1") if rpt.exists() else ""
    errores = re.findall(r"Error (\d+): ([^\n]*)(?:\n\s+([^\n]+))?", texto)
    especificos = [e for e in errores if e[0] != "200"] or errores
    codigo = int(especificos[0][0]) if especificos else err
    detalle = "; ".join(f"{m.strip()} {linea.strip()}".strip()
                        for _, m, linea in especificos) or mensaje_error(err)
    return EngineError(codigo, detalle)


@lru_cache(maxsize=1)
def version() -> str:
    try:
        v = ctypes.c_int()
        _lib().EN_getversion(ctypes.byref(v))
        n = v.value                              # p.ej. 20305
        return f"{n // 10000}.{(n // 100) % 100}.{n % 100:02d}"
    except Exception:
        return ""


def nombre_motor() -> str:
    return f"EPANET {version()}" if version() else "EPANET"


@lru_cache(maxsize=1)
def disponible() -> bool:
    """True si la biblioteca nativa de EPANET carga y resuelve una red mínima
    en esta plataforma."""
    try:
        mini = ("[JUNCTIONS]\nJ1 0 1\n[RESERVOIRS]\nR1 10\n[PIPES]\nP1 R1 J1 10 100 130\n"
                "[OPTIONS]\nUnits LPS\n[END]\n")
        _correr_estatico_epanet(mini, Cambios())
        return True
    except Exception:
        return False


# ---------------------------------------------------------------- utilidades

def _preparar(texto: str) -> str:
    """Declara `Units LPS` si el INP no trae unidades (EPANET asumiría GPM y
    el parser propio LPS: así ambos leen lo mismo)."""
    if net.unidades_inp(texto)[1]:
        return texto
    m = re.search(r"^\s*\[OPTIONS\][^\n]*\n", texto, flags=re.M | re.I)
    if m:
        return texto[:m.end()] + " Units LPS\n" + texto[m.end():]
    m = re.search(r"^\s*\[END\]", texto, flags=re.M | re.I)
    bloque = "\n[OPTIONS]\n Units LPS\n\n"
    return texto[:m.start()] + bloque + texto[m.start():] if m else texto + bloque


@contextmanager
def _directorio():
    d = Path(tempfile.mkdtemp(prefix=_PREFIJO))
    if not str(d).isascii():         # EPANET abre las rutas como bytes
        shutil.rmtree(d, ignore_errors=True)
        d = _TMP_APP / f"{_PREFIJO}{uuid.uuid4().hex}"
        d.mkdir(parents=True)
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


@contextmanager
def _proyecto(texto: str):
    with _LOCK, _directorio() as d:
        ruta = d / "red.inp"
        ruta.write_text(_preparar(texto), encoding="utf-8")
        en = _Proyecto(ruta)
        try:
            en("EN_setflowunits", EN_LPS, accion="fijar unidades LPS")
            yield en
        finally:
            en.cerrar()


def _id_seguro(nombre: str, prefijo: str) -> str:
    base = re.sub(r"[^A-Za-z0-9_]+", "_", nombre).strip("_") or "X"
    return (prefijo + base)[:31]


def _doubles(vals):
    return (ctypes.c_double * len(vals))(*[float(v) for v in vals])


def _aplicar(en: _Proyecto, c: Cambios, eps: bool) -> None:
    nn = en.entero("EN_getcount", EN_NODECOUNT)
    juntas = [i for i in range(1, nn + 1) if en.entero("EN_getnodetype", i) == EN_JUNCTION]
    for nid, q in c.demandas.items():
        i = en.indice_nodo(nid)
        for k in range(1, en.entero("EN_getnumdemands", i) + 1):
            en("EN_setbasedemand", i, k, float(q) if k == 1 else 0.0)
    pat = 0
    if eps and c.patron:
        en("EN_addpattern", PATRON_ID.encode(), accion="crear el patrón horario")
        pat = en.entero("EN_getpatternindex", PATRON_ID.encode())
        en("EN_setpattern", pat, _doubles(c.patron), len(c.patron))
    if not eps or c.patron:
        # Estático: sin patrones (se evalúa la demanda base). EPS con patrón
        # propio: reemplaza los patrones del archivo en todas las categorías.
        for i in juntas:
            for k in range(1, en.entero("EN_getnumdemands", i) + 1):
                en("EN_setdemandpattern", i, k, pat)
    for lid, d in c.diametros.items():
        en("EN_setlinkvalue", en.indice_enlace(lid), EN_DIAMETER, float(d))
    for lid, r in c.rugosidad.items():
        en("EN_setlinkvalue", en.indice_enlace(lid), EN_ROUGHNESS, float(r))
    for b in c.bombas:
        cid = _id_seguro(b.nombre, "C_").encode()
        en("EN_addcurve", cid, accion=f"curva de la bomba '{b.nombre}'")
        ci = en.entero("EN_getcurveindex", cid)
        xs, ys = zip(*sorted(b.curva_lps))
        en("EN_setcurve", ci, _doubles(xs), _doubles(ys), len(xs))
        li = ctypes.c_int()
        en("EN_addlink", _id_seguro(b.nombre, "B_").encode(), EN_PUMP, b.nodo1.encode(),
           b.nodo2.encode(), ctypes.byref(li),
           accion=f"conectar la bomba '{b.nombre}' entre {b.nodo1} y {b.nodo2}")
        en("EN_setlinkvalue", li.value, EN_PUMP_HCURVE, float(ci))
    en("EN_setoption", EN_DEMANDMULT, float(c.multiplicador))
    if eps:
        for p, v in ((EN_DURATION, 24 * 3600), (EN_HYDSTEP, 3600), (EN_PATTERNSTEP, 3600),
                     (EN_PATTERNSTART, 0), (EN_REPORTSTEP, 3600), (EN_REPORTSTART, 0)):
            en("EN_settimeparam", p, v)
    else:
        en("EN_settimeparam", EN_DURATION, 0)


def _ids(en: _Proyecto):
    nn, nl = en.entero("EN_getcount", EN_NODECOUNT), en.entero("EN_getcount", EN_LINKCOUNT)
    nodos = [en.texto("EN_getnodeid", i) for i in range(1, nn + 1)]
    tipos_n = [en.entero("EN_getnodetype", i) for i in range(1, nn + 1)]
    enlaces = [en.texto("EN_getlinkid", i) for i in range(1, nl + 1)]
    tipos_l = [en.entero("EN_getlinktype", i) for i in range(1, nl + 1)]
    extremos = []
    for i in range(1, nl + 1):
        a, b = ctypes.c_int(), ctypes.c_int()
        en("EN_getlinknodes", i, ctypes.byref(a), ctypes.byref(b))
        extremos.append((a.value, b.value))
    return nodos, tipos_n, enlaces, tipos_l, extremos


def _simular(en: _Proyecto, eps: bool):
    """Recorre la simulación y guarda una instantánea por hora exacta."""
    nn, nl = en.entero("EN_getcount", EN_NODECOUNT), en.entero("EN_getcount", EN_LINKCOUNT)

    def nodos(prop):
        return [en.real("EN_getnodevalue", i, prop) for i in range(1, nn + 1)]

    def enlaces(prop):
        return [en.real("EN_getlinkvalue", i, prop) for i in range(1, nl + 1)]

    avisos, fotos = [], []
    en("EN_openH")
    en("EN_initH", 0)
    t, dt = ctypes.c_long(), ctypes.c_long()
    while True:
        code = en("EN_runH", ctypes.byref(t))
        if code:
            avisos.append(Aviso(code, t.value / 3600, AVISOS.get(code, f"aviso {code}")))
        if t.value % 3600 == 0 and (not fotos or fotos[-1][0] != t.value):
            head, elev = nodos(EN_HEAD), nodos(EN_ELEVATION)
            # Presión = cabeza − cota (m): EN_PRESSURE sale en las unidades de
            # presión del archivo (psi en un INP US), que LPS no cambia.
            fotos.append((t.value, {
                "head": head, "pres": [h - z for h, z in zip(head, elev)],
                "dem": nodos(EN_DEMAND), "elev": elev, "flow": enlaces(EN_FLOW),
                "vel": enlaces(EN_VELOCITY), "iter": en.real("EN_getstatistic", EN_ITERATIONS)}))
        en("EN_nextH", ctypes.byref(dt))
        if dt.value <= 0 or not eps:
            break
    en("EN_closeH")
    return fotos, avisos


def _correr_estatico_epanet(texto: str, c: Cambios) -> SteadyResult:
    with _proyecto(texto) as en:
        _aplicar(en, c, eps=False)
        nodos, tipos_n, enlaces, tipos_l, extremos = _ids(en)
        fotos, avisos = _simular(en, eps=False)
    _, f = fotos[0]
    heads = dict(zip(nodos, f["head"]))
    presiones = {n: p for n, p, t in zip(nodos, f["pres"], tipos_n) if t == EN_JUNCTION}
    flows = dict(zip(enlaces, f["flow"]))
    vel = dict(zip(enlaces, f["vel"]))
    hf = {lid: abs(heads[nodos[a - 1]] - heads[nodos[b - 1]])
          for lid, t, (a, b) in zip(enlaces, tipos_l, extremos) if t != EN_PUMP}
    converge = not any(a.codigo in AVISOS_NO_CONVERGE for a in avisos)
    return SteadyResult(heads, flows, vel, hf, int(f["iter"]), converge,
                        presiones=presiones, avisos=avisos, motor=nombre_motor())


def _correr_estatico_gga(texto: str, c: Cambios) -> SteadyResult:
    red = net.parse_inp(texto)
    for jid, q in c.demandas.items():
        red.junctions[jid].demand = q
    for j in red.junctions.values():
        j.demand *= c.multiplicador
    for p in red.pipes:
        p.diameter_mm = c.diametros.get(p.id, p.diameter_mm)
        p.roughness = c.rugosidad.get(p.id, p.roughness)
    r = net.solve(red)
    avisos = [Aviso(0, 0.0, "EPANET no está disponible en este equipo: se usó el solver "
                            "propio (sin bombas ni válvulas; puede no converger en redes "
                            "grandes).")]
    if c.bombas:
        avisos.append(Aviso(0, 0.0, "El solver propio no simula bombas: se ignoraron."))
    presiones = {jid: r.heads[jid] - j.elevation for jid, j in red.junctions.items()}
    return SteadyResult(r.heads, r.flows, r.velocities, r.hf, r.iterations, r.converged,
                        presiones=presiones, avisos=avisos, motor=MOTOR_GGA)


# ---------------------------------------------------------------- API pública

def correr_estatico(texto: str, cambios: Cambios | None = None,
                    motor: str = "auto") -> SteadyResult:
    """Régimen permanente con la demanda base × multiplicador (sin patrones).
    motor: "auto" (EPANET si está disponible), "epanet" o "gga"."""
    c = cambios or Cambios()
    if motor == "gga" or (motor == "auto" and not disponible()):
        return _correr_estatico_gga(texto, c)
    return _correr_estatico_epanet(texto, c)


def correr_eps(texto: str, cambios: Cambios | None = None) -> EpsResult:
    """Periodo extendido de 24 h con paso horario. Con `cambios.patron` se
    reemplazan los patrones de demanda del archivo por ese patrón de 24 h."""
    if not disponible():
        raise EngineError(0, "La simulación de periodo extendido requiere EPANET, que no "
                             "está disponible en este equipo.")
    c = cambios or Cambios()
    with _proyecto(texto) as en:
        _aplicar(en, c, eps=True)
        nodos, tipos_n, enlaces, _, _ = _ids(en)
        fotos, avisos = _simular(en, eps=True)
    horas = [int(t // 3600) for t, _ in fotos]
    juntas = [i for i, t in enumerate(tipos_n) if t == EN_JUNCTION]
    tanques = [i for i, t in enumerate(tipos_n) if t == EN_TANK]

    def serie(clave, idx, ids):
        return {ids[i]: [f[clave][i] for _, f in fotos] for i in idx}

    niveles = {nodos[i]: [f["head"][i] - f["elev"][i] for _, f in fotos] for i in tanques}
    converge = not any(a.codigo in AVISOS_NO_CONVERGE for a in avisos)
    return EpsResult(horas, serie("pres", juntas, nodos), serie("head", range(len(nodos)), nodos),
                     serie("dem", juntas, nodos), serie("flow", range(len(enlaces)), enlaces),
                     serie("vel", range(len(enlaces)), enlaces), niveles, avisos, converge,
                     nombre_motor())


def leer_inp(texto: str) -> InpModel:
    unidades, explicitas = net.unidades_inp(texto)
    headloss = net.parse_inp(texto).headloss
    with _proyecto(texto) as en:
        nn, nl = en.entero("EN_getcount", EN_NODECOUNT), en.entero("EN_getcount", EN_LINKCOUNT)
        tn = [en.entero("EN_getnodetype", i) for i in range(1, nn + 1)]
        tl = [en.entero("EN_getlinktype", i) for i in range(1, nl + 1)]
        dur = ctypes.c_long()
        en("EN_gettimeparam", EN_DURATION, ctypes.byref(dur))
        npat, ncur = en.entero("EN_getcount", EN_PATCOUNT), en.entero("EN_getcount", EN_CURVECOUNT)
    tuberias = tl.count(EN_PIPE) + tl.count(EN_CVPIPE)
    return InpModel(unidades, explicitas, headloss, tn.count(EN_JUNCTION),
                    tn.count(EN_RESERVOIR), tn.count(EN_TANK), tuberias, tl.count(EN_PUMP),
                    len(tl) - tuberias - tl.count(EN_PUMP), npat, ncur, dur.value / 3600)


def exportar_eps_inp(texto: str, cambios: Cambios) -> str:
    """INP normalizado por EPANET con los cambios aplicados y el periodo
    extendido de 24 h configurado (patrón ACUCALC24). EPANET reescribe el
    archivo completo: se pierden comentarios y el orden original."""
    with _proyecto(texto) as en:
        _aplicar(en, cambios, eps=True)
        with tempfile.TemporaryDirectory(prefix=_PREFIJO) as d:
            salida = Path(d) / "exportado.inp"
            en("EN_saveinpfile", str(salida).encode(), accion="guardar el INP")
            return salida.read_text(encoding="latin-1")


def validar_inp(texto: str) -> None:
    """Lanza EngineError con el error específico si EPANET no acepta el INP."""
    if not disponible():
        net.parse_inp(texto)
        return
    with _proyecto(texto):
        pass


def solver_para(texto: str, multiplicador: float = 1.0, motor: str = "auto",
                bombas: list | None = None) -> Callable[[net.Network], net.NetworkResult]:
    """Solver con la firma de `network.solve` para `optimize_diameters`: toma
    los diámetros y demandas vigentes del modelo y resuelve con EPANET."""
    def _solver(red: net.Network) -> net.NetworkResult:
        c = Cambios(demandas={j.id: j.demand for j in red.junctions.values()},
                    diametros={p.id: p.diameter_mm for p in red.pipes},
                    bombas=list(bombas or []), multiplicador=multiplicador)
        return correr_estatico(texto, c, motor=motor)
    return _solver

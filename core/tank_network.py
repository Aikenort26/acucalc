"""Balance de masas horario entre varios tanques.

El usuario define los tanques (con su volumen asignado), las zonas de
consumo (fracción del QMD con el patrón horario) y las conexiones entre
fuentes, tanques y zonas (bombeo o gravedad, ventana horaria y caudal). La
app simula el día hora a hora, V(h+1) = V(h) + Q_entra(h) − Q_sale(h),
verifica el volumen asignado y sugiere el mínimo, sin aplicarlo.

Una conexión con caudal "auto" (None) solo cierra el balance diario del
tanque al que llega: reparte en su ventana el volumen que ese tanque entrega
aguas abajo. Un caudal explícito nunca se reescala: si el día no cierra, se
reporta la diferencia."""
import math
from dataclasses import dataclass, field

HORAS = 24


@dataclass(frozen=True)
class Tanque:
    nombre: str
    volumen: float                 # volumen asignado por el usuario [m³]


@dataclass(frozen=True)
class Zona:
    nombre: str
    fraccion: float                # fracción del QMD que consume
    patron: tuple | None = None    # 24 factores propios (None = patrón del proyecto)


@dataclass(frozen=True)
class Enlace:
    origen: str
    destino: str
    tipo: str = "bombeo"                            # bombeo | gravedad (informativo)
    ventana: tuple = tuple([1] * HORAS)             # 24 flags de operación
    caudal_lps: float | None = None                 # None = auto


@dataclass(frozen=True)
class BalanceTanque:
    nombre: str
    entradas_m3h: list
    salidas_m3h: list
    volumen_h: list          # 25 valores [m³], relativos al mínimo del día
    v_reg: float             # volumen de regulación requerido por el balance
    v_req: float             # con incendio y días de reserva
    v_sugerido: int          # v_req redondeado hacia arriba a 5 m³
    v_asignado: float
    cierre_diario_m3: float  # entra − sale en el día
    cierra: bool
    cumple: bool
    horas_rebose: list       # horas en que el volumen de regulación excede lo asignado


@dataclass(frozen=True)
class ResultadoRedTanques:
    tanques: list
    caudales: dict           # (origen, destino) -> L/s (promedio del día si va a una zona)
    avisos: list = field(default_factory=list)

    def tanque(self, nombre: str) -> BalanceTanque:
        return next(t for t in self.tanques if t.nombre == nombre)

    def caudal(self, origen: str, destino: str) -> float:
        return self.caudales[(origen, destino)]


def ventana(ini: int, fin: int) -> tuple:
    """24 flags de las horas ini..fin inclusive; si fin < ini cruza medianoche."""
    if fin >= ini:
        return tuple(1 if ini <= h <= fin else 0 for h in range(HORAS))
    return tuple(1 if (h >= ini or h <= fin) else 0 for h in range(HORAS))


def _orden_aguas_abajo_primero(nombres: set, enlaces: list) -> list:
    entrantes = {n: 0 for n in nombres}
    salidas = {n: [] for n in nombres}
    for e in enlaces:
        entrantes[e.destino] += 1
        salidas[e.origen].append(e.destino)
    orden, libres = [], [n for n, k in entrantes.items() if k == 0]
    while libres:
        n = libres.pop()
        orden.append(n)
        for d in salidas[n]:
            entrantes[d] -= 1
            if entrantes[d] == 0:
                libres.append(d)
    if len(orden) != len(nombres):
        raise ValueError("Las conexiones forman un ciclo: el balance requiere un flujo "
                         "de las fuentes hacia las zonas de consumo sin retornos.")
    return orden[::-1]


def resolver(tanques: list, zonas: list, enlaces: list, qmd_lps: float, patron24: list,
             frac_incendio: float, dias_reserva: float) -> ResultadoRedTanques:
    t_por = {t.nombre: t for t in tanques}
    z_por = {z.nombre: z for z in zonas}
    fuentes = {e.origen for e in enlaces} - set(t_por) - set(z_por)
    for e in enlaces:
        if e.origen in z_por:
            raise ValueError(f"La zona '{e.origen}' no puede alimentar a otro nodo.")
        if e.destino not in t_por and e.destino not in z_por:
            raise ValueError(f"Destino desconocido '{e.destino}': debe ser un tanque o una zona.")
    avisos = []
    qmd_m3d = qmd_lps * 86.4

    # demanda horaria de cada zona [m³/h]
    demanda = {}
    for z in zonas:
        pat = list(z.patron) if z.patron else list(patron24)
        if len(pat) != HORAS or sum(pat) <= 0:
            raise ValueError(f"El patrón de la zona '{z.nombre}' debe tener 24 factores.")
        demanda[z.nombre] = [z.fraccion * qmd_m3d * f / sum(pat) for f in pat]
        alimentan = [e for e in enlaces if e.destino == z.nombre]
        if len(alimentan) > 1:
            raise ValueError(f"La zona '{z.nombre}' tiene {len(alimentan)} alimentaciones; "
                             "defina una por zona (divida la zona si hace falta).")
        if not alimentan:
            avisos.append(f"La zona '{z.nombre}' no tiene alimentación: su consumo no entra "
                          "en el balance.")

    # caudal horario de cada enlace [m³/h], resolviendo "auto" aguas arriba
    flujo: dict = {}
    for e in enlaces:
        if e.destino in z_por:
            flujo[(e.origen, e.destino)] = demanda[e.destino]
        elif e.caudal_lps is not None:
            flujo[(e.origen, e.destino)] = [e.caudal_lps * 3.6 * w for w in e.ventana]
    for n in _orden_aguas_abajo_primero(set(t_por) | set(z_por) | fuentes, enlaces):
        if n not in t_por:
            continue
        sale = sum(sum(flujo[(e.origen, e.destino)]) for e in enlaces if e.origen == n)
        autos = [e for e in enlaces if e.destino == n and e.caudal_lps is None]
        if len(autos) > 1:
            raise ValueError(f"El tanque '{n}' tiene {len(autos)} entradas con caudal auto: "
                             "solo una puede cerrar su balance; fije el caudal de las demás.")
        if autos:
            e = autos[0]
            fijo = sum(sum(flujo[(x.origen, x.destino)]) for x in enlaces
                       if x.destino == n and x.caudal_lps is not None)
            horas = sum(e.ventana)
            if horas <= 0:
                raise ValueError(f"La conexión {e.origen} → {n} no opera ninguna hora.")
            falta = sale - fijo
            if falta < -1e-9:
                raise ValueError(f"Al tanque '{n}' le entran por caudal fijo {fijo:.1f} m³/d, "
                                 f"más de los {sale:.1f} m³/d que entrega.")
            flujo[(e.origen, e.destino)] = [max(falta, 0.0) / horas * w for w in e.ventana]

    resultados = []
    for t in tanques:
        entra = [sum(flujo[(e.origen, e.destino)][h] for e in enlaces if e.destino == t.nombre)
                 for h in range(HORAS)]
        sale = [sum(flujo[(e.origen, e.destino)][h] for e in enlaces if e.origen == t.nombre)
                for h in range(HORAS)]
        acum = [0.0]
        for a, b in zip(entra, sale):
            acum.append(acum[-1] + a - b)
        base = min(acum)
        vol = [v - base for v in acum]
        v_reg = max(acum) - base
        v_req = (v_reg + v_reg * frac_incendio) * dias_reserva
        cierre = sum(entra) - sum(sale)
        cierra = abs(cierre) <= 1e-6 * max(sum(sale), 1.0)
        if not cierra:
            avisos.append(f"El tanque '{t.nombre}' no cierra su balance diario: entran "
                          f"{sum(entra):.1f} m³/d y salen {sum(sale):.1f} m³/d "
                          f"(diferencia {cierre:+.1f} m³/d); con caudales fijos su nivel "
                          "deriva de un día a otro.")
        capacidad = t.volumen / ((1 + frac_incendio) * dias_reserva) if dias_reserva > 0 else 0.0
        rebose = [h for h, v in enumerate(vol[1:]) if v > capacidad + 1e-9]
        resultados.append(BalanceTanque(
            t.nombre, entra, sale, vol, v_reg, v_req, int(math.ceil(v_req / 5.0 - 1e-12) * 5),
            t.volumen, cierre, cierra, t.volumen + 1e-9 >= v_req, rebose))

    caudales = {k: (sum(v) / 86.4 if k[1] in z_por else max(v) / 3.6) for k, v in flujo.items()}
    return ResultadoRedTanques(resultados, caudales, avisos)


def desde_tankspecs(tankspecs: list) -> tuple[list, list, list]:
    """Modelo equivalente a la verificación por tanque: cada tanque recibe de
    su propia fuente en su ventana de entrada ("auto") y entrega el QMD
    completo, uniforme en su ventana de salida."""
    tanques, zonas, enlaces = [], [], []
    for t in tankspecs:
        salida = t.salida_flags()
        tanques.append(Tanque(t.nombre, t.volumen))
        zonas.append(Zona(f"Salida de {t.nombre}", 1.0, tuple(salida)))
        enlaces.append(Enlace(f"Fuente de {t.nombre}", t.nombre, "bombeo",
                              tuple(t.entrada_flags())))
        enlaces.append(Enlace(t.nombre, f"Salida de {t.nombre}", "gravedad"))
    return tanques, zonas, enlaces


def desde_config(alm) -> tuple[list, list, list]:
    """Modelo desde `StorageConfig`: sus tanques, zonas y conexiones."""
    tanques = [Tanque(t.nombre, t.volumen) for t in alm.tanques]
    zonas = [Zona(z.nombre, z.fraccion) for z in alm.zonas]
    enlaces = [Enlace(e.origen, e.destino, e.tipo, ventana(e.ini, e.fin),
                      e.caudal_lps if e.caudal_lps > 0 else None) for e in alm.enlaces]
    return tanques, zonas, enlaces


def config_inicial(alm) -> tuple[list, list]:
    """Punto de partida para el modo red: los tanques en cadena en el orden de
    la tabla (captación → primero → ... → último → población), cada conexión
    en la ventana de suministro del tanque al que llega, caudal auto."""
    from core.project import EnlaceSpec, ZonaSpec
    zonas = [ZonaSpec("Población", 1.0)]
    enlaces, origen = [], "Captación"
    for t in alm.tanques:
        enlaces.append(EnlaceSpec(origen, t.nombre, "bombeo", t.entrada_ini, t.entrada_fin, 0.0))
        origen = t.nombre
    if alm.tanques:
        enlaces.append(EnlaceSpec(origen, "Población", "gravedad", 0, 23, 0.0))
    return zonas, enlaces

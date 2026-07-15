"""Red de distribución: modelo INP, asignación de demandas por longitud
aferente y solver hidráulico propio (formulación de Todini/Global Gradient
Algorithm reducida a las cabezas nodales, densa con numpy — ver `solve()`)."""
import math
from dataclasses import dataclass, field

import numpy as np

G = 9.81


@dataclass
class Junction:
    id: str
    elevation: float
    demand: float = 0.0     # L/s


@dataclass
class Source:
    id: str
    head: float              # m (para tanques: elevación + nivel inicial)


@dataclass
class Pipe:
    id: str
    node1: str
    node2: str
    length: float             # m
    diameter_mm: float
    roughness: float          # C (Hazen-Williams) o ks en mm (Darcy-Weisbach)
    minorloss: float = 0.0


@dataclass
class Network:
    junctions: dict
    sources: dict
    pipes: list
    headloss: str = "H-W"     # "H-W" | "D-W"
    raw_text: str = ""


def parse_inp(text: str) -> Network:
    """Parser mínimo de EPANET INP: secciones [JUNCTIONS] [RESERVOIRS]
    [TANKS] [PIPES] [OPTIONS]. El resto de secciones se ignora (el texto
    completo se conserva en `raw_text` para reescritura con
    `write_inp_demands`)."""
    junctions: dict[str, Junction] = {}
    sources: dict[str, Source] = {}
    pipes: list[Pipe] = []
    headloss = "H-W"
    section = None
    for raw in text.splitlines():
        line = raw.split(";")[0].strip()
        if not line:
            continue
        if line.startswith("["):
            section = line.strip("[]").upper()
            continue
        parts = line.split()
        if section == "JUNCTIONS":
            jid, elev = parts[0], float(parts[1])
            demand = float(parts[2]) if len(parts) > 2 else 0.0
            junctions[jid] = Junction(jid, elev, demand)
        elif section == "RESERVOIRS":
            sources[parts[0]] = Source(parts[0], float(parts[1]))
        elif section == "TANKS":
            elevation, initlevel = float(parts[1]), float(parts[2])
            sources[parts[0]] = Source(parts[0], elevation + initlevel)
        elif section == "PIPES":
            pid, n1, n2 = parts[0], parts[1], parts[2]
            length, diam, rough = float(parts[3]), float(parts[4]), float(parts[5])
            km = float(parts[6]) if len(parts) > 6 else 0.0
            pipes.append(Pipe(pid, n1, n2, length, diam, rough, km))
        elif section == "OPTIONS" and parts and parts[0].lower() == "headloss":
            headloss = "D-W" if parts[1].upper().startswith("D") else "H-W"
    if not junctions:
        raise ValueError("El INP no contiene nodos [JUNCTIONS]")
    if not sources:
        raise ValueError("El INP no contiene fuentes ([RESERVOIRS] ni [TANKS])")
    return Network(junctions, sources, pipes, headloss, text)


def write_inp_demands(text: str, demands: dict) -> str:
    """Reescribe la columna de demanda en [JUNCTIONS], preservando el resto
    del archivo (otras secciones, comentarios de fin de línea, columnas
    adicionales como el patrón de demanda) intacto."""
    out, section = [], None
    for raw in text.splitlines():
        stripped = raw.split(";")[0].strip()
        if stripped.startswith("["):
            section = stripped.strip("[]").upper()
            out.append(raw)
            continue
        if section == "JUNCTIONS" and stripped:
            antes, _, comentario = raw.partition(";")
            body = antes.split()
            jid = body[0]
            if jid in demands:
                resto = body[3:]
                extra = ("   " + "   ".join(resto)) if resto else ""
                sufijo = f"   ;{comentario}" if comentario else ""
                out.append(f"{jid}   {body[1]}   {demands[jid]:.4f}{extra}{sufijo}")
                continue
        out.append(raw)
    return "\n".join(out)


def assign_demands_by_length(net_: Network, qmd_lps: float) -> dict:
    """Demanda por nodo = QMD · (Σ semi-longitudes de tuberías incidentes al
    nodo / Σ longitudes totales) — método de longitud aferente. Solo se
    asigna a nodos [JUNCTIONS]; la fracción aferente de un nodo fuente
    (reservorio/tanque) no se reparte, la sirve la fuente directamente."""
    total = sum(p.length for p in net_.pipes)
    if total <= 0:
        raise ValueError("La red no tiene tuberías con longitud")
    aferente = {jid: 0.0 for jid in net_.junctions}
    for p in net_.pipes:
        for nid in (p.node1, p.node2):
            if nid in aferente:
                aferente[nid] += p.length / 2.0
    return {jid: qmd_lps * a / total for jid, a in aferente.items()}


@dataclass
class NetworkResult:
    heads: dict           # node id -> cabeza [m]
    flows: dict            # pipe id -> Q [L/s] (positivo node1 -> node2)
    velocities: dict        # pipe id -> V [m/s]
    hf: dict                # pipe id -> pérdida de carga [m]
    iterations: int
    converged: bool


def _hw_r(pipe: Pipe) -> float:
    D = pipe.diameter_mm / 1000.0
    return 10.67 * pipe.length / (pipe.roughness ** 1.852 * D ** 4.8704)


def _dw_r(pipe: Pipe, Q_m3s: float, nu: float) -> float:
    from core import hydraulics as hy
    D = pipe.diameter_mm / 1000.0
    A = math.pi / 4.0 * D ** 2
    V = abs(Q_m3s) / A if A > 0 else 0.0
    Re = hy.reynolds(V, D, nu)
    f = hy.friction_factor(Re, (pipe.roughness / 1000.0) / D) if Re > 0 else 0.02
    return f * pipe.length / (2.0 * G * D * A ** 2)


def solve(net_: Network, temperatura: float = 20.0, tol: float = 1e-6,
         max_outer: int = 50, max_newton: int = 30) -> NetworkResult:
    """Newton-Raphson sobre las cabezas nodales (formulación reducida del
    Global Gradient Algorithm de Todini para fuentes de cabeza fija): dado
    Q_p = signo(Hi-Hj)·(|Hi-Hj|/r_p)^(1/n) en cada tubería, se itera H hasta
    que la continuidad en cada nodo se satisface (Jacobiano analítico). Con
    Darcy-Weisbach, r_p se recalcula cada iteración externa con el caudal de
    la iteración previa (n=2); con Hazen-Williams, r_p es constante
    (n=1.852)."""
    from core import catalogs
    nu = catalogs.water_props(temperatura).nu
    nodes = list(net_.junctions)
    idx = {nid: i for i, nid in enumerate(nodes)}
    nn = len(nodes)
    demand_m3s = np.array([net_.junctions[nid].demand / 1000.0 for nid in nodes])
    H = np.array([net_.junctions[nid].elevation + 10.0 for nid in nodes])
    n_exp = 2.0 if net_.headloss == "D-W" else 1.852
    Q = np.zeros(len(net_.pipes))
    converged, it = False, 0
    for it in range(1, max_outer + 1):
        r = (np.array([_dw_r(p, Q[k], nu) for k, p in enumerate(net_.pipes)])
             if net_.headloss == "D-W" else np.array([_hw_r(p) for p in net_.pipes]))
        Q_prev_outer = Q.copy()
        for _ in range(max_newton):
            F = -demand_m3s.copy()
            J = np.zeros((nn, nn))
            for k, p in enumerate(net_.pipes):
                h1 = (net_.sources[p.node1].head if p.node1 in net_.sources
                      else H[idx[p.node1]])
                h2 = (net_.sources[p.node2].head if p.node2 in net_.sources
                      else H[idx[p.node2]])
                dh = h1 - h2
                q = (math.copysign((abs(dh) / r[k]) ** (1.0 / n_exp), dh)
                     if dh != 0 else 0.0)
                Q[k] = q
                y = 1.0 / (n_exp * r[k] * max(abs(q), 1e-9) ** (n_exp - 1))
                if p.node1 in idx:
                    F[idx[p.node1]] -= q
                    J[idx[p.node1], idx[p.node1]] -= y
                if p.node2 in idx:
                    F[idx[p.node2]] += q
                    J[idx[p.node2], idx[p.node2]] -= y
                if p.node1 in idx and p.node2 in idx:
                    J[idx[p.node1], idx[p.node2]] += y
                    J[idx[p.node2], idx[p.node1]] += y
            try:
                dH = np.linalg.solve(J, -F)
            except np.linalg.LinAlgError:
                dH = np.linalg.lstsq(J, -F, rcond=None)[0]
            H = H + dH
            if np.max(np.abs(dH)) < tol:
                break
        if np.max(np.abs(Q - Q_prev_outer)) < tol:
            converged = True
            break
    heads = {nid: float(H[i]) for i, nid in enumerate(nodes)}
    heads.update({sid: s.head for sid, s in net_.sources.items()})
    flows, vel, hf = {}, {}, {}
    for k, p in enumerate(net_.pipes):
        D = p.diameter_mm / 1000.0
        A = math.pi / 4.0 * D ** 2
        flows[p.id] = float(Q[k] * 1000.0)
        vel[p.id] = float(Q[k] / A) if A > 0 else 0.0
        hf[p.id] = float(r[k] * abs(Q[k]) ** (n_exp - 1) * Q[k])
    return NetworkResult(heads, flows, vel, hf, it, converged)


@dataclass
class OptimizeResult:
    dn_original: dict
    dn_optimizado: dict
    result: NetworkResult
    avisos: list
    iteraciones: int


def _siguiente_dn(material: str, serie: str, dn_actual: float):
    """Siguiente diámetro nominal comercial por encima de `dn_actual`, o
    None si `dn_actual` ya es el mayor del catálogo. `dn_actual` debe ser
    un DN nominal del catálogo (no un diámetro interno) — comparar contra
    el interno rompería el avance monótono, ver `_dn_inicial`."""
    from core import pipes as pipe_cat
    mayores = [d for d in pipe_cat.diameters(material, serie) if d > dn_actual]
    return min(mayores) if mayores else None


def _dn_inicial(material: str, serie: str, diametro_mm: float) -> float:
    """DN nominal de catálogo desde el que arrancar la búsqueda para una
    tubería cuyo `diameter_mm` (diámetro interno usado por `solve()`) no
    necesariamente coincide con ningún DN del catálogo — típico cuando la
    red viene de un INP con diámetros "de diseño" en vez de comerciales.

    Se toma el menor DN cuyo diámetro interno de catálogo sea >= al
    diámetro actual (el DN comercial "equivalente o superior" más
    pequeño); si el diámetro actual excede el mayor DN del catálogo, se
    usa ese mayor DN. Esto evita el bug de comparar `diameter_mm` (interno)
    contra `dn` (nominal, basado en diámetro externo) en cada iteración —
    esa comparación nunca avanza más allá del primer paso porque el
    interno de un DN siempre es menor que su propio DN nominal."""
    from core import pipes as pipe_cat
    dns = sorted(pipe_cat.diameters(material, serie))
    candidatos = [d for d in dns
                  if pipe_cat.pipe(material, serie, d).id_mm >= diametro_mm]
    return min(candidatos) if candidatos else dns[-1]


def _ruta_desde_fuente(net_: Network, nodo: str) -> list:
    """BFS desde la primera fuente hasta `nodo`; asume topología en árbol
    (típica de una red rural) — con anillos, devuelve una ruta válida
    cualquiera, no necesariamente la de menor pérdida."""
    adj: dict = {}
    for p in net_.pipes:
        adj.setdefault(p.node1, []).append((p.node2, p))
        adj.setdefault(p.node2, []).append((p.node1, p))
    origen = next(iter(net_.sources))
    visitado = {origen}
    cola = [(origen, [])]
    while cola:
        actual, ruta = cola.pop(0)
        if actual == nodo:
            return ruta
        for vecino, p in adj.get(actual, []):
            if vecino not in visitado:
                visitado.add(vecino)
                cola.append((vecino, ruta + [p]))
    return []


def optimize_diameters(net_: Network, material: str, serie: str,
                       v_max: float = 6.0, p_min: float = 15.0,
                       p_max: float = 70.0, temperatura: float = 20.0,
                       max_iter: int = 30) -> OptimizeResult:
    """Heurística: sube al siguiente DN comercial toda tubería con V>v_max;
    para nodos con presión<p_min, sube el DN de la tubería con mayor pérdida
    en la ruta desde la fuente. Itera hasta estabilizar o `max_iter`.
    Violaciones de p_max se reportan como aviso de VRP (bajar diámetros no
    reduce la presión estática de un tramo).

    El DN nominal "actual" de cada tubería se rastrea aparte del
    `diameter_mm` (interno) que usa `solve()` — ver `_dn_inicial` para el
    porqué: comparar el interno contra el catálogo nominal directamente
    no avanza monótonamente."""
    from core import pipes as pipe_cat
    dn_original = {p.id: p.diameter_mm for p in net_.pipes}
    dn_actual = {p.id: _dn_inicial(material, serie, p.diameter_mm)
                 for p in net_.pipes}
    it = 0
    for it in range(1, max_iter + 1):
        res = solve(net_, temperatura)
        cambio = False
        for p in net_.pipes:
            if abs(res.velocities[p.id]) > v_max:
                nuevo = _siguiente_dn(material, serie, dn_actual[p.id])
                if nuevo is not None:
                    dn_actual[p.id] = nuevo
                    p.diameter_mm = pipe_cat.pipe(material, serie, nuevo).id_mm
                    cambio = True
        for jid, j in net_.junctions.items():
            if res.heads[jid] - j.elevation < p_min:
                ruta = _ruta_desde_fuente(net_, jid)
                if ruta:
                    peor = max(ruta, key=lambda p: res.hf[p.id])
                    nuevo = _siguiente_dn(material, serie, dn_actual[peor.id])
                    if nuevo is not None:
                        dn_actual[peor.id] = nuevo
                        peor.diameter_mm = pipe_cat.pipe(material, serie, nuevo).id_mm
                        cambio = True
        if not cambio:
            break
    res = solve(net_, temperatura)
    avisos = []
    for jid, j in net_.junctions.items():
        presion = res.heads[jid] - j.elevation
        if presion > p_max:
            avisos.append(f"Nodo '{jid}': presión {presion:.1f} m > máxima "
                          f"{p_max:.0f} m — requiere válvula reductora de presión "
                          "(VRP); bajar diámetros no reduce la presión estática.")
    dn_optimizado = {p.id: p.diameter_mm for p in net_.pipes}
    return OptimizeResult(dn_original, dn_optimizado, res, avisos, it)

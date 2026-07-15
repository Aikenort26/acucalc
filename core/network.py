"""Red de distribución: modelo INP, asignación de demandas por longitud
aferente y solver hidráulico propio (formulación de Todini/Global Gradient
Algorithm reducida a las cabezas nodales, densa con numpy — ver `solve()`)."""
from dataclasses import dataclass, field


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

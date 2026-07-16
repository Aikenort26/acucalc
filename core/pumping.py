"""Sistema de bombeo multi-tramo: pérdidas acumuladas, Hd, potencia."""
import math
from dataclasses import dataclass, field
from core import catalogs, hydraulics as hy

HP_W = 745.7


@dataclass(frozen=True)
class Segment:
    nombre: str
    tipo: str            # "succion" | "impulsion"
    L: float             # m
    D: float             # m (diámetro interno comercial)
    material: str        # clave de data/ks.json


@dataclass(frozen=True)
class Accessory:
    tipo: str            # clave de data/km.json
    cantidad: int
    tramo: str           # Segment.nombre al que pertenece


@dataclass(frozen=True)
class PumpSystem:
    tramos: list[Segment]
    accesorios: list[Accessory]
    he: float            # altura estática total [m]
    temperatura: float   # °C
    eficiencia: float


@dataclass(frozen=True)
class SegmentResult:
    segment: Segment
    V: float
    Re: float
    f: float
    hf: float
    sum_km: float
    hl: float


@dataclass(frozen=True)
class SolveResult:
    tramos: list[SegmentResult]
    hf_total: float
    hl_total: float
    hd: float
    potencia_kw: float
    potencia_hp: float
    issues: list[str] = field(default_factory=list)


def q_bombeo(qmd_lps: float, horas: float) -> float:
    """Q de bombeo [L/s] = QMD·24/h de operación."""
    return qmd_lps * 24.0 / horas


def solve(sys: PumpSystem, Q: float) -> SolveResult:
    """Resuelve pérdidas de todos los tramos/accesorios al caudal Q [m³/s]."""
    w = catalogs.water_props(sys.temperatura)
    ks = catalogs.roughness()
    km_cat = catalogs.minor_loss_coefficients()
    issues: list[str] = []
    results: list[SegmentResult] = []
    for seg in sys.tramos:
        V = hy.velocity(Q, seg.D)
        Re = hy.reynolds(V, seg.D, w.nu)
        f = hy.friction_factor(Re, ks[seg.material] / seg.D)
        hf = hy.hf_darcy(f, seg.L, seg.D, V)
        sum_km = sum(km_cat[a.tipo] * a.cantidad
                     for a in sys.accesorios if a.tramo == seg.nombre)
        hl = hy.hl_local(sum_km, V)
        if seg.tipo == "impulsion" and not 0.5 <= V <= 6.0:
            issues.append(f"Tramo '{seg.nombre}': V={V:.2f} m/s fuera de [0.5, 6.0] "
                          f"(Art. 56 Res. 0330 de 2017)")
        results.append(SegmentResult(seg, V, Re, f, hf, sum_km, hl))
    huerfanos = {a.tramo for a in sys.accesorios} - {s.nombre for s in sys.tramos}
    for h in huerfanos:
        issues.append(f"Accesorios asignados a tramo inexistente: '{h}'")
    hf_total = sum(r.hf for r in results)
    hl_total = sum(r.hl for r in results)
    hd = sys.he + hf_total + hl_total
    p_w = w.rho * hy.G * Q * hd / sys.eficiencia if sys.eficiencia > 0 else float("nan")
    return SolveResult(results, hf_total, hl_total, hd, p_w / 1000.0, p_w / HP_W, issues)


def bresse_continuo(Q: float, K: float = 1.2) -> float:
    """Diámetro económico d = K·√Q [m]. K de Bresse editable."""
    return K * math.sqrt(Q)


def bresse_no_continuo(Q: float, horas: float) -> float:
    """d = 1.3·λ^0.25·√Q con λ = horas de bombeo / 24."""
    return 1.3 * (horas / 24.0) ** 0.25 * math.sqrt(Q)


def system_curve(sys: PumpSystem, q_max: float, n: int = 25) -> list[tuple[float, float]]:
    """Puntos (Q [m³/s], H [m]) de la curva del sistema, Q en [0, q_max]."""
    pts = []
    for i in range(n):
        q = q_max * i / (n - 1)
        if q == 0.0:
            pts.append((0.0, sys.he))
        else:
            pts.append((q, solve(sys, q).hd))
    return pts


def celeridad(D: float, e: float, k_elast: float, a0: float = 9900.0) -> float:
    """Celeridad de onda (Allievi): C = 9900/√(48.3 + K·D/e) [m/s]."""
    return a0 / math.sqrt(48.3 + k_elast * D / e)


def sobrepresion_ariete(c: float, V: float) -> float:
    """Sobrepresión de Joukowsky ΔH = C·V/g [m]."""
    return c * V / hy.G


@dataclass(frozen=True)
class ArieteResult:
    """Verificación de golpe de ariete de un tramo frente a su presión nominal.

    El usuario pidió un "factor de seguridad frente a la rotura", pero describió
    la razón como (hd+ΔH)/PN — que es un *porcentaje de uso*, no un factor de
    seguridad (un FS convencional es el inverso: PN/solicitación, ≥1 = cumple).
    Para que no haya ambigüedad se entregan AMBOS, etiquetados sin lugar a
    confusión:

    - `fs = PN / (hd + ΔH)` → **factor de seguridad**; cumple si ≥ 1.
    - `uso_pct = (hd + ΔH) / PN · 100` → **% de la capacidad del material usada**.
    - `margen_pct = (1 − (hd + ΔH)/PN) · 100` → margen hasta el PN.

    Con `pn == 0` (tramo manual sin PN definido) no se puede evaluar: `fs`,
    `uso_pct`, `margen_pct` y `cumple` quedan en `None` (nunca ZeroDivisionError)."""
    tramo: str
    c: float                    # celeridad de onda [m/s]
    dh: float                   # sobrepresión de Joukowsky [m]
    h_total: float              # hd + ΔH [mca]
    pn: float                   # presión nominal del tramo [mca]
    fs: float | None            # factor de seguridad PN/(hd+ΔH); cumple si ≥ 1
    uso_pct: float | None       # % de la capacidad del material utilizada
    margen_pct: float | None    # % de margen hasta el PN
    cumple: bool | None


def ariete_tramo(tramo: str, D: float, e: float, k_elast: float, V: float,
                 hd: float, pn: float, a0: float = 9900.0) -> ArieteResult:
    """Construye la verificación de ariete de un tramo.

    `hd` es la altura dinámica que se suma a la sobrepresión (por criterio del
    proyecto, la Hd del sistema completo — conservador para tramos
    intermedios). `pn` en mca; `pn <= 0` → tramo sin PN (resultados en None)."""
    c = celeridad(D, e, k_elast, a0)
    dh = sobrepresion_ariete(c, V)
    h_total = hd + dh
    if pn and pn > 0 and h_total > 0:
        fs = pn / h_total
        uso_pct = h_total / pn * 100.0
        margen_pct = (1.0 - h_total / pn) * 100.0
        cumple = h_total <= pn
    else:
        fs = uso_pct = margen_pct = cumple = None
    return ArieteResult(tramo, c, dh, h_total, pn, fs, uso_pct, margen_pct, cumple)


def npsh_disponible(patm_m: float, h_succion: float, perdidas_succion: float,
                    presion_vapor_m: float) -> float:
    """NPSHd = Patm − Pv − h_succión_estática − pérdidas de succión [m]."""
    return patm_m - presion_vapor_m - h_succion - perdidas_succion


@dataclass(frozen=True)
class ArregloResult:
    n_bombas: int
    tipo: str          # "paralelo" | "serie"
    q_unit_lps: float  # caudal por bomba
    h_unit: float      # altura por bomba


def arreglo_bombas(q_total_lps: float, h_total: float, n: int,
                   tipo: str) -> ArregloResult:
    """Reparte el punto de diseño entre n bombas iguales.
    Paralelo: Q se divide, H igual. Serie: H se divide, Q igual."""
    if n < 1:
        raise ValueError("n debe ser ≥ 1")
    if tipo == "paralelo":
        return ArregloResult(n, tipo, q_total_lps / n, h_total)
    if tipo == "serie":
        return ArregloResult(n, tipo, q_total_lps, h_total / n)
    raise ValueError("tipo debe ser 'paralelo' o 'serie'")


def afinidad(q1: float, h1: float, p1: float, n1: float,
             n2: float) -> tuple[float, float, float]:
    """Leyes de afinidad (mismo rodete): Q∝N, H∝N², P∝N³."""
    if n1 <= 0:
        raise ValueError("n1 debe ser > 0")
    r = n2 / n1
    return q1 * r, h1 * r**2, p1 * r**3


def frecuencia_para_caudal(q_objetivo: float, q1: float, n1: float) -> float:
    """Velocidad/frecuencia requerida para llevar el caudal q1 (a n1) a q_objetivo."""
    if q1 <= 0:
        raise ValueError("q1 debe ser > 0")
    return n1 * q_objetivo / q1



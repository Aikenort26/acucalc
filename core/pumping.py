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


def npsh_disponible(patm_m: float, h_succion: float, perdidas_succion: float,
                    presion_vapor_m: float) -> float:
    """NPSHd = Patm − Pv − h_succión_estática − pérdidas de succión [m]."""
    return patm_m - presion_vapor_m - h_succion - perdidas_succion


@dataclass(frozen=True)
class PanelResult:
    cantidad: int
    area_total: float


def paneles_solares(potencia_kw: float, panel_w: float, fs: float,
                    area_panel_m2: float) -> PanelResult:
    n = math.ceil(potencia_kw * 1000.0 * fs / panel_w)
    return PanelResult(n, n * area_panel_m2)

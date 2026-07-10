"""Dotaciones y caudales de diseño (Arts. 43, 44, 47 Res. 0330/2017)."""
from dataclasses import dataclass, field


def dotacion_altitud(msnm: float) -> int:
    """Dotación neta máxima por altitud, Art. 43 Res. 0330."""
    if msnm > 2000:
        return 120
    if msnm >= 1000:
        return 130
    return 140


def dotacion_usos(usos: list[tuple[str, float]]) -> float:
    """Dotación neta como suma de la tabla de usos de la comunidad [L/hab/d]."""
    return sum(v for _, v in usos)


@dataclass(frozen=True)
class FlowResults:
    dneta: float
    perdidas: float
    dbruta: float          # L/hab/d
    qmed_lps: float
    qmd_lps: float
    qmh_lps: float
    k1: float
    k2: float
    issues: list[str] = field(default_factory=list)


def flows(pop: float, dneta: float, perdidas: float, k1: float = 1.3,
          k2: float = 1.6) -> FlowResults:
    if not 0 <= perdidas < 1:
        raise ValueError("perdidas debe estar en [0, 1)")
    issues = []
    if perdidas > 0.25:
        issues.append("Pérdidas técnicas superan el máximo de 25% (Art. 44 Res. 0330 de 2017)")
    dbruta = dneta / (1.0 - perdidas)
    qmed = pop * dbruta / 86400.0            # L/s
    qmd = qmed * k1
    qmh = qmd * k2
    return FlowResults(dneta, perdidas, dbruta, qmed, qmd, qmh, k1, k2, issues)


def design_flows_by_component(r: FlowResults) -> dict[str, float]:
    """Caudales de diseño por componente, Art. 47 Res. 0330 [L/s]."""
    return {
        "Captación superficial": 2.0 * r.qmd_lps,
        "Captación subterránea": r.qmd_lps,
        "Desarenador": r.qmd_lps,
        "Aducción": r.qmd_lps,
        "Conducción": r.qmd_lps,
        "Tanque": r.qmd_lps,
        "Red de distribución": r.qmh_lps,
    }

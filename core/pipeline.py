"""Cadena población → caudales de diseño calculada desde el `Project`
persistido. Única fuente para las páginas y el reporte, así que una página no
depende de que el usuario haya visitado antes la de Caudales."""
from dataclasses import dataclass

from core import demand, population as pop
from core.project import Project


@dataclass(frozen=True)
class DisenoCaudales:
    proj: pop.Projection
    serie_total: list          # [(año, población incluida la flotante)]
    pob_final: float
    flows: demand.FlowResults


def design_flows(p: Project) -> DisenoCaudales | None:
    """None si faltan datos mínimos: censo (≥2), población base, método de
    proyección válido y dotación neta."""
    cfg = p.poblacion
    if len(p.censo) < 2 or cfg.p0 <= 0 or p.demanda.dneta <= 0:
        return None
    proj = pop.project(cfg.p0, int(cfg.year0), int(cfg.horizon_year),
                       pop.growth_rates(p.censo), cfg.tasa_res0844)
    if cfg.metodo not in proj.series:
        return None
    serie_total = [(t, v * (1 + cfg.flotante_pct)) for t, v in proj.series[cfg.metodo]]
    pob_final = serie_total[-1][1]
    flows = demand.flows(pob_final, p.demanda.dneta, p.demanda.perdidas,
                         p.demanda.k1, p.demanda.k2)
    return DisenoCaudales(proj, serie_total, pob_final, flows)

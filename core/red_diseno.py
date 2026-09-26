"""Criterios de diseño de la red de distribución sobre los resultados del
motor hidráulico: presiones y velocidades límite, resumen del periodo
extendido y ensamblado de los cambios (demanda de diseño y bombas) que se
aplican al INP."""
from dataclasses import dataclass, field

from core import curves as cvs
from core import epanet_engine as ee
from core.project import Project


@dataclass(frozen=True)
class ResumenEstatico:
    p_min: float
    nodo_p_min: str
    p_max: float
    nodo_p_max: str
    v_max: float
    tubo_v_max: str
    bajo_p_min: list
    sobre_p_max: list
    sobre_v_max: list

    @property
    def cumple(self) -> bool:
        return not (self.bajo_p_min or self.sobre_p_max or self.sobre_v_max)


@dataclass(frozen=True)
class ResumenEps:
    p_min: float
    nodo_critico: str
    hora_critica: int
    p_min_por_nodo: dict               # nodo -> (presión mínima, hora)
    bajo_p_min: list                   # nodos que bajan de p_min en alguna hora
    tanques: dict = field(default_factory=dict)   # tanque -> {"min", "max", "ini", "fin"}


def resumen_estatico(res: ee.SteadyResult, p_min: float, p_max: float,
                     v_max: float) -> ResumenEstatico:
    pres = res.presiones
    vel = {k: abs(v) for k, v in res.velocities.items()}
    n_min = min(pres, key=pres.get)
    n_max = max(pres, key=pres.get)
    t_max = max(vel, key=vel.get) if vel else ""
    return ResumenEstatico(
        pres[n_min], n_min, pres[n_max], n_max, vel.get(t_max, 0.0), t_max,
        sorted(n for n, p in pres.items() if p < p_min),
        sorted(n for n, p in pres.items() if p > p_max),
        sorted(t for t, v in vel.items() if v > v_max))


def resumen_eps(eps: ee.EpsResult, p_min: float) -> ResumenEps:
    por_nodo = {}
    for n, serie in eps.presiones.items():
        h = min(range(len(serie)), key=serie.__getitem__)
        por_nodo[n] = (serie[h], eps.horas[h])
    critico = min(por_nodo, key=lambda n: por_nodo[n][0])
    tanques = {t: {"min": min(v), "max": max(v), "ini": v[0], "fin": v[-1]}
               for t, v in eps.niveles.items()}
    return ResumenEps(por_nodo[critico][0], critico, por_nodo[critico][1], por_nodo,
                      sorted(n for n, (p, _) in por_nodo.items() if p < p_min), tanques)


def aviso_pico_vs_k2(patron: list, k2: float, tolerancia: float = 0.05) -> str | None:
    """El estático usa K2 (norma) y el periodo extendido el patrón; si el pico
    del patrón difiere de K2 más de la tolerancia, las dos condiciones de
    diseño no representan el mismo caudal máximo horario."""
    pico = max(patron)
    if k2 and abs(pico - k2) / k2 > tolerancia:
        return (f"El pico del patrón horario ({pico:.2f}) difiere de K2 ({k2:.2f}) en más "
                f"de {tolerancia:.0%}: el análisis estático (QMH = K2·QMD) y el de periodo "
                "extendido no representan el mismo caudal máximo horario.")
    return None


def curvas_bombas(p: Project) -> dict:
    """{"Sistema · Bomba": [(Q L/s, H m)]} de la bomba seleccionada de cada
    sistema, con afinidad y arreglo aplicados (misma fuente que el informe)."""
    curvas = {}
    for s in p.bombeos:
        for b in s.bombas:
            if b.nombre == s.bomba_seleccionada and len(b.puntos_qh) >= 2:
                qh, _ = cvs.apply_pump_transform(b.puntos_qh, b.puntos_qe, b.n1_nominal,
                                                 b.n2_objetivo, b.n_unidades, b.arreglo)
                curvas[f"{s.nombre} · {b.nombre}"] = qh
    return curvas


def cambios_red(p: Project, k2: float, patron: list | None = None) -> ee.Cambios:
    """Demanda de diseño y bombas conectadas a nodos. Estático: demanda base
    del INP × K2 (QMH) si aplica. Periodo extendido (con `patron`): demanda
    base × patrón, sin K2 (el pico del patrón ya representa el máximo
    horario). Una bomba sin sus dos nodos definidos no se agrega."""
    bombas = []
    for nombre, curva in curvas_bombas(p).items():
        n1, n2 = (list(p.red_conexiones.get(nombre, [])) + ["", ""])[:2]
        if n1 and n2:
            bombas.append(ee.BombaINP(nombre, n1, n2, curva))
    return ee.Cambios(bombas=bombas, patron=patron,
                      multiplicador=k2 if (p.red_aplicar_k2 and k2 and not patron) else 1.0)

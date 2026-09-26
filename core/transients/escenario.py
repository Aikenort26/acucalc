"""Arma un escenario de transitorios desde el proyecto (perfil, tramos,
niveles, maniobra, bomba), lo resuelve con el MOC y lo contrasta con Allievi,
Joukowsky y Michaud. Las protecciones se diagnostican, no se modelan (salvo
el tanque hidroneumático a la salida de la bomba)."""
import math
from dataclasses import dataclass

import numpy as np

from core import catalogs, hydraulics as hy, pipes, propiedades as pr, pumping as pu
from core import red_diseno as rd
from core.project import Project
from core.transients import allievi, moc, perfil as pf

ESCENARIOS = {
    "cierre_valvula": "Cierre de válvula (aducción/conducción por gravedad)",
    "apertura_valvula": "Apertura de válvula (línea en reposo)",
    "parada_bomba": "Parada súbita de bomba",
    "arranque_bomba": "Arranque de bomba (línea llena en reposo)",
    "hidroneumatico": "Parada de bomba con tanque hidroneumático",
}
_CON_BOMBA = {"parada_bomba", "arranque_bomba", "hidroneumatico"}


@dataclass(frozen=True)
class TramoCalc:
    nombre: str
    x0: float
    x1: float
    D: float          # m
    e: float          # m
    k_elast: float
    ks_mm: float
    a: float
    f: float
    pn: float | None  # mca


@dataclass(frozen=True)
class ResultadoTransitorio:
    escenario: str
    perfil: pf.Perfil
    tramos: list
    moc: moc.MocResult
    Q0: float
    h_vapor_rel: float
    comparacion: list
    resumen: dict
    verificacion_pn: list
    recomendaciones: list
    avisos: list
    serie_allievi: tuple | None = None   # (t, H) en la válvula, cierre sin fricción


def perfil_de(tc) -> pf.Perfil:
    if len(tc.perfil) < 2:
        raise ValueError("Define el perfil de la línea (al menos dos puntos).")
    import pandas as pd
    filas = [(s, zt, ze) for s, zt, ze in tc.perfil]
    # cargar() valida siempre (abscisas crecientes); el diámetro solo hace falta
    # para deducir la cota del eje desde la cobertura
    faltan_ejes = any(ze is None for _, _, ze in filas)
    D = _props_tramo(tc.tramos[0])[0] if faltan_ejes and tc.tramos else None
    return pf.cargar(pd.DataFrame(filas, columns=["Abscisa", "Terreno", "Eje"]),
                     cobertura=tc.cobertura or None, D_m=D)


def _props_tramo(t):
    """(D, e, k_elast, ks_mm, pn) de un tramo del catálogo o manual."""
    if t.cat_material:
        spec = pipes.pipe(t.cat_material, t.cat_serie, t.cat_dn)
        return (spec.id_mm / 1000, spec.e_mm / 1000, spec.k_elast,
                spec.ks_mm or catalogs.roughness()[pipes.KS_KEY.get(t.cat_material, "PVC")],
                spec.pn_mca or None)
    if t.D_mm <= 0 or t.e_mm <= 0:
        raise ValueError(f"El tramo hasta la abscisa {t.hasta_abscisa:g} necesita diámetro "
                         "interno y espesor.")
    return (t.D_mm / 1000, t.e_mm / 1000,
            pipes.K_ELAST_MANUAL.get(t.material, pipes.K_ELAST_DEFAULT),
            catalogs.roughness().get(t.material, 0.0015), t.pn_mca or None)


def _tramos(tc, perfil: pf.Perfil, Q0: float, temperatura: float) -> list:
    if not tc.tramos:
        raise ValueError("Define al menos un tramo de tubería.")
    ordenados = sorted(tc.tramos, key=lambda t: t.hasta_abscisa)
    if ordenados[-1].hasta_abscisa + 1e-6 < perfil.abscisa[-1]:
        raise ValueError("Los tramos deben cubrir todo el perfil (el último debe llegar a "
                         f"la abscisa {perfil.abscisa[-1]:g}).")
    nu = catalogs.water_props(temperatura).nu
    salida, x0 = [], 0.0
    for i, t in enumerate(ordenados):
        x1 = min(perfil.x_de_abscisa(t.hasta_abscisa), perfil.longitud)
        if x1 <= x0 + 1e-6:
            continue
        D, e, k_el, ks, pn = _props_tramo(t)
        a = pu.celeridad(D, e, k_el)
        V = Q0 / (math.pi * D * D / 4)
        f = hy.friction_factor(hy.reynolds(V, D, nu), ks / 1000 / D) if V > 0 else 0.0
        nombre = (f"{t.cat_material} {t.cat_serie} DN{t.cat_dn:g}" if t.cat_material
                  else f"{t.material} Ø{t.D_mm:g} mm")
        salida.append(TramoCalc(f"Tramo {i + 1}: {nombre}", x0, x1, D, e, k_el, ks, a, f, pn))
        x0 = x1
    return salida


def _curva(p: Project, nombre: str) -> moc.CurvaBomba | None:
    puntos = rd.curvas_bombas(p).get(nombre)
    if not puntos or len(puntos) < 3:
        return None
    return moc.CurvaBomba.por_puntos([(q / 1000, h) for q, h in puntos])


def ejecutar(p: Project) -> ResultadoTransitorio:
    tc = p.transitorios
    esc = tc.escenario
    perfil = perfil_de(tc)
    curva = _curva(p, tc.bomba) if esc in _CON_BOMBA else None
    if esc == "arranque_bomba" and curva is None:
        raise ValueError("El arranque requiere la curva de una bomba del proyecto.")
    if tc.modo_parada == "inercia" and esc in ("parada_bomba", "hidroneumatico") and curva is None:
        raise ValueError("La parada con inercia requiere la curva de una bomba del proyecto.")

    # caudal de régimen: el dado, o el punto de operación de la curva (la
    # fricción depende del caudal: se itera)
    Q0 = tc.q0_lps / 1000
    if curva is not None:
        Q0 = Q0 or 0.01
        for _ in range(6):
            tubos = _tramos(tc, perfil, Q0, p.temperatura)
            R_tot = sum(t.f * (t.x1 - t.x0) / (2 * moc.G * t.D * (math.pi * t.D ** 2 / 4) ** 2)
                        for t in tubos)
            Q0 = moc.punto_operacion(curva, tc.h_abajo - tc.h_arriba, R_tot)
    if Q0 <= 0:
        raise ValueError("Define el caudal de régimen.")
    tubos = _tramos(tc, perfil, Q0, p.temperatura)
    tuberias = [moc.Tuberia(t.x1 - t.x0, t.D, t.a, t.f) for t in tubos]

    L = perfil.longitud
    a_eq = L / sum((t.x1 - t.x0) / t.a for t in tubos)
    T_crit = allievi.tiempo_critico(a_eq, L)
    t_fin = tc.t_sim or (max(tc.tc, tc.t_arranque) + 10 * T_crit)
    rho = catalogs.water_props(p.temperatura).rho
    z_max = max(perfil.z_eje)
    h_vap = pr.carga_m(pr.presion_vapor_pa(p.temperatura) - pr.presion_atmosferica_pa(z_max), rho)

    reposo = esc in ("apertura_valvula", "arranque_bomba")
    if esc in ("cierre_valvula", "apertura_valvula"):
        if tc.tc <= 0:
            raise ValueError("Define el tiempo de maniobra de la válvula.")
        if esc == "cierre_valvula":
            tau = (allievi.cierre_potencial(tc.tc, tc.em) if tc.ley == "potencial"
                   else allievi.cierre_lineal(tc.tc))
        else:
            tau = allievi.apertura_lineal(tc.tc)
        arriba, abajo = moc.Embalse(tc.h_arriba), moc.Valvula(tau, tc.h_abajo)
    else:
        vaso = None
        if esc == "hidroneumatico":
            if tc.v_aire <= 0:
                raise ValueError("Define el volumen de aire del tanque hidroneumático.")
            c_orif = 0.0
            if tc.d_orificio_mm > 0 and tc.cd_orificio > 0:
                a_o = tc.cd_orificio * math.pi * (tc.d_orificio_mm / 1000) ** 2 / 4
                c_orif = 1 / (2 * moc.G * a_o ** 2)
            vaso = moc.Hidroneumatico(tc.v_aire, tc.n_poli or 1.2, c_orif, perfil.z_eje[0],
                                      pr.carga_m(pr.presion_atmosferica_pa(perfil.z_eje[0]), rho))
        modo = ("arranque" if esc == "arranque_bomba" else
                "parada_inercia" if tc.modo_parada == "inercia" else "parada_instantanea")
        if modo == "parada_inercia" and (tc.n_rpm <= 0 or tc.eta <= 0 or tc.inercia <= 0):
            raise ValueError("Define velocidad, eficiencia e inercia de la bomba.")
        if modo == "arranque" and tc.t_arranque <= 0:
            raise ValueError("Define el tiempo de arranque de la bomba.")
        arriba = moc.Bomba(tc.h_arriba, modo, curva, tc.n_rpm, tc.inercia, tc.eta or 0.75,
                           tc.t_arranque, vaso)
        abajo = moc.Embalse(tc.h_abajo)

    cfg = moc.Config(tuberias, arriba, abajo, Q0, t_fin, max(tc.n_malla, 4), reposo,
                     perfil.z_en_x, h_vap)
    res = moc.run(cfg)

    # ---- comparación entre métodos
    A_ref = math.pi * (tubos[-1].D if esc in ("cierre_valvula", "apertura_valvula")
                       else tubos[0].D) ** 2 / 4
    V0 = res.Q0 / A_ref
    dh_j = allievi.joukowsky(a_eq, V0)
    comp, serie_allievi = [], None
    if esc == "cierre_valvula":
        h_v0 = res.H_abajo[0]
        dt_a = T_crit / 40
        h_all = allievi.cadena(tau, a_eq, L, V0, h_v0, tc.h_abajo, dt_a, int(t_fin / dt_a))
        serie_allievi = ([k * dt_a for k in range(len(h_all))], h_all)
        comp = [{"metodo": "MOC (perfil real, con fricción)", "dh": res.H_abajo.max() - h_v0,
                 "nota": "máxima en la válvula"},
                {"metodo": "Allievi (conducción equivalente sin fricción)",
                 "dh": np.nanmax(h_all) - h_v0, "nota": f"a = {a_eq:.0f} m/s, L = {L:.0f} m"},
                {"metodo": "Joukowsky (maniobra instantánea)", "dh": dh_j, "nota": "cota superior"}]
        if allievi.clasificar(tc.tc, a_eq, L) == "lenta":
            comp.append({"metodo": "Michaud (maniobra lenta)", "dh": allievi.michaud(L, V0, tc.tc),
                         "nota": "reducción lineal de la velocidad"})
    elif esc == "apertura_valvula":
        comp = [{"metodo": "MOC (perfil real, con fricción)",
                 "dh": res.H_abajo.min() - res.H_abajo[0], "nota": "mínima en la válvula"},
                {"metodo": "Joukowsky (maniobra instantánea)", "dh": -dh_j, "nota": "cota inferior"}]
    elif esc == "arranque_bomba":
        comp = [{"metodo": "MOC (perfil real, con fricción)",
                 "dh": res.H_arriba.max() - res.H_arriba[0], "nota": "máxima en la bomba"},
                {"metodo": "Joukowsky (arranque instantáneo)", "dh": dh_j, "nota": "cota superior"}]
    else:
        comp = [{"metodo": "MOC (perfil real, con fricción)",
                 "dh": res.H_arriba.min() - res.H_arriba[0], "nota": "mínima en la bomba"},
                {"metodo": "Joukowsky (parada instantánea)", "dh": -dh_j, "nota": "cota inferior"}]

    # ---- presiones, PN, vapor
    pmax, pmin = res.pmax, res.pmin
    i_max, i_min = int(np.argmax(pmax)), int(np.argmin(pmin))
    ver_pn = []
    for t in tubos:
        sel = (res.x >= t.x0 - 1e-9) & (res.x <= t.x1 + 1e-9)
        p_t = float(pmax[sel].max())
        ver_pn.append({"tramo": t.nombre, "p_max": p_t, "pn": t.pn,
                       "uso": p_t / t.pn * 100 if t.pn else None,
                       "cumple": (p_t <= t.pn) if t.pn else None})
    resumen = {
        "escenario": ESCENARIOS[esc], "Q0_lps": res.Q0 * 1000, "V0": V0, "L": L, "a_eq": a_eq,
        "T_crit": T_crit, "dt": res.dt, "N": sum(res.N), "ajuste_a_pct": res.ajuste_a_pct,
        "t_fin": t_fin, "p_max": float(pmax[i_max]), "x_p_max": float(res.x[i_max]),
        "p_min": float(pmin[i_min]), "x_p_min": float(res.x[i_min]), "h_vapor": h_vap,
        "s_p_max": float(perfil.abscisa_de_x(res.x[i_max])),
        "s_p_min": float(perfil.abscisa_de_x(res.x[i_min])),
        "clasificacion": allievi.clasificar(tc.tc, a_eq, L) if esc == "cierre_valvula" else "",
        "L_critica": allievi.longitud_critica(tc.tc, a_eq) if tc.tc else None}
    if res.V_aire is not None:
        resumen["v_aire_0"] = float(res.V_aire[0])
        resumen["v_aire_max"] = float(np.max(res.V_aire))
        resumen["v_aire_min"] = float(np.min(res.V_aire))

    avisos = []
    if res.ajuste_a_pct > 5:
        avisos.append(f"La celeridad se ajustó hasta {res.ajuste_a_pct:.1f}% para usar un paso "
                      "común: aumente la resolución de la malla.")
    if res.cavitacion:
        t_c, x_c = res.cavitacion
        avisos.append(f"La presión cae a la de vapor en t = {t_c:.2f} s, en la abscisa "
                      f"{pf.formato_abscisa(perfil.abscisa_de_x(x_c))}: los resultados "
                      "posteriores no son válidos (no se modela la separación de columna).")
    rec = []
    if res.cavitacion or pmin[i_min] < h_vap:
        altos = perfil.puntos_altos()
        rec.append("Riesgo de separación de columna (presión de vapor alcanzada). Opciones: "
                   "tanque hidroneumático o volante de inercia en la bomba, chimenea de "
                   "equilibrio, ventosas de triple efecto en los puntos altos"
                   + (f" (abscisas {', '.join(pf.formato_abscisa(s) for s in altos)})"
                      if altos else "")
                   + ", o maniobras más lentas.")
    elif pmin[i_min] < 0:
        rec.append(f"Hay subpresiones (mínima {pmin[i_min]:.2f} m en la abscisa "
                   f"{pf.formato_abscisa(resumen['s_p_min'])}): verificar la resistencia de la "
                   "tubería al colapso y ubicar ventosas de admisión en los puntos altos.")
    if any(v["cumple"] is False for v in ver_pn):
        rec.append("La presión máxima supera la PN de la tubería: aumentar la clase (PN) del "
                   "tramo, alargar la maniobra por encima de 2L/a = "
                   f"{T_crit:.1f} s, o instalar válvula anticipadora de onda o de alivio.")
    if "v_aire_max" in resumen:
        rec.append(f"El aire del tanque hidroneumático se expande de {resumen['v_aire_0']:.3f} a "
                   f"{resumen['v_aire_max']:.3f} m³: el volumen total del tanque debe superar "
                   "ese valor con una reserva de agua que evite su vaciado.")
    if esc == "cierre_valvula" and resumen["clasificacion"] == "rápida":
        rec.append(f"La maniobra es rápida (Tc ≤ 2L/a = {T_crit:.1f} s): la sobrepresión se "
                   "acerca a la de Joukowsky; un cierre más lento la reduce.")
    return ResultadoTransitorio(esc, perfil, tubos, res, res.Q0, h_vap, comp, resumen, ver_pn,
                                rec, avisos, serie_allievi)

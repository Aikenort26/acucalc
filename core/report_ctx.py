"""Construye el contexto del reporte recalculando TODO desde el proyecto.

Mismo pipeline que usa la página 7 de la app: población → caudales →
almacenamiento → sistemas de bombeo → figuras. Reproducible desde el JSON
del proyecto, sin Streamlit ni session_state."""
import base64
import tempfile
from pathlib import Path

import matplotlib.pyplot as plt

from core import biblio, curves as cvs, demand, network, pipeline, pipes, population as pop, pumping as pu
from core import epanet_engine as ee, formato as fm, geo, network_map as nm, red_diseno as rd
from core import detalles as dt, estudios as est, study_map as sm
from core import report_figs as rf, storage, tank_network as tn
from core.transients import escenario as esc, perfil as pf
from core.latex import latex_escape
from core.project import Project

LOGO_ACUCALC = Path(__file__).resolve().parent.parent / "assets" / "acucalc_logo.png"

# Autor de la aplicación ACUCALC (distinto del `consultor` del proyecto, que es
# quien firma cada memoria). Va a la sección "Acerca de ACUCALC" del informe.
AUTOR_APP = "Aiken H. Ortega-Heredia"

# Un patrón horario de consumo (y su ventana de suministro) debe traer las 24
# horas del día: `core/storage.volume_curva_integral` lo exige y las figuras lo
# asumen.
HORAS_DIA = 24

def referencias(p: Project) -> list[biblio.Ref]:
    """Biblioteca base + BibTeX del usuario; una clave del usuario igual a una
    de la base la reemplaza (permite corregir una entrada base)."""
    propias = biblio.parse_bibtex(p.bibtex_usuario)[0] if p.bibtex_usuario.strip() else []
    claves = {r.key for r in propias}
    return [r for r in biblio.biblioteca_base() if r.key not in claves] + propias


def _red_hidraulica(p: Project, red, inp: str, k2: float, factores_hora: list, _save) -> dict:
    """Régimen estático con la demanda de diseño (QMH si aplica) y, con
    EPANET, periodo extendido de 24 h con el patrón horario."""
    out = {"estatico": None, "eps": None, "error": ""}
    try:
        cambios = rd.cambios_red(p, k2)
        res = ee.correr_estatico(inp, cambios, motor=p.red_motor)
    except (ee.EngineError, ValueError) as e:
        out["error"] = latex_escape(str(e))
        return out
    r = rd.resumen_estatico(res, p.red_pmin, p.red_pmax, p.red_vmax)
    out["estatico"] = {
        "motor": latex_escape(res.motor), "multiplicador": f"{cambios.multiplicador:.2f}",
        "p_min": fm.fmt_h(r.p_min), "nodo_p_min": latex_escape(r.nodo_p_min),
        "p_max": fm.fmt_h(r.p_max), "nodo_p_max": latex_escape(r.nodo_p_max),
        "v_max": fm.fmt_v(r.v_max), "tubo_v_max": latex_escape(r.tubo_v_max),
        "n_bajo": len(r.bajo_p_min), "n_sobre": len(r.sobre_p_max),
        "n_vel": len(r.sobre_v_max), "pmin": f"{p.red_pmin:.0f}", "pmax": f"{p.red_pmax:.0f}",
        "vmax": f"{p.red_vmax:.1f}", "converge": res.converged,
        "cumple": "Sí" if (r.cumple and res.converged) else "No",
        "avisos": [latex_escape(a.texto) for a in res.avisos],
        "bombas": [latex_escape(b.nombre) for b in cambios.bombas],
        "fig": "red_presion.png"}
    _save(nm.fig_red(red, res, colorear="presion", dark=False), "red_presion")
    if res.motor.startswith("EPANET"):
        patron = (list(factores_hora) if len(factores_hora) == HORAS_DIA
                  else list(storage.DEFAULT_PATTERN))
        try:
            eps = ee.correr_eps(inp, rd.cambios_red(p, k2, patron=patron))
        except ee.EngineError as e:
            out["error"] = latex_escape(str(e))
            return out
        re_ = rd.resumen_eps(eps, p.red_pmin)
        out["eps"] = {
            "p_min": fm.fmt_h(re_.p_min), "nodo": latex_escape(re_.nodo_critico),
            "hora": f"{re_.hora_critica:02d}", "n_bajo": len(re_.bajo_p_min),
            "pico": f"{max(patron):.2f}", "aviso_k2": latex_escape(
                rd.aviso_pico_vs_k2(patron, k2) or ""),
            "avisos": sorted({latex_escape(a.texto) for a in eps.avisos}),
            "tanques": [{"id": latex_escape(t), "ini": fm.fmt_h(v["ini"]),
                         "min": fm.fmt_h(v["min"]), "max": fm.fmt_h(v["max"]),
                         "fin": fm.fmt_h(v["fin"])} for t, v in re_.tanques.items()],
            "fig": "red_eps.png"}
        _save(rf.fig_eps(eps.horas, re_.nodo_critico, eps.presiones[re_.nodo_critico],
                         eps.niveles, p.red_pmin), "red_eps")
    return out


def _grados(v: float, pos: str, neg: str) -> str:
    return latex_escape(f"{abs(v):.5f}° {pos if v >= 0 else neg}")


def _localizacion(p: Project, _save) -> dict | None:
    """Mapas de localización ya guardados en el proyecto (sin conexión: nunca
    descarga teselas aquí)."""
    ub = p.ubicacion
    mapas = {m.nombre: m for m in ub.mapas if m.img_b64}
    if not (ub.en_informe and mapas):
        return None
    general, zona = mapas.get("general"), mapas.get("zona")
    segmentos = None
    if ub.epsg_red and p.red_inp and zona:
        try:
            segmentos = sm.red_a_latlon(network.parse_inp(p.red_inp), ub.epsg_red)
        except (ValueError, geo.GeoError):
            segmentos = None
        if segmentos and sm.fraccion_dentro(zona, segmentos) == 0:
            segmentos = None                      # CRS equivocado: no se dibuja fuera de lugar
    nombres = {}
    for nombre, mapa, kw in (("general", general,
                              {"recuadro": sm.extension(zona) if zona else None}),
                             ("zona", zona, {"segmentos": segmentos})):
        fig = sm.fig_localizacion(mapa, ub.lat, ub.lon, **kw)
        if fig is not None:
            _save(fig, f"localizacion_{nombre}")
            nombres[nombre] = f"localizacion_{nombre}.png"
    if not nombres:
        return None
    fuente = (zona or general).fuente
    return {
        "lat": _grados(ub.lat, "N", "S"), "lon": _grados(ub.lon, "E", "O"),
        "fig_general": nombres.get("general"), "fig_zona": nombres.get("zona"),
        "fuente": latex_escape(geo.FUENTES[fuente].nombre),
        "atribucion": latex_escape(geo.FUENTES[fuente].atribucion),
        "cita": "esri_imagery" if fuente == "esri" else "osm",
        "con_red": bool(segmentos),
        "epsg": latex_escape(sm.EPSG_RED.get(ub.epsg_red, f"EPSG:{ub.epsg_red}")),
    }


def _detalles(p: Project, _save) -> dict:
    """Detalles típicos: zanja (solo con todas sus dimensiones), esquema de
    cada estación de bombeo y corte de cada tanque con sus niveles."""
    z = p.zanja
    faltan = dt.validar_zanja(z)
    zanja = None
    if z.en_informe and not faltan:
        _save(dt.fig_zanja(z), "detalle_zanja")
        zanja = {"fig": "detalle_zanja.png", "D": f"{z.d_ext_mm:.0f}",
                 "B": f"{z.ancho_fondo:.2f}", "sup": f"{dt.ancho_superior(z):.2f}",
                 "H": f"{z.profundidad:.2f}", "talud": f"{z.talud:g}",
                 "cama": f"{z.cama:.2f}", "atraque": f"{z.atraque:.2f}",
                 "pavimento": f"{z.pavimento:.2f}", "cobertura": f"{dt.cobertura(z):.2f}",
                 "mat_cama": latex_escape(z.mat_cama) or "---",
                 "mat_atraque": latex_escape(z.mat_atraque) or "---",
                 "mat_relleno": latex_escape(z.mat_relleno) or "---",
                 "nota": latex_escape(z.nota)}
    estaciones = []
    for i, s in enumerate(p.bombeos, 1):
        fig = dt.fig_estacion(s)
        if fig is not None:
            _save(fig, f"detalle_estacion_{i}")
            estaciones.append({"nombre": latex_escape(s.nombre),
                               "fig": f"detalle_estacion_{i}.png"})
    tanques = []
    frac = p.almacenamiento.frac_incendio
    for i, t in enumerate(p.almacenamiento.tanques, 1):
        fig = dt.fig_tanque(t, frac)
        if fig is None:
            continue
        nv = dt.niveles_tanque(t, frac)
        _save(fig, f"detalle_tanque_{i}")
        tanques.append({"nombre": latex_escape(t.nombre), "fig": f"detalle_tanque_{i}.png",
                        "cantidad": max(int(t.cantidad), 1), "area": f"{nv.area:.2f}",
                        "h_util": f"{nv.h_util:.2f}", "h_max": f"{nv.h_max:.2f}",
                        "h_inc": f"{nv.h_incendio:.2f}",
                        "borde_libre": f"{nv.borde_libre:.2f}" if nv.borde_libre > 0 else "",
                        "v_unidad": f"{nv.v_unidad:.0f}", "v_inc": f"{nv.v_incendio:.0f}"})
    return {"zanja": zanja, "zanja_faltantes": faltan if zanja is None else [],
            "estaciones": estaciones, "tanques": tanques,
            "frac_incendio": f"{frac * 100:.0f}"}


def _maniobra(tc) -> str:
    """Descripción en texto de la maniobra simulada (para el informe)."""
    bomba = f"la bomba {tc.bomba}" if tc.bomba else "la bomba"
    if tc.escenario == "cierre_valvula":
        ley = ("lineal" if tc.ley == "lineal" else f"potencial con exponente Em = {tc.em:.2f}")
        return (f"cierre {ley} de la válvula de aguas abajo en Tc = {tc.tc:.2f} s, con el "
                f"embalse de aguas arriba a {tc.h_arriba:.2f} m y la descarga a "
                f"{tc.h_abajo:.2f} m")
    if tc.escenario == "apertura_valvula":
        return (f"apertura lineal de la válvula de aguas abajo en {tc.tc:.2f} s, desde la línea "
                f"en reposo, con el embalse a {tc.h_arriba:.2f} m y la descarga a "
                f"{tc.h_abajo:.2f} m")
    if tc.escenario == "arranque_bomba":
        return (f"arranque de {bomba} con rampa lineal de velocidad de {tc.t_arranque:.1f} s, "
                f"desde la línea llena en reposo, succión a {tc.h_arriba:.2f} m y tanque de "
                f"descarga a {tc.h_abajo:.2f} m")
    parada = ("instantánea (Q = 0, cota conservadora)" if tc.modo_parada == "instantanea" else
              f"con la inercia del grupo (I = {tc.inercia:.3f} kg·m², {tc.n_rpm:.0f} rpm, "
              f"η = {tc.eta:.2f}) y retención ideal")
    txt = (f"parada súbita de {bomba}, {parada}, con succión a {tc.h_arriba:.2f} m y tanque "
           f"de descarga a {tc.h_abajo:.2f} m")
    if tc.escenario == "hidroneumatico":
        orif = (f"orificio de {tc.d_orificio_mm:.0f} mm (Cd = {tc.cd_orificio:.2f})"
                if tc.d_orificio_mm > 0 else "conexión sin orificio")
        txt += (f"; a la salida de la bomba hay un tanque hidroneumático con "
                f"{tc.v_aire:.3f} m³ de aire en régimen, exponente politrópico "
                f"n = {tc.n_poli:.2f} y {orif}")
    return txt


def _transitorio(p: Project, _save) -> dict | None:
    """Sección de transitorios: se recalcula desde el proyecto (MOC + Allievi).
    Un dato inválido no rompe el informe: se documenta el motivo."""
    tc = p.transitorios
    if not (tc.en_informe and len(tc.perfil) >= 2 and tc.tramos):
        return None
    try:
        rt = esc.ejecutar(p)
    except (ValueError, KeyError) as e:
        return {"error": latex_escape(str(e))}
    rs, m = rt.resumen, rt.moc
    _save(rf.fig_transitorio_perfil(rt, dark=False), "transitorio_perfil")
    _save(rf.fig_transitorio_tiempo(rt, dark=False), "transitorio_tiempo")
    cav = None
    if m.cavitacion:
        cav = {"t": f"{m.cavitacion[0]:.2f}",
               "s": pf.formato_abscisa(rt.perfil.abscisa_de_x(m.cavitacion[1]))}
    return {
        "error": None,
        "escenario": latex_escape(rs["escenario"]),
        "maniobra": latex_escape(_maniobra(tc)),
        "n_perfil": len(rt.perfil.abscisa),
        "s_ini": pf.formato_abscisa(rt.perfil.abscisa[0]),
        "s_fin": pf.formato_abscisa(rt.perfil.abscisa[-1]),
        "resumen": {
            "q0": f"{rs['Q0_lps']:.2f}", "v0": f"{rs['V0']:.2f}", "L": f"{rs['L']:.1f}",
            "a_eq": f"{rs['a_eq']:.0f}", "t_crit": f"{rs['T_crit']:.2f}",
            "dt": f"{rs['dt']:.4f}", "N": rs["N"], "ajuste": f"{rs['ajuste_a_pct']:.2f}",
            "t_fin": f"{rs['t_fin']:.1f}", "p_max": f"{rs['p_max']:.2f}",
            "s_p_max": pf.formato_abscisa(rs["s_p_max"]), "p_min": f"{rs['p_min']:.2f}",
            "s_p_min": pf.formato_abscisa(rs["s_p_min"]), "h_vapor": f"{rs['h_vapor']:.2f}",
            "clasificacion": rs["clasificacion"],
            "v_aire_max": f"{rs['v_aire_max']:.3f}" if "v_aire_max" in rs else ""},
        "tramos": [{"nombre": latex_escape(t.nombre), "desde": pf.formato_abscisa(
                        rt.perfil.abscisa_de_x(t.x0)),
                    "hasta": pf.formato_abscisa(rt.perfil.abscisa_de_x(t.x1)),
                    "D": f"{t.D * 1000:.1f}", "e": f"{t.e * 1000:.2f}",
                    "k": f"{t.k_elast:.2f}", "a": f"{t.a:.0f}", "f": f"{t.f:.4f}",
                    "pn": f"{t.pn:.0f}" if t.pn else "---"} for t in rt.tramos],
        "metodos": [{"metodo": latex_escape(c["metodo"]), "dh": f"{c['dh']:+.2f}",
                     "nota": latex_escape(c["nota"])} for c in rt.comparacion],
        "pn": [{"tramo": latex_escape(v["tramo"]), "p_max": f"{v['p_max']:.2f}",
                "pn": f"{v['pn']:.0f}" if v["pn"] else "---",
                "uso": f"{v['uso']:.0f}" if v["uso"] is not None else "---",
                "cumple": "---" if v["cumple"] is None else ("Sí" if v["cumple"] else "No")}
               for v in rt.verificacion_pn],
        "cavitacion": cav,
        "avisos": [latex_escape(a) for a in rt.avisos],
        "recomendaciones": [latex_escape(r) for r in rt.recomendaciones],
        "fig_perfil": "transitorio_perfil.png",
        "fig_tiempo": "transitorio_tiempo.png",
        "con_bomba": rt.escenario in ("parada_bomba", "arranque_bomba", "hidroneumatico"),
        "q0_de_curva": bool(tc.bomba) and rt.escenario in ("parada_bomba", "arranque_bomba",
                                                         "hidroneumatico"),
    }


def build(p: Project) -> tuple[dict, dict]:
    """Devuelve (ctx para la plantilla LaTeX, dict figuras nombre→ruta png).

    Requiere: nombre, censo (≥2), población base y método seleccionados."""
    cfg = p.poblacion
    diseno = pipeline.design_flows(p) if p.nombre else None
    if diseno is None:
        raise ValueError("Faltan datos mínimos: nombre, censo, población base, "
                         "método y dotación neta")

    # ---------- población y caudales ----------
    proj, serie_total = diseno.proj, diseno.serie_total
    pob_final, flows = diseno.pob_final, diseno.flows
    serie_q = demand.flows_series(serie_total, p.demanda.dneta, p.demanda.perdidas,
                                  p.demanda.k1, p.demanda.k2)
    comp = demand.design_flows_by_component(flows)
    qmd_m3d = flows.qmd_lps * 86.4

    # ---------- almacenamiento ----------
    # Flujo norma-first: volumen total = max(Art.81 QMD/3, curva integral de la
    # comunidad). Los tanques los define el usuario (volumen asignado + ventanas);
    # la app verifica el balance interno de cada uno, no reparte.
    alm = p.almacenamiento
    a = storage.volume_art81(qmd_m3d, alm.frac_regulacion, alm.frac_incendio,
                             alm.dias_reserva)

    # Un patrón horario solo es utilizable si trae las 24 horas: `storage` lo
    # exige y las figuras lo asumen. Se valida UNA vez y "patrón inválido" pasa
    # a ser equivalente a "sin patrón" en todo el reporte — volumen, figura y
    # tabla. Antes solo se atrapaba el ValueError del volumen, y un patrón de
    # otra longitud (un JSON viejo o editado a mano) reventaba más adelante en
    # `fig_balance_train` con un error de matplotlib incomprensible
    # ("x and y must have same first dimension").
    patron_ok = len(alm.factores_hora) == HORAS_DIA
    suministro_ok = len(alm.suministro_hora) == HORAS_DIA

    b = None
    if patron_ok and suministro_ok:
        try:
            b = storage.volume_curva_integral(qmd_m3d, alm.factores_hora,
                                              alm.suministro_hora, alm.frac_incendio,
                                              alm.dias_reserva)
        except ValueError:
            b = None
    v_final = storage.final_volume(a, b) if b else a.v_total_redondeado
    gobierna = ("Art. 81 (QMD/3)" if not b or a.v_total_redondeado >= b.v_total_redondeado
                else "Curva integral")

    # ---------- patrón horario de consumo (documentación en el informe) ----------
    patron_horas: list = []
    patron_pico = patron_valle = patron_suma = None
    if patron_ok:
        patron_horas = [
            {"hora": f"{h:02d}",
             "factor": f"{f:.2f}",
             # 1/0 de la ventana de suministro de la comunidad, si está definida
             "suministro": ("sí" if alm.suministro_hora[h] else "no")
                           if suministro_ok else "—"}
            for h, f in enumerate(alm.factores_hora)]
        patron_pico = f"{max(alm.factores_hora):.2f}"
        patron_valle = f"{min(alm.factores_hora):.2f}"
        # La media de los 24 factores debe rondar 1.0 (= QMD), así que su suma
        # ronda 24; se reporta para que el lector verifique la normalización.
        patron_suma = f"{sum(alm.factores_hora):.2f}"

    # verificación de balance interno por tanque (suministro=entrada, salida=salida)
    tanques_balance = []
    for t in alm.tanques:
        try:
            chk = storage.tank_balance_check(t.nombre, qmd_m3d, t.entrada_flags(),
                                             t.salida_flags(), t.volumen,
                                             alm.frac_incendio, alm.dias_reserva)
        except ValueError:
            continue
        tanques_balance.append({
            "nombre": latex_escape(chk.nombre),
            "horas_suministro": f"{chk.horas_suministro:.0f}",
            "horas_salida": f"{chk.horas_salida:.0f}",
            "frac": f"{chk.frac_balance:.4f}",
            "v_asignado": f"{chk.v_asignado:.0f}",
            "v_req": fm.fmt_vol(chk.v_balance_req),
            "cumple": "Sí" if chk.cumple else "No"})
    v_asignado_total = sum(t.volumen for t in alm.tanques)

    # balance de masas entre tanques (modo red, opcional)
    res_red, balance_red = None, None
    if alm.modo_balance == "red" and alm.tanques and alm.enlaces:
        patron_bal = (alm.factores_hora if patron_ok else list(storage.DEFAULT_PATTERN))
        try:
            res_red = tn.resolver(*tn.desde_config(alm), flows.qmd_lps, patron_bal,
                                  alm.frac_incendio, alm.dias_reserva)
        except ValueError as e:
            balance_red = {"error": latex_escape(str(e)), "tanques": [], "enlaces": [],
                           "avisos": [], "fig": None}
        else:
            balance_red = {
                "error": "",
                "tanques": [{"nombre": latex_escape(b.nombre), "v_asignado": f"{b.v_asignado:.0f}",
                             "v_reg": fm.fmt_vol(b.v_reg), "v_req": fm.fmt_vol(b.v_req),
                             "v_sugerido": f"{b.v_sugerido}",
                             "cierre": f"{b.cierre_diario_m3:+.2f}",
                             "cumple": "Sí" if b.cumple else "No"} for b in res_red.tanques],
                "enlaces": [{"origen": latex_escape(e.origen), "destino": latex_escape(e.destino),
                             "tipo": e.tipo, "ventana": f"{e.ini:02d}--{e.fin:02d} h",
                             "q": fm.fmt_q(res_red.caudal(e.origen, e.destino)),
                             "auto": e.caudal_lps <= 0} for e in alm.enlaces],
                "avisos": [latex_escape(a) for a in res_red.avisos],
                "fig": "balance_red.png"}

    # ---------- figuras ----------
    figdir = Path(tempfile.mkdtemp())
    figuras: dict[str, str] = {}

    def _save(fig, name):
        fp = figdir / f"{name}.png"
        fig.savefig(fp, dpi=150, bbox_inches="tight")
        plt.close(fig)
        figuras[name] = str(fp)

    _save(rf.fig_poblacion(proj, cfg.metodo, cfg.flotante_pct), "poblacion")
    _save(rf.fig_metodos(proj.deviations, pop.suggest_method(proj)), "metodos")
    _save(rf.fig_caudales([(t, fr.qmed_lps, fr.qmd_lps, fr.qmh_lps)
                           for t, fr in serie_q]), "caudales")
    # Mismo guard de 24 horas que el volumen y la tabla del patrón: la figura
    # grafica los factores contra un eje de 24 horas y con otra longitud
    # reventaba el build entero.
    if patron_ok and suministro_ok:
        _save(rf.fig_balance_train([("Comunidad", alm.suministro_hora, alm.factores_hora)]),
              "balance")
    if res_red is not None:
        _save(rf.fig_balance_red(res_red, alm.frac_incendio, alm.dias_reserva), "balance_red")
    sistemas_bomba_ctx = ([{"tipo_bomba": s.tipo_bomba} for s in p.bombeos]
                         or [{"tipo_bomba": "superficie"}])
    _save(rf.fig_esquema(sistemas_bomba_ctx, alm.tanques), "esquema")

    # ---------- imágenes b64 embebidas (logos, curvas de bomba) ----------
    def _save_b64_image(b64: str, name: str) -> str | None:
        if not b64:
            return None
        raw = base64.b64decode(b64)
        ext = "jpg" if raw[:3] == b"\xff\xd8\xff" else "png"
        fp = figdir / f"{name}.{ext}"
        fp.write_bytes(raw)
        figuras[name] = str(fp)
        return fp.name

    logo_cliente = _save_b64_image(p.logo_cliente_b64, "logo_cliente")
    figuras["acucalc_logo"] = str(LOGO_ACUCALC)
    logo_consultor = _save_b64_image(p.logo_consultor_b64, "logo_consultor")
    estudios_ctx, estudios_faltantes = est.contexto(
        p.estudios, {r.key for r in referencias(p)}, _save_b64_image)

    # ---------- sistemas de bombeo ----------
    sistemas_ctx = []
    for i, s in enumerate(p.bombeos):
        if not s.tramos:
            continue
        qb_lps = pu.q_bombeo(flows.qmd_lps, s.horas)
        he = s.he + (5.0 if s.sumar_5m_ras else 0.0)
        sistema = pu.PumpSystem(
            tramos=[pu.Segment(t.nombre, t.tipo, t.L, t.D_mm / 1000, t.material)
                    for t in s.tramos],
            accesorios=[pu.Accessory(a2.tipo, a2.cantidad, a2.tramo)
                        for a2 in s.accesorios],
            he=he, temperatura=p.temperatura, eficiencia=s.eficiencia)
        r = pu.solve(sistema, qb_lps / 1000)
        # ---------- golpe de ariete: FS por tramo (WP-2c) ----------
        # Usa Hd del sistema completo (criterio conservador, igual que la app).
        ariete_tab = []
        for t, tr in zip(s.tramos, r.tramos):
            if not t.e_mm:
                continue
            k_el, pn_t = pipes.k_elast_tramo(t)
            pn_t = pn_t or 0.0     # tramo manual: sin PN en el reporte (se evalúa en la app)
            ar = pu.ariete_tramo(t.nombre, t.D_mm / 1000, t.e_mm / 1000, k_el,
                                 tr.V, r.hd, pn_t)
            ariete_tab.append({
                "nombre": latex_escape(t.nombre), "c": fm.fmt_v(ar.c),
                "dh": fm.fmt_h(ar.dh), "h_total": fm.fmt_h(ar.h_total),
                "pn": f"{ar.pn:.0f}" if ar.pn else "—",
                "fs": fm.fmt_num(ar.fs, 2), "uso": fm.fmt_num(ar.uso_pct, 1),
                "margen": fm.fmt_num(ar.margen_pct, 1),
                "cumple": ("Sí" if ar.cumple else
                           ("No" if ar.cumple is False else "—"))})
        q_max_lps = max(qb_lps * 1.5, max((bb.puntos_qh[-1][0] for bb in s.bombas
                                           if len(bb.puntos_qh) >= 3), default=0.0))
        sys_lps = [(q * 1000, h) for q, h in
                   pu.system_curve(sistema, max(q_max_lps / 1000, 1e-4), n=30)]
        bombas_fig, bombas_tab = [], []
        for bb in s.bombas:
            if len(bb.puntos_qh) < 3:
                continue
            qh_t, qe_t = cvs.apply_pump_transform(
                bb.puntos_qh, bb.puntos_qe, bb.n1_nominal, bb.n2_objetivo,
                bb.n_unidades, bb.arreglo)
            fit = cvs.fit_curve(qh_t, 2)
            op = cvs.operating_point(fit, sys_lps)
            e_fit = cvs.fit_curve(qe_t, 2) if len(qe_t) >= 3 else None
            bep = cvs.best_efficiency_point(qe_t, 2) if e_fit else None
            eta = e_fit(op[0]) if (op and e_fit) else float("nan")
            pot = (998.29 * 9.81 * op[0] / 1000 * op[1] / eta / 745.7
                   if op and eta and eta > 0 else float("nan"))
            afinidad_activa = bb.n1_nominal > 0 and bb.n2_objetivo not in (0, bb.n1_nominal)
            partes_arr = []
            if bb.n_unidades > 1:
                partes_arr.append(f"{bb.n_unidades}$\\times${bb.arreglo}")
            if afinidad_activa:
                partes_arr.append(f"@ N$_2$={bb.n2_objetivo:.0f}")
            arreglo_txt = " ".join(partes_arr) if partes_arr else "nominal"
            bombas_fig.append({"nombre": bb.nombre, "fit": fit, "op": op, "e_fit": e_fit})
            A, B, C = fit.coeffs
            bombas_tab.append({
                "nombre": latex_escape(bb.nombre), "arreglo": arreglo_txt,
                "h_eq": f"$H = {A:+.4f}Q^2 {B:+.4f}Q {C:+.3f}$",
                "e_eq": (f"$\\eta = {e_fit.coeffs[0]:+.6f}Q^2 "
                         f"{e_fit.coeffs[1]:+.5f}Q {e_fit.coeffs[2]:+.4f}$"
                         if e_fit else "---"),
                "q_op": fm.fmt_q(op[0]) if op else "—",
                "h_op": fm.fmt_h(op[1]) if op else "—",
                "eta_op": f"{eta:.3f}" if eta == eta else "—",   # η: fracción 0-1, .3f a propósito
                "bep_q": fm.fmt_q(bep.q) if bep else "—",
                "desv_bep": f"{(op[0] - bep.q) / bep.q * 100:.1f}" if (op and bep) else "—",
                "p_hp": fm.fmt_p(pot) if pot == pot else "—"})
        npsh_ctx = None
        if s.tipo_bomba != "sumergible":
            n = pu.npsh_sistema(r, p.altitud, p.temperatura, s.z_succion, s.npsh_r,
                                s.margen_npsh)
            npsh_ctx = {
                "patm": fm.fmt_perdida(n.patm_m), "pv": fm.fmt_perdida(n.pv_m),
                "z": fm.fmt_perdida(n.z_succion), "perdidas": fm.fmt_perdida(n.perdidas_succion),
                "npsh_d": fm.fmt_h(n.npsh_d),
                "npsh_r": fm.fmt_h(n.npsh_r) if n.npsh_r else "—",
                "margen": fm.fmt_h(n.margen),
                "cumple": "—" if n.cumple is None else ("Sí" if n.cumple else "No")}
        fig_name = f"sistema_{i + 1}"
        _save(rf.fig_sistema(sys_lps, bombas_fig, qb_lps, r.hd, s.nombre), fig_name)
        sistemas_ctx.append({
            "nombre": latex_escape(s.nombre), "tipo_bomba": s.tipo_bomba,
            "horas": f"{s.horas:.0f}",
            "qb": fm.fmt_q(qb_lps), "hd": fm.fmt_h(r.hd), "eficiencia": s.eficiencia,
            "potencia_kw": fm.fmt_p(r.potencia_kw), "potencia_hp": fm.fmt_p(r.potencia_hp),
            "tramos": [{"nombre": latex_escape(t.segment.nombre), "L": fm.fmt_h(t.segment.L),
                        "D_mm": fm.fmt_d(t.segment.D * 1000),
                        "material": t.segment.material,
                        "V": fm.fmt_v(t.V), "hf": fm.fmt_perdida(t.hf),
                        "hl": fm.fmt_perdida(t.hl)}
                       for t in r.tramos],
            "bombas": bombas_tab,
            "ariete": ariete_tab,
            "npsh": npsh_ctx,
            "bomba_seleccionada": latex_escape(s.bomba_seleccionada or "—"),
            "fig": f"{fig_name}.png"})

    # ---------- anexo: curvas de bombas seleccionadas (imagen original del catálogo) ----------
    anexos_curvas = []
    for i, s in enumerate(p.bombeos):
        if not s.bomba_seleccionada:
            continue
        for j, bb in enumerate(s.bombas):
            if bb.nombre != s.bomba_seleccionada or not bb.imagen_b64:
                continue
            fig_curva = _save_b64_image(bb.imagen_b64, f"curva_{i}_{j}")
            if fig_curva:
                anexos_curvas.append({
                    "sistema": latex_escape(s.nombre),
                    "bomba": latex_escape(bb.nombre),
                    "fig": fig_curva})
            break

    # ---------- tanques ----------
    tanques_ctx = []
    for t in alm.tanques:
        v_unitario_obj = (t.volumen or 1.0) / max(t.cantidad, 1)
        ct = storage.dimensioned_tank(v_unitario_obj, t.altura, t.forma, t.ratio)
        dim = (f"Ø {fm.fmt_d(ct.diametro)} m" if ct.forma == "circular"
               else f"lado {fm.fmt_d(ct.lado)} m" if ct.forma == "cuadrado"
               else f"{fm.fmt_d(ct.ancho)} × {fm.fmt_d(ct.largo)} m")
        tanques_ctx.append({
            "nombre": latex_escape(t.nombre), "tipo": t.tipo,
            "tipo_constructivo": t.tipo_constructivo,
            "forma": t.forma, "cantidad": t.cantidad, "dim": dim,
            "altura": fm.fmt_h(ct.altura), "volumen": f"{t.volumen:.0f}",
            "volumen_real": fm.fmt_vol(ct.volumen_real * t.cantidad)})

    transitorio = _transitorio(p, _save)
    localizacion = _localizacion(p, _save)
    detalles = _detalles(p, _save)

    # ---------- red de distribución (opcional) ----------
    red_ctx = None
    if p.red_inp and p.red_en_informe:
        try:
            red = network.parse_inp(p.red_inp)
            demandas = network.assign_demands_by_length(red, flows.qmd_lps)
            for jid, q in demandas.items():
                red.junctions[jid].demand = q
            # El reparto conserva el QMD (Σ q_i = QMD); se reporta el total
            # asignado para que el lector lo verifique contra el QMD del informe.
            q_asignado = sum(demandas.values())
            red_ctx = {
                "n_nodos": len(red.junctions), "n_tuberias": len(red.pipes),
                # La plantilla la agrupa de a 3 por fila con el filtro `batch`
                # de Jinja y la imprime en un `longtable`: una fila por nodo
                # generaba una tabla de cientos de filas en una red real.
                "demandas": [{"nodo": latex_escape(jid), "q": fm.fmt_q(q)}
                             for jid, q in demandas.items()],
                "q_asignado": fm.fmt_q(q_asignado),
                "optimizacion": None,
                "fig": "red.png",
            }
            _save(nm.fig_red(red, dark=False), "red")
            red_ctx.update(_red_hidraulica(p, red, network.write_inp_demands(p.red_inp, demandas),
                                           flows.k2, alm.factores_hora, _save))
            # La optimización de diámetros (heurística iterativa, hasta 30
            # resoluciones densas del sistema) queda deliberadamente fuera del
            # reporte: para una red grande bloqueaba la generación del PDF sin
            # dar señal de progreso (el botón de la página 8 no llegaba a
            # aparecer). Se hace en la página 7 (Red), interactiva, con su
            # propio botón; el reporte solo documenta la red y la asignación
            # de demandas, que es O(nodos+tuberías) y siempre rápida.
        except ValueError:
            red_ctx = None

    # ---------- contexto ----------
    paso = max(1, len(serie_q) // 26)
    ctx = {
        "nombre": latex_escape(p.nombre), "municipio": latex_escape(p.municipio),
        "departamento": latex_escape(p.departamento),
        "corregimiento": latex_escape(p.corregimiento or p.municipio),
        "consultor": latex_escape(p.consultor), "fecha": latex_escape(p.fecha),
        "altitud": p.altitud, "temperatura": p.temperatura,
        "pob_metodo": cfg.metodo, "pob_justificacion": latex_escape(cfg.justificacion),
        "pob_final": f"{pob_final:,.0f}", "horizonte": cfg.horizon_year,
        "pob_tipo": ("cabecera municipal" if cfg.tipo == "municipio"
                     else "corregimiento/vereda"),
        "pob_fuente": (f"{latex_escape(cfg.mpio)} ({latex_escape(cfg.dpto)}), "
                       f"área {latex_escape(cfg.area)}, "
                       f"serie {p.censo[0][0]}–{p.censo[-1][0]}"
                       if cfg.fuente == "dane" else "censo ingresado manualmente"),
        # Distingue la fuente para que la plantilla cite el título oficial del
        # DANE (con su referencia cruzada) solo cuando la serie sea realmente
        # del DANE, y no cuando el censo se haya tecleado a mano.
        "pob_es_dane": cfg.fuente == "dane",
        "year0": cfg.year0,
        "flotante_pct": f"{cfg.flotante_pct * 100:.0f}" if cfg.flotante_pct else "",
        "dneta": f"{p.demanda.dneta:.0f}", "dneta_modo": p.demanda.modo,
        "dneta_justificacion": latex_escape(p.demanda.justificacion),
        "dbruta": f"{flows.dbruta:.1f}", "perdidas": f"{flows.perdidas * 100:.0f}",
        "k1": flows.k1, "k2": flows.k2,
        "qmed": fm.fmt_q(flows.qmed_lps), "qmd": fm.fmt_q(flows.qmd_lps),
        "qmh": fm.fmt_q(flows.qmh_lps),
        "componentes": [(k, fm.fmt_q(v)) for k, v in comp.items()],
        "caudales_anuales": [
            {"ano": t, "pob": f"{pob_t:,.0f}", "qmed": fm.fmt_q(fr.qmed_lps),
             "qmd": fm.fmt_q(fr.qmd_lps), "qmh": fm.fmt_q(fr.qmh_lps)}
            for (t, fr), (_, pob_t) in list(zip(serie_q, serie_total))[::paso]],
        "tanques_balance": tanques_balance,
        "balance_red": balance_red,
        "v_art81": a.v_total_redondeado,
        "v_curva": b.v_total_redondeado if b else "—",
        "v_gobierna": gobierna,
        "v_asignado_total": f"{v_asignado_total:.0f}",
        "v_final": v_final,
        "riesgo_nivel": latex_escape((alm.nivel_riesgo or "personalizado").capitalize()),
        "riesgo_pct": f"{alm.frac_incendio * 100:.0f}",
        # Patrón horario de consumo y ventana de suministro: gobiernan el volumen
        # de regulación por curva integral y, más adelante, la demanda en
        # simulación de periodo extendido. Antes se usaban para calcular pero
        # nunca se documentaban, así que el lector no podía reproducir el
        # dimensionamiento del tanque.
        "patron_horas": patron_horas,
        "patron_pico": patron_pico,
        "patron_valle": patron_valle,
        "patron_suma": patron_suma,
        "tanques": tanques_ctx,
        "sistemas": sistemas_ctx,
        "figuras": figuras,
        "logo_cliente": logo_cliente,
        "logo_consultor": logo_consultor,
        "logo_acucalc": LOGO_ACUCALC.name,
        "referencias": biblio.bibitems(referencias(p)),
        # Autoría de la aplicación (no del proyecto: eso es `consultor`).
        "autor": AUTOR_APP,
        "red": red_ctx,
        "transitorio": transitorio,
        "localizacion": localizacion,
        "detalles": detalles,
        "estudios": estudios_ctx,
        "estudios_faltantes": estudios_faltantes,
        "anexos_curvas": anexos_curvas,
    }
    return ctx, figuras

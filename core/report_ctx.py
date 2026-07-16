"""Construye el contexto del reporte recalculando TODO desde el proyecto.

Mismo pipeline que usa la página 7 de la app: población → caudales →
almacenamiento → sistemas de bombeo → figuras. Reproducible desde el JSON
del proyecto, sin Streamlit ni session_state."""
import base64
import tempfile
from pathlib import Path

from core import curves as cvs, demand, network, population as pop, pumping as pu
from core import formato as fm, report_figs as rf, storage
from core.project import Project

REFERENCIAS = [
    {"cita": "Ministerio de Vivienda, Ciudad y Territorio. Resolución 0330 de 2017, "
             "\"Por la cual se adopta el Reglamento Técnico para el Sector de Agua "
             "Potable y Saneamiento Básico — RAS\"."},
    {"cita": "Ministerio de Vivienda, Ciudad y Territorio. Resolución 0844 de 2018, "
             "por la cual se establecen esquemas diferenciales de dotación para "
             "zonas rurales."},
    {"cita": "Presidencia de la República. Decreto 1575 de 2007, por el cual se "
             "establece el Sistema para la Protección y Control de la Calidad del "
             "Agua para Consumo Humano."},
    {"cita": "Asociación Colombiana de Ingeniería Sísmica. Reglamento Colombiano de "
             "Construcción Sismo Resistente NSR-10, Título J — Requisitos de "
             "Protección contra Incendios en Edificaciones."},
    {"cita": "Corte Constitucional de Colombia. Sentencia T-740 de 2011 (mínimo "
             "vital de agua potable)."},
    {"cita": "Comisión de Regulación de Agua Potable y Saneamiento Básico (CRA). "
             "Resolución CRA 750 de 2016, metodología tarifaria — consumo básico."},
]

_LATEX_MAP = [
    ("\\", r"\textbackslash{}"),
    ("&", r"\&"), ("%", r"\%"), ("$", r"\$"), ("#", r"\#"),
    ("_", r"\_"), ("{", r"\{"), ("}", r"\}"),
    ("~", r"\textasciitilde{}"), ("^", r"\textasciicircum{}"),
    ("→", r"$\to$"), ("×", r"$\times$"), ("Ø", r"\O{}"),
    ("—", "---"), ("–", "--"),
    ("“", "``"), ("”", "''"), ("‘", "`"), ("’", "'"),
]


_LATEX_ESCAPE_TABLE = dict(_LATEX_MAP)


def latex_escape(s: str) -> str:
    """Escapa un string de usuario para LaTeX y normaliza unicode frágil
    (flechas, multiplicación, Ø, guiones y comillas tipográficas) a su forma
    ASCII/LaTeX robusta — necesario porque el `main.tex` generado puede ser
    reabierto y re-guardado externamente en un encoding no-UTF8 (bug
    reportado: tildes y unicode se corrompen a U+FFFD tras ese re-guardado;
    el ASCII sobrevive).

    Nota: se traduce carácter por carácter (no con `.replace()` encadenado)
    porque varios reemplazos de `_LATEX_MAP` insertan `{`/`}` literales
    (p.ej. `\\` -> `\textbackslash{}`); un `.replace()` en cadena volvería a
    escapar esas llaves recién insertadas y las duplicaría."""
    if not s:
        return s
    return "".join(_LATEX_ESCAPE_TABLE.get(ch, ch) for ch in s)


def build(p: Project) -> tuple[dict, dict]:
    """Devuelve (ctx para la plantilla LaTeX, dict figuras nombre→ruta png).

    Requiere: nombre, censo (≥2), población base y método seleccionados."""
    cfg = p.poblacion
    if not (p.nombre and len(p.censo) >= 2 and cfg.p0 > 0 and cfg.metodo):
        raise ValueError("Faltan datos mínimos: nombre, censo, población base y método")

    # ---------- población y caudales ----------
    rates = pop.growth_rates(p.censo)
    proj = pop.project(cfg.p0, int(cfg.year0), int(cfg.horizon_year), rates,
                       cfg.tasa_res0844)
    serie_total = [(t, v * (1 + cfg.flotante_pct)) for t, v in proj.series[cfg.metodo]]
    pob_final = serie_total[-1][1]

    flows = demand.flows(pob_final, p.demanda.dneta, p.demanda.perdidas,
                         p.demanda.k1, p.demanda.k2)
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
    b = None
    if alm.factores_hora and alm.suministro_hora:
        try:
            b = storage.volume_curva_integral(qmd_m3d, alm.factores_hora,
                                              alm.suministro_hora, alm.frac_incendio,
                                              alm.dias_reserva)
        except ValueError:
            b = None
    v_final = storage.final_volume(a, b) if b else a.v_total_redondeado
    gobierna = ("Art. 81 (QMD/3)" if not b or a.v_total_redondeado >= b.v_total_redondeado
                else "Curva integral")

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

    # ---------- figuras ----------
    figdir = Path(tempfile.mkdtemp())
    figuras: dict[str, str] = {}

    def _save(fig, name):
        fp = figdir / f"{name}.png"
        fig.savefig(fp, dpi=150, bbox_inches="tight")
        figuras[name] = str(fp)

    _save(rf.fig_poblacion(proj, cfg.metodo, cfg.flotante_pct), "poblacion")
    _save(rf.fig_metodos(proj.deviations, pop.suggest_method(proj)), "metodos")
    _save(rf.fig_caudales([(t, fr.qmed_lps, fr.qmd_lps, fr.qmh_lps)
                           for t, fr in serie_q]), "caudales")
    if alm.factores_hora and alm.suministro_hora:
        _save(rf.fig_balance_train([("Comunidad", alm.suministro_hora, alm.factores_hora)]),
              "balance")
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
    logo_consultor = _save_b64_image(p.logo_consultor_b64, "logo_consultor")

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

    # ---------- red de distribución (opcional) ----------
    red_ctx = None
    if p.red_inp:
        try:
            red = network.parse_inp(p.red_inp)
            demandas = network.assign_demands_by_length(red, flows.qmd_lps)
            for jid, q in demandas.items():
                red.junctions[jid].demand = q
            red_ctx = {
                "n_nodos": len(red.junctions), "n_tuberias": len(red.pipes),
                "demandas": [{"nodo": latex_escape(jid), "q": fm.fmt_q(q)}
                            for jid, q in demandas.items()],
                "optimizacion": None,
            }
            if p.red_material and p.red_serie:
                opt = network.optimize_diameters(
                    red, p.red_material, p.red_serie, p.red_vmax, p.red_pmin, p.red_pmax)
                red_ctx["optimizacion"] = {
                    "material": latex_escape(p.red_material),
                    "serie": latex_escape(p.red_serie),
                    "avisos": [latex_escape(a) for a in opt.avisos],
                    "tuberias": [{"id": latex_escape(pid), "dn0": f"{opt.dn_original[pid]:.0f}",
                                 "dn1": f"{opt.dn_optimizado[pid]:.0f}"}
                                for pid in opt.dn_original]}
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
        "pob_fuente": (f"proyecciones oficiales DANE — {cfg.mpio} ({cfg.dpto}), "
                       f"área {cfg.area}, serie {p.censo[0][0]}–{p.censo[-1][0]}"
                       if cfg.fuente == "dane" else "censo ingresado manualmente"),
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
        "v_art81": a.v_total_redondeado,
        "v_curva": b.v_total_redondeado if b else "—",
        "v_gobierna": gobierna,
        "v_asignado_total": f"{v_asignado_total:.0f}",
        "v_final": v_final,
        "tanques": tanques_ctx,
        "sistemas": sistemas_ctx,
        "figuras": figuras,
        "logo_cliente": logo_cliente,
        "logo_consultor": logo_consultor,
        "referencias": REFERENCIAS,
        "red": red_ctx,
        "anexos_curvas": anexos_curvas,
    }
    return ctx, figuras

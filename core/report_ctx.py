"""Construye el contexto del reporte recalculando TODO desde el proyecto.

Mismo pipeline que usa la página 7 de la app: población → caudales →
almacenamiento → sistemas de bombeo → figuras. Reproducible desde el JSON
del proyecto, sin Streamlit ni session_state."""
import base64
import tempfile
from pathlib import Path

from core import curves as cvs, demand, population as pop, pumping as pu
from core import report_figs as rf, storage
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
    alm = p.almacenamiento
    tren, a, b = None, None, None
    if alm.usar_cadena and alm.factores_hora and alm.tanques:
        try:
            tren = storage.tank_train(
                qmd_m3d, [(t.nombre, t.entrada_flags()) for t in alm.tanques],
                alm.factores_hora, alm.frac_incendio, alm.dias_reserva)
            for t, bal in zip(alm.tanques, tren):
                t.volumen = float(bal.v_total_redondeado)
        except ValueError:
            tren = None
    if tren:
        v_final = sum(bal.v_total_redondeado for bal in tren)
    elif alm.factores_hora and alm.suministro_hora:
        a = storage.volume_art81(qmd_m3d, alm.frac_regulacion, alm.frac_incendio,
                                 alm.dias_reserva)
        b = storage.volume_curva_integral(qmd_m3d, alm.factores_hora,
                                          alm.suministro_hora, alm.frac_incendio,
                                          alm.dias_reserva)
        v_final = storage.final_volume(a, b)
    else:
        a = storage.volume_art81(qmd_m3d, alm.frac_regulacion, alm.frac_incendio,
                                 alm.dias_reserva)
        v_final = a.v_total_redondeado

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
    if tren:
        pares = []
        for i, t in enumerate(alm.tanques):
            salida = (alm.tanques[i + 1].entrada_flags() if i + 1 < len(alm.tanques)
                      else alm.factores_hora)
            pares.append((t.nombre, t.entrada_flags(), salida))
        _save(rf.fig_balance_train(pares), "balance")
    sistemas_bomba_ctx = ([{"tipo_bomba": s.tipo_bomba} for s in p.bombeos]
                         or [{"tipo_bomba": "superficie"}])
    _save(rf.fig_esquema(sistemas_bomba_ctx, alm.tanques if tren else []), "esquema")

    # ---------- logos de portada ----------
    def _save_logo(b64: str, name: str) -> str | None:
        if not b64:
            return None
        raw = base64.b64decode(b64)
        ext = "jpg" if raw[:3] == b"\xff\xd8\xff" else "png"
        fp = figdir / f"{name}.{ext}"
        fp.write_bytes(raw)
        return fp.name

    logo_cliente = _save_logo(p.logo_cliente_b64, "logo_cliente")
    logo_consultor = _save_logo(p.logo_consultor_b64, "logo_consultor")

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
            fit = cvs.fit_curve(bb.puntos_qh, 2)
            op = cvs.operating_point(fit, sys_lps)
            e_fit = cvs.fit_curve(bb.puntos_qe, 2) if len(bb.puntos_qe) >= 3 else None
            bep = cvs.best_efficiency_point(bb.puntos_qe, 2) if e_fit else None
            eta = e_fit(op[0]) if (op and e_fit) else float("nan")
            pot = (998.29 * 9.81 * op[0] / 1000 * op[1] / eta / 745.7
                   if op and eta and eta > 0 else float("nan"))
            bombas_fig.append({"nombre": bb.nombre, "fit": fit, "op": op,
                               "e_fit": e_fit})
            A, B, C = fit.coeffs
            bombas_tab.append({
                "nombre": latex_escape(bb.nombre),
                "h_eq": f"$H = {A:+.4f}Q^2 {B:+.4f}Q {C:+.3f}$",
                "e_eq": (f"$\\eta = {e_fit.coeffs[0]:+.6f}Q^2 "
                         f"{e_fit.coeffs[1]:+.5f}Q {e_fit.coeffs[2]:+.4f}$"
                         if e_fit else "—"),
                "q_op": f"{op[0]:.2f}" if op else "—",
                "h_op": f"{op[1]:.2f}" if op else "—",
                "eta_op": f"{eta:.3f}" if eta == eta else "—",
                "bep_q": f"{bep.q:.2f}" if bep else "—",
                "desv_bep": f"{(op[0] - bep.q) / bep.q * 100:.1f}" if (op and bep) else "—",
                "p_hp": f"{pot:.2f}" if pot == pot else "—"})
        fig_name = f"sistema_{i + 1}"
        _save(rf.fig_sistema(sys_lps, bombas_fig, qb_lps, r.hd, s.nombre), fig_name)
        sistemas_ctx.append({
            "nombre": latex_escape(s.nombre), "tipo_bomba": s.tipo_bomba,
            "horas": f"{s.horas:.0f}",
            "qb": f"{qb_lps:.2f}", "hd": f"{r.hd:.2f}", "eficiencia": s.eficiencia,
            "potencia_kw": f"{r.potencia_kw:.2f}", "potencia_hp": f"{r.potencia_hp:.2f}",
            "tramos": [{"nombre": latex_escape(t.segment.nombre), "L": f"{t.segment.L:.1f}",
                        "D_mm": f"{t.segment.D * 1000:.1f}",
                        "material": t.segment.material,
                        "V": f"{t.V:.2f}", "hf": f"{t.hf:.3f}", "hl": f"{t.hl:.3f}"}
                       for t in r.tramos],
            "bombas": bombas_tab,
            "bomba_seleccionada": latex_escape(s.bomba_seleccionada or "—"),
            "fig": f"{fig_name}.png"})

    # ---------- tanques ----------
    tanques_ctx = []
    for t in alm.tanques:
        v_unitario_obj = (t.volumen or 1.0) / max(t.cantidad, 1)
        ct = storage.dimensioned_tank(v_unitario_obj, t.altura, t.forma, t.ratio)
        dim = (f"Ø {ct.diametro:.1f} m" if ct.forma == "circular"
               else f"lado {ct.lado:.1f} m" if ct.forma == "cuadrado"
               else f"{ct.ancho:.1f} × {ct.largo:.1f} m")
        tanques_ctx.append({
            "nombre": latex_escape(t.nombre), "tipo": t.tipo,
            "tipo_constructivo": t.tipo_constructivo,
            "forma": t.forma, "cantidad": t.cantidad, "dim": dim,
            "altura": f"{ct.altura:.1f}", "volumen": f"{t.volumen:.0f}",
            "volumen_real": f"{ct.volumen_real * t.cantidad:.1f}"})

    # ---------- contexto ----------
    paso = max(1, len(serie_q) // 26)
    ctx = {
        "nombre": latex_escape(p.nombre), "municipio": latex_escape(p.municipio),
        "departamento": latex_escape(p.departamento),
        "corregimiento": latex_escape(p.corregimiento or p.municipio),
        "consultor": latex_escape(p.consultor), "fecha": p.fecha,
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
        "qmed": f"{flows.qmed_lps:.3f}", "qmd": f"{flows.qmd_lps:.3f}",
        "qmh": f"{flows.qmh_lps:.3f}",
        "componentes": [(k, f"{v:.3f}") for k, v in comp.items()],
        "caudales_anuales": [
            {"ano": t, "pob": f"{pob_t:,.0f}", "qmed": f"{fr.qmed_lps:.3f}",
             "qmd": f"{fr.qmd_lps:.3f}", "qmh": f"{fr.qmh_lps:.3f}"}
            for (t, fr), (_, pob_t) in list(zip(serie_q, serie_total))[::paso]],
        "usar_cadena": bool(tren),
        "tanques_balance": ([{"nombre": bal.nombre,
                              "horas": f"{bal.horas_entrada:.0f}",
                              "q_entrada": f"{bal.q_entrada_lps:.2f}",
                              "horas_salida": (f"{bal.horas_salida:.0f}"
                                              if bal.horas_salida is not None else "—"),
                              "q_salida": (f"{bal.q_salida_lps:.2f}"
                                          if bal.q_salida_lps is not None
                                          else "red (variable)"),
                              "frac": f"{bal.frac_regulacion:.4f}",
                              "v": bal.v_total_redondeado} for bal in tren]
                            if tren else []),
        "v_art81": "—" if tren else (a.v_total_redondeado if a else "—"),
        "v_curva": "—" if tren else (b.v_total_redondeado if b else "—"),
        "v_final": v_final,
        "tanques": tanques_ctx,
        "sistemas": sistemas_ctx,
        "figuras": figuras,
        "logo_cliente": logo_cliente,
        "logo_consultor": logo_consultor,
        "referencias": REFERENCIAS,
    }
    return ctx, figuras

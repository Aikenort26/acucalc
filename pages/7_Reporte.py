import tempfile
from pathlib import Path

import streamlit as st
from core import curves as cvs, demand, population as pop, pumping as pu
from core import report, report_figs as rf, storage
from pages_common import get_project

st.header("7 · Reporte — memoria de cálculo LaTeX")
p = get_project()
cfg = p.poblacion

if not (p.nombre and len(p.censo) >= 2 and cfg.p0 > 0 and cfg.metodo):
    st.info("Completa al menos Proyecto y Población (censo, población base y método) "
            "antes de generar el reporte.")
    st.stop()

# ---------- recomputo completo desde el proyecto (reproducible desde el JSON) ----------
rates = pop.growth_rates(p.censo)
proj = pop.project(cfg.p0, int(cfg.year0), int(cfg.horizon_year), rates, cfg.tasa_res0844)
serie_total = [(t, v * (1 + cfg.flotante_pct)) for t, v in proj.series[cfg.metodo]]
pob_final = serie_total[-1][1]

flows = demand.flows(pob_final, p.demanda.dneta, p.demanda.perdidas,
                     p.demanda.k1, p.demanda.k2)
serie_q = demand.flows_series(serie_total, p.demanda.dneta, p.demanda.perdidas,
                              p.demanda.k1, p.demanda.k2)
comp = demand.design_flows_by_component(flows)
qmd_m3d = flows.qmd_lps * 86.4

alm = p.almacenamiento
chain = None
if alm.usar_cadena and alm.factores_hora and alm.suministro_hora:
    try:
        chain = storage.tank_chain(qmd_m3d, alm.factores_hora,
                                   alm.ventana_captacion or [1] * 24,
                                   alm.suministro_hora, alm.frac_incendio,
                                   alm.dias_reserva)
    except ValueError:
        chain = None
if chain:
    v_final = chain.total_redondeado
elif alm.factores_hora and alm.suministro_hora:
    a = storage.volume_art81(qmd_m3d, alm.frac_regulacion, alm.frac_incendio, alm.dias_reserva)
    b = storage.volume_curva_integral(qmd_m3d, alm.factores_hora, alm.suministro_hora,
                                      alm.frac_incendio, alm.dias_reserva)
    v_final = storage.final_volume(a, b)
else:
    a = storage.volume_art81(qmd_m3d, alm.frac_regulacion, alm.frac_incendio, alm.dias_reserva)
    b = None
    v_final = a.v_total_redondeado

# ---------- figuras ----------
figdir = Path(tempfile.mkdtemp())
figuras = {}


def _save(fig, name):
    fp = figdir / f"{name}.png"
    fig.savefig(fp, dpi=150, bbox_inches="tight")
    figuras[name] = str(fp)


_save(rf.fig_poblacion(proj, cfg.metodo, cfg.flotante_pct), "poblacion")
_save(rf.fig_metodos(proj.deviations, pop.suggest_method(proj)), "metodos")
_save(rf.fig_caudales([(t, fr.qmed_lps, fr.qmd_lps, fr.qmh_lps) for t, fr in serie_q]),
      "caudales")
if chain:
    _save(rf.fig_balance(alm.ventana_captacion or [1] * 24, alm.suministro_hora,
                         alm.factores_hora), "balance")
tipo_bomba_ppal = p.bombeos[0].tipo_bomba if p.bombeos else "superficie"
_save(rf.fig_esquema(tipo_bomba_ppal, cadena=bool(chain)), "esquema")

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
        accesorios=[pu.Accessory(a.tipo, a.cantidad, a.tramo) for a in s.accesorios],
        he=he, temperatura=p.temperatura, eficiencia=s.eficiencia)
    r = pu.solve(sistema, qb_lps / 1000)
    q_max_lps = max(qb_lps * 1.5, max((b.puntos_qh[-1][0] for b in s.bombas
                                       if len(b.puntos_qh) >= 3), default=0.0))
    sys_lps = [(q * 1000, h) for q, h in
               pu.system_curve(sistema, max(q_max_lps / 1000, 1e-4), n=30)]
    bombas_fig, bombas_tab = [], []
    for b in s.bombas:
        if len(b.puntos_qh) < 3:
            continue
        fit = cvs.fit_curve(b.puntos_qh, 2)
        op = cvs.operating_point(fit, sys_lps)
        e_fit = cvs.fit_curve(b.puntos_qe, 2) if len(b.puntos_qe) >= 3 else None
        bep = cvs.best_efficiency_point(b.puntos_qe, 2) if e_fit else None
        eta = e_fit(op[0]) if (op and e_fit) else float("nan")
        pot = (998.29 * 9.81 * op[0] / 1000 * op[1] / eta / 745.7
               if op and eta and eta > 0 else float("nan"))
        bombas_fig.append({"nombre": b.nombre, "fit": fit, "op": op})
        bombas_tab.append({
            "nombre": b.nombre,
            "q_op": f"{op[0]:.2f}" if op else "—",
            "h_op": f"{op[1]:.2f}" if op else "—",
            "eta_op": f"{eta:.3f}" if eta == eta else "—",
            "bep_q": f"{bep.q:.2f}" if bep else "—",
            "desv_bep": f"{(op[0] - bep.q) / bep.q * 100:.1f}" if (op and bep) else "—",
            "p_hp": f"{pot:.2f}" if pot == pot else "—"})
    fig_name = f"sistema_{i + 1}"
    _save(rf.fig_sistema(sys_lps, bombas_fig, qb_lps, r.hd, s.nombre), fig_name)
    sistemas_ctx.append({
        "nombre": s.nombre, "tipo_bomba": s.tipo_bomba, "horas": f"{s.horas:.0f}",
        "qb": f"{qb_lps:.2f}", "hd": f"{r.hd:.2f}", "eficiencia": s.eficiencia,
        "potencia_kw": f"{r.potencia_kw:.2f}", "potencia_hp": f"{r.potencia_hp:.2f}",
        "tramos": [{"nombre": t.segment.nombre, "L": f"{t.segment.L:.1f}",
                    "D_mm": f"{t.segment.D * 1000:.1f}", "material": t.segment.material,
                    "V": f"{t.V:.2f}", "hf": f"{t.hf:.3f}", "hl": f"{t.hl:.3f}"}
                   for t in r.tramos],
        "bombas": bombas_tab, "bomba_seleccionada": s.bomba_seleccionada or "—",
        "fig": f"{fig_name}.png"})

# ---------- tanques ----------
tanques_ctx = []
for t in alm.tanques:
    d = storage.tank_dimensions(t.volumen, t.altura, t.ratio)
    dim = (f"Ø {d.diametro:.2f} m" if t.forma == "circular"
           else f"lado {d.lado:.2f} m" if t.forma == "cuadrado"
           else f"{d.ancho:.2f} × {d.largo:.2f} m")
    tanques_ctx.append({"nombre": t.nombre, "tipo": t.tipo, "forma": t.forma,
                        "dim": dim, "volumen": f"{t.volumen:.0f}",
                        "altura": f"{t.altura:.2f}"})

# ---------- contexto ----------
paso = max(1, len(serie_q) // 26)
ctx = {
    "nombre": p.nombre, "municipio": p.municipio, "departamento": p.departamento,
    "corregimiento": p.corregimiento or p.municipio, "consultor": p.consultor,
    "fecha": p.fecha, "altitud": p.altitud, "temperatura": p.temperatura,
    "pob_metodo": cfg.metodo, "pob_justificacion": cfg.justificacion,
    "pob_final": f"{pob_final:,.0f}", "horizonte": cfg.horizon_year,
    "pob_tipo": ("cabecera municipal" if cfg.tipo == "municipio"
                 else "corregimiento/vereda"),
    "pob_fuente": (f"proyecciones oficiales DANE — {cfg.mpio} ({cfg.dpto}), "
                   f"área {cfg.area}, serie {p.censo[0][0]}–{p.censo[-1][0]}"
                   if cfg.fuente == "dane" else "censo ingresado manualmente"),
    "year0": cfg.year0,
    "flotante_pct": f"{cfg.flotante_pct * 100:.0f}" if cfg.flotante_pct else "",
    "dneta": f"{p.demanda.dneta:.0f}", "dneta_modo": p.demanda.modo,
    "dneta_justificacion": p.demanda.justificacion,
    "dbruta": f"{flows.dbruta:.1f}", "perdidas": f"{flows.perdidas * 100:.0f}",
    "k1": flows.k1, "k2": flows.k2,
    "qmed": f"{flows.qmed_lps:.3f}", "qmd": f"{flows.qmd_lps:.3f}",
    "qmh": f"{flows.qmh_lps:.3f}",
    "componentes": [(k, f"{v:.3f}") for k, v in comp.items()],
    "caudales_anuales": [
        {"ano": t, "pob": f"{pob_t:,.0f}", "qmed": f"{fr.qmed_lps:.3f}",
         "qmd": f"{fr.qmd_lps:.3f}", "qmh": f"{fr.qmh_lps:.3f}"}
        for (t, fr), (_, pob_t) in list(zip(serie_q, serie_total))[::paso]],
    "usar_cadena": bool(chain),
    "v_bajo": chain.bajo.v_total_redondeado if chain else "—",
    "v_elevado": chain.elevado.v_total_redondeado if chain else "—",
    "v_art81": "—" if chain else a.v_total_redondeado,
    "v_curva": "—" if chain else (b.v_total_redondeado if b else "—"),
    "v_final": v_final,
    "tanques": tanques_ctx,
    "sistemas": sistemas_ctx,
    "figuras": figuras,
}

st.caption(f"El reporte se genera recalculando todo desde el proyecto: población "
           f"{pob_final:,.0f} hab · QMD {flows.qmd_lps:.3f} L/s · almacenamiento "
           f"{v_final} m³ · {len(sistemas_ctx)} sistema(s) de bombeo · "
           f"{len(figuras)} figuras.")

if st.button("📄 Generar memoria LaTeX"):
    out = report.render(ctx, Path(tempfile.mkdtemp()) / "memoria")
    with st.spinner("Compilando PDF (si hay LaTeX instalado)…"):
        pdf = report.compile_pdf(out)
    z = report.make_zip(out)
    st.success("Proyecto LaTeX generado.")
    st.download_button("⬇️ Descargar proyecto LaTeX (.zip para Overleaf)",
                       data=z.read_bytes(), file_name=f"memoria_{p.nombre}.zip")
    if pdf:
        st.download_button("⬇️ Descargar PDF compilado", data=pdf.read_bytes(),
                           file_name=f"memoria_{p.nombre}.pdf")
    else:
        st.info("No se detectó LaTeX (latexmk/pdflatex) en el sistema — "
                "usa el ZIP en Overleaf.")

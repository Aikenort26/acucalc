import tempfile
from pathlib import Path
import streamlit as st
from core import report
from pages_common import get_project

st.header("7 · Reporte — memoria de cálculo LaTeX")
p = get_project()
flows = st.session_state.get("flows")
solve = st.session_state.get("pump_solve")
pob_final = st.session_state.get("pob_final", 0.0)
if not (p.nombre and flows and pob_final):
    st.info("Completa al menos Proyecto, Población y Caudales antes de generar el reporte.")
    st.stop()

# figuras desde session_state (matplotlib) → png temporales
figdir = Path(tempfile.mkdtemp())
figuras = {}
if "fig_curvas" in st.session_state:
    fp = figdir / "curvas.png"
    st.session_state["fig_curvas"].savefig(fp, dpi=150, bbox_inches="tight")
    figuras["curvas"] = str(fp)

from core import demand
comp = demand.design_flows_by_component(flows)
rows_bombas = st.session_state.get("tabla_bombas", [])
ctx = {
    "nombre": p.nombre, "municipio": p.municipio, "departamento": p.departamento,
    "corregimiento": p.corregimiento or p.municipio, "consultor": p.consultor,
    "fecha": p.fecha, "altitud": p.altitud, "temperatura": p.temperatura,
    "pob_metodo": p.poblacion.metodo, "pob_justificacion": p.poblacion.justificacion,
    "pob_final": f"{pob_final:,.0f}", "horizonte": p.poblacion.horizon_year,
    "censo": p.censo,
    "pob_tipo": ("cabecera municipal" if p.poblacion.tipo == "municipio"
                 else "corregimiento/vereda"),
    "pob_fuente": (f"proyecciones oficiales DANE — {p.poblacion.mpio} "
                   f"({p.poblacion.dpto}), área {p.poblacion.area}, "
                   f"serie {p.censo[0][0]}–{p.censo[-1][0]}"
                   if p.poblacion.fuente == "dane" and p.censo
                   else "censo ingresado manualmente"),
    "year0": p.poblacion.year0,
    "dneta": f"{p.demanda.dneta:.0f}", "dneta_modo": p.demanda.modo,
    "dneta_justificacion": p.demanda.justificacion,
    "dbruta": f"{flows.dbruta:.1f}", "perdidas": f"{flows.perdidas*100:.0f}",
    "k1": flows.k1, "k2": flows.k2,
    "qmed": f"{flows.qmed_lps:.3f}", "qmd": f"{flows.qmd_lps:.3f}",
    "qmh": f"{flows.qmh_lps:.3f}",
    "componentes": [(k, f"{v:.3f}") for k, v in comp.items()],
    "v_art81": st.session_state.get("v_art81", "—"),
    "v_curva": st.session_state.get("v_curva", "—"),
    "v_final": st.session_state.get("v_almacenamiento", "—"),
    "qb": f"{st.session_state.get('qb_lps', 0):.3f}",
    "hd": f"{solve.hd:.2f}" if solve else "—",
    "potencia_kw": f"{solve.potencia_kw:.2f}" if solve else "—",
    "potencia_hp": f"{solve.potencia_hp:.2f}" if solve else "—",
    "eficiencia": p.bombeo.eficiencia, "horas_bombeo": f"{p.bombeo.horas:.0f}",
    "tramos": [{"nombre": t.segment.nombre, "L": f"{t.segment.L:.1f}",
                "D_mm": f"{t.segment.D*1000:.1f}", "material": t.segment.material,
                "V": f"{t.V:.2f}", "hf": f"{t.hf:.3f}", "hl": f"{t.hl:.3f}"}
               for t in (solve.tramos if solve else [])],
    "bombas": rows_bombas, "bomba_seleccionada": p.bomba_seleccionada or "—",
    "figuras": figuras,
}

if st.button("📄 Generar memoria LaTeX"):
    out = report.render(ctx, Path(tempfile.mkdtemp()) / "memoria")
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

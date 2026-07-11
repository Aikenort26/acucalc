import shutil
import tempfile
from pathlib import Path

import streamlit as st
from core import report, report_ctx
from pages_common import page_setup

p = page_setup()
st.header("7 · Reporte — memoria de cálculo LaTeX")

try:
    ctx, figuras = report_ctx.build(p)
except ValueError:
    st.info("Completa al menos Proyecto y Población (censo, población base y método) "
            "antes de generar el reporte.")
    st.stop()

st.caption(f"El reporte se genera recalculando todo desde el proyecto: población "
           f"{ctx['pob_final']} hab · QMD {ctx['qmd']} L/s · almacenamiento "
           f"{ctx['v_final']} m³ · {len(ctx['sistemas'])} sistema(s) de bombeo · "
           f"{len(figuras)} figuras.")

hay_latex = bool(shutil.which("latexmk") or shutil.which("pdflatex"))
if not hay_latex:
    st.warning("No se detectó LaTeX (latexmk/pdflatex) en el PATH. Instala "
               "[MiKTeX](https://miktex.org/download) para compilar el PDF "
               "directamente desde la app; mientras tanto se entrega el proyecto "
               ".zip para compilar en Overleaf.")

if st.button("📄 Generar memoria" + (" (PDF)" if hay_latex else " (ZIP)"),
             type="primary"):
    out = report.render(ctx, Path(tempfile.mkdtemp()) / "memoria")
    pdf = None
    if hay_latex:
        with st.spinner("Compilando PDF con LaTeX…"):
            pdf = report.compile_pdf(out)
    if pdf:
        st.success("Memoria compilada.")
        st.download_button("⬇️ Descargar memoria (PDF)", data=pdf.read_bytes(),
                           file_name=f"memoria_{p.nombre}.pdf", type="primary")
    elif hay_latex:
        st.error("La compilación LaTeX falló — descarga el ZIP y revisa el log "
                 "en Overleaf.")
    z = report.make_zip(out)
    st.download_button("⬇️ Fuente LaTeX (.zip, editable/Overleaf)",
                       data=z.read_bytes(), file_name=f"memoria_{p.nombre}.zip")

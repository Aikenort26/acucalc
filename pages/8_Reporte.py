import shutil
import tempfile
from pathlib import Path

# noqa: shutil se usa para which y copy

import streamlit as st
from core import report, report_ctx
from pages_common import page_setup

p = page_setup()
st.header("8 · Reporte — memoria de cálculo LaTeX")

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

OUT_DIR = Path(__file__).resolve().parent.parent / "output"
slug = p.nombre.replace(" ", "_")
pdf_final = OUT_DIR / f"memoria_{slug}.pdf"
zip_final = OUT_DIR / f"memoria_{slug}.zip"

if st.button("📄 Generar memoria" + (" (PDF)" if hay_latex else " (ZIP)"),
             type="primary"):
    OUT_DIR.mkdir(exist_ok=True)
    out = report.render(ctx, Path(tempfile.mkdtemp()) / "memoria")
    log_tail = ""
    if hay_latex:
        with st.spinner("Compilando PDF con LaTeX (la primera vez puede tardar "
                        "varios minutos instalando paquetes)…"):
            pdf, log_tail = report.compile_pdf(out)
    else:
        pdf = None
    z = report.make_zip(out)
    shutil.copy(z, zip_final)
    if pdf:
        shutil.copy(pdf, pdf_final)
        st.session_state["reporte_ok"] = True
    else:
        pdf_final.unlink(missing_ok=True)
        st.session_state["reporte_ok"] = False
        if hay_latex:
            st.error("La compilación LaTeX falló. Cola del log:")
            st.code(log_tail or "(sin log)", language="text")

# resultados persistentes (sobreviven reruns: se leen del disco)
if pdf_final.exists():
    st.success(f"Memoria compilada: `{pdf_final}`")
    st.download_button("⬇️ Descargar memoria (PDF)", data=pdf_final.read_bytes(),
                       file_name=pdf_final.name, type="primary")
if zip_final.exists():
    st.download_button("⬇️ Fuente LaTeX (.zip, editable/Overleaf)",
                       data=zip_final.read_bytes(), file_name=zip_final.name)

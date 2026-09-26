import shutil
import tempfile
from pathlib import Path

import matplotlib.pyplot as plt
import streamlit as st
import pandas as pd

from core import biblio, detalles as dt, project as pj, report, report_ctx
from pages_common import num_input, page_setup, txt_state

p = page_setup()
st.header("8 · Reporte — memoria de cálculo LaTeX")

# ---------- referencias bibliográficas ----------
with st.expander("📚 Referencias bibliográficas", expanded=False):
    st.caption("La memoria cita la biblioteca base y tus referencias propias; la lista "
               "final del PDF incluye solo las que el texto cita, numeradas por orden "
               "de aparición. En los textos de estudios previos cita con `[@clave]`.")
    base = biblio.biblioteca_base()
    st.dataframe(pd.DataFrame([{"Clave": r.key, "Autor": r.autor, "Año": r.anio,
                                "Título": r.titulo} for r in base]),
                 hide_index=True, width="stretch", height=220)
    up_bib = st.file_uploader("Cargar archivo .bib", type=["bib", "txt"], key="w_up_bib")
    k_bib = txt_state("txt_bibtex", p.bibtex_usuario)
    if up_bib is not None and st.session_state.get("bib_upload_id") != up_bib.file_id:
        st.session_state["bib_upload_id"] = up_bib.file_id
        st.session_state[k_bib] = up_bib.getvalue().decode("utf-8", errors="replace")
    p.bibtex_usuario = st.text_area(
        "Referencias propias (BibTeX)", key=k_bib, height=180,
        placeholder="@book{perez2021,\n  author = {Pérez, Juan},\n  title = {Estudio de "
                    "suelos del municipio},\n  publisher = {Alcaldía}, year = {2021}}",
        help="Una clave igual a una de la biblioteca base la reemplaza.")
    if p.bibtex_usuario.strip():
        propias, errores = biblio.parse_bibtex(p.bibtex_usuario)
        for e in errores:
            st.warning(e)
        if propias:
            st.success(f"{len(propias)} referencia(s) propia(s): "
                       + ", ".join(f"`{r.key}`" for r in propias))

with st.expander("📐 Detalles típicos: zanja", expanded=False):
    z = p.zanja
    st.caption("Todas las dimensiones las define el proyectista según la norma o la "
               "especificación del proyecto; la app no asume valores. Sin datos completos "
               "la zanja no entra a la memoria. Los esquemas de las estaciones de bombeo y "
               "de los tanques salen de las páginas Bombeo y Almacenamiento.")
    z1, z2, z3, z4 = st.columns(4)
    z.d_ext_mm = num_input("Ø exterior de la tubería [mm]", "zj_d", z.d_ext_mm, decimals=1,
                           container=z1, min_value=0.0)
    z.ancho_fondo = num_input("Ancho de fondo [m]", "zj_b", z.ancho_fondo, decimals=2,
                              container=z2, min_value=0.0)
    z.profundidad = num_input("Profundidad, rasante a fondo [m]", "zj_h", z.profundidad,
                              decimals=2, container=z3, min_value=0.0)
    z.talud = num_input("Talud H:V (0 = vertical)", "zj_t", z.talud, decimals=2,
                        container=z4, min_value=0.0)
    z5, z6, z7, z8 = st.columns(4)
    z.cama = num_input("Cama bajo la tubería [m]", "zj_cama", z.cama, decimals=2,
                       container=z5, min_value=0.0)
    z.atraque = num_input("Relleno seleccionado sobre la clave [m]", "zj_atr", z.atraque,
                          decimals=2, container=z6, min_value=0.0)
    z.pavimento = num_input("Pavimento [m] (0 = sin)", "zj_pav", z.pavimento, decimals=2,
                            container=z7, min_value=0.0)
    z.en_informe = z8.checkbox("Incluir en la memoria", value=z.en_informe, key="w_chk_zj")
    m1, m2, m3 = st.columns(3)
    z.mat_cama = m1.text_input("Material de la cama", key=txt_state("txt_zj_mc", z.mat_cama))
    z.mat_atraque = m2.text_input("Relleno seleccionado",
                                  key=txt_state("txt_zj_ma", z.mat_atraque))
    z.mat_relleno = m3.text_input("Relleno superior", key=txt_state("txt_zj_mr", z.mat_relleno))
    z.nota = st.text_input("Fuente de las dimensiones (norma, especificación)",
                           key=txt_state("txt_zj_nota", z.nota))
    faltan = dt.validar_zanja(z)
    if faltan and any((z.d_ext_mm, z.ancho_fondo, z.profundidad)):
        for f_ in faltan:
            st.warning(f_)
    elif not faltan:
        fz = dt.fig_zanja(z)
        st.columns([3, 2])[0].pyplot(fz)
        plt.close(fz)

# build() recalcula todo y dibuja todas las figuras: se hace solo cuando el
# proyecto cambió, no en cada rerun de la página.
_clave = pj.huella(p)
_cache = st.session_state.get("rep_cache")
if _cache and _cache[0] == _clave:
    _, ctx, figuras = _cache
else:
    if _cache and _cache[2]:
        shutil.rmtree(Path(next(iter(_cache[2].values()))).parent, ignore_errors=True)
    st.session_state.pop("rep_cache", None)
    try:
        ctx, figuras = report_ctx.build(p)
    except ValueError:
        st.info("Completa al menos Proyecto, Población (censo, población base y "
                "método) y Caudales (dotación neta) antes de generar el reporte.")
        st.stop()
    st.session_state["rep_cache"] = (_clave, ctx, figuras)

st.caption(f"El reporte se genera recalculando todo desde el proyecto: población "
           f"{ctx['pob_final']} hab · QMD {ctx['qmd']} L/s · almacenamiento "
           f"{ctx['v_final']} m³ · {len(ctx['sistemas'])} sistema(s) de bombeo · "
           f"{len(figuras)} figuras.")

_motor, _exe = report._find_engine()
hay_latex = _exe is not None
if not hay_latex:
    st.warning("No se detectó ningún motor LaTeX. Instala "
               "[Tectonic](https://tectonic-typesetting.github.io/install.html) "
               "(recomendado, autocontenido — o solo copia `tectonic.exe` en la "
               "carpeta de ACUCALC) o [MiKTeX](https://miktex.org/download) para "
               "compilar el PDF directamente desde la app; mientras tanto se entrega "
               "el proyecto .zip para compilar en Overleaf.")
else:
    st.caption(f"Motor LaTeX detectado: **{_motor}**.")

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

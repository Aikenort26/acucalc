import base64
import uuid
from pathlib import Path

import streamlit as st
from core import biblio, estudios as es, project as pj, report_ctx
from pages_common import WIDGET_PREFIX, page_setup, sel_state, txt_state

p = page_setup()
st.header("Estudios previos")
st.caption("Secciones de la memoria con los estudios del proyecto: población, aspectos "
           "sociales y económicos, topografía, suelos, materiales… Cada una lleva texto, "
           "tablas (CSV o Excel) y figuras (imagen o la primera página de un PDF). Cite con "
           "[@clave] usando las claves de la bibliografía (página Reporte → Referencias).")

claves = {r.key: r for r in report_ctx.referencias(p)}
with st.expander(f"Claves de cita disponibles ({len(claves)})", expanded=False):
    st.markdown("\n".join(f"- `[@{k}]` — {r.titulo[:90]}" for k, r in claves.items()))


def _olvidar(prefijo: str) -> None:
    """Borra el estado de los widgets de una lista cuyos índices cambiaron."""
    for k in [k for k in st.session_state if k.startswith(WIDGET_PREFIX + prefijo)]:
        del st.session_state[k]


c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
tipos = list(es.TIPOS)
tipo_nuevo = c1.selectbox("Tipo de estudio", tipos, format_func=es.TIPOS.get,
                          key="w_est_tipo_nuevo")
if c2.button("➕ Agregar estudio", width="stretch"):
    p.estudios.append(pj.EstudioPrevio(id=uuid.uuid4().hex[:8], tipo=tipo_nuevo))
    st.rerun()
if not p.estudios:
    st.info("Aún no hay estudios. Agregue uno para que aparezca en la memoria, entre la "
            "localización y la proyección de población.")

for e in list(p.estudios):
    if not e.id:
        e.id = uuid.uuid4().hex[:8]
    with st.expander(f"{es.TIPOS.get(e.tipo, e.tipo)} — {e.titulo or 'sin título'}",
                     expanded=True):
        a1, a2, a3 = st.columns([2, 3, 1], vertical_alignment="bottom")
        e.tipo = a1.selectbox("Tipo", tipos, format_func=es.TIPOS.get,
                              key=sel_state(tipos, f"sel_est_{e.id}_tipo", e.tipo))
        e.titulo = a2.text_input("Título de la sección (vacío = el del tipo)",
                                 key=txt_state(f"txt_est_{e.id}_tit", e.titulo))
        e.en_informe = a3.checkbox("En la memoria", value=e.en_informe,
                                   key=f"w_chk_est_{e.id}")
        e.texto = st.text_area(
            "Texto (párrafos separados por una línea en blanco; citas como [@res0330])",
            key=txt_state(f"txt_est_{e.id}_texto", e.texto), height=180)
        _, faltan = biblio.citas(e.texto, set(claves))
        if faltan:
            st.warning("Claves que no están en la bibliografía (quedan como texto): "
                       + ", ".join(f"`{k}`" for k in dict.fromkeys(faltan))
                       + ". Agréguelas en BibTeX en la página Reporte.")

        st.markdown("**Tablas**")
        up = st.file_uploader("Agregar tabla (CSV o Excel; máximo "
                              f"{es.MAX_COLUMNAS} columnas)", type=["csv", "xlsx", "xls"],
                              key=f"w_up_est_{e.id}_tab")
        if up is not None and st.session_state.get(f"est_{e.id}_tab_id") != up.file_id:
            st.session_state[f"est_{e.id}_tab_id"] = up.file_id
            try:
                e.tablas.append(es.tabla_de_archivo(up.name, up.getvalue()))
                st.rerun()
            except ValueError as ex:
                st.error(str(ex))
        for k, t in enumerate(list(e.tablas)):
            t1, t2 = st.columns([5, 1], vertical_alignment="bottom")
            t.titulo = t1.text_input(f"Título de la tabla {k + 1}",
                                     key=txt_state(f"txt_est_{e.id}_tab{k}", t.titulo))
            if t2.button("Quitar", key=f"w_btn_est_{e.id}_rmtab{k}", width="stretch"):
                e.tablas.pop(k)
                _olvidar(f"txt_est_{e.id}_tab")
                st.rerun()
            st.dataframe(es.tabla_df(t), hide_index=True, width="stretch",
                         height=min(38 + 35 * len(es.tabla_df(t)), 260))

        st.markdown("**Figuras**")
        upf = st.file_uploader("Agregar figura (PNG, JPG o PDF: se usa la primera página)",
                               type=["png", "jpg", "jpeg", "pdf"], key=f"w_up_est_{e.id}_fig")
        if upf is not None and st.session_state.get(f"est_{e.id}_fig_id") != upf.file_id:
            st.session_state[f"est_{e.id}_fig_id"] = upf.file_id
            try:
                e.figuras.append(pj.FiguraEstudio(Path(upf.name).stem,
                                                  es.figura_de_archivo(upf.name, upf.getvalue())))
                st.rerun()
            except ValueError as ex:
                st.error(str(ex))
        for k, f in enumerate(list(e.figuras)):
            f1, f2, f3 = st.columns([1, 3, 1], vertical_alignment="center")
            f1.image(base64.b64decode(f.img_b64), width=160)
            f.leyenda = f2.text_input(f"Leyenda de la figura {k + 1}",
                                      key=txt_state(f"txt_est_{e.id}_fig{k}", f.leyenda))
            f.fuente = f2.text_input("Fuente", key=txt_state(f"txt_est_{e.id}_fue{k}", f.fuente))
            if f3.button("Quitar", key=f"w_btn_est_{e.id}_rmfig{k}", width="stretch"):
                e.figuras.pop(k)
                _olvidar(f"txt_est_{e.id}_fig")
                _olvidar(f"txt_est_{e.id}_fue")
                st.rerun()

        if st.button("🗑 Eliminar este estudio", key=f"w_btn_est_{e.id}_rm"):
            p.estudios.remove(e)
            _olvidar(f"txt_est_{e.id}")
            st.rerun()

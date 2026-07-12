import base64
import datetime as dt
import streamlit as st
from core import dane, project as pj
from pages_common import (SAVES_DIR, page_setup, num_input, clear_widget_state)

p = page_setup()
st.header("1 · Proyecto")

c1, c2 = st.columns(2)
with c1:
    p.nombre = st.text_input("Nombre del proyecto", p.nombre, key="w_txt_nombre")
    dptos = dane.departamentos()
    p.poblacion.dpto = st.selectbox(
        "Departamento (DANE)", dptos,
        index=dptos.index(p.poblacion.dpto) if p.poblacion.dpto in dptos else 0,
        key="w_sel_dpto")
    p.departamento = p.poblacion.dpto
    mpios = dane.municipios(p.poblacion.dpto)
    p.poblacion.mpio = st.selectbox(
        "Municipio (DANE)", mpios,
        index=mpios.index(p.poblacion.mpio) if p.poblacion.mpio in mpios else 0,
        key="w_sel_mpio")
    p.municipio = p.poblacion.mpio
    p.poblacion.tipo = st.radio(
        "El estudio es en:", ["municipio", "corregimiento"],
        format_func={"municipio": "Cabecera municipal",
                     "corregimiento": "Corregimiento / vereda"}.get,
        index=["municipio", "corregimiento"].index(p.poblacion.tipo),
        horizontal=True, key="w_radio_tipo")
    if p.poblacion.tipo == "corregimiento":
        p.corregimiento = st.text_input("Nombre del corregimiento / vereda",
                                        p.corregimiento, key="w_txt_corr")
    else:
        p.corregimiento = ""
with c2:
    p.consultor = st.text_input("Consultor / entidad", p.consultor, key="w_txt_consultor")
    p.fecha = st.text_input("Fecha", p.fecha or dt.date.today().isoformat(), key="w_txt_fecha")
    p.altitud = num_input("Altitud promedio [m.s.n.m.]", "altitud", p.altitud,
                          decimals=0, min_value=0.0, max_value=4500.0)
    p.temperatura = num_input("Temperatura del agua [°C]", "temperatura", p.temperatura,
                              decimals=1, min_value=0.0, max_value=50.0)

st.caption("La serie de población DANE del municipio seleccionado alimenta la página "
           "2 (tasas de crecimiento y proyección).")

with st.expander("Logos de portada del informe", expanded=False):
    l1, l2 = st.columns(2)
    up_cli = l1.file_uploader("Logo del cliente/entidad", type=["png", "jpg", "jpeg"],
                              key="w_up_logo_cli")
    if up_cli is not None:
        p.logo_cliente_b64 = base64.b64encode(up_cli.getvalue()).decode()
    if p.logo_cliente_b64:
        l1.image(base64.b64decode(p.logo_cliente_b64), width=160)
        if l1.button("Quitar logo del cliente", key="w_rm_logo_cli"):
            p.logo_cliente_b64 = ""
            st.rerun()
    up_con = l2.file_uploader("Logo del consultor", type=["png", "jpg", "jpeg"],
                              key="w_up_logo_con")
    if up_con is not None:
        p.logo_consultor_b64 = base64.b64encode(up_con.getvalue()).decode()
    if p.logo_consultor_b64:
        l2.image(base64.b64decode(p.logo_consultor_b64), width=160)
        if l2.button("Quitar logo del consultor", key="w_rm_logo_con"):
            p.logo_consultor_b64 = ""
            st.rerun()

st.divider()
c3, c4 = st.columns(2)
with c3:
    st.download_button(
        "💾 Guardar proyecto (.json)",
        data=__import__("json").dumps(
            {"schema_version": pj.SCHEMA_VERSION, "project": __import__("dataclasses").asdict(p)},
            ensure_ascii=False, indent=1),
        file_name=f"{(p.nombre or 'proyecto').replace(' ', '_')}.acucalc.json",
        mime="application/json",
    )
with c4:
    guardados = sorted(SAVES_DIR.glob("*.acucalc.json")) if SAVES_DIR.exists() else []
    if guardados:
        sel_g = st.selectbox("Proyectos guardados (saves/)",
                             ["—"] + [g.name for g in guardados], key="w_sel_save")
        if sel_g != "—" and st.button("📂 Abrir guardado"):
            try:
                st.session_state["project"] = pj.load(SAVES_DIR / sel_g)
                clear_widget_state()
                st.rerun()
            except pj.SchemaError as e:
                st.error(f"No se pudo cargar: {e}")
    up = st.file_uploader("…o cargar archivo de proyecto", type=["json"])
    if up is not None:
        import tempfile, pathlib
        tmp = pathlib.Path(tempfile.mkstemp(suffix=".json")[1])
        tmp.write_bytes(up.getvalue())
        try:
            st.session_state["project"] = pj.load(tmp)
            clear_widget_state()
            st.success("Proyecto cargado. Revisa las demás páginas.")
            st.rerun()
        except pj.SchemaError as e:
            st.error(f"No se pudo cargar: {e}")

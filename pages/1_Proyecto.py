import datetime as dt
import streamlit as st
from core import project as pj
from pages_common import get_project

st.header("1 · Proyecto")
p = get_project()

c1, c2 = st.columns(2)
with c1:
    p.nombre = st.text_input("Nombre del proyecto", p.nombre)
    p.departamento = st.text_input("Departamento", p.departamento)
    p.municipio = st.text_input("Municipio", p.municipio)
    p.corregimiento = st.text_input("Corregimiento / vereda", p.corregimiento)
with c2:
    p.consultor = st.text_input("Consultor / entidad", p.consultor)
    p.fecha = st.text_input("Fecha", p.fecha or dt.date.today().isoformat())
    p.altitud = st.number_input("Altitud promedio [m.s.n.m.]", 0.0, 4500.0, float(p.altitud))
    p.temperatura = st.number_input("Temperatura del agua [°C]", 0.0, 50.0, float(p.temperatura))

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
    up = st.file_uploader("Cargar proyecto", type=["json"])
    if up is not None:
        import json, tempfile, pathlib
        tmp = pathlib.Path(tempfile.mkstemp(suffix=".json")[1])
        tmp.write_bytes(up.getvalue())
        try:
            st.session_state["project"] = pj.load(tmp)
            st.success("Proyecto cargado. Revisa las demás páginas.")
            st.rerun()
        except pj.SchemaError as e:
            st.error(f"No se pudo cargar: {e}")

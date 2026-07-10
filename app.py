import streamlit as st
from pages_common import get_project

st.set_page_config(page_title="ACUCALC", page_icon="💧", layout="wide")
p = get_project()
st.title("ACUCALC")
st.caption("Diseño de sistemas de acueducto — Resolución 0330 de 2017 (MVCT)")
st.markdown(
    """
Flujo de trabajo (menú lateral):
1. **Proyecto** — datos generales, guardar/cargar
2. **Población** — censo y proyección
3. **Caudales** — dotación y caudales de diseño
4. **Almacenamiento** — volumen y tanques
5. **Bombeo** — tramos, accesorios y potencia
6. **Curvas de bomba** — digitalización y punto de operación
7. **Reporte** — memoria LaTeX
"""
)
if p.nombre:
    st.success(f"Proyecto activo: **{p.nombre}** — {p.corregimiento or p.municipio}")
else:
    st.info("Crea o carga un proyecto en la página **Proyecto**.")

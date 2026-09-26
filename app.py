import streamlit as st
from pages_common import page_setup

st.set_page_config(page_title="ACUCALC", page_icon="💧", layout="wide")


def _inicio():
    p = page_setup()
    st.title("ACUCALC")
    st.caption("Diseño de sistemas de acueducto — Resolución 0330 de 2017 (MVCT)")
    st.markdown(
        """
Flujo de trabajo (barra superior):
1. **Proyecto** — datos generales, localización y mapas, guardar/cargar
2. **Estudios** — estudios previos con texto, tablas, figuras y citas
3. **Población** — censo y proyección
4. **Caudales** — dotación y caudales de diseño
5. **Almacenamiento** — volumen, tanques y balance entre tanques
6. **Bombeo** — tramos, accesorios, potencia y NPSH
7. **Curvas de bomba** — digitalización y punto de operación
8. **Transitorios** — golpe de ariete en la aducción (MOC y Allievi)
9. **Red** — trazado y verificación hidráulica (EPANET)
10. **Reporte** — memoria LaTeX, referencias y detalles típicos
"""
    )
    if p.nombre:
        st.success(f"Proyecto activo: **{p.nombre}** — {p.corregimiento or p.municipio}")
    else:
        st.info("Crea o carga un proyecto en la página **Proyecto**.")


pg = st.navigation([
    st.Page(_inicio, title="Inicio", icon="💧", default=True),
    st.Page("pages/1_Proyecto.py", title="Proyecto", icon="📋"),
    st.Page("pages/10_Estudios.py", title="Estudios", icon="🗂️"),
    st.Page("pages/2_Poblacion.py", title="Población", icon="👥"),
    st.Page("pages/3_Caudales.py", title="Caudales", icon="🚰"),
    st.Page("pages/4_Almacenamiento.py", title="Almacenamiento", icon="🛢️"),
    st.Page("pages/5_Bombeo.py", title="Bombeo", icon="⚙️"),
    st.Page("pages/6_Curvas_de_bomba.py", title="Curvas de bomba", icon="📈"),
    st.Page("pages/9_Transitorios.py", title="Transitorios", icon="🌊"),
    st.Page("pages/7_Red.py", title="Red", icon="🗺️"),
    st.Page("pages/8_Reporte.py", title="Reporte", icon="📄"),
], position="top")
pg.run()

import pandas as pd
import streamlit as st
from core import population as pop
from pages_common import get_project, show_issues

st.header("2 · Proyección de población")
p = get_project()

st.subheader("Censo (DANE u otra fuente)")
st.caption("Edita la tabla o pega desde Excel (columnas: año, población).")
censo_df = pd.DataFrame(p.censo or [(2018, 0)], columns=["Año", "Población"])
censo_df = st.data_editor(censo_df, num_rows="dynamic", width="stretch")
p.censo = [(int(r["Año"]), int(r["Población"]))
           for _, r in censo_df.iterrows() if r["Población"] > 0]

st.subheader("Población base de la zona de estudio")
c1, c2, c3 = st.columns(3)
viviendas = c1.number_input("Viviendas", 0, 100000, 350)
hab_viv = c2.number_input("Hab/vivienda", 0.0, 20.0, 4.0)
p0_directo = c3.number_input("…o población directa (0 = usar viviendas)", 0.0, 1e7, 0.0)
p.poblacion.p0 = p0_directo if p0_directo > 0 else viviendas * hab_viv
st.metric("Población base", f"{p.poblacion.p0:,.0f} hab")

c4, c5, c6 = st.columns(3)
p.poblacion.year0 = c4.number_input("Año base", 1990, 2100, int(p.poblacion.year0))
p.poblacion.horizon_year = c5.number_input(
    "Año horizonte (Art. 40: 25 años)", 2000, 2150, int(p.poblacion.horizon_year))
p.poblacion.tasa_res0844 = c6.number_input(
    "Tasa Res. 0844/2018 [%]", 0.0, 10.0, p.poblacion.tasa_res0844 * 100) / 100

if len(p.censo) >= 2 and p.poblacion.p0 > 0:
    rates = pop.growth_rates(p.censo)
    st.subheader("Tasas de crecimiento")
    st.dataframe(pd.DataFrame({
        "Método": ["Aritmético", "Geométrico", "Exponencial", "Wappaus", "Res. 0844"],
        "Tasa [%]": [rates.aritmetica * 100, rates.geometrica * 100,
                     rates.exponencial * 100, rates.wappaus * 100,
                     p.poblacion.tasa_res0844 * 100],
    }).style.format({"Tasa [%]": "{:.4f}"}), width="stretch")

    proj = pop.project(p.poblacion.p0, p.poblacion.year0, p.poblacion.horizon_year,
                       rates, p.poblacion.tasa_res0844)
    df = pd.DataFrame({m: dict(s) for m, s in proj.series.items()})
    st.subheader("Proyección")
    st.line_chart(df)
    st.dataframe(df.style.format("{:,.0f}"), width="stretch")

    st.subheader("Desviaciones vs promedio (año horizonte)")
    st.dataframe(pd.DataFrame(proj.deviations.items(),
                              columns=["Método", "Desviación"])
                 .style.format({"Desviación": "{:+.4%}"}), width="stretch")

    p.poblacion.metodo = st.selectbox(
        "Método de proyección adoptado",
        list(proj.series.keys()),
        index=list(proj.series.keys()).index(p.poblacion.metodo)
        if p.poblacion.metodo in proj.series else 4)
    p.poblacion.justificacion = st.text_area(
        "Justificación (va al reporte)", p.poblacion.justificacion)
    pob_final = proj.series[p.poblacion.metodo][-1][1]
    st.metric(f"Población de diseño {p.poblacion.horizon_year}", f"{pob_final:,.0f} hab")
    st.session_state["pob_final"] = pob_final
else:
    st.info("Ingresa al menos 2 registros censales y la población base.")

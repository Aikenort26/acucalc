import datetime as dt
import pandas as pd
import streamlit as st
from core import dane, population as pop
from pages_common import get_project

st.header("2 · Proyección de población")
p = get_project()
cfg = p.poblacion

# ---------- tipo de proyecto y fuente ----------
c1, c2 = st.columns(2)
cfg.tipo = c1.radio("Tipo de proyecto", ["municipio", "corregimiento"],
                    format_func={"municipio": "Municipio (cabecera)",
                                 "corregimiento": "Corregimiento / vereda"}.get,
                    index=["municipio", "corregimiento"].index(cfg.tipo),
                    horizontal=True)
cfg.fuente = c2.radio("Fuente del censo", ["dane", "manual"],
                      format_func={"dane": "Proyecciones DANE (oficial)",
                                   "manual": "Censo manual"}.get,
                      index=["dane", "manual"].index(cfg.fuente),
                      horizontal=True)

# ---------- serie censal ----------
if cfg.fuente == "dane":
    m = dane.meta()
    st.caption(f"Dataset DANE: {m['fuente']} · años {m['anos'][0]}–{m['anos'][1]} · "
               f"{m['municipios']} municipios · extraído {m['fecha_extraccion']}")
    d1, d2, d3 = st.columns(3)
    dptos = dane.departamentos()
    cfg.dpto = d1.selectbox("Departamento", dptos,
                            index=dptos.index(cfg.dpto) if cfg.dpto in dptos else 0)
    mpios = dane.municipios(cfg.dpto)
    cfg.mpio = d2.selectbox("Municipio", mpios,
                            index=mpios.index(cfg.mpio) if cfg.mpio in mpios else 0)
    areas = dane.areas()
    default_area = ("Cabecera Municipal" if cfg.tipo == "municipio"
                    else "Centros Poblados y Rural Disperso")
    cfg.area = d3.selectbox("Área geográfica", areas,
                            index=areas.index(cfg.area) if cfg.area in areas
                            else areas.index(default_area))
    p.censo = dane.series(cfg.dpto, cfg.mpio, cfg.area)
    with st.expander(f"Listado DANE — {cfg.mpio} ({cfg.area})", expanded=False):
        df_dane = pd.DataFrame(p.censo, columns=["Año", "Población"])
        st.dataframe(df_dane, hide_index=True, width="stretch")
        st.line_chart(df_dane.set_index("Año"))
    with st.expander("Actualizar dataset DANE (nuevo archivo oficial)"):
        up = st.file_uploader("Archivo DANE (xlsx con hoja DANE, o csv)", type=["xlsx", "csv"])
        if up is not None and st.button("Reemplazar dataset"):
            import tempfile, pathlib
            tmp = pathlib.Path(tempfile.mkstemp(suffix=up.name)[1])
            tmp.write_bytes(up.getvalue())
            try:
                nuevo = dane.update_from_file(tmp)
                st.success(f"Dataset actualizado: {nuevo['filas']} filas, "
                           f"años {nuevo['anos'][0]}–{nuevo['anos'][1]}")
                st.rerun()
            except ValueError as e:
                st.error(str(e))
else:
    st.subheader("Censo manual")
    st.caption("Edita la tabla o pega desde Excel (columnas: año, población).")
    censo_df = pd.DataFrame(p.censo or [(2018, 0)], columns=["Año", "Población"])
    censo_df = st.data_editor(censo_df, num_rows="dynamic", width="stretch")
    p.censo = [(int(r["Año"]), int(r["Población"]))
               for _, r in censo_df.iterrows() if r["Población"] > 0]

if len(p.censo) < 2:
    st.info("Se requieren al menos 2 registros censales.")
    st.stop()

# ---------- tasas de crecimiento (formato memoria: por año + promedio) ----------
rates = pop.growth_rates(p.censo)
rows = pop.growth_rate_rows(p.censo)
st.subheader("Tasas de crecimiento del municipio")
tabla = pd.DataFrame(
    [{"Periodo": i + 1, "Año": r.year,
      "Población (hab)": dict(p.censo)[r.year],
      "Aritmético": r.aritmetica, "Geométrico": r.geometrica,
      "Exponencial": r.exponencial, "Wappaus": r.wappaus}
     for i, r in enumerate(rows)])
prom = {"Periodo": "—", "Año": "Promedio", "Población (hab)": None,
        "Aritmético": rates.aritmetica, "Geométrico": rates.geometrica,
        "Exponencial": rates.exponencial, "Wappaus": rates.wappaus}
tabla = pd.concat([tabla, pd.DataFrame([prom])], ignore_index=True)
st.dataframe(tabla.style.format({"Aritmético": "{:.6f}", "Geométrico": "{:.6f}",
                                 "Exponencial": "{:.6f}", "Wappaus": "{:.6f}",
                                 "Población (hab)": "{:,.0f}"}, na_rep="—"),
             hide_index=True, width="stretch")

# ---------- población base y año base ----------
st.subheader("Población base de la zona de estudio")
ultimo_ano_dane = p.censo[-1][0]
if cfg.tipo == "municipio":
    st.caption("El DANE ya proyecta el municipio: la proyección propia continúa "
               "desde el año base elegido de la serie oficial.")
    anos_serie = [a for a, _ in p.censo]
    year0_default = ultimo_ano_dane if cfg.year0 not in anos_serie else cfg.year0
    cfg.year0 = st.selectbox("Año base (último DANE recomendado)", anos_serie,
                             index=anos_serie.index(year0_default))
    cfg.p0 = float(dict(p.censo)[cfg.year0])
    st.metric(f"Población base ({cfg.year0}, DANE)", f"{cfg.p0:,.0f} hab")
else:
    st.caption("Sin detalle DANE a nivel de corregimiento: población base de visita "
               "de campo, certificado del municipio o conteo de viviendas.")
    b1, b2, b3, b4 = st.columns(4)
    viviendas = b1.number_input("Viviendas", 0, 100000, 350)
    hab_viv = b2.number_input("Hab/vivienda", 0.0, 20.0, 4.0)
    p0_directo = b3.number_input("…o población directa (0 = usar viviendas)", 0.0, 1e7, 0.0)
    cfg.p0 = p0_directo if p0_directo > 0 else viviendas * hab_viv
    cfg.year0 = b4.number_input("Año base (análisis)", 1990, 2100,
                                int(cfg.year0) or dt.date.today().year)
    st.metric(f"Población base ({cfg.year0})", f"{cfg.p0:,.0f} hab")

c4, c5 = st.columns(2)
cfg.horizon_year = c4.number_input("Año horizonte (Art. 40: 25 años)", 2000, 2150,
                                   max(int(cfg.horizon_year), int(cfg.year0) + 1))
cfg.tasa_res0844 = c5.number_input("Tasa Res. 0844/2018 [%]", 0.0, 10.0,
                                   cfg.tasa_res0844 * 100) / 100

if cfg.p0 <= 0:
    st.info("Define la población base.")
    st.stop()

# ---------- proyección (formato memoria: 5 métodos + promedio) ----------
proj = pop.project(cfg.p0, int(cfg.year0), int(cfg.horizon_year), rates, cfg.tasa_res0844)
df = pd.DataFrame({m: dict(s) for m, s in proj.series.items()})
df["promedio"] = df.mean(axis=1)
st.subheader("Proyección de población")
st.line_chart(df)
st.dataframe(df.style.format("{:,.0f}"), width="stretch")

st.subheader("Desviaciones vs promedio (año horizonte)")
sugerido = pop.suggest_method(proj)
dev_df = pd.DataFrame(
    [{"Método": m, "Desviación": d, "Sugerido": "✓" if m == sugerido else ""}
     for m, d in proj.deviations.items()])
st.dataframe(dev_df.style.format({"Desviación": "{:+.4%}"}),
             hide_index=True, width="stretch")
st.caption(f"Sugerido: **{sugerido}** (menor desviación absoluta vs promedio de los 5 métodos)")

metodos = list(proj.series.keys())
cfg.metodo = st.selectbox("Método de proyección adoptado", metodos,
                          index=metodos.index(cfg.metodo)
                          if cfg.metodo in metodos else metodos.index(sugerido))
cfg.justificacion = st.text_area("Justificación (va al reporte)", cfg.justificacion)
pob_final = proj.series[cfg.metodo][-1][1]
st.metric(f"Población de diseño {cfg.horizon_year}", f"{pob_final:,.0f} hab")
st.session_state["pob_final"] = pob_final

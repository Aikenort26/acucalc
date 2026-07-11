import datetime as dt
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from core import dane, population as pop
from pages_common import page_setup, num_input, int_input

p = page_setup()
st.header("2 · Proyección de población")
cfg = p.poblacion

if not cfg.mpio:
    st.info("Selecciona departamento y municipio en la página 1 · Proyecto.")
    st.stop()

tipo_txt = ("cabecera municipal" if cfg.tipo == "municipio"
            else f"corregimiento/vereda {p.corregimiento or ''}".strip())
st.info(f"Zona de estudio: **{tipo_txt}** — {cfg.mpio} ({cfg.dpto}). "
        "Cambia municipio o tipo en la página 1.")

cfg.fuente = st.radio("Fuente del censo", ["dane", "manual"],
                      format_func={"dane": "Proyecciones DANE (oficial)",
                                   "manual": "Censo manual"}.get,
                      index=["dane", "manual"].index(cfg.fuente),
                      horizontal=True, key="w_radio_fuente")

# ---------- serie censal ----------
if cfg.fuente == "dane":
    m = dane.meta()
    st.caption(f"Dataset DANE: {m['fuente']} · años {m['anos'][0]}–{m['anos'][1]} · "
               f"{m['municipios']} municipios · extraído {m['fecha_extraccion']}")
    areas = dane.areas()
    default_area = ("Cabecera Municipal" if cfg.tipo == "municipio"
                    else "Centros Poblados y Rural Disperso")
    cfg.area = st.selectbox("Área geográfica DANE (para las tasas del municipio)", areas,
                            index=areas.index(cfg.area) if cfg.area in areas
                            else areas.index(default_area), key="w_sel_area")
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
    censo_df = st.data_editor(censo_df, num_rows="dynamic", width="stretch",
                              key="w_ed_censo")
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
if cfg.tipo == "municipio":
    st.caption("El DANE ya proyecta el municipio: la proyección propia continúa "
               "desde el año base elegido de la serie oficial.")
    anos_serie = [a for a, _ in p.censo]
    year0_default = p.censo[-1][0] if cfg.year0 not in anos_serie else cfg.year0
    cfg.year0 = st.selectbox("Año base (último DANE recomendado)", anos_serie,
                             index=anos_serie.index(year0_default), key="w_sel_year0")
    cfg.p0 = float(dict(p.censo)[cfg.year0])
    st.metric(f"Población base ({cfg.year0}, DANE)", f"{cfg.p0:,.0f} hab")
else:
    st.caption("Sin detalle DANE a nivel de corregimiento: población base de visita "
               "de campo, certificado del municipio o conteo de viviendas.")
    b1, b2, b3, b4 = st.columns(4)
    viviendas = int_input("Viviendas", "viviendas", 350, container=b1,
                          min_value=0, max_value=100000)
    hab_viv = num_input("Hab/vivienda", "hab_viv", 4.0, decimals=1, container=b2,
                        min_value=0.0, max_value=20.0)
    p0_directo = num_input("…o población directa (0 = usar viviendas)", "p0_directo",
                           0.0, decimals=0, container=b3, min_value=0.0, max_value=1e7)
    cfg.p0 = p0_directo if p0_directo > 0 else viviendas * hab_viv
    cfg.year0 = int_input("Año base (análisis)", "year0",
                          int(cfg.year0) or dt.date.today().year, container=b4,
                          min_value=1990, max_value=2100)
    st.metric(f"Población base ({cfg.year0})", f"{cfg.p0:,.0f} hab")

c4, c5, c6 = st.columns(3)
cfg.horizon_year = int_input("Año horizonte (Art. 40: 25 años)", "horizonte",
                             max(int(cfg.horizon_year), int(cfg.year0) + 1),
                             container=c4, min_value=2000, max_value=2150)
cfg.tasa_res0844 = num_input("Tasa Res. 0844/2018 [%]", "tasa0844",
                             cfg.tasa_res0844 * 100, decimals=2, container=c5,
                             min_value=0.0, max_value=10.0) / 100
cfg.flotante_pct = num_input("Población flotante [%]", "flotante",
                             cfg.flotante_pct * 100, decimals=1, container=c6,
                             min_value=0.0, max_value=100.0) / 100

if cfg.p0 <= 0:
    st.info("Define la población base.")
    st.stop()

# ---------- proyección (formato memoria: 5 métodos + promedio + flotante) ----------
proj = pop.project(cfg.p0, int(cfg.year0), int(cfg.horizon_year), rates, cfg.tasa_res0844)
df = pd.DataFrame({m: dict(s) for m, s in proj.series.items()})
df["promedio"] = df.mean(axis=1)
st.subheader("Proyección de población")
with plt.style.context("dark_background"):
    fig, ax = plt.subplots(figsize=(9, 4.2))
    fig.patch.set_alpha(0)
    ax.set_facecolor("none")
    for col in df.columns:
        ax.plot(df.index, df[col], lw=2.2 if col == "promedio" else 1.6,
                ls="--" if col == "promedio" else "-", label=col)
    vmin, vmax = df.values.min(), df.values.max()
    margen = (vmax - vmin) * 0.05 or 1
    ax.set_ylim(vmin - margen, vmax + margen)          # zoom real, no desde 0
    ax.set_xlim(df.index.min(), df.index.max())
    ax.set_xlabel("Año"); ax.set_ylabel("Población [hab]")
    ax.grid(alpha=0.25); ax.legend(fontsize=8)
    st.pyplot(fig)
    plt.close(fig)
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
                          if cfg.metodo in metodos else metodos.index(sugerido),
                          key="w_sel_metodo")
cfg.justificacion = st.text_area("Justificación (va al reporte)", cfg.justificacion,
                                 key="w_txt_justif")

serie_metodo = proj.series[cfg.metodo]
serie_total = [(t, v * (1.0 + cfg.flotante_pct)) for t, v in serie_metodo]
if cfg.flotante_pct > 0:
    st.subheader("Población de diseño con flotante")
    df_fl = pd.DataFrame(
        [{"Año": t, "Residente (hab)": v, "Flotante (hab)": v * cfg.flotante_pct,
          "Total (hab)": tot} for (t, v), (_, tot) in zip(serie_metodo, serie_total)])
    st.dataframe(df_fl.style.format({"Residente (hab)": "{:,.0f}",
                                     "Flotante (hab)": "{:,.0f}",
                                     "Total (hab)": "{:,.0f}"}),
                 hide_index=True, width="stretch")

pob_final = serie_total[-1][1]
st.metric(f"Población de diseño {cfg.horizon_year}"
          + (f" (incluye {cfg.flotante_pct:.0%} flotante)" if cfg.flotante_pct else ""),
          f"{pob_final:,.0f} hab")
st.session_state["pob_final"] = pob_final
st.session_state["pob_series"] = serie_total

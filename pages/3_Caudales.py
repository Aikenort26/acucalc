import pandas as pd
import streamlit as st
from core import catalogs, demand
from pages_common import page_setup, num_input, show_issues

p = page_setup()
st.header("3 · Dotación y caudales de diseño")
refs = catalogs.dotacion_references()

p.demanda.modo = st.radio(
    "Modo de dotación neta",
    ["altitud", "usos", "manual"],
    format_func={"altitud": "Por altitud (Art. 43 Res. 0330)",
                 "usos": "Por tabla de usos de la comunidad",
                 "manual": "Valor manual con sustento normativo"}.get,
    index=["altitud", "usos", "manual"].index(p.demanda.modo),
    horizontal=True, key="w_radio_dot")

if p.demanda.modo == "altitud":
    p.demanda.dneta = float(demand.dotacion_altitud(p.altitud))
    st.info(f"Altitud {p.altitud:,.0f} m.s.n.m. → dotación neta máxima "
            f"**{p.demanda.dneta:.0f} L/hab/d** (Art. 43 Res. 0330 de 2017)")
elif p.demanda.modo == "usos":
    base = p.demanda.usos or [(u["actividad"], float(u["adoptada"]))
                              for u in refs["usos_default"]]
    df = st.data_editor(pd.DataFrame(base, columns=["Actividad", "Dotación [L/hab/d]"]),
                        num_rows="dynamic", width="stretch", key="w_ed_usos")
    p.demanda.usos = [(str(r["Actividad"]), float(r["Dotación [L/hab/d]"]))
                      for _, r in df.iterrows()]
    p.demanda.dneta = demand.dotacion_usos(p.demanda.usos)
    st.metric("Dotación neta adoptada", f"{p.demanda.dneta:.0f} L/hab/d")
else:
    p.demanda.dneta = num_input("Dotación neta [L/hab/d]", "dneta",
                                p.demanda.dneta or 80.0, decimals=0,
                                min_value=20.0, max_value=300.0)
    opciones = {r["id"]: r for r in refs["otras_referencias"]}
    p.demanda.referencia = st.selectbox(
        "Referencia normativa de sustento", list(opciones),
        format_func=lambda i: opciones[i]["nombre"],
        index=list(opciones).index(p.demanda.referencia)
        if p.demanda.referencia in opciones else 0, key="w_sel_ref")
    st.caption(opciones[p.demanda.referencia]["cita"])
p.demanda.justificacion = st.text_area("Justificación de la dotación (va al reporte)",
                                       p.demanda.justificacion, key="w_txt_justdot")

pob = st.session_state.get("pob_final", 0.0)

c1, c2, c3 = st.columns(3)
p.demanda.perdidas = num_input("Pérdidas técnicas [%] (máx 25, Art. 44)", "perdidas",
                               p.demanda.perdidas * 100, decimals=1, container=c1,
                               min_value=0.0, max_value=60.0) / 100
if pob > 0:
    k1_max, k2_max = demand.k_factors(pob)
    auto_k = st.checkbox(
        f"K1/K2 automáticos según población de diseño "
        f"({pob:,.0f} hab → K1={k1_max}, K2={k2_max} — Par. 2 Art. 47 Res. 0330)",
        value=p.demanda.k_auto, key="w_chk_autok")
    p.demanda.k_auto = auto_k
else:
    k1_max, k2_max, auto_k = None, None, p.demanda.k_auto
if auto_k and k1_max is not None:
    p.demanda.k1, p.demanda.k2 = k1_max, k2_max
    c2.metric("K1 (Par. 2 Art. 47)", f"{p.demanda.k1}")
    c3.metric("K2 (Par. 2 Art. 47)", f"{p.demanda.k2}")
else:
    p.demanda.k1 = num_input("K1 (Par. 2 Art. 47)", "k1", p.demanda.k1, decimals=2,
                             container=c2, min_value=1.0, max_value=2.0)
    p.demanda.k2 = num_input("K2 (Par. 2 Art. 47)", "k2", p.demanda.k2, decimals=2,
                             container=c3, min_value=1.0, max_value=2.5)
    if k1_max and (p.demanda.k1 > k1_max or p.demanda.k2 > k2_max):
        st.warning(f"K1/K2 superan el máximo del Par. 2 Art. 47 para "
                   f"{pob:,.0f} hab (K1≤{k1_max}, K2≤{k2_max})")

if pob <= 0:
    st.info("Calcula primero la población en la página 2.")
else:
    r = demand.flows(pob, p.demanda.dneta, p.demanda.perdidas, p.demanda.k1, p.demanda.k2)
    show_issues(r.issues)
    st.subheader("Caudales de diseño (año horizonte)")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Dotación bruta", f"{r.dbruta:.1f} L/hab/d")
    m2.metric("Qmed", f"{r.qmed_lps:.3f} L/s")
    m3.metric("QMD", f"{r.qmd_lps:.3f} L/s")
    m4.metric("QMH", f"{r.qmh_lps:.3f} L/s")
    st.session_state["flows"] = r

    # ---------- proyección de caudales año a año (Art. 47) ----------
    pob_series = st.session_state.get("pob_series", [])
    if pob_series:
        serie_q = demand.flows_series(pob_series, p.demanda.dneta, p.demanda.perdidas,
                                      p.demanda.k1, p.demanda.k2)
        st.subheader("Proyección de caudales en el periodo de diseño")
        df_q = pd.DataFrame(
            [{"Año": t, "Población (hab)": pob_t, "Qmed [L/s]": fr.qmed_lps,
              "QMD [L/s]": fr.qmd_lps, "QMH [L/s]": fr.qmh_lps}
             for (t, fr), (_, pob_t) in zip(serie_q, pob_series)])
        st.line_chart(df_q.set_index("Año")[["Qmed [L/s]", "QMD [L/s]", "QMH [L/s]"]])
        st.dataframe(df_q.style.format({"Población (hab)": "{:,.0f}",
                                        "Qmed [L/s]": "{:.3f}", "QMD [L/s]": "{:.3f}",
                                        "QMH [L/s]": "{:.3f}"}),
                     hide_index=True, width="stretch")
        st.session_state["flows_series"] = serie_q

    st.subheader("Caudal por componente (Art. 47 Res. 0330)")
    comp = demand.design_flows_by_component(r)
    st.dataframe(pd.DataFrame(comp.items(), columns=["Componente", "Q diseño [L/s]"])
                 .style.format({"Q diseño [L/s]": "{:.3f}"}), width="stretch")

import pandas as pd
import streamlit as st
from core import catalogs, demand
from pages_common import get_project, show_issues

st.header("3 · Dotación y caudales de diseño")
p = get_project()
refs = catalogs.dotacion_references()

p.demanda.modo = st.radio(
    "Modo de dotación neta",
    ["altitud", "usos", "manual"],
    format_func={"altitud": "Por altitud (Art. 43 Res. 0330)",
                 "usos": "Por tabla de usos de la comunidad",
                 "manual": "Valor manual con sustento normativo"}.get,
    index=["altitud", "usos", "manual"].index(p.demanda.modo),
    horizontal=True)

if p.demanda.modo == "altitud":
    p.demanda.dneta = float(demand.dotacion_altitud(p.altitud))
    st.info(f"Altitud {p.altitud:,.0f} m.s.n.m. → dotación neta máxima "
            f"**{p.demanda.dneta:.0f} L/hab/d** (Art. 43 Res. 0330 de 2017)")
elif p.demanda.modo == "usos":
    base = p.demanda.usos or [(u["actividad"], float(u["adoptada"]))
                              for u in refs["usos_default"]]
    df = st.data_editor(pd.DataFrame(base, columns=["Actividad", "Dotación [L/hab/d]"]),
                        num_rows="dynamic", width="stretch")
    p.demanda.usos = [(str(r["Actividad"]), float(r["Dotación [L/hab/d]"]))
                      for _, r in df.iterrows()]
    p.demanda.dneta = demand.dotacion_usos(p.demanda.usos)
    st.metric("Dotación neta adoptada", f"{p.demanda.dneta:.0f} L/hab/d")
else:
    p.demanda.dneta = st.number_input("Dotación neta [L/hab/d]", 20.0, 300.0,
                                      p.demanda.dneta or 80.0)
    opciones = {r["id"]: r for r in refs["otras_referencias"]}
    p.demanda.referencia = st.selectbox(
        "Referencia normativa de sustento", list(opciones),
        format_func=lambda i: opciones[i]["nombre"],
        index=list(opciones).index(p.demanda.referencia)
        if p.demanda.referencia in opciones else 0)
    st.caption(opciones[p.demanda.referencia]["cita"])
p.demanda.justificacion = st.text_area("Justificación de la dotación (va al reporte)",
                                       p.demanda.justificacion)

pob = st.session_state.get("pob_final", 0.0)

c1, c2, c3 = st.columns(3)
p.demanda.perdidas = c1.number_input("Pérdidas técnicas [%] (máx 25, Art. 44)",
                                     0.0, 60.0, p.demanda.perdidas * 100) / 100
if pob > 0:
    k1_max, k2_max = demand.k_factors(pob)
    auto_k = st.checkbox(
        f"K1/K2 automáticos según población de diseño "
        f"({pob:,.0f} hab → K1={k1_max}, K2={k2_max} — Par. 2 Art. 47 Res. 0330)",
        value=True)
else:
    k1_max, k2_max, auto_k = None, None, False
if auto_k:
    p.demanda.k1, p.demanda.k2 = k1_max, k2_max
    c2.metric("K1 (Par. 2 Art. 47)", f"{p.demanda.k1}")
    c3.metric("K2 (Par. 2 Art. 47)", f"{p.demanda.k2}")
else:
    p.demanda.k1 = c2.number_input("K1 (Par. 2 Art. 47)", 1.0, 2.0, p.demanda.k1)
    p.demanda.k2 = c3.number_input("K2 (Par. 2 Art. 47)", 1.0, 2.5, p.demanda.k2)
    if k1_max and (p.demanda.k1 > k1_max or p.demanda.k2 > k2_max):
        st.warning(f"K1/K2 superan el máximo del Par. 2 Art. 47 para "
                   f"{pob:,.0f} hab (K1≤{k1_max}, K2≤{k2_max})")

if pob <= 0:
    st.info("Calcula primero la población en la página 2.")
else:
    r = demand.flows(pob, p.demanda.dneta, p.demanda.perdidas, p.demanda.k1, p.demanda.k2)
    show_issues(r.issues)
    st.subheader("Caudales de diseño")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Dotación bruta", f"{r.dbruta:.1f} L/hab/d")
    m2.metric("Qmed", f"{r.qmed_lps:.3f} L/s")
    m3.metric("QMD", f"{r.qmd_lps:.3f} L/s")
    m4.metric("QMH", f"{r.qmh_lps:.3f} L/s")
    st.session_state["flows"] = r
    st.subheader("Caudal por componente (Art. 47 Res. 0330)")
    comp = demand.design_flows_by_component(r)
    st.dataframe(pd.DataFrame(comp.items(), columns=["Componente", "Q diseño [L/s]"])
                 .style.format({"Q diseño [L/s]": "{:.3f}"}), width="stretch")

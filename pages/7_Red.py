import pandas as pd
import streamlit as st
from core import network as net, pipes
from pages_common import page_setup

p = page_setup()
st.header("7 · Red de distribución")
flows = st.session_state.get("flows")

up = st.file_uploader("Archivo INP de la red (EPANET)", type=["inp", "txt"])
if up is not None:
    texto_subido = up.getvalue().decode("utf-8", errors="replace")
    if texto_subido != p.red_inp:
        p.red_inp = texto_subido
        st.session_state.pop("red_demandas", None)
        st.session_state.pop("red_optim", None)
        st.session_state.pop("red_optim_inp", None)

if not p.red_inp:
    st.info("Carga un archivo .inp (EPANET) con [JUNCTIONS], [RESERVOIRS]/[TANKS] "
            "y [PIPES] para asignar demandas y optimizar diámetros.")
    st.stop()

try:
    red = net.parse_inp(p.red_inp)
except ValueError as e:
    st.error(f"No se pudo leer el INP: {e}")
    st.stop()

st.caption(f"Red cargada: {len(red.junctions)} nodos de consumo, "
           f"{len(red.sources)} fuente(s), {len(red.pipes)} tuberías "
           f"(pérdidas: {red.headloss}).")

st.subheader("Asignación de demandas por longitud aferente")
if flows is None:
    st.info("Calcula primero los caudales en la página 3 para asignar demandas.")
else:
    if st.button("Asignar demandas (QMD por longitud aferente)"):
        demandas = net.assign_demands_by_length(red, flows.qmd_lps)
        st.session_state["red_demandas"] = demandas
        p.red_inp = net.write_inp_demands(p.red_inp, demandas)
        st.rerun()
    demandas = st.session_state.get("red_demandas")
    if demandas:
        st.dataframe(pd.DataFrame(
            [{"Nodo": jid, "Demanda [L/s]": q} for jid, q in demandas.items()])
            .style.format({"Demanda [L/s]": "{:.3f}"}), hide_index=True, width="stretch")
        c1, c2 = st.columns(2)
        c1.download_button("⬇️ INP con demandas asignadas", data=p.red_inp,
                           file_name="red_demandas.inp")
        csv = "Nodo,Demanda [L/s]\n" + "\n".join(f"{j},{q:.4f}" for j, q in demandas.items())
        c2.download_button("⬇️ CSV de demandas", data=csv, file_name="demandas.csv")

st.divider()
st.subheader("Optimización de diámetros")
o1, o2, o3 = st.columns(3)
p.red_material = o1.selectbox("Material", pipes.materials(),
                              index=pipes.materials().index(p.red_material)
                              if p.red_material in pipes.materials() else 0)
series_mat = pipes.series(p.red_material)
p.red_serie = o2.selectbox("Serie / clase", series_mat,
                           index=series_mat.index(p.red_serie)
                           if p.red_serie in series_mat else 0)
p.red_vmax = o3.number_input("V máxima [m/s]", value=p.red_vmax, min_value=0.5, max_value=10.0)
o4, o5 = st.columns(2)
p.red_pmin = o4.number_input("Presión mínima [m]", value=p.red_pmin, min_value=0.0, max_value=100.0)
p.red_pmax = o5.number_input("Presión máxima [m]", value=p.red_pmax, min_value=0.0, max_value=200.0)

if st.button("🧮 Optimizar diámetros", type="primary"):
    resultado = net.optimize_diameters(red, p.red_material, p.red_serie,
                                       p.red_vmax, p.red_pmin, p.red_pmax)
    st.session_state["red_optim"] = resultado
    st.session_state["red_optim_inp"] = red

opt = st.session_state.get("red_optim")
if opt:
    st.dataframe(pd.DataFrame([
        {"Tubería": pid, "DN original [mm]": opt.dn_original[pid],
         "DN optimizado [mm]": opt.dn_optimizado[pid],
         "V [m/s]": opt.result.velocities[pid], "hf [m]": opt.result.hf[pid]}
        for pid in opt.dn_original]).style.format(
        {"V [m/s]": "{:.2f}", "hf [m]": "{:.3f}"}), hide_index=True, width="stretch")
    st.dataframe(pd.DataFrame([
        {"Nodo": jid, "Presión [m]": opt.result.heads[jid] - red.junctions[jid].elevation}
        for jid in red.junctions]).style.format({"Presión [m]": "{:.2f}"}),
        hide_index=True, width="stretch")
    for a in opt.avisos:
        st.warning(a)
    st.caption(f"Convergió en {opt.iteraciones} iteración(es).")
    st.download_button("⬇️ INP con demandas asignadas (referencia para actualizar diámetros)",
                       data=p.red_inp, file_name="red_optimizada_demandas.inp")

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from core import network as net, network_map as nm, pipes, curves as cv
from pages_common import (page_setup, num_input, sel_state, SP_CAUDAL,
                          SP_VELOCIDAD, SP_PERDIDA, SP_ALTURA)

p = page_setup()
st.header("7 · Red de distribución")
flows = st.session_state.get("flows")

up = st.file_uploader("Archivo INP de la red (EPANET)", type=["inp", "txt"])
if up is not None:
    if st.session_state.get("red_upload_id") != up.file_id:
        st.session_state["red_upload_id"] = up.file_id
        p.red_inp = up.getvalue().decode("utf-8", errors="replace")
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
p.red_en_informe = st.checkbox("Incluir la sección de red en la memoria del reporte",
                               value=p.red_en_informe, key="w_chk_red_informe",
                               help="Desmárcalo si esta red es solo para explorar/optimizar "
                                    "y no quieres que aparezca en el PDF final.")

# ---------- WP-7: mapa de la red ----------
with st.expander("🗺 Mapa de la red", expanded=False):
    col_c, _ = st.columns([1, 2])
    colorear = col_c.radio("Colorear por", ["presión", "velocidad", "topología"],
                           horizontal=True, key="w_red_colorear")
    if colorear == "topología":
        fig_map = nm.fig_red(red, dark=True)
    else:
        try:
            res_map = net.solve(red)
            fig_map = nm.fig_red(red, res_map,
                                 colorear="presion" if colorear == "presión" else "velocidad",
                                 dark=True)
        except Exception as e:
            st.warning(f"No se pudo simular para colorear el mapa: {e}")
            fig_map = nm.fig_red(red, dark=True)
    if not nm.tiene_coordenadas(red):
        st.caption("El INP no trae sección [COORDINATES]; se usa un layout "
                   "automático (la topología es correcta, las posiciones son "
                   "aproximadas). Triángulo = reservorio, cuadrado = tanque, "
                   "círculo = nodo de consumo.")
    st.pyplot(fig_map)
    plt.close(fig_map)

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
            .style.format({"Demanda [L/s]": SP_CAUDAL}), hide_index=True, width="stretch")
        c1, c2 = st.columns(2)
        c1.download_button("⬇️ INP con demandas asignadas", data=p.red_inp,
                           file_name="red_demandas.inp")
        csv = "Nodo,Demanda [L/s]\n" + "\n".join(f"{j},{q:.4f}" for j, q in demandas.items())
        c2.download_button("⬇️ CSV de demandas", data=csv, file_name="demandas.csv")

st.divider()
st.subheader("Optimización de diámetros")
o1, o2, o3 = st.columns(3)
mats = pipes.materials()
p.red_material = o1.selectbox("Material", mats,
                              key=sel_state(mats, "sel_red_mat", p.red_material))
series_mat = pipes.series(p.red_material)
p.red_serie = o2.selectbox("Serie / clase", series_mat,
                           key=sel_state(series_mat, "sel_red_ser", p.red_serie))
p.red_vmax = num_input("V máxima [m/s]", "red_vmax", p.red_vmax, decimals=2,
                       container=o3, min_value=0.5, max_value=10.0)
o4, o5 = st.columns(2)
p.red_pmin = num_input("Presión mínima [m]", "red_pmin", p.red_pmin, decimals=2,
                       container=o4, min_value=0.0, max_value=100.0)
p.red_pmax = num_input("Presión máxima [m]", "red_pmax", p.red_pmax, decimals=2,
                       container=o5, min_value=0.0, max_value=200.0)

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
        {"V [m/s]": SP_VELOCIDAD, "hf [m]": SP_PERDIDA}), hide_index=True, width="stretch")
    st.dataframe(pd.DataFrame([
        {"Nodo": jid, "Presión [m]": opt.result.heads[jid] - red.junctions[jid].elevation}
        for jid in red.junctions]).style.format({"Presión [m]": SP_ALTURA}),
        hide_index=True, width="stretch")
    for a in opt.avisos:
        st.warning(a)
    st.caption(f"Convergió en {opt.iteraciones} iteración(es).")

    # INP exportado CON los cambios aplicados: diámetros optimizados + la
    # rugosidad del material elegido (el writer viejo solo reescribía demandas,
    # así que el .inp descargado no reflejaba la optimización — bug reportado).
    red_opt = st.session_state.get("red_optim_inp", red)
    coef = net.coef_rugosidad(p.red_material, red.headloss)
    cambios = {pp.id: (pp.diameter_mm, coef) for pp in red_opt.pipes}
    inp_final = net.write_inp_pipes(p.red_inp, cambios)
    st.download_button(
        "⬇️ INP optimizado (demandas + diámetros internos + rugosidad del material)",
        data=inp_final, file_name="red_optimizada.inp", type="primary")
    st.caption(f"Rugosidad escrita para **{p.red_material}** "
               f"({'C Hazen-Williams' if red.headloss == 'H-W' else 'ks [mm] Darcy-Weisbach'}"
               f" = {coef:g}) — valor referencial de literatura para tubería nueva; "
               "verifícalo según el estado real de la tubería.")

# ---------- WP-8: transferir curvas de bomba al INP ----------
st.divider()
st.subheader("Transferir curvas de bomba al INP")
# Reúne las bombas seleccionadas de todos los sistemas, con la transformada de
# afinidad/arreglo aplicada (misma fuente que el reporte, no puntos crudos).
curvas_bomba = {}
for s in p.bombeos:
    for b in s.bombas:
        if b.nombre == s.bomba_seleccionada and len(b.puntos_qh) >= 2:
            qh_t, _ = cv.apply_pump_transform(b.puntos_qh, b.puntos_qe, b.n1_nominal,
                                              b.n2_objetivo, b.n_unidades, b.arreglo)
            curvas_bomba[f"{s.nombre} · {b.nombre}"] = qh_t
if not curvas_bomba:
    st.caption("No hay bombas seleccionadas con curva Q-H en los sistemas de bombeo "
               "(página 6). Selecciona una bomba por sistema para poder exportarla.")
else:
    st.caption(f"Se exportarán {len(curvas_bomba)} curva(s): "
               f"{', '.join(curvas_bomba)}. Q en las unidades de caudal del INP "
               "(verifica [OPTIONS] Units en EPANET); H en m.")
    base_inp = st.session_state.get("red_inp_export", p.red_inp)
    inp_con_curvas = net.write_inp_pump_curves(base_inp, curvas_bomba)
    st.download_button("⬇️ INP con curvas de bomba ([CURVES] + plantilla [PUMPS])",
                       data=inp_con_curvas, file_name="red_con_bombas.inp")
    st.caption("La sección [PUMPS] queda comentada: conéctala a los nodos de "
               "succión/impulsión en EPANET (ACUCALC no conoce esa topología). "
               "El solver interno de ACUCALC no simula bombas — asume cabeza fija.")

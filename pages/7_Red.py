import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from core import epanet_engine as ee
from core import network as net, network_map as nm, pipeline, pipes, red_diseno as rd, storage
from pages_common import (page_setup, num_input, sel_state, SP_CAUDAL,
                          SP_VELOCIDAD, SP_PERDIDA, SP_ALTURA)

p = page_setup()
st.header("7 · Red de distribución")
_diseno = pipeline.design_flows(p)
flows = _diseno.flows if _diseno else None
K2 = flows.k2 if flows else p.demanda.k2

_RESULTADOS = ("red_demandas", "red_optim", "red_optim_inp", "red_inp_export",
               "red_estatico", "red_eps")

up = st.file_uploader("Archivo INP de la red (EPANET)", type=["inp", "txt"])
if up is not None:
    if st.session_state.get("red_upload_id") != up.file_id:
        st.session_state["red_upload_id"] = up.file_id
        p.red_inp = up.getvalue().decode("utf-8", errors="replace")
        for k in _RESULTADOS:                      # resultados de la red anterior
            st.session_state.pop(k, None)

if not p.red_inp:
    st.info("Carga un archivo .inp (EPANET) con [JUNCTIONS], [RESERVOIRS]/[TANKS] "
            "y [PIPES] para asignar demandas, simular y optimizar diámetros.")
    st.stop()

HAY_EPANET = ee.disponible()
try:
    red = net.parse_inp(p.red_inp)
    ee.validar_inp(p.red_inp)
except (ValueError, ee.EngineError) as e:
    st.error(f"No se pudo leer el INP: {e}")
    st.stop()

if HAY_EPANET:
    m = ee.leer_inp(p.red_inp)
    st.caption(f"Red cargada: {m.n_nodos} nodos de consumo, {m.n_reservorios} reservorio(s), "
               f"{m.n_tanques} tanque(s), {m.n_tuberias} tuberías, {m.n_bombas} bomba(s), "
               f"{m.n_valvulas} válvula(s) · pérdidas {m.headloss} · unidades {m.unidades}.")
else:
    st.caption(f"Red cargada: {len(red.junctions)} nodos de consumo, {len(red.sources)} "
               f"fuente(s), {len(red.pipes)} tuberías (pérdidas: {red.headloss}).")
if not red.unidades_explicitas:
    st.warning("El INP no declara `[OPTIONS] Units`: EPANET de escritorio lo leería en GPM. "
               "ACUCALC lo trata como **LPS** (caudal en L/s, longitudes en m).")
elif red.unidades != "LPS":
    st.info(f"Unidades del archivo: **{red.unidades}**. ACUCALC trabaja en SI (L/s, m) y "
            "escribe las exportaciones en las unidades originales del archivo.")

# ---------- motor y criterios de diseño ----------
c_m, c_i = st.columns([2, 1])
opciones_motor = ["auto", "epanet", "gga"] if HAY_EPANET else ["gga"]
etiquetas = {"auto": f"Automático ({ee.nombre_motor()})",
             "epanet": ee.nombre_motor(), "gga": ee.MOTOR_GGA}
p.red_motor = c_m.radio("Motor hidráulico", opciones_motor, format_func=etiquetas.get,
                        horizontal=True,
                        key=sel_state(opciones_motor, "radio_red_motor", p.red_motor))
if not HAY_EPANET:
    c_m.warning("EPANET no está disponible en este equipo: se usa el solver propio "
                "(sin bombas ni válvulas, sin periodo extendido).")
p.red_en_informe = c_i.checkbox("Incluir la red en la memoria", value=p.red_en_informe,
                                key="w_chk_red_informe")

o3, o4, o5 = st.columns(3)
p.red_pmin = num_input("Presión mínima [m]", "red_pmin", p.red_pmin, decimals=2,
                       container=o3, min_value=0.0, max_value=100.0)
p.red_pmax = num_input("Presión máxima [m]", "red_pmax", p.red_pmax, decimals=2,
                       container=o4, min_value=0.0, max_value=200.0)
p.red_vmax = num_input("V máxima [m/s]", "red_vmax", p.red_vmax, decimals=2,
                       container=o5, min_value=0.5, max_value=10.0)

# ---------- 1. asignación de demandas ----------
st.subheader("1 · Asignación de demandas por longitud aferente (QMD)")
if flows is None:
    st.info("Completa Población y Caudales para asignar demandas.")
else:
    st.caption(f"Reparte el QMD = {flows.qmd_lps:.2f} L/s como demanda base de los nodos, "
               "proporcional a la longitud de tubería que abastece cada uno.")
    if st.button("Asignar demandas (QMD por longitud aferente)"):
        demandas = net.assign_demands_by_length(red, flows.qmd_lps)
        st.session_state["red_demandas"] = demandas
        p.red_inp = net.write_inp_demands(p.red_inp, demandas)
        st.rerun()
    demandas = st.session_state.get("red_demandas")
    if demandas:
        with st.expander(f"Demandas asignadas ({len(demandas)} nodos)"):
            st.dataframe(pd.DataFrame(
                [{"Nodo": jid, "Demanda [L/s]": q} for jid, q in demandas.items()])
                .style.format({"Demanda [L/s]": SP_CAUDAL}), hide_index=True, width="stretch")
        c1, c2 = st.columns(2)
        c1.download_button("⬇️ INP con demandas asignadas", data=p.red_inp,
                           file_name="red_demandas.inp")
        csv = "Nodo,Demanda [L/s]\n" + "\n".join(f"{j},{q:.4f}" for j, q in demandas.items())
        c2.download_button("⬇️ CSV de demandas", data=csv, file_name="demandas.csv")

# ---------- bombas del proyecto conectadas a la red ----------
curvas_bomba = rd.curvas_bombas(p)
if curvas_bomba:
    with st.expander(f"Bombas del proyecto en la red ({len(curvas_bomba)})"):
        st.caption("Conecta la bomba seleccionada de cada sistema entre su nodo de succión "
                   "e impulsión para simularla (curva con afinidad y arreglo aplicados). "
                   "Sin los dos nodos, la bomba no se incluye.")
        ids_nodos = ["—"] + sorted(list(red.junctions) + list(red.sources))
        for nombre in curvas_bomba:
            n1, n2 = (list(p.red_conexiones.get(nombre, [])) + ["", ""])[:2]
            b1, b2, b3 = st.columns([2, 1, 1])
            b1.markdown(f"**{nombre}**")
            k = "".join(ch for ch in nombre if ch.isalnum())
            s1 = b2.selectbox("Succión", ids_nodos,
                              key=sel_state(ids_nodos, f"bs_{k}", n1 or "—"))
            s2 = b3.selectbox("Impulsión", ids_nodos,
                              key=sel_state(ids_nodos, f"bi_{k}", n2 or "—"))
            p.red_conexiones[nombre] = ["" if s1 == "—" else s1, "" if s2 == "—" else s2]

# ---------- 2. análisis estático ----------
st.subheader("2 · Análisis estático — condición de diseño (QMH)")
p.red_aplicar_k2 = st.checkbox(
    f"Multiplicar las demandas base por K2 = {K2:.2f} (QMH = K2·QMD, Art. 47)",
    value=p.red_aplicar_k2, key="w_chk_red_k2",
    help="Desmárcalo solo si las demandas del INP ya representan el caudal máximo horario.")
cambios_est = rd.cambios_red(p, K2)
clave_est = (p.red_inp, repr(cambios_est), p.red_motor)
if st.button("🧮 Calcular régimen estático", type="primary"):
    with st.spinner("Resolviendo la red…"):
        try:
            st.session_state["red_estatico"] = (clave_est, ee.correr_estatico(
                p.red_inp, cambios_est, motor=p.red_motor))
        except (ee.EngineError, ValueError) as e:
            st.error(f"No se pudo resolver la red: {e}")
est = st.session_state.get("red_estatico")
res_est = est[1] if est and est[0] == clave_est else None
if est and res_est is None:
    st.caption("Los datos cambiaron desde el último cálculo: vuelve a calcular.")
if res_est is not None:
    for a in res_est.avisos:
        (st.error if a.codigo in ee.AVISOS_NO_CONVERGE else st.warning)(
            f"{'Aviso ' + str(a.codigo) + ': ' if a.codigo else ''}{a.texto}")
    if not res_est.converged:
        st.error("⚠️ **La solución NO es válida** (ver avisos): no uses estas presiones "
                 "para diseño.")
    r = rd.resumen_estatico(res_est, p.red_pmin, p.red_pmax, p.red_vmax)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(f"Presión mínima · nodo {r.nodo_p_min}", f"{r.p_min:.2f} m")
    m2.metric(f"Presión máxima · nodo {r.nodo_p_max}", f"{r.p_max:.2f} m")
    m3.metric(f"Velocidad máxima · tubería {r.tubo_v_max}", f"{r.v_max:.2f} m/s")
    m4.metric("Motor", res_est.motor)
    if r.bajo_p_min:
        st.error(f"{len(r.bajo_p_min)} nodo(s) bajo la presión mínima de {p.red_pmin:.0f} m: "
                 + ", ".join(r.bajo_p_min[:15]) + ("…" if len(r.bajo_p_min) > 15 else ""))
    if r.sobre_p_max:
        st.warning(f"{len(r.sobre_p_max)} nodo(s) sobre la presión máxima de "
                   f"{p.red_pmax:.0f} m (requieren válvula reductora de presión): "
                   + ", ".join(r.sobre_p_max[:15]) + ("…" if len(r.sobre_p_max) > 15 else ""))
    if r.sobre_v_max:
        st.warning(f"{len(r.sobre_v_max)} tubería(s) sobre {p.red_vmax:.1f} m/s: "
                   + ", ".join(r.sobre_v_max[:15]))
    if r.cumple and res_est.converged:
        st.success("La red cumple los criterios de presión y velocidad en la condición de QMH.")
    with st.expander("Resultados por nodo y por tubería"):
        t1, t2 = st.columns(2)
        t1.dataframe(pd.DataFrame([{"Nodo": n, "Presión [m]": v}
                                   for n, v in res_est.presiones.items()])
                     .style.format({"Presión [m]": SP_ALTURA}), hide_index=True, width="stretch")
        t2.dataframe(pd.DataFrame([{"Enlace": k, "Q [L/s]": res_est.flows[k],
                                    "V [m/s]": abs(res_est.velocities[k]),
                                    "hf [m]": res_est.hf.get(k)}
                                   for k in res_est.flows])
                     .style.format({"Q [L/s]": SP_CAUDAL, "V [m/s]": SP_VELOCIDAD,
                                    "hf [m]": SP_PERDIDA}, na_rep="—"),
                     hide_index=True, width="stretch")

# ---------- mapa ----------
with st.expander("🗺 Mapa de la red", expanded=False):
    col_c, col_e = st.columns([2, 1])
    colorear = col_c.radio("Colorear por", ["topología", "presión", "velocidad"],
                           horizontal=True, key="w_red_colorear")
    escala_map = num_input("Escala de los iconos", "red_map_escala", 1.0, decimals=2,
                           container=col_e, min_value=0.2, max_value=4.0,
                           help="Tamaño de nodos, fuentes y grosor de tramos.")
    if colorear != "topología" and res_est is None:
        st.caption("Calcula el régimen estático para colorear el mapa.")
    fig_map = nm.fig_red(red, res_est if colorear != "topología" else None,
                         colorear="presion" if colorear == "presión" else "velocidad",
                         dark=True, escala=escala_map)
    if not nm.tiene_coordenadas(red):
        st.caption("El INP no trae [COORDINATES]; se usa un layout automático.")
    st.pyplot(fig_map)
    plt.close(fig_map)

# ---------- 3. periodo extendido ----------
st.subheader("3 · Periodo extendido de 24 h")
patron = (list(p.almacenamiento.factores_hora) if len(p.almacenamiento.factores_hora) == 24
          else list(storage.DEFAULT_PATTERN))
if not HAY_EPANET:
    st.info("El periodo extendido requiere EPANET.")
else:
    st.caption("Demanda base (QMD) × patrón horario de la página Almacenamiento"
               + ("" if len(p.almacenamiento.factores_hora) == 24 else " (por defecto)")
               + f", pico {max(patron):.2f}. Los tanques de la red varían su nivel.")
    aviso = rd.aviso_pico_vs_k2(patron, K2)
    if aviso:
        st.warning(aviso)
    cambios_eps = rd.cambios_red(p, K2, patron=patron)
    clave_eps = (p.red_inp, repr(cambios_eps))
    if st.button("⏱ Simular 24 h"):
        with st.spinner("Simulando 24 h con EPANET…"):
            try:
                st.session_state["red_eps"] = (clave_eps, ee.correr_eps(p.red_inp, cambios_eps))
            except ee.EngineError as e:
                st.error(f"No se pudo simular: {e}")
    eps_s = st.session_state.get("red_eps")
    eps = eps_s[1] if eps_s and eps_s[0] == clave_eps else None
    if eps is not None:
        for a in eps.avisos:
            (st.error if a.codigo in ee.AVISOS_NO_CONVERGE else st.warning)(
                f"Hora {a.hora:.0f} — aviso {a.codigo}: {a.texto}")
        re_ = rd.resumen_eps(eps, p.red_pmin)
        e1, e2, e3 = st.columns(3)
        e1.metric(f"Presión mínima del día · nodo {re_.nodo_critico}, "
                  f"{re_.hora_critica:02d} h", f"{re_.p_min:.2f} m")
        e2.metric("Nodos bajo P mín. en alguna hora", len(re_.bajo_p_min))
        e3.metric("Motor", eps.motor)
        g1, g2 = st.columns(2)
        g1.caption(f"Presión en el nodo crítico {re_.nodo_critico} [m]")
        g1.line_chart(pd.DataFrame({re_.nodo_critico: eps.presiones[re_.nodo_critico]},
                                   index=eps.horas), x_label="Hora", height=240)
        if eps.niveles:
            g2.caption("Nivel de los tanques [m]")
            g2.line_chart(pd.DataFrame(eps.niveles, index=eps.horas), x_label="Hora",
                          height=240)
        if re_.tanques:
            st.dataframe(pd.DataFrame([{"Tanque": t, "Nivel inicial [m]": v["ini"],
                                        "Mínimo [m]": v["min"], "Máximo [m]": v["max"],
                                        "Final [m]": v["fin"]}
                                       for t, v in re_.tanques.items()])
                         .style.format(SP_ALTURA, subset=["Nivel inicial [m]", "Mínimo [m]",
                                                          "Máximo [m]", "Final [m]"]),
                         hide_index=True, width="stretch")
        st.download_button("⬇️ INP para periodo extendido (normalizado por EPANET)",
                           data=ee.exportar_eps_inp(p.red_inp, cambios_eps),
                           file_name="red_24h.inp",
                           help="EPANET reescribe el archivo: incluye el patrón ACUCALC24, "
                                "las bombas conectadas y los tiempos de 24 h; se pierden los "
                                "comentarios del original.")

# ---------- 4. optimización de diámetros ----------
st.divider()
st.subheader("4 · Optimización de diámetros")
o1, o2 = st.columns(2)
mats = pipes.materials()
p.red_material = o1.selectbox("Material", mats,
                              key=sel_state(mats, "sel_red_mat", p.red_material))
series_mat = pipes.series(p.red_material)
p.red_serie = o2.selectbox("Serie / clase", series_mat,
                           key=sel_state(series_mat, "sel_red_ser", p.red_serie))
st.caption("Sube al siguiente DN comercial las tuberías con V > V máx. y las de mayor "
           "pérdida en la ruta hacia nodos con P < P mín., resolviendo la red en cada "
           "iteración con el motor elegido y la demanda de diseño (QMH si aplica).")
if st.button("🧮 Optimizar diámetros"):
    red_opt_in = net.parse_inp(p.red_inp)
    solver = ee.solver_para(p.red_inp, cambios_est.multiplicador, p.red_motor,
                            cambios_est.bombas)
    with st.spinner("Optimizando…"):
        try:
            resultado = net.optimize_diameters(red_opt_in, p.red_material, p.red_serie,
                                               p.red_vmax, p.red_pmin, p.red_pmax,
                                               solver=solver)
            st.session_state["red_optim"] = resultado
            st.session_state["red_optim_inp"] = red_opt_in
        except (ee.EngineError, ValueError) as e:
            st.error(f"No se pudo optimizar: {e}")

opt = st.session_state.get("red_optim")
if opt:
    red_opt = st.session_state.get("red_optim_inp", red)
    st.dataframe(pd.DataFrame([
        {"Tubería": pid, "D interno original [mm]": opt.dn_original[pid],
         "D interno optimizado [mm]": opt.dn_optimizado[pid],
         "V [m/s]": abs(opt.result.velocities[pid]), "hf [m]": opt.result.hf[pid]}
        for pid in opt.dn_original]).style.format(
        {"V [m/s]": SP_VELOCIDAD, "hf [m]": SP_PERDIDA}), hide_index=True, width="stretch")
    for a in opt.avisos:
        st.warning(a)
    if not opt.result.converged:
        st.error("⚠️ **El solver hidráulico NO convergió** en la última resolución: los "
                 "diámetros de esta tabla no son confiables.")
    else:
        st.caption(f"Optimización: {opt.iteraciones} iteración(es) de diámetros · "
                   f"motor {getattr(opt.result, 'motor', ee.MOTOR_GGA)}.")
    coef = net.coef_rugosidad(p.red_material, red.headloss)
    cambios = {pp.id: (pp.diameter_mm, coef) for pp in red_opt.pipes}
    inp_final = net.write_inp_pipes(p.red_inp, cambios)
    st.session_state["red_inp_export"] = inp_final   # base de la exportación de curvas
    st.download_button(
        "⬇️ INP optimizado (demandas + diámetros internos + rugosidad del material)",
        data=inp_final, file_name="red_optimizada.inp", type="primary")
    st.caption(f"Rugosidad escrita para **{p.red_material}** "
               f"({'C Hazen-Williams' if red.headloss == 'H-W' else 'ks Darcy-Weisbach'}"
               f" = {coef:g}) — valor referencial de literatura para tubería nueva.")

# ---------- 5. exportar curvas de bomba ----------
if curvas_bomba:
    st.divider()
    st.subheader("5 · Exportar bombas al INP")
    conexiones = {n: tuple(v) for n, v in p.red_conexiones.items()
                  if n in curvas_bomba and all(v)}
    base_inp = st.session_state.get("red_inp_export", p.red_inp)
    st.download_button("⬇️ INP con curvas de bomba ([CURVES] + [PUMPS])",
                       data=net.write_inp_pump_curves(base_inp, curvas_bomba, conexiones),
                       file_name="red_con_bombas.inp")
    st.caption(f"{len(conexiones)} de {len(curvas_bomba)} bomba(s) quedan conectadas; las "
               "demás van como plantilla [PUMPS] comentada. Q y H se escriben en las "
               "unidades del archivo.")

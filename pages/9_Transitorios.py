import io

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from core import catalogs, pipes, project as pj, red_diseno as rd, report_figs as rf
from core.transients import escenario as esc, perfil as pf
from pages_common import (editor_commit, editor_seed, f_num, num_input, int_input, page_setup,
                          s_txt, sel_state)

p = page_setup()
st.header("Transitorios hidráulicos — golpe de ariete")
st.caption("Método de las características (Wylie–Streeter) sobre el perfil real de la línea, "
           "con fricción y tuberías en serie; se contrasta con el método de Allievi, "
           "Joukowsky y Michaud. Las protecciones se diagnostican (el tanque hidroneumático "
           "a la salida de la bomba sí se modela).")
tc = p.transitorios
curvas = rd.curvas_bombas(p)

# ---------- 1 · perfil ----------
st.subheader("1 · Perfil de la línea")
fuente = st.radio("Origen del perfil", ["tabla", "recto"], horizontal=True,
                  format_func={"tabla": "Tabla o archivo (abscisa, cota terreno, cota eje)",
                               "recto": "Recto: longitud y cotas de inicio y fin"}.get,
                  key="w_radio_tr_perfil")
if fuente == "recto":
    r1, r2, r3 = st.columns(3)
    L_rec = num_input("Longitud de la tubería [m]", "tr_lrec",
                      sum(t.L for s in p.bombeos for t in s.tramos if t.tipo == "impulsion")
                      if p.bombeos else 1000.0, decimals=1, container=r1, min_value=1.0)
    z1 = num_input("Cota del eje al inicio [m]", "tr_z1", 0.0, decimals=2, container=r2)
    z2 = num_input("Cota del eje al final [m]", "tr_z2", 0.0, decimals=2, container=r3)
    if st.button("Generar perfil recto"):
        try:
            pr_ = pf.recto(L_rec, z1, z2)
            tc.perfil = [(s, z, z) for s, z in zip(pr_.abscisa, pr_.z_eje)]
            st.session_state.pop(editor_seed("tr_perfil", lambda: None), None)
            st.rerun()
        except ValueError as e:
            st.error(str(e))
else:
    up = st.file_uploader("Cargar perfil (CSV o Excel)", type=["csv", "xlsx", "xls"],
                          key="w_up_tr_perfil",
                          help="Columnas: Abscisa (m o K0+120.50), Cota terreno y, si la tiene, "
                               "Cota eje/clave. Sin cota del eje se calcula con la cobertura.")
    tc.cobertura = num_input("Cobertura hasta la clave (si el perfil no trae cota del eje) [m]",
                             "tr_cob", tc.cobertura, decimals=2, min_value=0.0, max_value=10.0)
    if up is not None and st.session_state.get("tr_perfil_id") != up.file_id:
        st.session_state["tr_perfil_id"] = up.file_id
        try:
            df_up = (pd.read_csv(io.BytesIO(up.getvalue())) if up.name.lower().endswith(".csv")
                     else pd.read_excel(io.BytesIO(up.getvalue())))
            c_e = pf._columna(df_up, "eje", "clave", "tuber", "batea")
            c_s, c_t = pf._columna(df_up, "absc"), pf._columna(df_up, "terreno")
            if c_s is None or c_t is None:
                raise ValueError("El archivo debe tener columnas de abscisa y de cota de terreno.")
            tc.perfil = [(pf.abscisa(r[c_s]), float(r[c_t]),
                          float(r[c_e]) if c_e is not None and pd.notna(r[c_e]) else None)
                         for _, r in df_up.iterrows() if pd.notna(r[c_s]) and pd.notna(r[c_t])]
            st.session_state.pop(editor_seed("tr_perfil", lambda: None), None)
            st.rerun()
        except (ValueError, KeyError) as e:
            st.error(f"No se pudo leer el perfil: {e}")
seed_pf = editor_seed("tr_perfil", lambda: pd.DataFrame(
    [{"Abscisa [m]": s, "Cota terreno [m]": zt, "Cota eje [m]": ze} for s, zt, ze in tc.perfil]
    or [{"Abscisa [m]": 0.0, "Cota terreno [m]": None, "Cota eje [m]": None}]))
df_pf = st.data_editor(st.session_state[seed_pf], num_rows="dynamic", width="stretch",
                       key="w_ed_tr_perfil", height=220)
editor_commit(seed_pf, df_pf)
tc.perfil = [(f_num(r["Abscisa [m]"]), f_num(r["Cota terreno [m]"]),
              None if pd.isna(r["Cota eje [m]"]) else f_num(r["Cota eje [m]"]))
             for _, r in df_pf.iterrows()
             if not pd.isna(r["Abscisa [m]"]) and not pd.isna(r["Cota terreno [m]"])]

# ---------- 2 · tramos ----------
st.subheader("2 · Tramos de tubería")
st.caption("Cada tramo va hasta la abscisa indicada. Del catálogo (material, serie, DN) salen "
           "diámetro interno, espesor, k de elasticidad, rugosidad y PN; con «Manual» se "
           "ingresan diámetro interno, espesor, material (rugosidad y k) y PN.")
mats = pipes.materials()
ks_mats = list(catalogs.roughness())
if not tc.tramos and tc.perfil:
    tc.tramos = [pj.TramoTransitorio(max(s for s, _, _ in tc.perfil))]
seed_tr = editor_seed("tr_tramos", lambda: pd.DataFrame(
    [{"Hasta abscisa [m]": t.hasta_abscisa, "Material": t.cat_material or "Manual",
      "Serie": t.cat_serie, "DN": t.cat_dn, "D interno [mm]": t.D_mm, "Espesor [mm]": t.e_mm,
      "Material (manual)": t.material, "PN [mca]": t.pn_mca} for t in tc.tramos]))
df_tr = st.data_editor(st.session_state[seed_tr], num_rows="dynamic", width="stretch",
                       key="w_ed_tr_tramos", column_config={
                           "Material": st.column_config.SelectboxColumn(options=mats + ["Manual"]),
                           "Material (manual)": st.column_config.SelectboxColumn(options=ks_mats)})
editor_commit(seed_tr, df_tr)
tramos, errores = [], []
for _, r in df_tr.iterrows():
    if pd.isna(r["Hasta abscisa [m]"]):
        continue
    mat = s_txt(r["Material"], "Manual")
    t = pj.TramoTransitorio(f_num(r["Hasta abscisa [m]"]),
                            "" if mat == "Manual" else mat, s_txt(r["Serie"]), f_num(r["DN"]),
                            f_num(r["D interno [mm]"]), f_num(r["Espesor [mm]"]),
                            s_txt(r["Material (manual)"], "PVC"), f_num(r["PN [mca]"]))
    if t.cat_material:
        try:
            pipes.pipe(t.cat_material, t.cat_serie, t.cat_dn)
        except (KeyError, ValueError, StopIteration):
            errores.append(f"{t.cat_material}: la serie '{t.cat_serie}' con DN {t.cat_dn:g} no "
                           f"está en el catálogo (series: {', '.join(pipes.series(t.cat_material))}).")
    tramos.append(t)
tc.tramos = tramos
for e in errores:
    st.warning(e)

# ---------- 3 · escenario ----------
st.subheader("3 · Escenario")
tc.escenario = st.radio("Maniobra", list(esc.ESCENARIOS), format_func=esc.ESCENARIOS.get,
                        key=sel_state(list(esc.ESCENARIOS), "radio_tr_esc", tc.escenario))
con_bomba = tc.escenario in ("parada_bomba", "arranque_bomba", "hidroneumatico")
c1, c2, c3 = st.columns(3)
tc.h_arriba = num_input("Nivel de succión [m]" if con_bomba else "Nivel del embalse aguas arriba [m]",
                        "tr_harr", tc.h_arriba, decimals=2, container=c1)
tc.h_abajo = num_input("Nivel del tanque de descarga [m]" if con_bomba
                       else "Nivel de descarga tras la válvula [m]",
                       "tr_hab", tc.h_abajo, decimals=2, container=c2)
if con_bomba:
    opciones_b = ["—"] + list(curvas)
    tc.bomba = c3.selectbox("Bomba (curva del proyecto)", opciones_b,
                            key=sel_state(opciones_b, "sel_tr_bomba", tc.bomba or "—"))
    tc.bomba = "" if tc.bomba == "—" else tc.bomba
    if not tc.bomba:
        tc.q0_lps = num_input("Caudal de régimen [L/s]", "tr_q0", tc.q0_lps, decimals=2,
                              min_value=0.0)
    else:
        st.caption("El caudal de régimen es el punto de operación de la bomba contra la línea.")
    if tc.escenario == "arranque_bomba":
        tc.t_arranque = num_input("Tiempo de arranque hasta velocidad nominal [s]", "tr_tarr",
                                  tc.t_arranque, decimals=1, min_value=0.0,
                                  help="Rampa lineal de velocidad (arrancador suave o variador); "
                                       "la retención abre cuando la bomba supera la carga "
                                       "de la línea.")
    else:
        modos = ["instantanea", "inercia"]
        tc.modo_parada = st.radio(
            "Modelo de la parada", modos, horizontal=True,
            format_func={"instantanea": "Instantánea (Q = 0, conservadora)",
                         "inercia": "Con inercia del grupo (requiere la curva)"}.get,
            key=sel_state(modos, "radio_tr_modo", tc.modo_parada))
        if tc.modo_parada == "inercia":
            b1, b2, b3 = st.columns(3)
            tc.n_rpm = num_input("Velocidad nominal [rpm]", "tr_rpm", tc.n_rpm, decimals=0,
                                 container=b1, min_value=0.0)
            tc.inercia = num_input("Inercia bomba + motor [kg·m²]", "tr_I", tc.inercia,
                                   decimals=3, container=b2, min_value=0.0,
                                   help="Dato del fabricante (GD²/4).")
            tc.eta = num_input("Eficiencia η", "tr_eta", tc.eta, decimals=2, container=b3,
                               min_value=0.0, max_value=1.0)
    if tc.escenario == "hidroneumatico":
        v1, v2, v3, v4 = st.columns(4)
        tc.v_aire = num_input("Volumen de aire en régimen [m³]", "tr_vaire", tc.v_aire,
                              decimals=3, container=v1, min_value=0.0)
        tc.n_poli = num_input("Exponente politrópico n", "tr_npoli", tc.n_poli, decimals=2,
                              container=v2, min_value=1.0, max_value=1.4,
                              help="1.0 isotérmico … 1.4 adiabático.")
        tc.d_orificio_mm = num_input("Diámetro del orificio [mm] (0 = sin)", "tr_dor",
                                     tc.d_orificio_mm, decimals=1, container=v3, min_value=0.0)
        tc.cd_orificio = num_input("Coeficiente de descarga del orificio", "tr_cd",
                                   tc.cd_orificio, decimals=2, container=v4, min_value=0.0,
                                   max_value=1.0)
else:
    tc.q0_lps = num_input("Caudal de régimen [L/s]", "tr_q0", tc.q0_lps, decimals=2,
                          container=c3, min_value=0.0)
    m1, m2, m3 = st.columns(3)
    tc.tc = num_input("Tiempo de maniobra [s]", "tr_tc", tc.tc, decimals=2, container=m1,
                      min_value=0.0)
    if tc.escenario == "cierre_valvula":
        leyes = ["lineal", "potencial"]
        tc.ley = m2.selectbox("Ley de cierre", leyes,
                              format_func={"lineal": "Lineal τ = 1 − t/Tc",
                                           "potencial": "Potencial τ = (1 − t/Tc)^Em"}.get,
                              key=sel_state(leyes, "sel_tr_ley", tc.ley))
        if tc.ley == "potencial":
            tc.em = num_input("Exponente Em", "tr_em", tc.em, decimals=2, container=m3,
                              min_value=0.1, max_value=5.0)
a1, a2, a3 = st.columns(3)
tc.n_malla = int_input("Tramos de malla (tubería más corta)", "tr_nmalla", tc.n_malla,
                       container=a1, min_value=4, max_value=400)
tc.t_sim = num_input("Tiempo a simular [s] (0 = automático)", "tr_tsim", tc.t_sim, decimals=1,
                     container=a2, min_value=0.0)
tc.en_informe = a3.checkbox("Incluir en la memoria", value=tc.en_informe, key="w_chk_tr_inf")

# ---------- 4 · resultados ----------
clave = pj.huella(p)
if st.button("🌊 Calcular transitorio", type="primary"):
    with st.spinner("Resolviendo por el método de las características…"):
        try:
            st.session_state["tr_res"] = (clave, esc.ejecutar(p))
        except (ValueError, KeyError) as e:
            st.session_state.pop("tr_res", None)
            st.error(str(e))
guardado = st.session_state.get("tr_res")
res = guardado[1] if guardado and guardado[0] == clave else None
if guardado and res is None:
    st.caption("Los datos cambiaron desde el último cálculo: vuelve a calcular.")
if res is not None:
    rs = res.resumen
    st.subheader("4 · Resultados")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("ΔH MOC en la maniobra", f"{res.comparacion[0]['dh']:+.2f} m")
    k2.metric(f"Presión máxima · {pf.formato_abscisa(rs['s_p_max'])}", f"{rs['p_max']:.2f} m")
    if res.moc.cavitacion:
        # sin modelo de separación de columna la envolvente cae por debajo del vapor: se
        # reporta la presión de vapor en el punto donde se alcanza
        s_cav = res.perfil.abscisa_de_x(res.moc.cavitacion[1])
        k3.metric(f"Presión mínima · vapor en {pf.formato_abscisa(s_cav)}",
                  f"{rs['h_vapor']:.2f} m")
    else:
        k3.metric(f"Presión mínima · {pf.formato_abscisa(rs['s_p_min'])}", f"{rs['p_min']:.2f} m")
    k4.metric("2L/a", f"{rs['T_crit']:.2f} s"
              + (f" · maniobra {rs['clasificacion']}" if rs["clasificacion"] else ""))
    st.caption(f"Q₀ = {rs['Q0_lps']:.2f} L/s · V₀ = {rs['V0']:.2f} m/s · L = {rs['L']:.0f} m · "
               f"a equivalente = {rs['a_eq']:.0f} m/s · Δt = {rs['dt']:.4f} s · "
               f"{rs['N']} tramos de malla · ajuste de celeridad {rs['ajuste_a_pct']:.2f}% · "
               f"presión de vapor {rs['h_vapor']:.2f} m (manométrica).")
    for a in res.avisos:
        st.error(a)
    for r_ in res.recomendaciones:
        st.warning(r_)
    st.markdown("**Tramos de cálculo**")
    st.dataframe(pd.DataFrame([{"Tramo": t.nombre, "Desde [m]": t.x0, "Hasta [m]": t.x1,
                                "D interno [mm]": t.D * 1000, "Espesor [mm]": t.e * 1000,
                                "k elasticidad": t.k_elast, "a [m/s]": t.a, "f Darcy": t.f,
                                "PN [m]": t.pn} for t in res.tramos])
                 .style.format({"Desde [m]": "{:.1f}", "Hasta [m]": "{:.1f}",
                                "D interno [mm]": "{:.1f}", "Espesor [mm]": "{:.2f}",
                                "k elasticidad": "{:.2f}", "a [m/s]": "{:.0f}",
                                "f Darcy": "{:.4f}", "PN [m]": "{:.0f}"}, na_rep="—"),
                 hide_index=True, width="stretch")
    t1, t2 = st.columns(2)
    t1.markdown("**Comparación de métodos**")
    t1.dataframe(pd.DataFrame([{"Método": c["metodo"], "ΔH [m]": c["dh"], "Nota": c["nota"]}
                               for c in res.comparacion]).style.format({"ΔH [m]": "{:+.2f}"}),
                 hide_index=True, width="stretch")
    t2.markdown("**Presión máxima frente a la PN**")
    t2.dataframe(pd.DataFrame([{"Tramo": v["tramo"], "P máx [m]": v["p_max"],
                                "PN [m]": v["pn"], "Uso [%]": v["uso"],
                                "Cumple": "—" if v["cumple"] is None else ("✓" if v["cumple"] else "✗")}
                               for v in res.verificacion_pn])
                 .style.format({"P máx [m]": "{:.2f}", "PN [m]": "{:.0f}", "Uso [%]": "{:.0f}"},
                               na_rep="—"), hide_index=True, width="stretch")
    f1 = rf.fig_transitorio_perfil(res, dark=True)
    st.pyplot(f1)
    plt.close(f1)
    f2 = rf.fig_transitorio_tiempo(res, dark=True)
    st.pyplot(f2)
    plt.close(f2)
    m = res.moc
    env = pd.DataFrame({"x [m]": m.x, "Abscisa [m]": res.perfil.abscisa_de_x(m.x), "Cota eje [m]": m.z,
                        "H régimen [m]": m.H_inicial, "H máx [m]": m.Hmax, "H mín [m]": m.Hmin,
                        "P máx [m]": m.pmax, "P mín [m]": m.pmin})
    st.download_button("⬇️ Envolventes (CSV)", env.to_csv(index=False).encode("utf-8"),
                       file_name="transitorio_envolventes.csv")

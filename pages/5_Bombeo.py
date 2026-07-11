import pandas as pd
import streamlit as st
from core import catalogs, pipes, pumping as pu
from core.project import PumpSystemData, SegmentData, AccessoryData
from pages_common import page_setup, num_input, int_input, show_issues

p = page_setup()
st.header("5 · Sistemas de bombeo")
flows = st.session_state.get("flows")
if flows is None:
    st.info("Calcula primero los caudales en la página 3.")
    st.stop()

# ---------- selección / creación / eliminación de sistema ----------
if "sel_sys_next" in st.session_state:
    st.session_state["w_sel_sys"] = st.session_state.pop("sel_sys_next")
nombres = [s.nombre for s in p.bombeos]
sel = st.selectbox("Sistema de bombeo", nombres + ["➕ Nuevo sistema…"], key="w_sel_sys")
if sel == "➕ Nuevo sistema…":
    nuevo = st.text_input("Nombre del nuevo sistema (ej. 'Captación→T.Bajo', "
                          "'T.Bajo→T.Elevado')", key="w_txt_newsys")
    if st.button("Crear sistema") and nuevo:
        p.bombeos.append(PumpSystemData(nombre=nuevo))
        st.session_state["sel_sys_next"] = nuevo   # selecciona el sistema recién creado
        st.rerun()
    st.stop()
sys_d = next(s for s in p.bombeos if s.nombre == sel)
K = sys_d.nombre.replace(" ", "_")

with st.popover("🗑 Eliminar este sistema"):
    st.warning(f"Elimina '{sys_d.nombre}' con sus tramos, accesorios y bombas.")
    if st.button("Eliminar definitivamente", key=f"w_del_sys_{K}"):
        p.bombeos.remove(sys_d)
        st.session_state.get("sistemas", {}).pop(sys_d.nombre, None)
        st.session_state["sel_sys_next"] = (p.bombeos[0].nombre if p.bombeos
                                            else "➕ Nuevo sistema…")
        st.rerun()

# ---------- parámetros del sistema ----------
c0, c1, c2, c3, c4 = st.columns(5)
sys_d.tipo_bomba = c0.selectbox("Tipo de bomba", ["superficie", "sumergible"],
                                index=["superficie", "sumergible"].index(sys_d.tipo_bomba),
                                key=f"w_sel_tb_{K}")
sys_d.horas = num_input("Horas de bombeo/día", f"horas_{K}", sys_d.horas,
                        decimals=1, container=c1, min_value=1.0, max_value=24.0)
sys_d.he = num_input("Altura estática [m]", f"he_{K}", sys_d.he,
                     decimals=1, container=c2, min_value=0.0, max_value=1000.0)
sys_d.sumar_5m_ras = c3.checkbox("+5 m (RAS B 9.4.11)", sys_d.sumar_5m_ras,
                                 key=f"w_chk_5m_{K}")
sys_d.eficiencia = num_input("Eficiencia η", f"efi_{K}", sys_d.eficiencia,
                             decimals=3, container=c4, min_value=0.05, max_value=1.0)
qb_lps = pu.q_bombeo(flows.qmd_lps, sys_d.horas)
st.metric("Caudal de bombeo", f"{qb_lps:.3f} L/s")
st.caption(f"Diámetro económico Bresse (referencia): continuo "
           f"{pu.bresse_continuo(qb_lps/1000)*1000:.1f} mm · no continuo "
           f"{pu.bresse_no_continuo(qb_lps/1000, sys_d.horas)*1000:.1f} mm")

# ---------- agregar tramo (catálogo en cascada) ----------
st.subheader("Tramos de tubería")
with st.expander("➕ Agregar tramo", expanded=not sys_d.tramos):
    a1, a2, a3 = st.columns(3)
    nombre_t = a1.text_input("Nombre", f"Tramo {len(sys_d.tramos) + 1}",
                             key=f"w_txt_nt_{K}_{len(sys_d.tramos)}")
    tipo_t = a2.selectbox("Tipo", ["impulsion", "succion"], key=f"w_sel_tt_{K}")
    L_t = num_input("Longitud [m]", f"lt_{K}", 100.0, decimals=1, container=a3,
                    min_value=0.1, max_value=100000.0)
    modo_t = st.radio("Dimensiones", ["Catálogo normativo", "Manual"],
                      horizontal=True, key=f"w_radio_mt_{K}")
    if modo_t == "Catálogo normativo":
        b1, b2, b3 = st.columns(3)
        mat = b1.selectbox("Material", pipes.materials(), key=f"w_sel_mat_{K}")
        ser = b2.selectbox("Serie / clase (RDE)", pipes.series(mat), key=f"w_sel_ser_{K}")
        dns = pipes.diameters(mat, ser)
        dn = b3.selectbox("Diámetro nominal", dns,
                          format_func=lambda d: pipes.dn_label(mat, d),
                          key=f"w_sel_dn_{K}")
        spec = pipes.pipe(mat, ser, dn)
        st.caption(
            f"DN **{spec.dn_mm:.0f} mm / {spec.dn_in:.2f}\"** · D interno "
            f"**{spec.id_mm:.1f} mm** · espesor **{spec.e_mm:.1f} mm** · "
            f"ks **{spec.ks_mm} mm** · PN **{spec.pn_mca:.0f} mca** · "
            f"largo de presentación **{spec.largo_m:.0f} m**"
            + (f" · {spec.nota}" if spec.nota else ""))
        if st.button("Agregar tramo", key=f"w_add_t_{K}"):
            sys_d.tramos.append(SegmentData(
                nombre_t, tipo_t, L_t, spec.id_mm, pipes.KS_KEY[mat],
                cat_material=mat, cat_serie=ser, cat_dn=dn, e_mm=spec.e_mm))
            st.rerun()
    else:
        b1, b2, b3 = st.columns(3)
        d_int = num_input("D interno [mm]", f"di_{K}", 79.5, decimals=1,
                          container=b1, min_value=5.0, max_value=2000.0)
        mat_ks = b2.selectbox("Material (rugosidad)", list(catalogs.roughness().keys()),
                              key=f"w_sel_ks_{K}")
        e_man = num_input("Espesor [mm] (ariete)", f"em_{K}", 5.0, decimals=1,
                          container=b3, min_value=0.0, max_value=100.0)
        if st.button("Agregar tramo", key=f"w_add_tm_{K}"):
            sys_d.tramos.append(SegmentData(nombre_t, tipo_t, L_t, d_int, mat_ks,
                                            e_mm=e_man))
            st.rerun()

if sys_d.tramos:
    filas = []
    for t in sys_d.tramos:
        if t.cat_material:
            spec = pipes.pipe(t.cat_material, t.cat_serie, t.cat_dn)
            filas.append({"Tramo": t.nombre, "Tipo": t.tipo, "L [m]": t.L,
                          "Material": t.cat_material, "Serie": t.cat_serie,
                          "DN [mm]": round(spec.dn_mm), "DN [in]": round(spec.dn_in, 2),
                          "D interno [mm]": spec.id_mm, "e [mm]": spec.e_mm,
                          "ks [mm]": spec.ks_mm, "PN [mca]": spec.pn_mca,
                          "Largo present. [m]": spec.largo_m})
        else:
            ks = catalogs.roughness()[t.material] * 1000
            filas.append({"Tramo": t.nombre, "Tipo": t.tipo, "L [m]": t.L,
                          "Material": f"{t.material} (manual)", "Serie": "—",
                          "DN [mm]": None, "DN [in]": None,
                          "D interno [mm]": t.D_mm, "e [mm]": t.e_mm or None,
                          "ks [mm]": round(ks, 4), "PN [mca]": None,
                          "Largo present. [m]": None})
    st.dataframe(pd.DataFrame(filas).style.format(precision=2, na_rep="—"),
                 hide_index=True, width="stretch")
    cdel1, cdel2 = st.columns([3, 1])
    t_del = cdel1.selectbox("Eliminar tramo", ["—"] + [t.nombre for t in sys_d.tramos],
                            key=f"w_sel_delt_{K}")
    if t_del != "—" and cdel2.button("🗑 Eliminar", key=f"w_del_t_{K}"):
        sys_d.tramos = [t for t in sys_d.tramos if t.nombre != t_del]
        sys_d.accesorios = [a for a in sys_d.accesorios if a.tramo != t_del]
        st.rerun()

# ---------- accesorios (con Km visible) ----------
st.subheader("Accesorios")
km_cat = catalogs.minor_loss_coefficients()
tipos_km = [f"{k}  (Km={v})" for k, v in km_cat.items()]
nombres_tramos = [t.nombre for t in sys_d.tramos]
acc_df = st.data_editor(pd.DataFrame(
    [{"Accesorio": f"{a.tipo}  (Km={km_cat.get(a.tipo, '?')})",
      "Cantidad": a.cantidad, "Tramo": a.tramo} for a in sys_d.accesorios] or
    [{"Accesorio": tipos_km[2], "Cantidad": 1,
      "Tramo": nombres_tramos[0] if nombres_tramos else ""}]),
    num_rows="dynamic", width="stretch", key=f"w_ed_acc_{K}",
    column_config={
        "Accesorio": st.column_config.SelectboxColumn(options=tipos_km),
        "Tramo": st.column_config.SelectboxColumn(options=nombres_tramos)})
sys_d.accesorios = []
for _, r in acc_df.iterrows():
    if not r["Cantidad"]:
        continue
    tipo_acc = str(r["Accesorio"]).split("  (Km=")[0]
    if tipo_acc in km_cat and str(r["Tramo"]) in nombres_tramos:
        sys_d.accesorios.append(AccessoryData(tipo_acc, int(r["Cantidad"]), str(r["Tramo"])))
if sys_d.accesorios:
    km_total = sum(km_cat[a.tipo] * a.cantidad for a in sys_d.accesorios)
    st.caption(f"ΣKm del sistema = **{km_total:.1f}**")

if not sys_d.tramos:
    st.info("Agrega al menos un tramo.")
    st.stop()

# ---------- resolución hidráulica ----------
he = sys_d.he + (5.0 if sys_d.sumar_5m_ras else 0.0)
sistema = pu.PumpSystem(
    tramos=[pu.Segment(t.nombre, t.tipo, t.L, t.D_mm / 1000, t.material)
            for t in sys_d.tramos],
    accesorios=[pu.Accessory(a.tipo, a.cantidad, a.tramo) for a in sys_d.accesorios],
    he=he, temperatura=p.temperatura, eficiencia=sys_d.eficiencia)
r = pu.solve(sistema, qb_lps / 1000)
show_issues(r.issues)
st.subheader("Pérdidas por tramo (acumuladas)")
st.dataframe(pd.DataFrame(
    [{"Tramo": t.segment.nombre, "V [m/s]": t.V, "Re": t.Re, "f": t.f,
      "hf [m]": t.hf, "ΣKm": t.sum_km, "hl [m]": t.hl} for t in r.tramos])
    .style.format({"V [m/s]": "{:.3f}", "Re": "{:,.0f}", "f": "{:.5f}",
                   "hf [m]": "{:.3f}", "ΣKm": "{:.1f}", "hl [m]": "{:.3f}"}),
    hide_index=True, width="stretch")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Σ pérdidas", f"{r.hf_total + r.hl_total:.2f} m")
m2.metric("Altura dinámica Hd", f"{r.hd:.2f} m")
m3.metric("Potencia", f"{r.potencia_kw:.2f} kW")
m4.metric("Potencia", f"{r.potencia_hp:.2f} HP")
st.info(f"Bomba mínima requerida: **Q = {qb_lps:.1f} L/s · H = {r.hd:.0f} m · "
        f"P = {r.potencia_hp:.1f} HP** → compárala en la página 6 con las curvas "
        f"de las bombas candidatas de este sistema.")

sistemas = st.session_state.setdefault("sistemas", {})
sistemas[sys_d.nombre] = {"sistema": sistema, "solve": r, "qb_lps": qb_lps}

# ---------- arreglo de bombas y leyes de afinidad ----------
with st.expander("Arreglo de bombas y leyes de afinidad", expanded=False):
    st.caption("Con el punto de diseño resuelto (Qb, Hd), reparte entre varias "
               "bombas iguales y escala por leyes de afinidad (Q∝N, H∝N², P∝N³).")
    ar1, ar2 = st.columns(2)
    n_b = int_input("Número de bombas", f"nb_{K}", 2, container=ar1,
                    min_value=1, max_value=10)
    tipo_ar = ar2.selectbox("Arreglo", ["paralelo", "serie"], key=f"w_sel_ar_{K}")
    arr = pu.arreglo_bombas(qb_lps, r.hd, n_b, tipo_ar)
    aa1, aa2, aa3 = st.columns(3)
    aa1.metric("Q por bomba", f"{arr.q_unit_lps:.2f} L/s")
    aa2.metric("H por bomba", f"{arr.h_unit:.2f} m")
    aa3.metric("P por bomba (η del sistema)",
               f"{r.potencia_hp / n_b:.2f} HP")
    st.divider()
    af1, af2, af3 = st.columns(3)
    n1 = num_input("Velocidad/frecuencia nominal N₁ [rpm o Hz]", f"n1_{K}", 3500.0,
                   decimals=0, container=af1, min_value=1.0, max_value=10000.0)
    n2 = num_input("Nueva velocidad/frecuencia N₂", f"n2_{K}", 3500.0,
                   decimals=0, container=af2, min_value=1.0, max_value=10000.0)
    q_obj = num_input("…o caudal objetivo por bomba [L/s] (0 = no usar)",
                      f"qobj_{K}", 0.0, decimals=2, container=af3,
                      min_value=0.0, max_value=10000.0)
    if q_obj > 0:
        n2 = pu.frecuencia_para_caudal(q_obj, arr.q_unit_lps, n1)
        st.caption(f"Frecuencia requerida para {q_obj:.2f} L/s: **N₂ = {n2:.0f}**")
    q2, h2, p2 = pu.afinidad(arr.q_unit_lps, arr.h_unit, r.potencia_hp / n_b, n1, n2)
    b1, b2, b3 = st.columns(3)
    b1.metric("Q @ N₂", f"{q2:.2f} L/s")
    b2.metric("H @ N₂", f"{h2:.2f} m")
    b3.metric("P @ N₂", f"{p2:.2f} HP")

# ---------- golpe de ariete ----------
with st.expander("Golpe de ariete (Joukowsky) — por tramo"):
    sys_d.pn_mca = num_input("PN de la tubería [mca]", f"pn_{K}", sys_d.pn_mca,
                             decimals=0, min_value=0.0, max_value=600.0)
    rows_ar = []
    k_elast_manual = {"PVC": 18.0, "PEAD": 111.11, "HD": 1.0,
                      "Acero comercial": 0.5, "GRP": 8.3, "Concreto": 5.0,
                      "Hierro galvanizado": 1.0}
    for t, tr in zip(sys_d.tramos, r.tramos):
        if not t.e_mm:
            rows_ar.append({"Tramo": t.nombre, "e [mm]": None, "C [m/s]": None,
                            "ΔH [mca]": None, "Hd+ΔH [mca]": None})
            continue
        k_el = (pipes.pipe(t.cat_material, t.cat_serie, t.cat_dn).k_elast
                if t.cat_material else k_elast_manual.get(t.material, 18.0))
        c = pu.celeridad(t.D_mm / 1000, t.e_mm / 1000, k_el)
        dp = pu.sobrepresion_ariete(c, tr.V)
        rows_ar.append({"Tramo": t.nombre, "e [mm]": t.e_mm, "C [m/s]": c,
                        "ΔH [mca]": dp, "Hd+ΔH [mca]": r.hd + dp})
    st.dataframe(pd.DataFrame(rows_ar).style.format(
        {"e [mm]": "{:.1f}", "C [m/s]": "{:.1f}", "ΔH [mca]": "{:.1f}",
         "Hd+ΔH [mca]": "{:.1f}"}, na_rep="sin espesor"),
        hide_index=True, width="stretch")
    pn_cat = min((pipes.pipe(t.cat_material, t.cat_serie, t.cat_dn).pn_mca
                  for t in sys_d.tramos if t.cat_material), default=0)
    if pn_cat:
        st.caption(f"PN mínima de los tramos de catálogo: {pn_cat:.0f} mca")
    peor = max((row["Hd+ΔH [mca]"] or 0 for row in rows_ar), default=0)
    pn_ref = sys_d.pn_mca or pn_cat
    if pn_ref and peor > pn_ref:
        st.warning(f"Hd + sobrepresión ({peor:.1f} mca) supera la PN "
                   f"({pn_ref:.0f} mca) — revisar clase o protecciones.")

# ---------- paneles ----------
with st.expander("Paneles solares (pre-cálculo)"):
    pc1, pc2, pc3 = st.columns(3)
    sys_d.panel_w = num_input("Potencia panel [W]", f"pw_{K}", sys_d.panel_w,
                              decimals=0, container=pc1, min_value=100.0, max_value=1500.0)
    sys_d.panel_fs = num_input("Factor de seguridad", f"pfs_{K}", sys_d.panel_fs,
                               decimals=1, container=pc2, min_value=1.0, max_value=5.0)
    sys_d.panel_area = num_input("Área panel [m²]", f"pa_{K}", sys_d.panel_area,
                                 decimals=2, container=pc3, min_value=0.5, max_value=5.0)
    pan = pu.paneles_solares(r.potencia_kw, sys_d.panel_w, sys_d.panel_fs, sys_d.panel_area)
    st.write(f"**{pan.cantidad} paneles** · área total {pan.area_total:.1f} m²")

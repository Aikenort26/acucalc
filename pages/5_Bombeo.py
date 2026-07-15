import pandas as pd
import streamlit as st
from core import catalogs, pipes, pumping as pu
from core.project import PumpSystemData, SegmentData, AccessoryData
from pages_common import page_setup, num_input, show_issues

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

with st.popover("✏ Renombrar sistema"):
    nuevo_nombre = st.text_input("Nuevo nombre", sys_d.nombre, key=f"w_ren_{K}")
    if st.button("Renombrar", key=f"w_ren_btn_{K}") and nuevo_nombre and nuevo_nombre != sys_d.nombre:
        if nuevo_nombre in [s.nombre for s in p.bombeos if s is not sys_d]:
            st.error(f"Ya existe un sistema llamado '{nuevo_nombre}'.")
        else:
            viejo = sys_d.nombre
            sys_d.nombre = nuevo_nombre
            sistemas_dict = st.session_state.get("sistemas", {})
            if viejo in sistemas_dict:
                sistemas_dict[nuevo_nombre] = sistemas_dict.pop(viejo)
            st.session_state["sel_sys_next"] = nuevo_nombre
            st.rerun()

# ---------- sincronizar horas con la entrada de un tanque del tren ----------
tanques_tren = [t for t in p.almacenamiento.tanques
                if p.almacenamiento.usar_cadena]
if tanques_tren:
    opciones_tk = ["—"] + [f"{t.nombre} ({sum(t.entrada_flags())} h)"
                           for t in tanques_tren]
    sel_tk = st.selectbox("Sincronizar horas de bombeo con la entrada del tanque…",
                          opciones_tk, key=f"w_sel_synctk_{K}")
    if sel_tk != "—":
        horas_tk = float(sum(tanques_tren[opciones_tk.index(sel_tk) - 1]
                             .entrada_flags()))
        st.session_state["w_horas_" + K] = horas_tk

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

# ---------- agregar / editar tramo (catálogo en cascada) ----------
st.subheader("Tramos de tubería")

# precarga diferida del formulario cuando se pide editar un tramo
editando = st.session_state.get(f"editing_{K}")
pend_edit = st.session_state.pop(f"edit_next_{K}", None)
if pend_edit is not None:
    t0 = next(t for t in sys_d.tramos if t.nombre == pend_edit)
    st.session_state[f"editing_{K}"] = pend_edit
    st.session_state[f"w_nt_{K}"] = t0.nombre
    st.session_state[f"w_sel_tt_{K}"] = t0.tipo
    st.session_state["w_lt_" + K] = float(t0.L)
    if t0.cat_material:
        st.session_state[f"w_radio_mt_{K}"] = "Catálogo normativo"
        st.session_state[f"w_sel_mat_{K}"] = t0.cat_material
        st.session_state[f"w_sel_ser_{K}"] = t0.cat_serie
        st.session_state[f"w_sel_dn_{K}"] = t0.cat_dn
    else:
        st.session_state[f"w_radio_mt_{K}"] = "Manual"
        st.session_state["w_di_" + K] = float(t0.D_mm)
        st.session_state[f"w_sel_ks_{K}"] = t0.material
        st.session_state["w_em_" + K] = float(t0.e_mm)
    editando = pend_edit

with st.expander("➕ Agregar / ✏ editar tramo", expanded=not sys_d.tramos):
    if editando:
        st.caption(f"Editando **{editando}** — 'Guardar cambios' lo reemplaza.")
    a1, a2, a3 = st.columns(3)
    nombre_t = a1.text_input("Nombre", f"Tramo {len(sys_d.tramos) + 1}",
                             key=f"w_nt_{K}")
    tipo_t = a2.selectbox("Tipo", ["impulsion", "succion"], key=f"w_sel_tt_{K}")
    L_t = num_input("Longitud [m]", f"lt_{K}", 100.0, decimals=1, container=a3,
                    min_value=0.1, max_value=100000.0)
    modo_t = st.radio("Dimensiones", ["Catálogo normativo", "Manual"],
                      horizontal=True, key=f"w_radio_mt_{K}")
    etiqueta = "Guardar cambios" if editando else "Agregar tramo"
    nuevo_tramo = None
    if modo_t == "Catálogo normativo":
        b1, b2, b3 = st.columns(3)
        mat = b1.selectbox("Material", pipes.materials(), key=f"w_sel_mat_{K}")
        ser = b2.selectbox("Serie / clase (RDE)", pipes.series(mat), key=f"w_sel_ser_{K}")
        dns = pipes.diameters(mat, ser)
        dn_prop = pipes.suggest_dn(mat, ser, qb_lps / 1000)
        if f"w_sel_dn_{K}" not in st.session_state:
            st.session_state[f"w_sel_dn_{K}"] = dn_prop
        if st.session_state[f"w_sel_dn_{K}"] not in dns:      # cambió material/serie
            st.session_state[f"w_sel_dn_{K}"] = dn_prop
        dn = b3.selectbox("Diámetro nominal", dns,
                          format_func=lambda d: pipes.dn_label(mat, d),
                          key=f"w_sel_dn_{K}")
        st.caption(f"Propuesto para Qb={qb_lps:.1f} L/s: "
                   f"**{pipes.dn_label(mat, dn_prop)}** (≥ Bresse y V ≤ 6 m/s, Art. 56)")
        spec = pipes.pipe(mat, ser, dn)
        st.caption(
            f"DN **{spec.dn_mm:.0f} mm / {spec.dn_in:.2f}\"** · D interno "
            f"**{spec.id_mm:.1f} mm** · espesor **{spec.e_mm:.1f} mm** · "
            f"ks **{spec.ks_mm} mm** · PN **{spec.pn_mca:.0f} mca** · "
            f"largo de presentación **{spec.largo_m:.0f} m**"
            + (f" · {spec.nota}" if spec.nota else ""))
        if st.button(etiqueta, key=f"w_add_t_{K}"):
            nuevo_tramo = SegmentData(
                nombre_t, tipo_t, L_t, spec.id_mm, pipes.KS_KEY[mat],
                cat_material=mat, cat_serie=ser, cat_dn=dn, e_mm=spec.e_mm)
    else:
        b1, b2, b3 = st.columns(3)
        d_int = num_input("D interno [mm]", f"di_{K}", 79.5, decimals=1,
                          container=b1, min_value=5.0, max_value=2000.0)
        mat_ks = b2.selectbox("Material (rugosidad)", list(catalogs.roughness().keys()),
                              key=f"w_sel_ks_{K}")
        e_man = num_input("Espesor [mm] (ariete)", f"em_{K}", 5.0, decimals=1,
                          container=b3, min_value=0.0, max_value=100.0)
        if st.button(etiqueta, key=f"w_add_tm_{K}"):
            nuevo_tramo = SegmentData(nombre_t, tipo_t, L_t, d_int, mat_ks, e_mm=e_man)
    if nuevo_tramo is not None:
        if editando:
            idx = next(i for i, t in enumerate(sys_d.tramos) if t.nombre == editando)
            sys_d.tramos[idx] = nuevo_tramo
            for acc in sys_d.accesorios:
                if acc.tramo == editando:
                    acc.tramo = nuevo_tramo.nombre
            st.session_state.pop(f"editing_{K}", None)
        else:
            sys_d.tramos.append(nuevo_tramo)
        st.rerun()
    if editando and st.button("✖ Cancelar edición", key=f"w_cancel_e_{K}"):
        st.session_state.pop(f"editing_{K}", None)
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
    cdel1, cdel2, cdel3 = st.columns([3, 1, 1])
    t_sel = cdel1.selectbox("Tramo a editar/eliminar",
                            ["—"] + [t.nombre for t in sys_d.tramos],
                            key=f"w_sel_delt_{K}")
    if t_sel != "—" and cdel2.button("✏ Editar", key=f"w_edit_t_{K}"):
        st.session_state[f"edit_next_{K}"] = t_sel
        st.rerun()
    if t_sel != "—" and cdel3.button("🗑 Eliminar", key=f"w_del_t_{K}"):
        sys_d.tramos = [t for t in sys_d.tramos if t.nombre != t_sel]
        sys_d.accesorios = [a for a in sys_d.accesorios if a.tramo != t_sel]
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

# ---------- golpe de ariete: verificación automática contra PN por tramo ----------
with st.expander("Golpe de ariete (Joukowsky) — verificación PN por tramo",
                 expanded=False):
    rows_ar, fallan = [], []
    k_elast_manual = {"PVC": 18.0, "PEAD": 111.11, "HD": 1.0,
                      "Acero comercial": 0.5, "GRP": 8.3, "Concreto": 5.0,
                      "Hierro galvanizado": 1.0}
    for t, tr in zip(sys_d.tramos, r.tramos):
        if not t.e_mm:
            rows_ar.append({"Tramo": t.nombre, "e [mm]": None, "C [m/s]": None,
                            "ΔH [mca]": None, "Hd+ΔH [mca]": None,
                            "PN [mca]": None, "Cumple": "sin datos"})
            continue
        if t.cat_material:
            spec = pipes.pipe(t.cat_material, t.cat_serie, t.cat_dn)
            k_el, pn_t = spec.k_elast, spec.pn_mca
        else:
            k_el = k_elast_manual.get(t.material, 18.0)
            pn_t = num_input(f"PN del tramo manual '{t.nombre}' [mca]",
                             f"pn_{K}_{t.nombre}", 100.0, decimals=0,
                             min_value=0.0, max_value=600.0)
        c = pu.celeridad(t.D_mm / 1000, t.e_mm / 1000, k_el)
        dp = pu.sobrepresion_ariete(c, tr.V)
        total = r.hd + dp
        ok = total <= pn_t if pn_t else None
        if ok is False:
            fallan.append((t.nombre, total, pn_t))
        rows_ar.append({"Tramo": t.nombre, "e [mm]": t.e_mm, "C [m/s]": c,
                        "ΔH [mca]": dp, "Hd+ΔH [mca]": total,
                        "PN [mca]": pn_t or None,
                        "Cumple": "✓" if ok else ("✗ FALLA" if ok is False else "—")})
    st.dataframe(pd.DataFrame(rows_ar).style.format(
        {"e [mm]": "{:.1f}", "C [m/s]": "{:.1f}", "ΔH [mca]": "{:.1f}",
         "Hd+ΔH [mca]": "{:.1f}", "PN [mca]": "{:.0f}"}, na_rep="—"),
        hide_index=True, width="stretch")
    if fallan:
        lista = "; ".join(f"'{n}' ({tot:.1f} > PN {pn:.0f} mca)"
                          for n, tot, pn in fallan)
        st.error(f"Tramos que NO resisten la sobrepresión: {lista}.")
        st.warning("Opciones: subir la clase de presión (RDE menor) del tramo, o "
                   "incorporar protecciones contra transitorios: válvula de alivio "
                   "o anticipadora de onda, cámara de aire/tanque hidroneumático, "
                   "volante de inercia en la bomba, o válvula de cheque de cierre "
                   "controlado. Verificar con análisis transitorio detallado.")
    else:
        st.success("Todos los tramos con datos resisten Hd + sobrepresión de Joukowsky.")

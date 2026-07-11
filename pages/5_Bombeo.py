import pandas as pd
import streamlit as st
from core import catalogs, pipes, pumping as pu
from core.project import PumpSystemData, SegmentData, AccessoryData
from pages_common import get_project, num_input, show_issues

st.header("5 · Sistemas de bombeo")
p = get_project()
flows = st.session_state.get("flows")
if flows is None:
    st.info("Calcula primero los caudales en la página 3.")
    st.stop()

# ---------- selección / creación de sistema ----------
nombres = [s.nombre for s in p.bombeos]
sel = st.selectbox("Sistema de bombeo", nombres + ["➕ Nuevo sistema…"], key="w_sel_sys")
if sel == "➕ Nuevo sistema…":
    nuevo = st.text_input("Nombre del nuevo sistema (ej. 'Captación→T.Bajo', "
                          "'T.Bajo→T.Elevado')", key="w_txt_newsys")
    if st.button("Crear sistema") and nuevo:
        p.bombeos.append(PumpSystemData(nombre=nuevo))
        st.rerun()
    st.stop()
sys_d = next(s for s in p.bombeos if s.nombre == sel)
K = sys_d.nombre.replace(" ", "_")   # sufijo de keys por sistema

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

# ---------- tramos con catálogo normativo ----------
st.subheader("Tramos de tubería")
st.caption("Material/Serie/DN del catálogo normativo (RDE/clase) rellenan el diámetro "
           "interno y el espesor automáticamente. Material 'Manual' usa tus valores.")
mat_opts = ["Manual"] + pipes.materials()
serie_opts = sorted({s for m in pipes.materials() for s in pipes.series(m)})
ks_opts = list(catalogs.roughness().keys())
tramos_df = st.data_editor(pd.DataFrame(
    [{"Nombre": t.nombre, "Tipo": t.tipo, "L [m]": t.L,
      "Material": t.cat_material or "Manual", "Serie": t.cat_serie or "",
      "DN": t.cat_dn or None, "D interno [mm]": t.D_mm, "Espesor [mm]": t.e_mm or None,
      "Rugosidad (manual)": t.material}
     for t in sys_d.tramos] or
    [{"Nombre": "Impulsión 1", "Tipo": "impulsion", "L [m]": 100.0,
      "Material": "PEAD PE100", "Serie": "RDE 21", "DN": 90.0,
      "D interno [mm]": None, "Espesor [mm]": None, "Rugosidad (manual)": "PEAD"}]),
    num_rows="dynamic", width="stretch", key=f"w_ed_tramos_{K}",
    column_config={
        "Tipo": st.column_config.SelectboxColumn(options=["succion", "impulsion"]),
        "Material": st.column_config.SelectboxColumn(options=mat_opts),
        "Serie": st.column_config.SelectboxColumn(options=serie_opts),
        "Rugosidad (manual)": st.column_config.SelectboxColumn(options=ks_opts)})

sys_d.tramos = []
issues_cat = []
for _, r in tramos_df.iterrows():
    if not r["L [m]"]:
        continue
    nombre, mat = str(r["Nombre"]), str(r["Material"])
    if mat != "Manual":
        try:
            spec = pipes.pipe(mat, str(r["Serie"]), float(r["DN"]))
            sys_d.tramos.append(SegmentData(
                nombre, str(r["Tipo"]), float(r["L [m]"]), spec.id_mm,
                pipes.KS_KEY[mat], cat_material=mat, cat_serie=spec.serie,
                cat_dn=spec.dn, e_mm=spec.e_mm))
            continue
        except (KeyError, TypeError, ValueError):
            issues_cat.append(f"Tramo '{nombre}': combinación {mat}/{r['Serie']}/DN "
                              f"{r['DN']} no existe en el catálogo — usando modo manual.")
    if r["D interno [mm]"]:
        sys_d.tramos.append(SegmentData(
            nombre, str(r["Tipo"]), float(r["L [m]"]), float(r["D interno [mm]"]),
            str(r["Rugosidad (manual)"]), e_mm=float(r["Espesor [mm]"] or 0)))
    else:
        issues_cat.append(f"Tramo '{nombre}': sin catálogo válido ni D interno manual — omitido.")
show_issues(issues_cat)

# ---------- accesorios ----------
st.subheader("Accesorios")
tipos_km = list(catalogs.minor_loss_coefficients().keys())
nombres_tramos = [t.nombre for t in sys_d.tramos]
acc_df = st.data_editor(pd.DataFrame(
    [{"Accesorio": a.tipo, "Cantidad": a.cantidad, "Tramo": a.tramo}
     for a in sys_d.accesorios] or
    [{"Accesorio": "Válvula de cheque", "Cantidad": 1,
      "Tramo": nombres_tramos[0] if nombres_tramos else ""}]),
    num_rows="dynamic", width="stretch", key=f"w_ed_acc_{K}",
    column_config={
        "Accesorio": st.column_config.SelectboxColumn(options=tipos_km),
        "Tramo": st.column_config.SelectboxColumn(options=nombres_tramos)})
sys_d.accesorios = [AccessoryData(str(r["Accesorio"]), int(r["Cantidad"]), str(r["Tramo"]))
                    for _, r in acc_df.iterrows() if r["Cantidad"]]

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

# ---------- golpe de ariete (espesores del catálogo) ----------
with st.expander("Golpe de ariete (Joukowsky) — por tramo"):
    sys_d.pn_mca = num_input("PN de la tubería [mca]", f"pn_{K}", sys_d.pn_mca,
                             decimals=0, min_value=0.0, max_value=500.0)
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
    peor = max((row["Hd+ΔH [mca]"] or 0 for row in rows_ar), default=0)
    if sys_d.pn_mca and peor > sys_d.pn_mca:
        st.warning(f"Hd + sobrepresión ({peor:.1f} mca) supera la PN "
                   f"({sys_d.pn_mca:.0f} mca) — revisar clase o protecciones.")

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

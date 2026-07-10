import pandas as pd
import streamlit as st
from core import catalogs, pumping as pu
from core.project import SegmentData, AccessoryData
from pages_common import get_project, show_issues

st.header("5 · Sistema de bombeo (multi-tramo)")
p = get_project()
flows = st.session_state.get("flows")
if flows is None:
    st.info("Calcula primero los caudales en la página 3.")
    st.stop()

c1, c2, c3, c4 = st.columns(4)
p.bombeo.horas = c1.number_input("Horas de bombeo/día", 1.0, 24.0, p.bombeo.horas)
p.bombeo.he = c2.number_input("Altura estática total [m]", 0.0, 1000.0, p.bombeo.he)
p.bombeo.sumar_5m_ras = c3.checkbox("+5 m (RAS Título B 9.4.11)", p.bombeo.sumar_5m_ras)
p.bombeo.eficiencia = c4.number_input("Eficiencia η", 0.05, 1.0, p.bombeo.eficiencia)
qb_lps = pu.q_bombeo(flows.qmd_lps, p.bombeo.horas)
st.metric("Caudal de bombeo", f"{qb_lps:.3f} L/s")
st.caption(f"Diámetro económico Bresse (referencia): continuo "
           f"{pu.bresse_continuo(qb_lps/1000)*1000:.1f} mm · no continuo "
           f"{pu.bresse_no_continuo(qb_lps/1000, p.bombeo.horas)*1000:.1f} mm")

st.subheader("Tramos de tubería")
st.caption("Agrega tantos tramos como cambios de diámetro/material tengas.")
materiales = list(catalogs.roughness().keys())
tramos_df = st.data_editor(pd.DataFrame(
    [{"Nombre": t.nombre, "Tipo": t.tipo, "L [m]": t.L, "D interno [mm]": t.D_mm,
      "Material": t.material} for t in p.tramos] or
    [{"Nombre": "Impulsión 1", "Tipo": "impulsion", "L [m]": 100.0,
      "D interno [mm]": 79.5, "Material": "PEAD"}]),
    num_rows="dynamic", width="stretch",
    column_config={
        "Tipo": st.column_config.SelectboxColumn(options=["succion", "impulsion"]),
        "Material": st.column_config.SelectboxColumn(options=materiales)})
p.tramos = [SegmentData(str(r["Nombre"]), str(r["Tipo"]), float(r["L [m]"]),
                        float(r["D interno [mm]"]), str(r["Material"]))
            for _, r in tramos_df.iterrows() if r["L [m]"] and r["D interno [mm]"]]

st.subheader("Accesorios")
tipos_km = list(catalogs.minor_loss_coefficients().keys())
nombres_tramos = [t.nombre for t in p.tramos]
acc_df = st.data_editor(pd.DataFrame(
    [{"Accesorio": a.tipo, "Cantidad": a.cantidad, "Tramo": a.tramo}
     for a in p.accesorios] or
    [{"Accesorio": "Válvula de cheque", "Cantidad": 1,
      "Tramo": nombres_tramos[0] if nombres_tramos else ""}]),
    num_rows="dynamic", width="stretch",
    column_config={
        "Accesorio": st.column_config.SelectboxColumn(options=tipos_km),
        "Tramo": st.column_config.SelectboxColumn(options=nombres_tramos)})
p.accesorios = [AccessoryData(str(r["Accesorio"]), int(r["Cantidad"]), str(r["Tramo"]))
                for _, r in acc_df.iterrows() if r["Cantidad"]]

if p.tramos:
    he = p.bombeo.he + (5.0 if p.bombeo.sumar_5m_ras else 0.0)
    sistema = pu.PumpSystem(
        tramos=[pu.Segment(t.nombre, t.tipo, t.L, t.D_mm / 1000, t.material)
                for t in p.tramos],
        accesorios=[pu.Accessory(a.tipo, a.cantidad, a.tramo) for a in p.accesorios],
        he=he, temperatura=p.temperatura, eficiencia=p.bombeo.eficiencia)
    r = pu.solve(sistema, qb_lps / 1000)
    show_issues(r.issues)
    st.subheader("Pérdidas por tramo (acumuladas)")
    st.dataframe(pd.DataFrame(
        [{"Tramo": t.segment.nombre, "V [m/s]": t.V, "Re": t.Re, "f": t.f,
          "hf [m]": t.hf, "ΣKm": t.sum_km, "hl [m]": t.hl} for t in r.tramos])
        .style.format({"V [m/s]": "{:.3f}", "Re": "{:,.0f}", "f": "{:.5f}",
                       "hf [m]": "{:.3f}", "ΣKm": "{:.1f}", "hl [m]": "{:.3f}"}),
        width="stretch")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Σ pérdidas", f"{r.hf_total + r.hl_total:.2f} m")
    m2.metric("Altura dinámica Hd", f"{r.hd:.2f} m")
    m3.metric("Potencia", f"{r.potencia_kw:.2f} kW")
    m4.metric("Potencia", f"{r.potencia_hp:.2f} HP")
    st.info(f"Bomba mínima requerida: **Q = {qb_lps:.1f} L/s · H = {r.hd:.0f} m · "
            f"P = {r.potencia_hp:.1f} HP**")
    st.session_state["pump_solve"] = r
    st.session_state["pump_system"] = sistema
    st.session_state["qb_lps"] = qb_lps

    with st.expander("Golpe de ariete (Joukowsky)"):
        cc1, cc2, cc3 = st.columns(3)
        p.bombeo.espesor_mm = cc1.number_input("Espesor tubería [mm]", 0.1, 100.0,
                                               p.bombeo.espesor_mm or 5.3)
        p.bombeo.k_elast = cc2.number_input("K elasticidad (PVC 18, PEAD 111.11, Acero 0.5)",
                                            0.1, 200.0, p.bombeo.k_elast)
        p.bombeo.pn_mca = cc3.number_input("PN de la tubería [mca]", 0.0, 500.0, p.bombeo.pn_mca)
        tramo_crit = r.tramos[0]
        c = pu.celeridad(tramo_crit.segment.D, p.bombeo.espesor_mm / 1000, p.bombeo.k_elast)
        dp = pu.sobrepresion_ariete(c, tramo_crit.V)
        st.write(f"Celeridad **{c:.1f} m/s** · Sobrepresión **{dp:.1f} mca** · "
                 f"Presión total {r.hd + dp:.1f} mca")
        if p.bombeo.pn_mca and r.hd + dp > p.bombeo.pn_mca:
            st.warning("Hd + sobrepresión supera la PN de la tubería — revisar clase o protecciones")

    with st.expander("Paneles solares (pre-cálculo)"):
        pc1, pc2, pc3 = st.columns(3)
        p.bombeo.panel_w = pc1.number_input("Potencia panel [W]", 100.0, 1500.0, p.bombeo.panel_w)
        p.bombeo.panel_fs = pc2.number_input("Factor de seguridad", 1.0, 5.0, p.bombeo.panel_fs)
        p.bombeo.panel_area = pc3.number_input("Área panel [m²]", 0.5, 5.0, p.bombeo.panel_area)
        pan = pu.paneles_solares(r.potencia_kw, p.bombeo.panel_w, p.bombeo.panel_fs,
                                 p.bombeo.panel_area)
        st.write(f"**{pan.cantidad} paneles** · área total {pan.area_total:.1f} m²")

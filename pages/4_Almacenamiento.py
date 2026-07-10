import pandas as pd
import streamlit as st
from core import storage
from pages_common import get_project

st.header("4 · Almacenamiento")
p = get_project()
flows = st.session_state.get("flows")
if flows is None:
    st.info("Calcula primero los caudales en la página 3.")
    st.stop()
qmd_m3d = flows.qmd_lps * 86.4

c1, c2, c3 = st.columns(3)
p.almacenamiento.frac_regulacion = c1.number_input(
    "Fracción de regulación (Art. 81)", 0.1, 1.0, p.almacenamiento.frac_regulacion)
p.almacenamiento.frac_incendio = c2.number_input(
    "Afectación incendio [%] (NSR-10 J)", 0.0, 100.0,
    p.almacenamiento.frac_incendio * 100) / 100
p.almacenamiento.dias_reserva = c3.number_input(
    "Días de reserva", 0.5, 5.0, p.almacenamiento.dias_reserva)

st.subheader("Patrón horario (curva integral)")
DEFAULT_F = [0.6,0.7,0.8,0.9,1,1.2,1.6,1.2,1,1.1,1.1,1.2,1.1,1.1,1,1.1,1.2,1.1,0.9,0.9,0.9,0.8,0.8,0.7]
if not p.almacenamiento.factores_hora:
    p.almacenamiento.factores_hora = DEFAULT_F
    p.almacenamiento.suministro_hora = [1 if 5 <= h <= 14 else 0 for h in range(24)]
df = st.data_editor(pd.DataFrame({
    "Hora": list(range(24)),
    "Factor consumo": p.almacenamiento.factores_hora,
    "Suministro (1/0)": p.almacenamiento.suministro_hora,
}), hide_index=True, width="stretch")
p.almacenamiento.factores_hora = [float(x) for x in df["Factor consumo"]]
p.almacenamiento.suministro_hora = [int(x) for x in df["Suministro (1/0)"]]

a = storage.volume_art81(qmd_m3d, p.almacenamiento.frac_regulacion,
                         p.almacenamiento.frac_incendio, p.almacenamiento.dias_reserva)
try:
    b = storage.volume_curva_integral(qmd_m3d, p.almacenamiento.factores_hora,
                                      p.almacenamiento.suministro_hora,
                                      p.almacenamiento.frac_incendio,
                                      p.almacenamiento.dias_reserva)
except ValueError as e:
    st.error(str(e)); st.stop()

st.session_state["v_art81"] = a.v_total_redondeado
st.session_state["v_curva"] = b.v_total_redondeado

st.subheader("Resultados")
res = pd.DataFrame([
    ["Regulación [m³]", a.v_regulacion, b.v_regulacion],
    ["Incendio [m³]", a.v_incendio, b.v_incendio],
    ["Total [m³]", a.v_total, b.v_total],
    ["Redondeado (múltiplo 5) [m³]", a.v_total_redondeado, b.v_total_redondeado],
], columns=["Concepto", "Art. 81", "Curva integral"])
st.dataframe(res.style.format({"Art. 81": "{:.2f}", "Curva integral": "{:.2f}"}),
             width="stretch")
v_final = storage.final_volume(a, b)
st.metric("Volumen de almacenamiento adoptado", f"{v_final} m³")
st.session_state["v_almacenamiento"] = v_final

st.subheader("Predimensionado de tanque")
c4, c5 = st.columns(2)
vol = c4.number_input("Volumen del tanque [m³]", 1.0, 10000.0, float(v_final))
alt = c5.number_input("Altura útil [m]", 1.0, 10.0, 2.5)
t = storage.tank_dimensions(vol, alt)
st.write(f"Cilíndrico: Ø **{t.diametro:.2f} m** · Planta cuadrada: lado **{t.lado:.2f} m** "
         f"(+0.30 m de borde libre para el dimensionamiento estructural)")

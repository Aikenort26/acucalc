import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from core import storage
from core.project import TankSpec
from pages_common import page_setup, num_input

p = page_setup()
st.header("4 · Almacenamiento")
cfg = p.almacenamiento
flows = st.session_state.get("flows")
if flows is None:
    st.info("Calcula primero los caudales en la página 3.")
    st.stop()
qmd_m3d = flows.qmd_lps * 86.4

c1, c2 = st.columns(2)
cfg.frac_incendio = num_input("Afectación incendio [%] (NSR-10 J)", "incendio",
                              cfg.frac_incendio * 100, decimals=1, container=c1,
                              min_value=0.0, max_value=100.0) / 100
cfg.dias_reserva = num_input("Días de reserva", "reserva", cfg.dias_reserva,
                             decimals=1, container=c2, min_value=0.5, max_value=5.0)

# ---------- patrones horarios ----------
st.subheader("Patrones horarios")
DEFAULT_F = [0.6,0.7,0.8,0.9,1,1.2,1.6,1.2,1,1.1,1.1,1.2,1.1,1.1,1,1.1,1.2,1.1,0.9,0.9,0.9,0.8,0.8,0.7]
if not cfg.factores_hora:
    cfg.factores_hora = DEFAULT_F
    cfg.suministro_hora = [1 if 5 <= h <= 14 else 0 for h in range(24)]
if not cfg.ventana_captacion:
    cfg.ventana_captacion = [1] * 24

with st.expander("Cargar patrones desde Excel/CSV"):
    st.caption("Columnas requeridas: `Hora` (0-23), `Factor consumo`, `Suministro` (1/0). "
               "Opcional: `Captacion` (1/0). Exactamente 24 filas.")
    up = st.file_uploader("Archivo de patrones", type=["xlsx", "csv"])
    if up is not None:
        try:
            df_up = (pd.read_excel(up) if up.name.endswith("xlsx") else pd.read_csv(up))
            df_up.columns = [str(c).strip().lower() for c in df_up.columns]
            req = {"hora", "factor consumo", "suministro"}
            if not req <= set(df_up.columns):
                st.error(f"Faltan columnas: {req - set(df_up.columns)}")
            elif len(df_up) != 24:
                st.error(f"Se requieren exactamente 24 filas (hay {len(df_up)})")
            else:
                df_up = df_up.sort_values("hora")
                cfg.factores_hora = [float(x) for x in df_up["factor consumo"]]
                cfg.suministro_hora = [int(x) for x in df_up["suministro"]]
                if "captacion" in df_up.columns:
                    cfg.ventana_captacion = [int(x) for x in df_up["captacion"]]
                st.success("Patrones cargados.")
        except Exception as e:
            st.error(f"No se pudo leer el archivo: {e}")

df_pat = st.data_editor(pd.DataFrame({
    "Hora": list(range(24)),
    "Factor consumo": cfg.factores_hora,
    "Bombeo (1/0)": cfg.suministro_hora,
    "Captación (1/0)": cfg.ventana_captacion,
}), hide_index=True, width="stretch", key="w_ed_patrones")
cfg.factores_hora = [float(x) for x in df_pat["Factor consumo"]]
cfg.suministro_hora = [int(x) for x in df_pat["Bombeo (1/0)"]]
cfg.ventana_captacion = [int(x) for x in df_pat["Captación (1/0)"]]

# ---------- cálculo ----------
cfg.usar_cadena = st.toggle("Cadena de tanques (captación → tanque bajo → bombeo → "
                            "tanque elevado → red)", value=cfg.usar_cadena)
try:
    if cfg.usar_cadena:
        chain = storage.tank_chain(qmd_m3d, cfg.factores_hora, cfg.ventana_captacion,
                                   cfg.suministro_hora, cfg.frac_incendio, cfg.dias_reserva)
        resultados = [("Tanque bajo", chain.bajo), ("Tanque elevado", chain.elevado)]
        v_final = chain.total_redondeado
    else:
        cfg.frac_regulacion = num_input("Fracción de regulación (Art. 81)", "fracreg",
                                        cfg.frac_regulacion, decimals=3,
                                        min_value=0.1, max_value=1.0)
        a = storage.volume_art81(qmd_m3d, cfg.frac_regulacion,
                                 cfg.frac_incendio, cfg.dias_reserva)
        b = storage.volume_curva_integral(qmd_m3d, cfg.factores_hora, cfg.suministro_hora,
                                          cfg.frac_incendio, cfg.dias_reserva)
        resultados = [("Art. 81", a), ("Curva integral", b)]
        v_final = storage.final_volume(a, b)
except ValueError as e:
    st.error(str(e)); st.stop()

st.subheader("Resultados")
st.dataframe(pd.DataFrame(
    [{"Concepto": nombre, "Fracción regulación": r.frac_regulacion,
      "Regulación [m³]": r.v_regulacion, "Incendio [m³]": r.v_incendio,
      "Total [m³]": r.v_total, "Redondeado [m³]": r.v_total_redondeado}
     for nombre, r in resultados])
    .style.format({"Fracción regulación": "{:.4f}", "Regulación [m³]": "{:.2f}",
                   "Incendio [m³]": "{:.2f}", "Total [m³]": "{:.2f}"}, na_rep="—"),
    hide_index=True, width="stretch")
st.metric("Volumen de almacenamiento adoptado", f"{v_final} m³")
st.session_state["v_almacenamiento"] = v_final
st.session_state["v_art81"] = resultados[0][1].v_total_redondeado
st.session_state["v_curva"] = resultados[-1][1].v_total_redondeado

# ---------- curvas consumo vs suministro por tanque ----------
if cfg.usar_cadena:
    st.subheader("Curvas de consumo vs suministro (acumuladas)")
    capta = [x / sum(cfg.ventana_captacion) for x in cfg.ventana_captacion]
    bombeo = [x / sum(cfg.suministro_hora) for x in cfg.suministro_hora]
    consumo = [x / sum(cfg.factores_hora) for x in cfg.factores_hora]

    def _acum(v):
        out, s = [], 0.0
        for x in v:
            s += x
            out.append(s)
        return out

    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    horas = list(range(24))
    axes[0].plot(horas, _acum(capta), label="Suministro (captación)")
    axes[0].plot(horas, _acum(bombeo), label="Consumo (bombeo)")
    axes[0].set_title("Tanque bajo"); axes[0].legend(); axes[0].grid(alpha=0.3)
    axes[1].plot(horas, _acum(bombeo), label="Suministro (bombeo)")
    axes[1].plot(horas, _acum(consumo), label="Consumo (población)")
    axes[1].set_title("Tanque elevado"); axes[1].legend(); axes[1].grid(alpha=0.3)
    for ax in axes:
        ax.set_xlabel("Hora"); ax.set_ylabel("Fracción acumulada del día")
    st.pyplot(fig)
    plt.close(fig)

# ---------- predimensionado por tanque ----------
st.subheader("Predimensionado de tanques")
if not cfg.tanques:
    if cfg.usar_cadena:
        cfg.tanques = [
            TankSpec("Tanque bajo", "bajo", "rectangular",
                     float(resultados[0][1].v_total_redondeado), 2.5, 1.5),
            TankSpec("Tanque elevado", "elevado", "circular",
                     float(resultados[1][1].v_total_redondeado), 2.5, 1.0),
        ]
    else:
        cfg.tanques = [TankSpec("Tanque único", "bajo", "circular", float(v_final), 2.5, 1.0)]

df_tk = st.data_editor(pd.DataFrame(
    [{"Nombre": t.nombre, "Tipo": t.tipo, "Forma": t.forma,
      "Volumen [m³]": t.volumen, "Altura útil [m]": t.altura,
      "Relación largo/ancho": t.ratio} for t in cfg.tanques]),
    num_rows="dynamic", width="stretch", key="w_ed_tanques",
    column_config={
        "Tipo": st.column_config.SelectboxColumn(options=["bajo", "elevado"]),
        "Forma": st.column_config.SelectboxColumn(
            options=["circular", "cuadrado", "rectangular"])})
cfg.tanques = [TankSpec(str(r["Nombre"]), str(r["Tipo"]), str(r["Forma"]),
                        float(r["Volumen [m³]"]), float(r["Altura útil [m]"]),
                        float(r["Relación largo/ancho"] or 1.0))
               for _, r in df_tk.iterrows() if r["Volumen [m³]"]]

dims_rows = []
for t in cfg.tanques:
    d = storage.tank_dimensions(t.volumen, t.altura, t.ratio)
    if t.forma == "circular":
        dim = f"Ø {d.diametro:.2f} m"
    elif t.forma == "cuadrado":
        dim = f"lado {d.lado:.2f} m"
    else:
        dim = f"{d.ancho:.2f} × {d.largo:.2f} m"
    dims_rows.append({"Tanque": t.nombre, "Tipo": t.tipo, "Forma": t.forma,
                      "Volumen [m³]": t.volumen, "Altura [m]": t.altura,
                      "Dimensiones": dim})
st.dataframe(pd.DataFrame(dims_rows), hide_index=True, width="stretch")
st.caption("Añadir 0.30 m de borde libre para el dimensionamiento estructural "
           "(volúmenes indicados = volumen útil de líquido).")

suma_tk = sum(t.volumen for t in cfg.tanques)
if abs(suma_tk - v_final) > 0.5:
    st.warning(f"La suma de los tanques ({suma_tk:.0f} m³) difiere del volumen "
               f"adoptado ({v_final} m³) — ajusta el reparto.")
if cfg.usar_cadena:
    minimos = {"bajo": resultados[0][1].v_total_redondeado,
               "elevado": resultados[1][1].v_total_redondeado}
    for t in cfg.tanques:
        if t.volumen + 0.5 < minimos.get(t.tipo, 0):
            st.warning(f"'{t.nombre}' ({t.volumen:.0f} m³) queda por debajo del mínimo "
                       f"de su balance ({minimos[t.tipo]} m³ para tanque {t.tipo}).")

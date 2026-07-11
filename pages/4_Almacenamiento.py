import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from core import report_figs as rf, storage
from core.project import TankSpec
from pages_common import get_project, num_input, page_setup

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

# ---------- patrón de consumo de la población ----------
st.subheader("Patrón horario de consumo de la población")
DEFAULT_F = [0.6,0.7,0.8,0.9,1,1.2,1.6,1.2,1,1.1,1.1,1.2,1.1,1.1,1,1.1,1.2,1.1,0.9,0.9,0.9,0.8,0.8,0.7]
if not cfg.factores_hora:
    cfg.factores_hora = DEFAULT_F
with st.expander("Cargar patrón desde Excel/CSV"):
    st.caption("Columnas requeridas: `Hora` (0-23) y `Factor consumo`. 24 filas.")
    up = st.file_uploader("Archivo de patrón", type=["xlsx", "csv"])
    if up is not None:
        try:
            df_up = (pd.read_excel(up) if up.name.endswith("xlsx") else pd.read_csv(up))
            df_up.columns = [str(c).strip().lower() for c in df_up.columns]
            if not {"hora", "factor consumo"} <= set(df_up.columns):
                st.error("Faltan columnas Hora / Factor consumo")
            elif len(df_up) != 24:
                st.error(f"Se requieren exactamente 24 filas (hay {len(df_up)})")
            else:
                cfg.factores_hora = [float(x) for x in
                                     df_up.sort_values("hora")["factor consumo"]]
                st.success("Patrón cargado.")
        except Exception as e:
            st.error(f"No se pudo leer el archivo: {e}")
df_pat = st.data_editor(pd.DataFrame({"Hora": list(range(24)),
                                      "Factor consumo": cfg.factores_hora}),
                        hide_index=True, width="stretch", key="w_ed_patron")
cfg.factores_hora = [float(x) for x in df_pat["Factor consumo"]]

# ---------- modo ----------
cfg.usar_cadena = st.toggle("Tren de tanques en serie (captación → … → red)",
                            value=cfg.usar_cadena)

if not cfg.usar_cadena:
    # ---------- modo tanque único (Art. 81 + curva integral) ----------
    if not cfg.suministro_hora:
        cfg.suministro_hora = [1 if 5 <= h <= 14 else 0 for h in range(24)]
    st.caption("Ventana de suministro al tanque (horas con 1):")
    df_su = st.data_editor(pd.DataFrame({"Hora": list(range(24)),
                                         "Suministro (1/0)": cfg.suministro_hora}),
                           hide_index=True, width="stretch", key="w_ed_sum")
    cfg.suministro_hora = [int(x) for x in df_su["Suministro (1/0)"]]
    cfg.frac_regulacion = num_input("Fracción de regulación (Art. 81)", "fracreg",
                                    cfg.frac_regulacion, decimals=3,
                                    min_value=0.1, max_value=1.0)
    try:
        a = storage.volume_art81(qmd_m3d, cfg.frac_regulacion,
                                 cfg.frac_incendio, cfg.dias_reserva)
        b = storage.volume_curva_integral(qmd_m3d, cfg.factores_hora,
                                          cfg.suministro_hora,
                                          cfg.frac_incendio, cfg.dias_reserva)
    except ValueError as e:
        st.error(str(e)); st.stop()
    st.dataframe(pd.DataFrame(
        [{"Concepto": n, "Fracción": r0.frac_regulacion, "Regulación [m³]": r0.v_regulacion,
          "Incendio [m³]": r0.v_incendio, "Total [m³]": r0.v_total,
          "Redondeado [m³]": r0.v_total_redondeado}
         for n, r0 in (("Art. 81", a), ("Curva integral", b))])
        .style.format(precision=2, na_rep="—"), hide_index=True, width="stretch")
    v_final = storage.final_volume(a, b)
    if not cfg.tanques:
        cfg.tanques = [TankSpec("Tanque único", "bajo", "circular", float(v_final), 2.5)]
else:
    # ---------- tren de N tanques ----------
    st.subheader("Tren de tanques (en orden hidráulico)")
    st.caption("Cada tanque define la **ventana de entrada** (horas del bombeo o "
               "gravedad que lo alimenta). Su salida es la entrada del siguiente "
               "tanque; la salida del último es el consumo de la población.")
    if not cfg.tanques:
        cfg.tanques = [
            TankSpec("Tanque bajo", "bajo", "rectangular", 0, 2.5, 1.5, 5, 14),
            TankSpec("Tanque elevado", "elevado", "circular", 0, 2.5, 1.0, 6, 15),
        ]
    df_tk = st.data_editor(pd.DataFrame(
        [{"Orden": i + 1, "Nombre": t.nombre, "Tipo": t.tipo, "Forma": t.forma,
          "Altura útil [m]": t.altura, "Largo/ancho": t.ratio,
          "Entrada desde [h]": t.entrada_ini, "Entrada hasta [h]": t.entrada_fin}
         for i, t in enumerate(cfg.tanques)]),
        num_rows="dynamic", width="stretch", key="w_ed_tren",
        column_config={
            "Tipo": st.column_config.SelectboxColumn(options=["bajo", "elevado"]),
            "Forma": st.column_config.SelectboxColumn(
                options=["circular", "cuadrado", "rectangular"]),
            "Entrada desde [h]": st.column_config.NumberColumn(min_value=0, max_value=23),
            "Entrada hasta [h]": st.column_config.NumberColumn(min_value=0, max_value=23)})
    volumenes_previos = {t.nombre: t.volumen for t in cfg.tanques}
    cfg.tanques = [TankSpec(str(r["Nombre"]), str(r["Tipo"]), str(r["Forma"]),
                            volumenes_previos.get(str(r["Nombre"]), 0.0),
                            float(r["Altura útil [m]"] or 2.5),
                            float(r["Largo/ancho"] or 1.0),
                            int(r["Entrada desde [h]"] or 0),
                            int(r["Entrada hasta [h]"] or 23))
                   for _, r in df_tk.sort_values("Orden").iterrows() if r["Nombre"]]

    if not cfg.tanques:
        st.info("Agrega al menos un tanque.")
        st.stop()
    try:
        tren = storage.tank_train(qmd_m3d,
                                  [(t.nombre, t.entrada_flags()) for t in cfg.tanques],
                                  cfg.factores_hora, cfg.frac_incendio, cfg.dias_reserva)
    except ValueError as e:
        st.error(str(e)); st.stop()

    # asignación automática del volumen redondeado a cada tanque
    for t, bal in zip(cfg.tanques, tren):
        t.volumen = float(bal.v_total_redondeado)

    st.subheader("Regulación por tanque (volúmenes asignados automáticamente)")
    st.dataframe(pd.DataFrame(
        [{"Tanque": b.nombre, "Entrada [h/día]": b.horas_entrada,
          "Q entrada [L/s]": b.q_entrada_lps, "Fracción regulación": b.frac_regulacion,
          "Regulación [m³]": b.v_regulacion, "Incendio [m³]": b.v_incendio,
          "V asignado [m³]": b.v_total_redondeado} for b in tren])
        .style.format({"Q entrada [L/s]": "{:.2f}", "Fracción regulación": "{:.4f}",
                       "Regulación [m³]": "{:.2f}", "Incendio [m³]": "{:.2f}",
                       "Entrada [h/día]": "{:.0f}"}),
        hide_index=True, width="stretch")
    st.caption("El Q de entrada de cada tanque es el caudal del bombeo que lo alimenta "
               "(QMD·24/h de su ventana) — sincronizable en la página 5.")
    v_final = sum(b.v_total_redondeado for b in tren)
    st.session_state["tank_train"] = tren

    # gráfica de balance por tanque
    pares = []
    for i, t in enumerate(cfg.tanques):
        salida = (cfg.tanques[i + 1].entrada_flags() if i + 1 < len(cfg.tanques)
                  else cfg.factores_hora)
        pares.append((t.nombre, t.entrada_flags(), salida))
    with plt.style.context("dark_background"):
        fig = rf.fig_balance_train(pares)
        fig.patch.set_alpha(0)
        for ax in fig.axes:
            ax.set_facecolor("none")
        st.pyplot(fig)
        plt.close(fig)

st.metric("Volumen total de almacenamiento", f"{v_final:.0f} m³")
st.session_state["v_almacenamiento"] = v_final

# ---------- predimensionado ----------
st.subheader("Predimensionado de tanques")
dims_rows = []
for t in cfg.tanques:
    d = storage.tank_dimensions(t.volumen or 1.0, t.altura, t.ratio)
    dim = (f"Ø {d.diametro:.2f} m" if t.forma == "circular"
           else f"lado {d.lado:.2f} m" if t.forma == "cuadrado"
           else f"{d.ancho:.2f} × {d.largo:.2f} m")
    dims_rows.append({"Tanque": t.nombre, "Tipo": t.tipo, "Forma": t.forma,
                      "Volumen [m³]": t.volumen, "Altura [m]": t.altura,
                      "Dimensiones": dim})
st.dataframe(pd.DataFrame(dims_rows), hide_index=True, width="stretch")
st.caption("Añadir 0.30 m de borde libre (volúmenes = volumen útil de líquido).")

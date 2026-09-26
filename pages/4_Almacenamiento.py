import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from core import catalogs, pipeline, report_figs as rf, storage, tank_network as tn
from core.project import EnlaceSpec, TankSpec, ZonaSpec
from pages_common import (SP_ALTURA, SP_VOLUMEN, editor_commit, editor_seed,
                          f_num, fila_incompleta, fmt_vol, get_project, i_num,
                          num_input, page_setup, s_txt, sel_state)

p = page_setup()
st.header("4 · Almacenamiento")
cfg = p.almacenamiento
_diseno = pipeline.design_flows(p)
if _diseno is None:
    st.info("Completa primero Población (censo, población base y método) y "
            "Caudales (dotación neta).")
    st.stop()
flows = _diseno.flows
qmd_m3d = flows.qmd_lps * 86.4

# ---------- nivel de riesgo contra incendio (catálogo, WP-2b) ----------
riesgo_niveles = catalogs.riesgo_incendio()["niveles"]
opciones_riesgo = list(riesgo_niveles.keys())   # bajo, medio, alto, personalizado


def _label_riesgo(n: str) -> str:
    fr = riesgo_niveles[n]["frac"]
    return f"{n.capitalize()} ({fr * 100:.0f}%)" if fr is not None else "Personalizado"


c1, c2 = st.columns(2)
# "" (legado, proyectos sin nivel_riesgo) → personalizado, conservando su frac.
k_riesgo = sel_state(opciones_riesgo, "nivel_riesgo",
                     cfg.nivel_riesgo or "personalizado")
cfg.nivel_riesgo = c1.selectbox(
    "Nivel de riesgo contra incendio (NSR-10 Título J · Art. 81 Res. 0330/2017)",
    opciones_riesgo, format_func=_label_riesgo, key=k_riesgo)
if cfg.nivel_riesgo == "personalizado":
    cfg.frac_incendio = num_input("Afectación incendio [%]", "incendio",
                                  cfg.frac_incendio * 100, decimals=1, container=c1,
                                  min_value=0.0, max_value=100.0) / 100
else:
    cfg.frac_incendio = riesgo_niveles[cfg.nivel_riesgo]["frac"]
    c1.caption(f"{cfg.frac_incendio * 100:.0f}% — {riesgo_niveles[cfg.nivel_riesgo]['nota']}")
cfg.dias_reserva = num_input("Días de reserva", "reserva", cfg.dias_reserva,
                             decimals=1, container=c2, min_value=0.5, max_value=5.0)

# ---------- patrón de consumo de la población ----------
st.subheader("Patrón horario de consumo de la población")
if not cfg.factores_hora:
    cfg.factores_hora = list(storage.DEFAULT_PATTERN)
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
                cfg.factores_hora = [f_num(x, 1.0) for x in
                                     df_up.sort_values("hora")["factor consumo"]]
                st.success("Patrón cargado.")
        except Exception as e:
            st.error(f"No se pudo leer el archivo: {e}")
seed_pat = editor_seed("patron", lambda: pd.DataFrame(
    {"Hora": list(range(24)), "Factor consumo": cfg.factores_hora}))
df_pat = st.data_editor(st.session_state[seed_pat],
                        hide_index=True, width="stretch", key="w_ed_patron")
editor_commit(seed_pat, df_pat)
cfg.factores_hora = [f_num(x, 1.0) for x in df_pat["Factor consumo"]]

# ========== Sección 1 · Volumen total por norma ==========
st.subheader("1 · Volumen total por norma")
if not cfg.suministro_hora:
    cfg.suministro_hora = [1 if 5 <= h <= 14 else 0 for h in range(24)]
st.caption("Ventana de suministro de la comunidad (horas de entrada al sistema, 1/0). "
           "La curva integral compara este suministro contra el patrón de consumo.")
seed_su = editor_seed("suministro", lambda: pd.DataFrame(
    {"Hora": list(range(24)), "Suministro (1/0)": cfg.suministro_hora}))
df_su = st.data_editor(st.session_state[seed_su],
                       hide_index=True, width="stretch", key="w_ed_sum")
editor_commit(seed_su, df_su)
cfg.suministro_hora = [1 if i_num(x, 0) else 0 for x in df_su["Suministro (1/0)"]]
cfg.frac_regulacion = num_input("Fracción de regulación (criterio QMD/3, Art. 81)",
                                "fracreg", cfg.frac_regulacion, decimals=3,
                                min_value=0.1, max_value=1.0)
try:
    a = storage.volume_art81(qmd_m3d, cfg.frac_regulacion,
                             cfg.frac_incendio, cfg.dias_reserva)
    b = storage.volume_curva_integral(qmd_m3d, cfg.factores_hora,
                                      cfg.suministro_hora,
                                      cfg.frac_incendio, cfg.dias_reserva)
except ValueError as e:
    st.error(str(e)); st.stop()
v_norma = storage.final_volume(a, b)
gobierna = "Art. 81 (QMD/3)" if a.v_total_redondeado >= b.v_total_redondeado else "Curva integral"
st.dataframe(pd.DataFrame(
    [{"Criterio": n, "Fracción": r0.frac_regulacion, "Regulación [m³]": r0.v_regulacion,
      "Incendio [m³]": r0.v_incendio, "Total [m³]": r0.v_total,
      "Redondeado [m³]": r0.v_total_redondeado,
      "Gobierna": "◄" if r0.v_total_redondeado == v_norma else ""}
     for n, r0 in (("Art. 81 (QMD/3)", a), ("Curva integral", b))])
    .style.format({"Fracción": "{:.4f}", "Regulación [m³]": SP_VOLUMEN,
                   "Incendio [m³]": SP_VOLUMEN, "Total [m³]": SP_VOLUMEN,
                   "Redondeado [m³]": "{:.0f}"}, na_rep="—"),
    hide_index=True, width="stretch")
st.metric("Volumen total por norma (gobernante)", f"{v_norma:.0f} m³",
          help=f"Máximo entre los dos criterios. Gobierna: {gobierna}.")
fig = rf.fig_balance_train([("Comunidad", cfg.suministro_hora, cfg.factores_hora)], dark=True)
st.pyplot(fig)
plt.close(fig)

st.session_state["v_almacenamiento"] = v_norma

# ========== Sección 2 · Tanques (el usuario define todo) ==========
st.subheader("2 · Tanques")
st.caption("Define cada tanque: tipo, forma, unidades, geometría, el **volumen que "
           "le asignas**, y sus ventanas de **suministro** (entrada) y **salida** "
           "(consumo/bombeo hacia adelante). La app dimensiona la geometría y verifica; "
           "no reparte automáticamente.")
if not cfg.tanques:
    cfg.tanques = [TankSpec("Tanque 1", "elevado", "circular", float(v_norma), 2.5,
                            entrada_ini=5, entrada_fin=14, salida_ini=6, salida_fin=22)]
seed_tk = editor_seed("tanques", lambda: pd.DataFrame(
    [{"Nombre": t.nombre, "Tipo constructivo": t.tipo_constructivo, "Forma": t.forma,
      "Cantidad": t.cantidad, "Altura útil [m]": t.altura, "Largo/ancho": t.ratio,
      "Volumen asignado [m³]": t.volumen,
      "Suministro desde [h]": t.entrada_ini, "Suministro hasta [h]": t.entrada_fin,
      "Salida desde [h]": t.salida_ini, "Salida hasta [h]": t.salida_fin,
      "Borde libre [m]": t.borde_libre}
     for t in cfg.tanques]))
df_tk = st.data_editor(st.session_state[seed_tk],
    num_rows="dynamic", width="stretch", key="w_ed_tanques",
    column_config={
        "Tipo constructivo": st.column_config.SelectboxColumn(
            options=["superficial", "enterrado", "semienterrado", "elevado"]),
        "Forma": st.column_config.SelectboxColumn(
            options=["circular", "cuadrado", "rectangular"]),
        "Cantidad": st.column_config.NumberColumn(min_value=1, max_value=20, step=1),
        "Volumen asignado [m³]": st.column_config.NumberColumn(min_value=0.0),
        "Suministro desde [h]": st.column_config.NumberColumn(min_value=0, max_value=23),
        "Suministro hasta [h]": st.column_config.NumberColumn(min_value=0, max_value=23),
        "Salida desde [h]": st.column_config.NumberColumn(min_value=0, max_value=23),
        "Salida hasta [h]": st.column_config.NumberColumn(min_value=0, max_value=23),
        "Borde libre [m]": st.column_config.NumberColumn(
            min_value=0.0, help="Altura del muro sobre el nivel máximo; se dibuja en el "
                                "detalle del tanque de la memoria (0 = no se dibuja).")})
editor_commit(seed_tk, df_tk)
tipos_previos = {t.nombre: t.tipo for t in cfg.tanques}
NUM_TK = ["Cantidad", "Altura útil [m]", "Largo/ancho", "Volumen asignado [m³]",
          "Suministro desde [h]", "Suministro hasta [h]",
          "Salida desde [h]", "Salida hasta [h]"]
filas_tk = [r for _, r in df_tk.iterrows() if s_txt(r["Nombre"])]
incompletos = [s_txt(r["Nombre"]) for r in filas_tk
               if fila_incompleta(r, NUM_TK) or not s_txt(r["Forma"])
               or not s_txt(r["Tipo constructivo"])]
cfg.tanques = [TankSpec(nombre=s_txt(r["Nombre"]),
                        tipo=tipos_previos.get(s_txt(r["Nombre"]), "elevado"),
                        forma=s_txt(r["Forma"], "circular"),
                        volumen=f_num(r["Volumen asignado [m³]"], 0.0),
                        altura=f_num(r["Altura útil [m]"], 2.5),
                        ratio=f_num(r["Largo/ancho"], 1.0),
                        entrada_ini=i_num(r["Suministro desde [h]"], 0),
                        entrada_fin=i_num(r["Suministro hasta [h]"], 23),
                        cantidad=i_num(r["Cantidad"], 1),
                        tipo_constructivo=s_txt(r["Tipo constructivo"], "superficial"),
                        salida_ini=i_num(r["Salida desde [h]"], 0),
                        salida_fin=i_num(r["Salida hasta [h]"], 23),
                        borde_libre=f_num(r.get("Borde libre [m]"), 0.0))
               for r in filas_tk]

if not cfg.tanques:
    st.info("Agrega al menos un tanque.")
    st.stop()
if incompletos:
    st.info("📝 Completa la tabla del tanque que agregaste: "
            f"faltan datos en **{', '.join(incompletos)}**. "
            "Mientras tanto se usan valores por defecto y la verificación de "
            "abajo no es válida para ese tanque.")

# ---------- predimensionado por tanque ----------
st.markdown("**Predimensionado (dimensiones a 10 cm, siempre ≥ el volumen asignado)**")
dims_rows = []
v_real_total = 0.0
for t in cfg.tanques:
    v_unitario_obj = (t.volumen or 1.0) / max(t.cantidad, 1)
    ct = storage.dimensioned_tank(v_unitario_obj, t.altura, t.forma, t.ratio)
    dim = (f"Ø {ct.diametro:.1f} m" if ct.forma == "circular"
           else f"lado {ct.lado:.1f} m" if ct.forma == "cuadrado"
           else f"{ct.ancho:.1f} × {ct.largo:.1f} m")
    v_real_fila = ct.volumen_real * t.cantidad
    v_real_total += v_real_fila
    dims_rows.append({"Tanque": t.nombre, "Tipo constructivo": t.tipo_constructivo,
                      "Forma": t.forma, "Cantidad": t.cantidad,
                      "Dimensiones (c/u)": dim, "Altura [m]": ct.altura,
                      "V asignado [m³]": t.volumen,
                      "V real (c/u) [m³]": ct.volumen_real,
                      "V real total [m³]": v_real_fila})
st.dataframe(pd.DataFrame(dims_rows).style.format(
    {"Altura [m]": SP_ALTURA, "V asignado [m³]": "{:.0f}",
     "V real (c/u) [m³]": SP_VOLUMEN, "V real total [m³]": SP_VOLUMEN}),
    hide_index=True, width="stretch")
st.caption("Añadir 0.30 m de borde libre adicional en la construcción "
           "(volúmenes = volumen útil de líquido).")

# ========== Sección 3 · Verificación ==========
st.subheader("3 · Verificación")
v_asignado_total = sum(t.volumen for t in cfg.tanques)

# --- global ---
st.markdown("**Global** — suma de volúmenes asignados vs. volumen por norma")
if v_asignado_total + 1e-9 >= v_norma:
    st.success(f"Los tanques suman {v_asignado_total:.0f} m³ ≥ {v_norma:.0f} m³ "
               f"requeridos por norma. ✓")
else:
    st.warning(f"Faltan {v_norma - v_asignado_total:.0f} m³: los tanques suman "
               f"{v_asignado_total:.0f} m³ y la norma exige {v_norma:.0f} m³.")

# --- por tanque (balance interno) ---
st.markdown("**Por tanque** — balance interno (suministro vs. salida de cada tanque)")
checks = []
for t in cfg.tanques:
    try:
        chk = storage.tank_balance_check(t.nombre, qmd_m3d, t.entrada_flags(),
                                         t.salida_flags(), t.volumen,
                                         cfg.frac_incendio, cfg.dias_reserva)
    except ValueError as e:
        st.error(f"Tanque '{t.nombre}': {e}")
        continue
    checks.append(chk)
if checks:
    st.dataframe(pd.DataFrame(
        [{"Tanque": c.nombre, "Suministro [h/día]": c.horas_suministro,
          "Salida [h/día]": c.horas_salida, "Fracción balance": c.frac_balance,
          "V asignado [m³]": c.v_asignado, "V requerido balance [m³]": c.v_balance_req,
          "Cumple": "✓" if c.cumple else "✗"} for c in checks])
        .style.format({"Suministro [h/día]": "{:.0f}", "Salida [h/día]": "{:.0f}",
                       "Fracción balance": "{:.4f}", "V asignado [m³]": "{:.0f}",
                       "V requerido balance [m³]": SP_VOLUMEN}),
        hide_index=True, width="stretch")
    for c in checks:
        if not c.cumple:
            st.warning(f"El tanque '{c.nombre}' necesita ≥ {c.v_balance_req:.0f} m³ "
                       f"por su balance interno (asignado: {c.v_asignado:.0f} m³).")

# --- balance de masas entre tanques (opcional) ---
st.markdown("**Balance de masas entre tanques**")
modos = ["por_tanque", "red"]
cfg.modo_balance = st.radio(
    "Modo", modos, horizontal=True, label_visibility="collapsed",
    format_func={"por_tanque": "Cada tanque por separado (ventanas propias, QMD completo)",
                 "red": "Red de tanques: conexiones, caudales y zonas de consumo"}.get,
    key=sel_state(modos, "radio_modo_balance", cfg.modo_balance))
if cfg.modo_balance == "red":
    st.caption("Define qué alimenta a cada tanque y qué zona abastece cada uno. La app "
               "simula el día hora a hora (V(h+1) = V(h) + Q entra − Q sale), verifica el "
               "volumen que asignaste y sugiere el mínimo; no cambia tus volúmenes. "
               "Caudal 0 = **auto**: reparte en la ventana lo que ese tanque entrega aguas "
               "abajo. Un caudal fijo nunca se reescala: si el día no cierra, se avisa.")
    if not cfg.enlaces:
        cfg.zonas, cfg.enlaces = tn.config_inicial(cfg)
    nombres_tk = [t.nombre for t in cfg.tanques]
    z1, z2 = st.columns([1, 2])
    seed_z = editor_seed("zonas", lambda: pd.DataFrame(
        [{"Zona": z.nombre, "Fracción del QMD": z.fraccion} for z in cfg.zonas]))
    df_z = z1.data_editor(st.session_state[seed_z], num_rows="dynamic", width="stretch",
                          key="w_ed_zonas", column_config={
                              "Fracción del QMD": st.column_config.NumberColumn(
                                  min_value=0.0, max_value=1.0, step=0.05)})
    editor_commit(seed_z, df_z)
    cfg.zonas = [ZonaSpec(s_txt(r["Zona"]), f_num(r["Fracción del QMD"], 0.0))
                 for _, r in df_z.iterrows() if s_txt(r["Zona"])]
    destinos = nombres_tk + [z.nombre for z in cfg.zonas]
    seed_e = editor_seed("enlaces", lambda: pd.DataFrame(
        [{"Origen": e.origen, "Destino": e.destino, "Tipo": e.tipo, "Desde [h]": e.ini,
          "Hasta [h]": e.fin, "Caudal [L/s] (0 = auto)": e.caudal_lps} for e in cfg.enlaces]))
    df_e = z2.data_editor(st.session_state[seed_e], num_rows="dynamic", width="stretch",
                          key="w_ed_enlaces", column_config={
                              "Destino": st.column_config.SelectboxColumn(options=destinos),
                              "Tipo": st.column_config.SelectboxColumn(
                                  options=["bombeo", "gravedad"]),
                              "Desde [h]": st.column_config.NumberColumn(min_value=0, max_value=23),
                              "Hasta [h]": st.column_config.NumberColumn(min_value=0, max_value=23),
                              "Caudal [L/s] (0 = auto)": st.column_config.NumberColumn(
                                  min_value=0.0)})
    editor_commit(seed_e, df_e)
    cfg.enlaces = [EnlaceSpec(s_txt(r["Origen"]), s_txt(r["Destino"]), s_txt(r["Tipo"], "bombeo"),
                              i_num(r["Desde [h]"], 0), i_num(r["Hasta [h]"], 23),
                              f_num(r["Caudal [L/s] (0 = auto)"], 0.0))
                   for _, r in df_e.iterrows() if s_txt(r["Origen"]) and s_txt(r["Destino"])]
    suma_z = sum(z.fraccion for z in cfg.zonas)
    if abs(suma_z - 1.0) > 1e-6:
        st.warning(f"Las fracciones de las zonas suman {suma_z:.2f}: el balance reparte "
                   f"{suma_z * 100:.0f}% del QMD.")
    patron_bal = (cfg.factores_hora if len(cfg.factores_hora) == 24
                  else list(storage.DEFAULT_PATTERN))
    try:
        res_red = tn.resolver(*tn.desde_config(cfg), flows.qmd_lps, patron_bal,
                              cfg.frac_incendio, cfg.dias_reserva)
    except ValueError as e:
        st.error(str(e))
    else:
        for a in res_red.avisos:
            st.warning(a)
        st.dataframe(pd.DataFrame(
            [{"Tanque": b.nombre, "V asignado [m³]": b.v_asignado,
              "V regulación [m³]": b.v_reg, "V requerido [m³]": b.v_req,
              "V sugerido [m³]": b.v_sugerido, "Cierre diario [m³]": b.cierre_diario_m3,
              "Cumple": "✓" if b.cumple else "✗"} for b in res_red.tanques])
            .style.format({"V asignado [m³]": "{:.0f}", "V regulación [m³]": SP_VOLUMEN,
                           "V requerido [m³]": SP_VOLUMEN, "V sugerido [m³]": "{:.0f}",
                           "Cierre diario [m³]": "{:+.2f}"}),
            hide_index=True, width="stretch")
        st.caption("V requerido = regulación × (1 + incendio) × días de reserva. El sugerido "
                   "es ese valor redondeado a 5 m³: aplícalo tú en la tabla de tanques si "
                   "lo adoptas.")
        st.dataframe(pd.DataFrame([{"Conexión": f"{o} → {d}", "Caudal [L/s]": q}
                                   for (o, d), q in res_red.caudales.items()])
                     .style.format({"Caudal [L/s]": "{:.2f}"}), hide_index=True)
        fig_bal = rf.fig_balance_red(res_red, cfg.frac_incendio, cfg.dias_reserva, dark=True)
        st.pyplot(fig_bal)
        plt.close(fig_bal)

st.metric("Volumen total de almacenamiento (por norma)", f"{v_norma:.0f} m³")

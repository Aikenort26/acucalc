import base64, io
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
from PIL import Image
from streamlit_image_coordinates import streamlit_image_coordinates
from core import curves as cv, pumping as pu
from core.project import PumpData
from pages_common import get_project

st.header("6 · Curvas de bomba — digitalización y punto de operación")
p = get_project()

if not p.bombeos:
    st.info("Crea primero un sistema de bombeo en la página 5.")
    st.stop()

# ---------- sistema activo ----------
nombres_sys = [s.nombre for s in p.bombeos]
sel_sys = st.selectbox("Sistema de bombeo", nombres_sys, key="w_sel_sys6")
sys_d = next(s for s in p.bombeos if s.nombre == sel_sys)
resuelto = st.session_state.get("sistemas", {}).get(sel_sys)
if resuelto is None:
    st.info("Resuelve este sistema en la página 5 para tener su curva y punto de diseño.")
    st.stop()
qb_lps = resuelto["qb_lps"]
hd = resuelto["solve"].hd
st.caption(f"Punto de diseño del sistema: **Q = {qb_lps:.2f} L/s · Hd = {hd:.1f} m** "
           f"(caudal de bombeo por {sys_d.horas:.0f} h/día)")

# ---------- selección / creación de bomba del sistema ----------
nombres = [b.nombre for b in sys_d.bombas]
sel = st.selectbox("Bomba candidata", nombres + ["➕ Nueva bomba…"], key=f"w_sel_bomba_{sel_sys}")
if sel == "➕ Nueva bomba…":
    nuevo = st.text_input("Nombre / modelo de la nueva bomba", key=f"w_txt_nb_{sel_sys}")
    if st.button("Crear bomba") and nuevo:
        sys_d.bombas.append(PumpData(nombre=nuevo))
        st.rerun()
    st.stop()
bomba = next(b for b in sys_d.bombas if b.nombre == sel)
BK = f"{sel_sys}_{bomba.nombre}".replace(" ", "_")

# ---------- imagen ----------
up = st.file_uploader("Imagen de la curva (png/jpg del catálogo)", type=["png", "jpg", "jpeg"],
                      key=f"w_up_{BK}")
if up is not None:
    bomba.imagen_b64 = base64.b64encode(up.getvalue()).decode()
if not bomba.imagen_b64:
    st.info("Sube la imagen del catálogo, o ingresa los puntos Q-H / Q-η a mano abajo.")
img = None
if bomba.imagen_b64:
    img = Image.open(io.BytesIO(base64.b64decode(bomba.imagen_b64))).convert("RGB")

# ---------- calibración y captura ----------
if img is not None:
    st.subheader("Calibración de ejes")
    st.caption("Modo calibración: click en un punto conocido del eje y escribe su valor. "
               "4 puntos: X1, X2, Y1, Y2.")
    modo = st.radio("Modo de click", ["Calibrar X1", "Calibrar X2", "Calibrar Y1",
                                      "Calibrar Y2", "Agregar punto Q-H",
                                      "Agregar punto Q-E"], horizontal=True,
                    key=f"w_radio_modo_{BK}")
    log_x = st.checkbox("Eje X logarítmico", value=False, key=f"w_chk_lx_{BK}")
    log_y = st.checkbox("Eje Y logarítmico", value=False, key=f"w_chk_ly_{BK}")
    unidad_q = st.selectbox("Unidad de Q en la gráfica", ["L/s", "L/min", "m³/h", "GPM"],
                            key=f"w_sel_uq_{BK}")
    FACTOR_Q = {"L/s": 1.0, "L/min": 1 / 60, "m³/h": 1 / 3.6, "GPM": 0.0630902}

    click = streamlit_image_coordinates(img, key=f"img_{BK}")
    cal = bomba.cal or {}
    if click is not None:
        px, py = click["x"], click["y"]
        if modo.startswith("Calibrar"):
            eje = modo.split()[-1]
            val = st.number_input(f"Valor real en {eje}", key=f"w_val_{eje}_{BK}", value=0.0)
            if st.button(f"Fijar {eje} = {val} en pixel ({px},{py})", key=f"w_fix_{eje}_{BK}"):
                cal[eje] = {"px": px if eje.startswith("X") else py, "val": val}
                bomba.cal = cal
                st.rerun()
        elif {"X1", "X2", "Y1", "Y2"} <= set(cal):
            calx = cv.AxisCalibration(cal["X1"]["px"], cal["X1"]["val"],
                                      cal["X2"]["px"], cal["X2"]["val"], log_x)
            caly = cv.AxisCalibration(cal["Y1"]["px"], cal["Y1"]["val"],
                                      cal["Y2"]["px"], cal["Y2"]["val"], log_y)
            q, y = cv.pixel_to_data((px, py), calx, caly)
            q *= FACTOR_Q[unidad_q]
            if modo.endswith("Q-H"):
                bomba.puntos_qh.append((round(q, 4), round(y, 4)))
            else:
                bomba.puntos_qe.append((round(q, 4), round(y, 4)))
            st.rerun()
        else:
            st.warning("Calibra los 4 puntos de eje antes de capturar puntos.")
    st.write("Calibración:", {k: v for k, v in (bomba.cal or {}).items()})

    if {"X1", "X2", "Y1", "Y2"} <= set(cal) and st.button(
            "🪄 Detectar curva automáticamente (click previo sobre un pixel del color "
            "de la curva, en modo 'Agregar punto Q-H')", key=f"w_auto_{BK}"):
        arr = np.array(img)
        if click is not None:
            color = tuple(int(c) for c in arr[click["y"], click["x"]])
            pts_px = cv.detect_curve_by_color(arr, color, tolerance=60, n_points=15)
            calx = cv.AxisCalibration(cal["X1"]["px"], cal["X1"]["val"],
                                      cal["X2"]["px"], cal["X2"]["val"], log_x)
            caly = cv.AxisCalibration(cal["Y1"]["px"], cal["Y1"]["val"],
                                      cal["Y2"]["px"], cal["Y2"]["val"], log_y)
            bomba.puntos_qh = [(round(cv.pixel_to_data(pt, calx, caly)[0] * FACTOR_Q[unidad_q], 4),
                                round(cv.pixel_to_data(pt, calx, caly)[1], 4)) for pt in pts_px]
            st.rerun()

# ---------- tablas de puntos (siempre editables) ----------
st.subheader("Puntos de la bomba (editables)")
c1, c2 = st.columns(2)
qh_df = c1.data_editor(pd.DataFrame(bomba.puntos_qh or [(0.0, 0.0)],
                                    columns=["Q [L/s]", "H [m]"]),
                       num_rows="dynamic", key=f"w_qh_{BK}")
bomba.puntos_qh = [(float(r["Q [L/s]"]), float(r["H [m]"]))
                   for _, r in qh_df.iterrows() if r["Q [L/s]"] or r["H [m]"]]
qe_df = c2.data_editor(pd.DataFrame(bomba.puntos_qe or [(0.0, 0.0)],
                                    columns=["Q [L/s]", "η [-]"]),
                       num_rows="dynamic", key=f"w_qe_{BK}")
bomba.puntos_qe = [(float(r["Q [L/s]"]), float(r["η [-]"]))
                   for _, r in qe_df.iterrows() if r["Q [L/s]"] or r["η [-]"]]

# ---------- comparación de las bombas del sistema ----------
st.divider()
st.subheader(f"Curva del sistema '{sel_sys}' vs bombas candidatas")
q_max_lps = max(qb_lps * 1.5, max((b.puntos_qh[-1][0] for b in sys_d.bombas
                                   if len(b.puntos_qh) >= 3), default=0.0))
sys_pts = pu.system_curve(resuelto["sistema"], q_max=max(q_max_lps / 1000, 1e-4), n=30)
sys_lps = [(q * 1000, h) for q, h in sys_pts]

fig, ax = plt.subplots(figsize=(9, 5.5))
ax.plot([q for q, _ in sys_lps], [h for _, h in sys_lps],
        "k--", lw=2, label="Curva del sistema")
ax.plot(qb_lps, hd, "r*", ms=16, zorder=5,
        label=f"Punto de diseño ({qb_lps:.1f} L/s, {hd:.1f} m)")
rows = []
for b in sys_d.bombas:
    if len(b.puntos_qh) < 3:
        continue
    fit = cv.fit_curve(b.puntos_qh, 2)
    qs = np.linspace(fit.q_min, fit.q_max, 100)
    ax.plot(qs, [fit(q) for q in qs], lw=1.8, label=f"{b.nombre} (R²={fit.r2:.3f})")
    op = cv.operating_point(fit, sys_lps)
    bep = cv.best_efficiency_point(b.puntos_qe, 2) if len(b.puntos_qe) >= 3 else None
    e_fit = cv.fit_curve(b.puntos_qe, 2) if len(b.puntos_qe) >= 3 else None
    if op:
        ax.plot(*op, "o", ms=9)
        eta = e_fit(op[0]) if e_fit else float("nan")
        pot = (998.29 * 9.81 * op[0] / 1000 * op[1] / eta / 745.7
               if eta and eta > 0 else float("nan"))
        rows.append({"Bomba": b.nombre, "Q_op [L/s]": op[0], "H_op [m]": op[1],
                     "η(Q_op)": eta, "BEP Q [L/s]": bep.q if bep else float("nan"),
                     "Desv. BEP [%]": (op[0] - bep.q) / bep.q * 100 if bep else float("nan"),
                     "P absorbida [HP]": pot})
    else:
        rows.append({"Bomba": b.nombre, "Q_op [L/s]": float("nan"),
                     "H_op [m]": float("nan"), "η(Q_op)": float("nan"),
                     "BEP Q [L/s]": bep.q if bep else float("nan"),
                     "Desv. BEP [%]": float("nan"), "P absorbida [HP]": float("nan")})
ax.set_xlabel("Q [L/s]"); ax.set_ylabel("H [m]"); ax.grid(alpha=0.3); ax.legend()
st.pyplot(fig)
plt.close(fig)

if rows:
    df_cmp = pd.DataFrame(rows)
    st.dataframe(df_cmp.style.format(precision=3), hide_index=True, width="stretch")
    validas = df_cmp.dropna(subset=["η(Q_op)"])
    if not validas.empty:
        mejor = validas.loc[validas["η(Q_op)"].idxmax(), "Bomba"]
        st.caption(f"Sugerida: **{mejor}** (mayor eficiencia en el punto de operación)")
    else:
        mejor = rows[0]["Bomba"]
    opciones = [r["Bomba"] for r in rows]
    sys_d.bomba_seleccionada = st.selectbox(
        "Bomba seleccionada para este sistema (va al reporte)", opciones,
        index=opciones.index(sys_d.bomba_seleccionada)
        if sys_d.bomba_seleccionada in opciones else opciones.index(mejor),
        key=f"w_sel_final_{sel_sys}")
    tablas = st.session_state.setdefault("tabla_bombas_sys", {})
    tablas[sel_sys] = [
        {"nombre": r["Bomba"], "q_op": f"{r['Q_op [L/s]']:.2f}",
         "h_op": f"{r['H_op [m]']:.2f}", "eta_op": f"{r['η(Q_op)']:.3f}",
         "bep_q": f"{r['BEP Q [L/s]']:.2f}", "desv_bep": f"{r['Desv. BEP [%]']:.1f}",
         "p_hp": f"{r['P absorbida [HP]']:.2f}"} for r in rows]

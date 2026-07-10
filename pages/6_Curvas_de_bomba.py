import base64, io
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

# ---------- selección / creación de bomba ----------
nombres = [b.nombre for b in p.bombas]
sel = st.selectbox("Bomba", nombres + ["➕ Nueva bomba…"])
if sel == "➕ Nueva bomba…":
    nuevo = st.text_input("Nombre / modelo de la nueva bomba")
    if st.button("Crear") and nuevo:
        p.bombas.append(PumpData(nombre=nuevo))
        st.rerun()
    st.stop()
bomba = next(b for b in p.bombas if b.nombre == sel)

# ---------- imagen ----------
up = st.file_uploader("Imagen de la curva (png/jpg del catálogo)", type=["png", "jpg", "jpeg"])
if up is not None:
    bomba.imagen_b64 = base64.b64encode(up.getvalue()).decode()
if not bomba.imagen_b64:
    st.info("Sube la imagen del catálogo, o ingresa los puntos a mano en la tabla de abajo.")
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
                                      "Agregar punto Q-E"], horizontal=True)
    log_x = st.checkbox("Eje X logarítmico", value=False)
    log_y = st.checkbox("Eje Y logarítmico", value=False)
    unidad_q = st.selectbox("Unidad de Q en la gráfica", ["L/s", "L/min", "m³/h", "GPM"])
    FACTOR_Q = {"L/s": 1.0, "L/min": 1 / 60, "m³/h": 1 / 3.6, "GPM": 0.0630902}

    click = streamlit_image_coordinates(img, key=f"img_{bomba.nombre}")
    cal = bomba.cal or {}
    if click is not None:
        px, py = click["x"], click["y"]
        if modo.startswith("Calibrar"):
            eje = modo.split()[-1]           # X1/X2/Y1/Y2
            val = st.number_input(f"Valor real en {eje}", key=f"val_{eje}", value=0.0)
            if st.button(f"Fijar {eje} = {val} en pixel ({px},{py})"):
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
            "🪄 Detectar curva automáticamente (click previo en 'Agregar punto Q-H' "
            "sobre un pixel del color de la curva)"):
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
st.subheader("Puntos digitalizados (editables)")
c1, c2 = st.columns(2)
qh_df = c1.data_editor(pd.DataFrame(bomba.puntos_qh or [(0.0, 0.0)],
                                    columns=["Q [L/s]", "H [m]"]),
                       num_rows="dynamic", key=f"qh_{bomba.nombre}")
bomba.puntos_qh = [(float(r["Q [L/s]"]), float(r["H [m]"]))
                   for _, r in qh_df.iterrows() if r["Q [L/s]"] or r["H [m]"]]
qe_df = c2.data_editor(pd.DataFrame(bomba.puntos_qe or [(0.0, 0.0)],
                                    columns=["Q [L/s]", "η [-]"]),
                       num_rows="dynamic", key=f"qe_{bomba.nombre}")
bomba.puntos_qe = [(float(r["Q [L/s]"]), float(r["η [-]"]))
                   for _, r in qe_df.iterrows() if r["Q [L/s]"] or r["η [-]"]]

# ---------- comparación multi-bomba ----------
st.divider()
st.subheader("Comparación: curva del sistema vs bombas")
sistema = st.session_state.get("pump_system")
qb_lps = st.session_state.get("qb_lps")
if sistema is None:
    st.info("Resuelve primero el bombeo en la página 5 para tener la curva del sistema.")
    st.stop()
sys_pts = pu.system_curve(sistema, q_max=max(qb_lps * 1.5 / 1000, 1e-4), n=30)
sys_lps = [(q * 1000, h) for q, h in sys_pts]

import matplotlib.pyplot as plt
fig, ax = plt.subplots(figsize=(9, 5.5))
ax.plot([q for q, _ in sys_lps], [h for _, h in sys_lps],
        "k--", lw=2, label="Curva del sistema")
rows = []
for b in p.bombas:
    if len(b.puntos_qh) >= 3:
        fit = cv.fit_curve(b.puntos_qh, 2)
        qs = np.linspace(fit.q_min, fit.q_max, 100)
        ax.plot(qs, [fit(q) for q in qs], lw=1.8, label=f"{b.nombre} (R²={fit.r2:.3f})")
        op = cv.operating_point(fit, sys_lps)
        bep = (cv.best_efficiency_point(b.puntos_qe, 2)
               if len(b.puntos_qe) >= 3 else None)
        if op:
            ax.plot(*op, "o", ms=9)
            e_fit = cv.fit_curve(b.puntos_qe, 2) if len(b.puntos_qe) >= 3 else None
            eta = e_fit(op[0]) if e_fit else float("nan")
            pot = (998.29 * 9.81 * op[0] / 1000 * op[1] / eta / 745.7
                   if eta and eta > 0 else float("nan"))
            rows.append({"Bomba": b.nombre, "Q_op [L/s]": op[0], "H_op [m]": op[1],
                         "η(Q_op)": eta,
                         "BEP Q [L/s]": bep.q if bep else float("nan"),
                         "Desv. BEP [%]": (op[0] - bep.q) / bep.q * 100 if bep else float("nan"),
                         "P absorbida [HP]": pot})
        else:
            rows.append({"Bomba": b.nombre, "Q_op [L/s]": float("nan"),
                         "H_op [m]": float("nan"), "η(Q_op)": float("nan"),
                         "BEP Q [L/s]": bep.q if bep else float("nan"),
                         "Desv. BEP [%]": float("nan"), "P absorbida [HP]": float("nan")})
ax.set_xlabel("Q [L/s]"); ax.set_ylabel("H [m]"); ax.grid(alpha=0.3); ax.legend()
st.pyplot(fig)
st.session_state["fig_curvas"] = fig
if rows:
    st.dataframe(pd.DataFrame(rows).style.format(precision=3), width="stretch")
    p.bomba_seleccionada = st.selectbox(
        "Bomba seleccionada para el diseño (va al reporte)",
        [r["Bomba"] for r in rows],
        index=[r["Bomba"] for r in rows].index(p.bomba_seleccionada)
        if p.bomba_seleccionada in [r["Bomba"] for r in rows] else 0)
    st.session_state["tabla_bombas"] = [
        {"nombre": r["Bomba"], "q_op": f"{r['Q_op [L/s]']:.2f}",
         "h_op": f"{r['H_op [m]']:.2f}", "eta_op": f"{r['η(Q_op)']:.3f}",
         "bep_q": f"{r['BEP Q [L/s]']:.2f}", "desv_bep": f"{r['Desv. BEP [%]']:.1f}",
         "p_hp": f"{r['P absorbida [HP]']:.2f}"} for r in rows]

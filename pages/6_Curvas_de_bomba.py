import base64, io
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
from PIL import Image, ImageDraw
from streamlit_image_coordinates import streamlit_image_coordinates
from core import curves as cv, pumping as pu
from core.project import PumpData
from pages_common import page_setup, num_input

p = page_setup()
st.header("6 · Curvas de bomba — digitalización y punto de operación")

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

# ---------- selección / creación / eliminación de bomba ----------
if "sel_bomba_next" in st.session_state:
    st.session_state[f"w_sel_bomba_{sel_sys}"] = st.session_state.pop("sel_bomba_next")
nombres = [b.nombre for b in sys_d.bombas]
sel = st.selectbox("Bomba candidata", nombres + ["➕ Nueva bomba…"],
                   key=f"w_sel_bomba_{sel_sys}")
if sel == "➕ Nueva bomba…":
    nuevo = st.text_input("Nombre / modelo de la nueva bomba", key=f"w_txt_nb_{sel_sys}")
    if st.button("Crear bomba") and nuevo:
        sys_d.bombas.append(PumpData(nombre=nuevo))
        st.session_state["sel_bomba_next"] = nuevo
        st.rerun()
    st.stop()
bomba = next(b for b in sys_d.bombas if b.nombre == sel)
BK = f"{sel_sys}_{bomba.nombre}".replace(" ", "_")

with st.popover("🗑 Eliminar esta bomba"):
    st.warning(f"Elimina '{bomba.nombre}' con sus puntos e imagen.")
    if st.button("Eliminar definitivamente", key=f"w_del_b_{BK}"):
        sys_d.bombas.remove(bomba)
        if sys_d.bomba_seleccionada == bomba.nombre:
            sys_d.bomba_seleccionada = ""
        st.session_state["sel_bomba_next"] = (
            sys_d.bombas[0].nombre if sys_d.bombas else "➕ Nueva bomba…")
        st.rerun()

# ---------- imagen ----------
up = st.file_uploader("Imagen de la curva (png/jpg del catálogo)",
                      type=["png", "jpg", "jpeg"], key=f"w_up_{BK}")
if up is not None:
    bomba.imagen_b64 = base64.b64encode(up.getvalue()).decode()
if not bomba.imagen_b64:
    st.info("Sube la imagen del catálogo, o ingresa los puntos Q-H / Q-η a mano abajo.")
img = None
if bomba.imagen_b64:
    img = Image.open(io.BytesIO(base64.b64decode(bomba.imagen_b64))).convert("RGB")

FACTOR_Q = {"L/s": 1.0, "L/min": 1 / 60, "m³/h": 1 / 3.6, "GPM": 0.0630902}


def _draw_cross(d: ImageDraw.ImageDraw, x, y, color, size=9, w=2, label=""):
    d.line([(x - size, y), (x + size, y)], fill=color, width=w)
    d.line([(x, y - size), (x, y + size)], fill=color, width=w)
    if label:
        d.text((x + size + 2, y - size - 2), label, fill=color)


def _overlay(base: Image.Image, cal: dict, pend) -> Image.Image:
    """Copia de la imagen con marcadores: calibración (rojo), puntos Q-H (cian),
    Q-E (verde) y punto pendiente (amarillo)."""
    im = base.copy()
    d = ImageDraw.Draw(im)
    for eje, v in (cal or {}).items():
        px = v["px"]
        if eje.startswith("X"):
            _draw_cross(d, px, v.get("py", im.height - 20), "#FF3333", label=eje)
        else:
            _draw_cross(d, v.get("px_x", 20), px, "#FF3333", label=eje)
    for (x, y) in st.session_state.get(f"qh_px_{BK}", []):
        d.ellipse([x - 5, y - 5, x + 5, y + 5], outline="#00E5FF", width=3)
    for (x, y) in st.session_state.get(f"qe_px_{BK}", []):
        d.ellipse([x - 5, y - 5, x + 5, y + 5], outline="#4ADE80", width=3)
    if pend:
        _draw_cross(d, pend["x"], pend["y"], "#FFD400", size=12, w=2, label="●")
    return im


if img is not None:
    st.subheader("Calibración y captura de puntos")
    st.caption("1) Elige el modo · 2) haz click en la imagen · 3) afina el punto en el "
               "panel de zoom (±1 px) · 4) confirma. Los puntos confirmados quedan "
               "marcados sobre la imagen, como en automeris.io.")
    modo = st.radio("Modo de click", ["Calibrar X1", "Calibrar X2", "Calibrar Y1",
                                      "Calibrar Y2", "Punto Q-H", "Punto Q-E"],
                    horizontal=True, key=f"w_radio_modo_{BK}")
    o1, o2, o3 = st.columns(3)
    log_x = o1.checkbox("Eje X logarítmico", value=False, key=f"w_chk_lx_{BK}")
    log_y = o2.checkbox("Eje Y logarítmico", value=False, key=f"w_chk_ly_{BK}")
    unidad_q = o3.selectbox("Unidad de Q en la gráfica", list(FACTOR_Q),
                            key=f"w_sel_uq_{BK}")

    cal = bomba.cal or {}
    pend_key = f"pend_{BK}"
    pend = st.session_state.get(pend_key)

    col_zoom, col_img = st.columns([1, 3])

    with col_img:
        shown = _overlay(img, cal, pend)
        click = streamlit_image_coordinates(shown, key=f"img_{BK}")
        if click is not None:
            nuevo_p = {"x": int(click["x"]), "y": int(click["y"])}
            if nuevo_p != st.session_state.get(f"last_click_{BK}"):
                st.session_state[f"last_click_{BK}"] = nuevo_p
                st.session_state[pend_key] = dict(nuevo_p)
                st.rerun()

    with col_zoom:
        st.markdown("**Zoom de precisión**")
        if pend:
            Z, R = 4, 30
            x0, y0 = max(pend["x"] - R, 0), max(pend["y"] - R, 0)
            crop = img.crop((x0, y0, min(pend["x"] + R, img.width),
                             min(pend["y"] + R, img.height)))
            crop = crop.resize((crop.width * Z, crop.height * Z), Image.NEAREST)
            dz = ImageDraw.Draw(crop)
            cx, cy = (pend["x"] - x0) * Z, (pend["y"] - y0) * Z
            dz.line([(cx, 0), (cx, crop.height)], fill="#FFD400", width=1)
            dz.line([(0, cy), (crop.width, cy)], fill="#FFD400", width=1)
            st.image(crop, width="stretch")
            st.caption(f"pixel ({pend['x']}, {pend['y']})")
            n1, n2, n3, n4 = st.columns(4)
            if n1.button("←", key=f"w_l_{BK}"):
                pend["x"] -= 1; st.rerun()
            if n2.button("→", key=f"w_r_{BK}"):
                pend["x"] += 1; st.rerun()
            if n3.button("↑", key=f"w_u_{BK}"):
                pend["y"] -= 1; st.rerun()
            if n4.button("↓", key=f"w_d_{BK}"):
                pend["y"] += 1; st.rerun()

            if modo.startswith("Calibrar"):
                eje = modo.split()[-1]
                val = num_input(f"Valor real en {eje}", f"val_{eje}_{BK}", 0.0,
                                decimals=3)
                if st.button(f"✔ Fijar {eje}", key=f"w_fix_{eje}_{BK}"):
                    cal[eje] = ({"px": pend["x"], "py": pend["y"]}
                                if eje.startswith("X")
                                else {"px": pend["y"], "px_x": pend["x"]})
                    cal[eje]["val"] = val
                    bomba.cal = cal
                    st.session_state[pend_key] = None
                    st.rerun()
            else:
                if {"X1", "X2", "Y1", "Y2"} <= set(cal):
                    calx = cv.AxisCalibration(cal["X1"]["px"], cal["X1"]["val"],
                                              cal["X2"]["px"], cal["X2"]["val"], log_x)
                    caly = cv.AxisCalibration(cal["Y1"]["px"], cal["Y1"]["val"],
                                              cal["Y2"]["px"], cal["Y2"]["val"], log_y)
                    q, y = cv.pixel_to_data((pend["x"], pend["y"]), calx, caly)
                    q *= FACTOR_Q[unidad_q]
                    st.caption(f"→ Q = {q:.3f} L/s · {'H' if modo.endswith('Q-H') else 'η'}"
                               f" = {y:.3f}")
                    if st.button("✔ Confirmar punto", key=f"w_ok_{BK}"):
                        if modo.endswith("Q-H"):
                            bomba.puntos_qh.append((round(q, 4), round(y, 4)))
                            st.session_state.setdefault(f"qh_px_{BK}", []).append(
                                (pend["x"], pend["y"]))
                        else:
                            bomba.puntos_qe.append((round(q, 4), round(y, 4)))
                            st.session_state.setdefault(f"qe_px_{BK}", []).append(
                                (pend["x"], pend["y"]))
                        st.session_state[pend_key] = None
                        st.rerun()
                else:
                    st.warning("Calibra X1, X2, Y1 y Y2 antes de capturar puntos.")
        else:
            st.caption("Haz click en la imagen para ubicar un punto.")

    estado_cal = " · ".join(f"{e}={cal[e]['val']}" for e in ("X1", "X2", "Y1", "Y2")
                            if e in cal) or "sin calibrar"
    st.caption(f"Calibración: {estado_cal}")
    cc1, cc2 = st.columns(2)
    if cc1.button("♻ Reiniciar calibración", key=f"w_rst_cal_{BK}"):
        bomba.cal = {}
        st.session_state[pend_key] = None
        st.rerun()
    if {"X1", "X2", "Y1", "Y2"} <= set(cal) and cc2.button(
            "🪄 Detectar curva por color (usa el punto pendiente como muestra)",
            key=f"w_auto_{BK}"):
        if pend:
            arr = np.array(img)
            color = tuple(int(c) for c in arr[pend["y"], pend["x"]])
            pts_px = cv.detect_curve_by_color(arr, color, tolerance=60, n_points=15)
            calx = cv.AxisCalibration(cal["X1"]["px"], cal["X1"]["val"],
                                      cal["X2"]["px"], cal["X2"]["val"], log_x)
            caly = cv.AxisCalibration(cal["Y1"]["px"], cal["Y1"]["val"],
                                      cal["Y2"]["px"], cal["Y2"]["val"], log_y)
            bomba.puntos_qh = [(round(cv.pixel_to_data(pt, calx, caly)[0] * FACTOR_Q[unidad_q], 4),
                                round(cv.pixel_to_data(pt, calx, caly)[1], 4))
                               for pt in pts_px]
            st.session_state[f"qh_px_{BK}"] = [(int(x), int(y)) for x, y in pts_px]
            st.session_state[pend_key] = None
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

with plt.style.context("dark_background"):
    fig, ax = plt.subplots(figsize=(9, 5.5))
    fig.patch.set_alpha(0)
    ax.set_facecolor("none")
    ax.plot([q for q, _ in sys_lps], [h for _, h in sys_lps],
            "w--", lw=2, label="Curva del sistema")
    ax.plot(qb_lps, hd, "*", color="#FFD400", ms=18, zorder=5,
            label=f"Punto de diseño ({qb_lps:.1f} L/s, {hd:.1f} m)")
    rows = []
    for b in sys_d.bombas:
        if len(b.puntos_qh) < 3:
            continue
        fit = cv.fit_curve(b.puntos_qh, 2)
        qs = np.linspace(fit.q_min, fit.q_max, 100)
        ax.plot(qs, [fit(q) for q in qs], lw=1.8, label=f"{b.nombre} (R²={fit.r2:.3f})")
        ax.plot(*zip(*b.puntos_qh), "o", ms=4, alpha=0.6)   # puntos digitalizados
        op = cv.operating_point(fit, sys_lps)
        bep = cv.best_efficiency_point(b.puntos_qe, 2) if len(b.puntos_qe) >= 3 else None
        e_fit = cv.fit_curve(b.puntos_qe, 2) if len(b.puntos_qe) >= 3 else None
        if op:
            ax.plot(*op, "o", color="#00E5FF", ms=10, zorder=5)
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
    ax.set_xlabel("Q [L/s]"); ax.set_ylabel("H [m]"); ax.grid(alpha=0.25)
    ax.legend(fontsize=8)
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

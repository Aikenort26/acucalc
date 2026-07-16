import base64, io
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
from PIL import Image, ImageDraw
from streamlit_image_coordinates import streamlit_image_coordinates
from core import curves as cv, pumping as pu
from core import project as pj
from core.project import PumpData
from pages_common import page_setup, num_input, int_input

try:
    from components.digitizer import digitizer
    DIGITIZER_OK = True
except Exception:
    DIGITIZER_OK = False

try:
    import pypdfium2 as pdfium
    PDFIUM_OK = True
except Exception:
    PDFIUM_OK = False


def _pdf_page1_to_png_bytes(pdf_bytes: bytes, scale: float = 3.5) -> bytes:
    """Renderiza la página 1 de un PDF (ficha técnica del catálogo) a PNG en
    alta resolución (scale~3.5x, igual o mejor que la resolución de impresión
    típica de un PDF de catálogo), para digitalizar la curva con la misma
    calidad que un PNG/JPG de buena fuente."""
    doc = pdfium.PdfDocument(pdf_bytes)
    page = doc.get_page(0)
    bitmap = page.render(scale=scale)
    pil_img = bitmap.to_pil().convert("RGB")
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    return buf.getvalue()

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
up = st.file_uploader("Imagen de la curva (png/jpg/pdf del catálogo)",
                      type=["png", "jpg", "jpeg", "pdf"], key=f"w_up_{BK}")
if up is not None:
    raw = up.getvalue()
    es_pdf = raw[:4] == b"%PDF" or up.name.lower().endswith(".pdf")
    if es_pdf:
        if not PDFIUM_OK:
            st.error("No se pudo cargar el soporte de PDF (pypdfium2). "
                     "Sube la imagen como PNG/JPG en su lugar.")
        else:
            try:
                png_bytes = _pdf_page1_to_png_bytes(raw)
                bomba.imagen_b64 = base64.b64encode(png_bytes).decode()
            except Exception as e:
                st.error(f"No se pudo renderizar el PDF: {e}")
    else:
        bomba.imagen_b64 = base64.b64encode(raw).decode()
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


def _puntos_transformados(b: PumpData) -> tuple[list, list]:
    """Aplica afinidad (N1→N2) y luego arreglo (paralelo/serie ×n_unidades)
    a los puntos Q-H/Q-η digitalizados de la bomba. Devuelve (qh, qe).
    Envoltorio delgado sobre `cv.apply_pump_transform` — misma fuente única
    de la transformación que usa `core/report_ctx.build`."""
    return cv.apply_pump_transform(b.puntos_qh, b.puntos_qe, b.n1_nominal,
                                   b.n2_objetivo, b.n_unidades, b.arreglo)


# ---------- WP-B2: calibración de ejes independiente Q-H / Q-η ----------
# H y η se grafican en ejes Y distintos con escalas no relacionadas (ver
# captura del usuario) — una sola calibración compartida (esquema viejo) era
# incorrecta para η. La cadena de etapas ahora encadena las 4 calibraciones
# de Q-H, luego captura de puntos Q-H, y (solo con Enter explícito, no
# automático) pasa a calibrar Q-η y capturar sus puntos.
ETAPAS_QH = ["Calibrar X1 (Q-H)", "Calibrar X2 (Q-H)", "Calibrar Y1 (Q-H)",
            "Calibrar Y2 (Q-H)", "Punto Q-H"]
ETAPAS_QE = ["Calibrar X1 (Q-η)", "Calibrar X2 (Q-η)", "Calibrar Y1 (Q-η)",
            "Calibrar Y2 (Q-η)", "Punto Q-η"]
ETAPAS = ETAPAS_QH + ETAPAS_QE
_NEXT_CAL = {  # (curva, eje fijado) -> siguiente etapa, misma curva
    ("qh", "X1"): "Calibrar X2 (Q-H)", ("qh", "X2"): "Calibrar Y1 (Q-H)",
    ("qh", "Y1"): "Calibrar Y2 (Q-H)", ("qh", "Y2"): "Punto Q-H",
    ("qe", "X1"): "Calibrar X2 (Q-η)", ("qe", "X2"): "Calibrar Y1 (Q-η)",
    ("qe", "Y1"): "Calibrar Y2 (Q-η)", ("qe", "Y2"): "Punto Q-η",
}
# avance explícito por Enter: termina de capturar puntos de una curva y pasa
# a calibrar la otra. En "Punto Q-η" (última etapa) Enter no hace nada.
_ENTER_ADVANCE = {"Punto Q-H": "Calibrar X1 (Q-η)"}


def _curva_activa(modo: str) -> str:
    return "qh" if "Q-H" in modo else "qe"


def _estado_cal(c: dict) -> str:
    return (" · ".join(f"{e}={c[e]['val']}" for e in ("X1", "X2", "Y1", "Y2") if e in c)
           or "sin calibrar")


if img is not None:
    st.subheader("Calibración y captura de puntos")
    st.caption("1) Elige el modo · 2) haz click en la imagen · 3) afina el punto en el "
               "panel de zoom (±1 px) · 4) confirma. Los puntos confirmados quedan "
               "marcados sobre la imagen. Q-H y Q-η tienen calibración de ejes "
               "independiente (escalas distintas). Enter físico avanza de Q-H a Q-η "
               "en modo 'lupa en tiempo real'; en modo clásico usa el botón ⏎ equivalente.")
    if f"modo_next_{BK}" in st.session_state:      # auto-avance tras confirmar / Enter
        st.session_state[f"w_radio_modo_{BK}"] = st.session_state.pop(f"modo_next_{BK}")

    # WP-B3: layout de una sola pantalla — imagen a la izquierda (más ancha,
    # es lo que el usuario necesita ver grande) y TODOS los controles
    # (modo/ejes/unidad/clásico + zoom + calibración + confirmar/nudge/enter)
    # apilados en una única columna angosta a la derecha, en vez de una fila
    # de controles a todo el ancho arriba + una columna angosta aparte para
    # el zoom (el layout viejo dejaba hueco vacío y obligaba a hacer scroll
    # en la barra de controles). [3, 2] deja la imagen dominante sin dejar
    # los controles demasiado angostos para sus botones/inputs.
    col_img, col_ctrl = st.columns([3, 2])

    with col_ctrl:
        modo = st.radio("Modo de click (avanza solo al confirmar)", ETAPAS,
                        key=f"w_radio_modo_{BK}")
        curva = _curva_activa(modo)
        oc1, oc2 = st.columns(2)
        log_x = oc1.checkbox("Eje X log", value=False, key=f"w_chk_lx_{BK}")
        log_y = oc2.checkbox("Eje Y log", value=False, key=f"w_chk_ly_{BK}")
        unidad_q = st.selectbox("Unidad de Q en la gráfica", list(FACTOR_Q),
                                key=f"w_sel_uq_{BK}")
        clasico = st.checkbox("Modo clásico (sin lupa en vivo)",
                              value=not DIGITIZER_OK, disabled=not DIGITIZER_OK,
                              key=f"w_chk_clasico_{BK}")

    cal_all = pj.migrate_pump_cal(bomba.cal)   # {"qh": {...}, "qe": {...}}
    bomba.cal = cal_all
    cal = cal_all[curva]                       # calibración de la curva activa
    pend_key = f"pend_{BK}"
    pend = st.session_state.get(pend_key)

    with col_img:
        if not clasico:
            marks_cal = []
            for eje, v in (cal or {}).items():
                if eje.startswith("X"):
                    marks_cal.append({"x": v["px"], "y": v.get("py", img.height - 20),
                                      "label": eje})
                else:
                    marks_cal.append({"x": v.get("px_x", 20), "y": v["px"],
                                      "label": eje})
            markers = {"cal": marks_cal,
                       "qh": st.session_state.get(f"qh_px_{BK}", []),
                       "qe": st.session_state.get(f"qe_px_{BK}", []),
                       "pending": [pend["x"], pend["y"]] if pend else None}
            click = digitizer(bomba.imagen_b64, markers, key=f"dg_{BK}")
            if click:
                n = click.get("n")
                if click.get("enterPressed"):
                    if n != st.session_state.get(f"last_enter_{BK}"):
                        st.session_state[f"last_enter_{BK}"] = n
                        siguiente = _ENTER_ADVANCE.get(modo)
                        if siguiente:
                            st.session_state[f"modo_next_{BK}"] = siguiente
                        st.rerun()
                elif n != st.session_state.get(f"last_click_{BK}"):
                    st.session_state[f"last_click_{BK}"] = n
                    st.session_state[pend_key] = {"x": int(click["x"]), "y": int(click["y"])}
                    st.rerun()
        else:
            shown = _overlay(img, cal, pend)
            click = streamlit_image_coordinates(shown, key=f"img_{BK}")
            if click is not None:
                nuevo_p = {"x": int(click["x"]), "y": int(click["y"])}
                if nuevo_p != st.session_state.get(f"last_click_{BK}"):
                    st.session_state[f"last_click_{BK}"] = nuevo_p
                    st.session_state[pend_key] = dict(nuevo_p)
                    st.rerun()

    with col_ctrl:
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
                eje = modo.split()[1]
                val = num_input(f"Valor real en {eje}", f"val_{eje}_{curva}_{BK}", 0.0,
                                decimals=3)
                if st.button(f"✔ Fijar {eje}", key=f"w_fix_{eje}_{curva}_{BK}"):
                    cal[eje] = ({"px": pend["x"], "py": pend["y"]}
                                if eje.startswith("X")
                                else {"px": pend["y"], "px_x": pend["x"]})
                    cal[eje]["val"] = val
                    cal_all[curva] = cal
                    bomba.cal = cal_all
                    st.session_state[pend_key] = None
                    st.session_state[f"modo_next_{BK}"] = _NEXT_CAL[(curva, eje)]
                    st.rerun()
            else:
                if {"X1", "X2", "Y1", "Y2"} <= set(cal):
                    calx = cv.AxisCalibration(cal["X1"]["px"], cal["X1"]["val"],
                                              cal["X2"]["px"], cal["X2"]["val"], log_x)
                    caly = cv.AxisCalibration(cal["Y1"]["px"], cal["Y1"]["val"],
                                              cal["Y2"]["px"], cal["Y2"]["val"], log_y)
                    q, y = cv.pixel_to_data((pend["x"], pend["y"]), calx, caly)
                    q *= FACTOR_Q[unidad_q]
                    st.caption(f"→ Q = {q:.3f} L/s · {'H' if curva == 'qh' else 'η'}"
                               f" = {y:.3f}")
                    if st.button("✔ Confirmar punto", key=f"w_ok_{curva}_{BK}"):
                        if curva == "qh":
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
                    st.warning(f"Calibra X1, X2, Y1 y Y2 de {'Q-H' if curva == 'qh' else 'Q-η'} "
                              "antes de capturar puntos.")
        else:
            st.caption("Haz click en la imagen para ubicar un punto.")

        st.caption(f"Calibración Q-H: {_estado_cal(cal_all['qh'])} · "
                  f"Calibración Q-η: {_estado_cal(cal_all['qe'])}")
        # botones en fila propia (no en la columna angosta de controles) para
        # que quepan legibles — apilados verticalmente en vez de a 3 por fila.
        if st.button(f"♻ Reiniciar calibración {'Q-H' if curva == 'qh' else 'Q-η'} (esta curva)",
                     key=f"w_rst_cal_{BK}"):
            cal_all[curva] = {}
            bomba.cal = cal_all
            st.session_state[pend_key] = None
            st.rerun()
        if {"X1", "X2", "Y1", "Y2"} <= set(cal) and st.button(
                f"🪄 Detectar {'Q-H' if curva == 'qh' else 'Q-η'} por color "
                "(usa el punto pendiente como muestra)", key=f"w_auto_{curva}_{BK}"):
            if pend:
                arr = np.array(img)
                color = tuple(int(c) for c in arr[pend["y"], pend["x"]])
                pts_px = cv.detect_curve_by_color(arr, color, tolerance=60, n_points=15)
                calx = cv.AxisCalibration(cal["X1"]["px"], cal["X1"]["val"],
                                          cal["X2"]["px"], cal["X2"]["val"], log_x)
                caly = cv.AxisCalibration(cal["Y1"]["px"], cal["Y1"]["val"],
                                          cal["Y2"]["px"], cal["Y2"]["val"], log_y)
                pts_data = [(round(cv.pixel_to_data(pt, calx, caly)[0] * FACTOR_Q[unidad_q], 4),
                            round(cv.pixel_to_data(pt, calx, caly)[1], 4)) for pt in pts_px]
                if curva == "qh":
                    bomba.puntos_qh = pts_data
                    st.session_state[f"qh_px_{BK}"] = [(int(x), int(y)) for x, y in pts_px]
                else:
                    bomba.puntos_qe = pts_data
                    st.session_state[f"qe_px_{BK}"] = [(int(x), int(y)) for x, y in pts_px]
                st.session_state[pend_key] = None
                st.rerun()
        _siguiente_enter = _ENTER_ADVANCE.get(modo)
        if st.button("⏎ Enter — pasar a Q-η" if _siguiente_enter
                     else "⏎ Enter (ya en la última etapa)",
                     key=f"w_enter_{BK}", disabled=_siguiente_enter is None,
                     help="Equivalente al Enter físico (que solo funciona sobre la imagen "
                          "en modo 'lupa en tiempo real'). Termina de capturar los puntos "
                          "de la curva activa y pasa a calibrar los ejes de la otra."):
            st.session_state[f"modo_next_{BK}"] = _siguiente_enter
            st.rerun()

# ---------- importar puntos desde CSV (de cualquier herramienta externa) ----------
with st.expander("📥 Importar puntos desde CSV"):
    st.caption("Dos columnas sin encabezado o con encabezado libre: la primera "
               "columna es Q, la segunda es H (o η). Sirve para pegar puntos "
               "digitalizados con cualquier herramienta externa.")
    ic1, ic2 = st.columns(2)
    up_qh = ic1.file_uploader("CSV de puntos Q-H", type=["csv"], key=f"w_csv_qh_{BK}")
    if up_qh is not None:
        try:
            df_imp = pd.read_csv(up_qh, header=None, comment="#")
            if df_imp.iloc[0].apply(lambda v: isinstance(v, str)).any():
                df_imp = df_imp.iloc[1:]
            nuevos = [(float(r[0]), float(r[1])) for _, r in df_imp.iterrows()]
            bomba.puntos_qh = sorted(set(bomba.puntos_qh) | set(nuevos))
            st.success(f"{len(nuevos)} puntos Q-H importados.")
        except Exception as e:
            st.error(f"No se pudo leer el CSV: {e}")
    up_qe = ic2.file_uploader("CSV de puntos Q-η", type=["csv"], key=f"w_csv_qe_{BK}")
    if up_qe is not None:
        try:
            df_imp = pd.read_csv(up_qe, header=None, comment="#")
            if df_imp.iloc[0].apply(lambda v: isinstance(v, str)).any():
                df_imp = df_imp.iloc[1:]
            nuevos = [(float(r[0]), float(r[1])) for _, r in df_imp.iterrows()]
            bomba.puntos_qe = sorted(set(bomba.puntos_qe) | set(nuevos))
            st.success(f"{len(nuevos)} puntos Q-η importados.")
        except Exception as e:
            st.error(f"No se pudo leer el CSV: {e}")

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

# ---------- catálogo de bombas desde Excel ----------
st.divider()
with st.expander("📚 Catálogo de bombas (Excel) — evalúa y escoge la más eficiente"):
    from core import pump_catalog as pc
    st.download_button("⬇️ Plantilla del catálogo (.xlsx)", data=pc.template_xlsx(),
                       file_name="catalogo_bombas.xlsx")
    st.download_button("⬇️ Exportar bombas del proyecto (.xlsx)",
                       data=pc.export_xlsx(p.bombeos),
                       file_name=f"{(p.nombre or 'proyecto').replace(' ', '_')}_bombas.xlsx",
                       disabled=not any(s.bombas for s in p.bombeos))
    up_cat = st.file_uploader("Catálogo (columnas: Bomba | Q [L/s] | H [m] | eta)",
                              type=["xlsx", "csv"], key=f"w_cat_{sel_sys}")
    if up_cat is not None:
        try:
            candidatas = pc.parse(up_cat)
        except ValueError as e:
            st.error(str(e))
            candidatas = []
        if candidatas:
            q_max_cat = max(qb_lps * 1.5,
                            max(b.puntos_qh[-1][0] for b in candidatas))
            sys_cat = [(q * 1000, h) for q, h in
                       pu.system_curve(resuelto["sistema"], q_max_cat / 1000, n=30)]
            ranking = []
            for b in candidatas:
                fit_c = cv.fit_curve(b.puntos_qh, 2)
                op_c = cv.operating_point(fit_c, sys_cat)
                e_fit_c = (cv.fit_curve(b.puntos_qe, 2)
                           if len(b.puntos_qe) >= 3 else None)
                eta_c = (e_fit_c(op_c[0]) if (op_c and e_fit_c) else float("nan"))
                ranking.append({"Bomba": b.nombre,
                                "Q_op [L/s]": op_c[0] if op_c else float("nan"),
                                "H_op [m]": op_c[1] if op_c else float("nan"),
                                "η(Q_op)": eta_c, "_pump": b})
            df_rank = (pd.DataFrame(ranking).drop(columns="_pump")
                       .sort_values("η(Q_op)", ascending=False))
            st.dataframe(df_rank.style.format(precision=3, na_rep="sin cruce"),
                         hide_index=True, width="stretch")
            validas_cat = [r for r in ranking if r["η(Q_op)"] == r["η(Q_op)"]]
            if validas_cat:
                mejor_cat = max(validas_cat, key=lambda r: r["η(Q_op)"])
                st.caption(f"Mejor del catálogo: **{mejor_cat['Bomba']}** "
                           f"(η={mejor_cat['η(Q_op)']:.3f} en el punto de operación)")
                cb1, cb2 = st.columns(2)
                if cb1.button("✔ Usar la mejor", key=f"w_best_{sel_sys}"):
                    if mejor_cat["Bomba"] not in [x.nombre for x in sys_d.bombas]:
                        sys_d.bombas.append(mejor_cat["_pump"])
                    sys_d.bomba_seleccionada = mejor_cat["Bomba"]
                    st.session_state["sel_bomba_next"] = mejor_cat["Bomba"]
                    st.rerun()
                if cb2.button("➕ Añadir todas al sistema", key=f"w_all_{sel_sys}"):
                    nombres_exist = {x.nombre for x in sys_d.bombas}
                    sys_d.bombas.extend(r["_pump"] for r in ranking
                                        if r["Bomba"] not in nombres_exist)
                    st.rerun()

# ---------- comparación de las bombas del sistema ----------
st.divider()
st.subheader(f"Curva del sistema '{sel_sys}' vs bombas candidatas")
q_max_lps = max(qb_lps * 1.5, max((b.puntos_qh[-1][0] for b in sys_d.bombas
                                   if len(b.puntos_qh) >= 3), default=0.0))
sys_pts = pu.system_curve(resuelto["sistema"], q_max=max(q_max_lps / 1000, 1e-4), n=30)
sys_lps = [(q * 1000, h) for q, h in sys_pts]

rows, ecuaciones, bombas_fig = [], [], []
for b in sys_d.bombas:
    if len(b.puntos_qh) < 3:
        continue
    with st.expander(f"⚙ Afinidad / arreglo — {b.nombre}", expanded=False):
        af1, af2, af3, af4 = st.columns(4)
        b.n1_nominal = num_input("N₁ nominal (rpm/Hz, 0=sin afinidad)",
                                 f"n1_{BK}_{b.nombre}", b.n1_nominal, decimals=0,
                                 container=af1, min_value=0.0, max_value=10000.0)
        b.n2_objetivo = num_input("N₂ objetivo", f"n2_{BK}_{b.nombre}",
                                  b.n2_objetivo, decimals=0, container=af2,
                                  min_value=0.0, max_value=10000.0)
        b.n_unidades = int_input("Nº de bombas", f"nu_{BK}_{b.nombre}",
                                 b.n_unidades, container=af3, min_value=1, max_value=10)
        b.arreglo = af4.selectbox("Arreglo", ["paralelo", "serie"],
                                  index=["paralelo", "serie"].index(b.arreglo),
                                  key=f"w_sel_arr_{BK}_{b.nombre}")
    qh_t, qe_t = _puntos_transformados(b)
    fit = cv.fit_curve(qh_t, 2)
    op = cv.operating_point(fit, sys_lps)
    bep = cv.best_efficiency_point(qe_t, 2) if len(qe_t) >= 3 else None
    e_fit = cv.fit_curve(qe_t, 2) if len(qe_t) >= 3 else None
    afinidad_activa = b.n1_nominal > 0 and b.n2_objetivo not in (0, b.n1_nominal)
    transformada = b.n_unidades > 1 or afinidad_activa
    partes_etq = []
    if b.n_unidades > 1:
        partes_etq.append(f"{b.n_unidades}×{b.arreglo}")
    if afinidad_activa:
        partes_etq.append(f"@ N₂={b.n2_objetivo:.0f}")
    etiqueta = (f"{b.nombre} ({' '.join(partes_etq)})"
               if transformada else f"{b.nombre} (R²={fit.r2:.3f})")
    bombas_fig.append({"nombre": etiqueta, "fit": fit, "op": op, "e_fit": e_fit})
    if transformada:
        fit_nom = cv.fit_curve(b.puntos_qh, 2)
        bombas_fig.append({"nombre": f"{b.nombre} (nominal)", "fit": fit_nom, "op": None,
                           "e_fit": None, "faint": True})
    A, B, C = fit.coeffs
    ecu = {"Bomba": b.nombre,
           "H(Q)": f"H = {A:+.4f}·Q² {B:+.4f}·Q {C:+.3f}  (R²={fit.r2:.4f})",
           "η(Q)": (f"η = {e_fit.coeffs[0]:+.6f}·Q² {e_fit.coeffs[1]:+.5f}·Q "
                    f"{e_fit.coeffs[2]:+.4f}  (R²={e_fit.r2:.4f})" if e_fit else "—"),
           "H(Qb) [m]": fit(qb_lps) if fit.q_min <= qb_lps <= fit.q_max else float("nan"),
           "η(Qb)": (e_fit(qb_lps) if e_fit and e_fit.q_min <= qb_lps <= e_fit.q_max
                     else float("nan"))}
    if op:
        eta = e_fit(op[0]) if e_fit else float("nan")
        pot = (998.29 * 9.81 * op[0] / 1000 * op[1] / eta / 745.7
               if eta and eta > 0 else float("nan"))
        rows.append({"Bomba": b.nombre, "Q_op [L/s]": op[0], "H_op [m]": op[1],
                     "η(Q_op)": eta, "BEP Q [L/s]": bep.q if bep else float("nan"),
                     "Desv. BEP [%]": (op[0] - bep.q) / bep.q * 100 if bep else float("nan"),
                     "P absorbida [HP]": pot})
        ecu["H(Q_op) [m]"], ecu["η(Q_op)"] = op[1], eta
    else:
        rows.append({"Bomba": b.nombre, "Q_op [L/s]": float("nan"),
                     "H_op [m]": float("nan"), "η(Q_op)": float("nan"),
                     "BEP Q [L/s]": bep.q if bep else float("nan"),
                     "Desv. BEP [%]": float("nan"), "P absorbida [HP]": float("nan")})
        ecu["H(Q_op) [m]"], ecu["η(Q_op)"] = float("nan"), float("nan")
    ecuaciones.append(ecu)

from core import report_figs as rf
fig = rf.fig_sistema(sys_lps, bombas_fig, qb_lps, hd, dark=True)
st.pyplot(fig)
plt.close(fig)

if ecuaciones:
    st.subheader("Regresiones polinómicas (H = A·Q²+B·Q+C · η = D·Q²+E·Q+F)")
    st.dataframe(pd.DataFrame(ecuaciones).style.format(
        {"H(Qb) [m]": "{:.2f}", "η(Qb)": "{:.3f}", "H(Q_op) [m]": "{:.2f}",
         "η(Q_op)": "{:.3f}"}, na_rep="fuera de rango"),
        hide_index=True, width="stretch")

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

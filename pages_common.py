"""Helpers compartidos por las páginas."""
import datetime as dt
from pathlib import Path

import streamlit as st
from core import project as pj
from core.project import Project

# Prefijo de todos los keys de widgets numéricos — permite limpiarlos al cargar proyecto
WIDGET_PREFIX = "w_"
SAVES_DIR = Path(__file__).resolve().parent / "saves"
AUTOSAVE_FILE = SAVES_DIR / "_autosave.acucalc.json"
AUTOSAVE_THROTTLE_S = 30

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&display=swap');

:root {
  --ac-green: #22C55E;
  --ac-green-bright: #4ADE80;
  --ac-blue: #38BDF8;
  --ac-blue-deep: #0EA5E9;
  --ac-bg: #0B1416;
  --ac-surface: #12242A;
  --ac-surface-2: #16323A;
  --ac-border: #1E3A42;
  --ac-text-dim: #9FBFB6;
  --ac-ease: cubic-bezier(0.4, 0, 0.2, 1);
}

html, body, [data-testid="stAppViewContainer"], .stMarkdown, p, label,
h1, h2, h3, h4, button, input, textarea, select {
  font-family: 'Space Grotesk', 'Inter', -apple-system, sans-serif !important;
}
[data-testid^="stIcon"], [class*="material-symbols"] {
  font-family: 'Material Symbols Rounded', 'Material Symbols Outlined' !important;
}

/* ---------- tipografía y jerarquía ---------- */
h1, h2, h3 {
  color: var(--ac-green-bright) !important;
  font-weight: 600 !important;
  letter-spacing: -0.01em;
}
[data-testid="stMetricValue"] { color: var(--ac-blue) !important; font-weight: 600 !important; }
[data-testid="stMetricLabel"] { color: var(--ac-text-dim) !important; }
a { color: var(--ac-blue) !important; transition: color 0.15s var(--ac-ease); }
a:hover { color: var(--ac-green-bright) !important; }
[data-testid="stCaptionContainer"] { color: var(--ac-text-dim) !important; }

/* ---------- fondo con gradiente sutil (glass look) ---------- */
[data-testid="stAppViewContainer"] {
  background: radial-gradient(1200px 800px at 15% -10%, rgba(34,197,94,0.06), transparent 60%),
              radial-gradient(1000px 700px at 100% 0%, rgba(56,189,248,0.05), transparent 55%),
              var(--ac-bg) !important;
}
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, var(--ac-surface) 0%, var(--ac-bg) 100%) !important;
  border-right: 1px solid var(--ac-border);
}

/* ---------- superficies: dataframe, expander, popover, contenedores ---------- */
div[data-testid="stDataFrame"], div[data-testid="stDataEditor"] {
  border: 1px solid var(--ac-border);
  border-radius: 10px;
  overflow: hidden;
}
[data-testid="stExpander"] {
  border: 1px solid var(--ac-border) !important;
  border-radius: 10px !important;
  background: rgba(18, 36, 42, 0.5) !important;
  backdrop-filter: blur(6px);
  transition: border-color 0.2s var(--ac-ease);
}
[data-testid="stExpander"]:hover { border-color: rgba(34,197,94,0.4) !important; }
[data-testid="stVerticalBlockBorderWrapper"] > div {
  border-radius: 10px;
}

/* ---------- botones ---------- */
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {
  border-radius: 8px !important;
  border: 1px solid var(--ac-border) !important;
  background: linear-gradient(135deg, rgba(34,197,94,0.12), rgba(56,189,248,0.08)) !important;
  transition: transform 0.12s var(--ac-ease), border-color 0.15s var(--ac-ease),
              box-shadow 0.15s var(--ac-ease) !important;
}
.stButton > button:hover, .stDownloadButton > button:hover, .stFormSubmitButton > button:hover {
  border-color: var(--ac-green) !important;
  box-shadow: 0 0 0 1px rgba(34,197,94,0.25), 0 4px 12px rgba(34,197,94,0.12) !important;
  transform: translateY(-1px);
}
.stButton > button:active, .stDownloadButton > button:active { transform: translateY(0); }
.stButton > button[kind="primary"] {
  background: linear-gradient(135deg, var(--ac-green), var(--ac-blue-deep)) !important;
  border: none !important;
  color: #06120B !important;
  font-weight: 600 !important;
}

/* ---------- inputs, selects, sliders ---------- */
[data-testid="stTextInput"] input, [data-testid="stNumberInput"] input,
[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
[data-testid="stTextArea"] textarea {
  border-radius: 8px !important;
  border: 1px solid var(--ac-border) !important;
  transition: border-color 0.15s var(--ac-ease), box-shadow 0.15s var(--ac-ease) !important;
  background: var(--ac-surface-2) !important;
}
[data-testid="stTextInput"] input:focus, [data-testid="stNumberInput"] input:focus,
[data-testid="stTextArea"] textarea:focus {
  border-color: var(--ac-blue) !important;
  box-shadow: 0 0 0 2px rgba(56,189,248,0.18) !important;
}
[data-testid="stSlider"] [role="slider"] {
  background: var(--ac-green-bright) !important;
  box-shadow: 0 0 0 4px rgba(74,222,128,0.15) !important;
}

/* ---------- alertas ---------- */
[data-testid="stAlertContentInfo"], div[data-baseweb="notification"] {
  border-radius: 10px !important;
}
[data-testid="stNotification"] {
  border-radius: 10px !important;
  border-left: 3px solid var(--ac-blue) !important;
  animation: ac-fade-in 0.25s var(--ac-ease);
}

/* ---------- tabs ---------- */
[data-testid="stTabs"] [data-baseweb="tab"] {
  transition: color 0.15s var(--ac-ease);
}
[data-testid="stTabs"] [aria-selected="true"] {
  color: var(--ac-green-bright) !important;
}
[data-baseweb="tab-highlight"] {
  background: linear-gradient(90deg, var(--ac-green), var(--ac-blue)) !important;
}

/* ---------- aparición suave de bloques al cargar ---------- */
[data-testid="stVerticalBlock"] > div { animation: ac-fade-in 0.35s var(--ac-ease); }
@keyframes ac-fade-in {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Cursor de cruz sobre imágenes y el componente de digitalización */
[data-testid="stImage"] img, iframe[title*="image_coordinates"] { cursor: crosshair !important; }

/* ---------- responsive: tablet / pantallas angostas ---------- */
@media (max-width: 900px) {
  h1, h2, h3 { font-size: 90% !important; }
  .stButton > button, .stDownloadButton > button { width: 100% !important; }
  [data-testid="stMetricValue"] { font-size: 1.4rem !important; }
}
</style>
"""


def get_project() -> Project:
    if "project" not in st.session_state:
        st.session_state["project"] = Project()
    return st.session_state["project"]


def resolve_save_path(p: Project) -> Path | None:
    """Ruta destino del `.acucalc.json` según `p.ruta_guardado` (la carpeta/archivo
    que el usuario fija en la página 1). Devuelve None si no hay ruta configurada
    (entonces se usa la carpeta interna `saves/`).

    - Cadena vacía → None.
    - Termina en `.json` → se usa ese archivo tal cual.
    - Si no → se trata como carpeta: `<carpeta>/<nombre>.acucalc.json`.
    """
    raw = (p.ruta_guardado or "").strip().strip('"')
    if not raw:
        return None
    path = Path(raw).expanduser()
    if path.suffix.lower() == ".json":
        return path
    slug = (p.nombre or "proyecto").replace(" ", "_")
    return path / f"{slug}.acucalc.json"


def _autosave(p: Project) -> None:
    if not p.nombre:
        return
    now = dt.datetime.now().timestamp()
    if now - st.session_state.get("_autosave_ts", 0.0) < AUTOSAVE_THROTTLE_S:
        return
    dest = resolve_save_path(p)
    try:
        if dest is not None:
            dest.parent.mkdir(parents=True, exist_ok=True)
            pj.save(p, dest)               # canónico: el archivo del usuario
        else:
            SAVES_DIR.mkdir(exist_ok=True)
            pj.save(p, AUTOSAVE_FILE)      # fallback interno si no hay ruta
        st.session_state["_autosave_ts"] = now
        st.session_state.pop("_autosave_error", None)
    except Exception as e:                  # ruta inválida/permiso/etc: no romper la app
        st.session_state["_autosave_error"] = str(e)


def page_setup() -> Project:
    """CSS del tema + autosave + controles de guardado en la barra lateral.
    Llamar al inicio de cada página; devuelve el proyecto activo."""
    st.markdown(_CSS, unsafe_allow_html=True)
    p = get_project()
    _autosave(p)
    with st.sidebar:
        st.divider()
        if p.nombre:
            st.caption(f"Proyecto: **{p.nombre}**")
        dest = resolve_save_path(p)
        ayuda = (f"Guarda en tu carpeta: {dest}" if dest is not None
                 else "Guarda en la carpeta saves/ del programa (fija una ruta en "
                      "la página 1 para guardar en tu propia carpeta)")
        if st.button("💾 Guardar estado del proyecto", width="stretch",
                     disabled=not p.nombre, help=ayuda):
            try:
                if dest is not None:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    pj.save(p, dest)
                    guardado_en = str(dest)
                else:
                    SAVES_DIR.mkdir(exist_ok=True)
                    f = SAVES_DIR / f"{p.nombre.replace(' ', '_')}.acucalc.json"
                    pj.save(p, f)
                    guardado_en = f.name
                st.session_state["last_save"] = (
                    guardado_en, dt.datetime.now().strftime("%H:%M:%S"))
                st.session_state.pop("_autosave_error", None)
            except OSError as e:
                st.error(f"No se pudo guardar en la ruta indicada: {e}")
        if "last_save" in st.session_state:
            n, h = st.session_state["last_save"]
            st.caption(f"Guardado: {n} · {h}")
        if "_autosave_error" in st.session_state:
            st.caption(f"⚠ Autosave falló: {st.session_state['_autosave_error']}")
    return p


def show_issues(issues: list[str]) -> None:
    for i in issues:
        st.warning(i)


def num_input(label: str, key: str, default: float, decimals: int = 2,
              container=None, **kw) -> float:
    """number_input con key estable: session_state manda, `default` solo aplica
    la primera vez. Evita el bug de valores que se resetean/pisan lo tecleado
    (el patrón value=modelo cambia el default entre reruns por redondeos float
    y Streamlit descarta la edición del usuario)."""
    k = WIDGET_PREFIX + key
    if k not in st.session_state:
        st.session_state[k] = round(float(default), decimals)
    target = container if container is not None else st
    return float(target.number_input(
        label, key=k, step=10.0 ** -decimals, format=f"%.{decimals}f", **kw))


def int_input(label: str, key: str, default: int, container=None, **kw) -> int:
    """number_input entero con key estable (mismo principio que num_input)."""
    k = WIDGET_PREFIX + key
    if k not in st.session_state:
        st.session_state[k] = int(default)
    target = container if container is not None else st
    return int(target.number_input(label, key=k, step=1, **kw))


def clear_widget_state() -> None:
    """Borra los keys de widgets numéricos — llamar al cargar un proyecto para
    que los valores del archivo cargado se conviertan en los nuevos defaults."""
    for k in [k for k in st.session_state if k.startswith(WIDGET_PREFIX)]:
        del st.session_state[k]

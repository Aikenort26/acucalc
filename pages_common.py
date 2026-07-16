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
/* Tema oscuro de alto contraste — énfasis verde (primario) y azul */
h1, h2, h3 { color: #4ADE80 !important; }
[data-testid="stMetricValue"] { color: #38BDF8 !important; }
[data-testid="stMetricLabel"] { color: #A7D3C8 !important; }
a { color: #38BDF8 !important; }
[data-testid="stCaptionContainer"] { color: #9FBFB6 !important; }
div[data-testid="stDataFrame"] { border: 1px solid #1E3A42; border-radius: 6px; }
/* Cursor de cruz sobre imágenes y el componente de digitalización */
[data-testid="stImage"] img, iframe[title*="image_coordinates"] { cursor: crosshair !important; }
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
    except OSError as e:                    # ruta inválida/permiso: no romper la app
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

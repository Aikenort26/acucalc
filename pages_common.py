"""Helpers compartidos por las páginas."""
import streamlit as st
from core.project import Project

# Prefijo de todos los keys de widgets numéricos — permite limpiarlos al cargar proyecto
WIDGET_PREFIX = "w_"


def get_project() -> Project:
    if "project" not in st.session_state:
        st.session_state["project"] = Project()
    return st.session_state["project"]


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

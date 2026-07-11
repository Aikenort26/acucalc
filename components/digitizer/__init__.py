"""Digitalizador de curvas con lupa en tiempo real (componente Streamlit propio).

Devuelve {"x": int, "y": int, "n": timestamp} del último click sobre la imagen,
en coordenadas de pixel de la imagen original."""
from pathlib import Path

import streamlit.components.v1 as components

_component = components.declare_component(
    "acucalc_digitizer", path=str(Path(__file__).resolve().parent))


def digitizer(image_b64: str, markers: dict, key: str | None = None):
    """image_b64: base64 crudo (jpg/png). markers: {"cal": [{"x","y","label"}],
    "qh": [[x,y]], "qe": [[x,y]], "pending": [x,y]|None}."""
    mime = "image/jpeg" if image_b64.startswith("/9j") else "image/png"
    return _component(image=f"data:{mime};base64,{image_b64}",
                      markers=markers, key=key, default=None)

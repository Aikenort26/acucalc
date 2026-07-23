"""Pegar imagen desde el portapapeles (componente Streamlit propio).

Mismo contrato de declare_component que components/digitizer: devuelve
{"b64": str, "n": timestamp} de la última imagen pegada (Ctrl+V), o None si
aún no se ha pegado nada. `b64` es el contenido crudo (sin el prefijo
`data:image/...;base64,`) para poder decodificarse igual que la imagen del
file_uploader existente."""
from pathlib import Path

import streamlit.components.v1 as components

_component = components.declare_component(
    "acucalc_paste_image", path=str(Path(__file__).resolve().parent))


def paste_image(key: str | None = None):
    return _component(key=key, default=None)

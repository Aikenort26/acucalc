"""Utilidades de imagen para lo que se guarda como base64 dentro del proyecto."""
import base64
import io

from PIL import Image, UnidentifiedImageError

MAX_LADO = 2000


def reducir_a_b64(raw: bytes, max_lado: int = MAX_LADO) -> str:
    """Base64 de la imagen, reducida para que su lado mayor no pase de
    `max_lado` px, conservando proporción y formato. El proyecto completo se
    reescribe con cada autosave (~30 s), así que una foto de 20 MB lo vuelve
    lento. Bytes que no son imagen se devuelven sin cambios."""
    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except (UnidentifiedImageError, OSError):
        return base64.b64encode(raw).decode()
    if max(img.size) <= max_lado:
        return base64.b64encode(raw).decode()
    formato = img.format or "PNG"
    img.thumbnail((max_lado, max_lado), Image.LANCZOS)
    buf = io.BytesIO()
    if formato == "JPEG":
        img.convert("RGB").save(buf, "JPEG", quality=90)
    else:
        img.save(buf, "PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode()

import base64
import io

from PIL import Image

from core import imagenes as im


def _png(w, h, modo="RGBA"):
    buf = io.BytesIO()
    Image.new(modo, (w, h), (10, 20, 30, 255) if modo == "RGBA" else (10, 20, 30)).save(buf, "PNG")
    return buf.getvalue()


def _jpg(w, h):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (200, 100, 50)).save(buf, "JPEG")
    return buf.getvalue()


def _dims(b64):
    return Image.open(io.BytesIO(base64.b64decode(b64))).size


def test_imagen_grande_se_reduce_conservando_proporcion():
    b64 = im.reducir_a_b64(_png(4000, 1000), max_lado=2000)
    assert _dims(b64) == (2000, 500)


def test_imagen_pequena_no_se_toca():
    raw = _png(300, 200)
    assert base64.b64decode(im.reducir_a_b64(raw, max_lado=2000)) == raw


def test_formato_se_conserva():
    b64 = im.reducir_a_b64(_jpg(3000, 3000), max_lado=1000)
    assert base64.b64decode(b64)[:3] == b"\xff\xd8\xff"          # JPEG
    b64 = im.reducir_a_b64(_png(3000, 3000), max_lado=1000)
    assert base64.b64decode(b64)[:8] == b"\x89PNG\r\n\x1a\n"      # PNG con alfa


def test_bytes_no_imagen_se_devuelven_intactos():
    raw = b"no soy una imagen"
    assert base64.b64decode(im.reducir_a_b64(raw)) == raw

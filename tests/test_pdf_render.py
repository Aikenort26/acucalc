"""WP-B1: render de PDF de curva de bomba a PNG de alta resolución.

`pages/6_Curvas_de_bomba.py` no es importable directamente en tests (es un
script de página de Streamlit que ejecuta `page_setup()`/`st.stop()` al
importarse, fuera de un runtime de Streamlit). Por eso este test no importa
`_pdf_page1_to_png_bytes` de la página; en su lugar ejercita exactamente la
misma secuencia de pypdfium2 (PdfDocument → get_page(0) → render(scale=...)
→ to_pil()) sobre un PDF sintético de una sola página generado con el propio
pypdfium2 (evita depender de reportlab u otro generador de PDF externo), y
confirma que escala la resolución tal como hace la página. Esto cubre el
camino de render de PDF con una dependencia real, aunque no ejecute la línea
exacta de la página — ver el reporte de la tarea para la justificación."""
import io

import pypdfium2 as pdfium
from PIL import Image


def _synthetic_pdf_bytes(width_pt: float = 200.0, height_pt: float = 150.0) -> bytes:
    doc = pdfium.PdfDocument.new()
    doc.new_page(width_pt, height_pt)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_render_pagina1_a_png_escala_resolucion():
    pdf_bytes = _synthetic_pdf_bytes(200.0, 150.0)
    doc = pdfium.PdfDocument(pdf_bytes)
    assert len(doc) == 1
    page = doc.get_page(0)
    bitmap = page.render(scale=3.5)
    pil_img = bitmap.to_pil().convert("RGB")

    # 200x150 pt a scale=3.5 -> 700x525 px (pypdfium2 redondea al entero más cercano)
    assert pil_img.size == (700, 525)

    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    png_bytes = buf.getvalue()
    assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n"
    reopened = Image.open(io.BytesIO(png_bytes))
    assert reopened.size == (700, 525)


def test_render_escala_mayor_produce_imagen_mas_grande():
    pdf_bytes = _synthetic_pdf_bytes(100.0, 100.0)
    doc = pdfium.PdfDocument(pdf_bytes)
    page = doc.get_page(0)
    small = page.render(scale=1.0).to_pil()
    big = page.render(scale=4.0).to_pil()
    assert big.size[0] > small.size[0] and big.size[1] > small.size[1]

import io
import math

import pytest
from PIL import Image

from core import geo


def _png(color, lado=256):
    buf = io.BytesIO()
    Image.new("RGB", (lado, lado), color).save(buf, "PNG")
    return buf.getvalue()


def _color_de(x, y):
    return (x * 40 % 256, y * 40 % 256, 128)


class _FetchFalso:
    """Devuelve teselas de color según (x, y) y registra las URL pedidas."""

    def __init__(self):
        self.urls = []

    def __call__(self, url):
        self.urls.append(url)
        z, x, y = (int(v) for v in url.rsplit(".", 1)[0].split("/")[-3:])
        return _png(_color_de(x, y))


def test_pixel_global_del_origen_en_zoom_0():
    assert geo.latlon_a_pixel(0.0, 0.0, 0) == pytest.approx((128.0, 128.0))


def test_ida_y_vuelta_pixel_latlon():
    px, py = geo.latlon_a_pixel(9.83, -75.12, 14)
    lat, lon = geo.pixel_a_latlon(px, py, 14)
    assert (lat, lon) == pytest.approx((9.83, -75.12), abs=1e-9)


def test_resolucion_en_metros_por_pixel():
    assert geo.metros_por_pixel(0.0, 0) == pytest.approx(2 * math.pi * 6378137 / 256)
    assert geo.metros_por_pixel(60.0, 10) == pytest.approx(geo.metros_por_pixel(0.0, 10) / 2)


def test_urls_osm_y_esri_con_su_orden_de_indices():
    assert geo.url_tesela("osm", 5, 7, 9) == "https://tile.openstreetmap.org/5/7/9.png"
    assert geo.url_tesela("esri", 5, 7, 9).endswith("/World_Imagery/MapServer/tile/5/9/7")
    with pytest.raises(KeyError):
        geo.url_tesela("google", 1, 0, 0)


def test_mosaico_centrado_y_minimo_de_teselas(tmp_path):
    fetch = _FetchFalso()
    m = geo.componer(9.83, -75.12, 12, 600, 400, "osm", fetch=fetch, cache_dir=tmp_path)
    assert m.imagen.size == (600, 400)
    cx, cy = m.a_pixel(9.83, -75.12)
    assert (cx, cy) == pytest.approx((300.0, 200.0), abs=1.0)   # origen en píxel entero
    # el píxel del punto tiene el color de la tesela que lo contiene
    px, py = geo.latlon_a_pixel(9.83, -75.12, 12)
    assert m.imagen.getpixel((int(cx), int(cy))) == _color_de(int(px // 256), int(py // 256))
    # ida y vuelta entre píxel local y lat/lon
    assert m.a_latlon(cx, cy) == pytest.approx((9.83, -75.12), abs=1e-9)
    # 600×400 px cubre a lo sumo 4×3 teselas
    assert len(fetch.urls) <= 12 and len(set(fetch.urls)) == len(fetch.urls)


def test_la_cache_evita_volver_a_descargar(tmp_path):
    fetch = _FetchFalso()
    geo.componer(4.6, -74.08, 10, 300, 300, "osm", fetch=fetch, cache_dir=tmp_path)
    n = len(fetch.urls)
    geo.componer(4.6, -74.08, 10, 300, 300, "osm", fetch=fetch, cache_dir=tmp_path)
    assert n > 0 and len(fetch.urls) == n


def test_sin_conexion_da_error_en_espanol(tmp_path):
    def falla(url):
        raise OSError("sin red")
    with pytest.raises(geo.GeoError, match="teselas"):
        geo.componer(4.6, -74.08, 10, 300, 300, "osm", fetch=falla, cache_dir=tmp_path)


def test_respuesta_que_no_es_imagen_es_error(tmp_path):
    with pytest.raises(geo.GeoError):
        geo.componer(4.6, -74.08, 10, 300, 300, "esri", fetch=lambda u: b"<html>",
                     cache_dir=tmp_path)


def test_zoom_fuera_de_rango_es_error(tmp_path):
    with pytest.raises(ValueError):
        geo.componer(4.6, -74.08, 25, 300, 300, "osm", fetch=_FetchFalso(), cache_dir=tmp_path)


def test_descarga_por_defecto_envia_user_agent(monkeypatch):
    enviado = {}

    class _Resp:
        status_code = 200
        content = b"x"

        def raise_for_status(self):
            pass

    def get(url, headers=None, timeout=None, params=None):
        enviado.update(headers or {})
        return _Resp()

    monkeypatch.setattr(geo.requests, "get", get)
    geo.descargar("https://tile.openstreetmap.org/0/0/0.png")
    assert enviado["User-Agent"].startswith("ACUCALC")


def test_buscar_con_nominatim(monkeypatch):
    monkeypatch.setattr(geo, "_INTERVALO", 0.0)
    pedido = {}

    def fetch_json(url, params):
        pedido.update(params)
        return [{"display_name": "San Jacinto, Bolívar, Colombia", "lat": "9.8307",
                 "lon": "-75.1215"}]

    lugares = geo.buscar("San Jacinto, Bolívar", fetch_json=fetch_json)
    assert lugares == [geo.Lugar("San Jacinto, Bolívar, Colombia", 9.8307, -75.1215)]
    assert pedido["q"] == "San Jacinto, Bolívar" and pedido["format"] == "jsonv2"
    assert geo.buscar("   ", fetch_json=fetch_json) == []


def test_mensaje_de_error_legible_sin_conexion(tmp_path):
    def falla(url):
        raise geo.requests.exceptions.ConnectionError("Max retries exceeded ... proxy")
    with pytest.raises(geo.GeoError, match="sin conexión con el servidor") as e:
        geo.componer(4.6, -74.08, 10, 300, 300, "osm", fetch=falla, cache_dir=tmp_path)
    assert "Max retries" not in str(e.value)

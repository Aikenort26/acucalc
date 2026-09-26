import io

import matplotlib
matplotlib.use("Agg")
import pytest
from PIL import Image

from core import geo, network, study_map as sm

INP_9377 = """[JUNCTIONS]
J1 10 0
J2 8 0

[RESERVOIRS]
R1 50

[PIPES]
P1 R1 J1 200 150 130
P2 J1 J2 150 100 130

[COORDINATES]
R1 4999800 2000000
J1 5000000 2000000
J2 5000150 2000100

[OPTIONS]
Units LPS
"""


def _mosaico(lat=4.0, lon=-73.0, z=15, ancho=400, alto=300, fuente="osm"):
    def fetch(url):
        buf = io.BytesIO()
        Image.new("RGB", (256, 256), (200, 220, 200)).save(buf, "PNG")
        return buf.getvalue()
    return geo.componer(lat, lon, z, ancho, alto, fuente, fetch=fetch, cache_dir=_CACHE[0])


_CACHE = [None]


@pytest.fixture(autouse=True)
def _cache(tmp_path):
    _CACHE[0] = tmp_path


def test_mapa_guardado_conserva_geometria_e_imagen():
    m = _mosaico(fuente="esri")
    g = sm.mapa_de_mosaico("zona", m)
    assert (g.nombre, g.fuente, g.z, g.px0, g.py0, g.ancho, g.alto) == \
        ("zona", "esri", 15, m.px0, m.py0, 400, 300)
    img = sm.imagen_de(g)
    assert img.size == (400, 300) and img.format == "JPEG"      # Esri se guarda en JPEG
    assert sm.imagen_de(sm.mapa_de_mosaico("zona", _mosaico())).format == "PNG"


def test_extension_contiene_el_centro():
    g = sm.mapa_de_mosaico("zona", _mosaico())
    lat_min, lon_min, lat_max, lon_max = sm.extension(g)
    assert lat_min < 4.0 < lat_max and lon_min < -73.0 < lon_max


def test_red_en_magna_origen_nacional_a_wgs84():
    red = network.parse_inp(INP_9377)
    seg = sm.red_a_latlon(red, 9377)
    assert len(seg) == 2
    j1 = next(s for s in seg if s.id == "P1").puntos[1]
    assert j1 == pytest.approx((4.0, -73.0), abs=1e-7)           # J1 en el origen de 9377
    assert sm.fraccion_dentro(sm.mapa_de_mosaico("zona", _mosaico()), seg) == 1.0


def test_red_en_otro_sistema_queda_fuera_del_mapa():
    red = network.parse_inp(INP_9377)
    seg = sm.red_a_latlon(red, 3116)                              # CRS equivocado
    assert sm.fraccion_dentro(sm.mapa_de_mosaico("zona", _mosaico()), seg) == 0.0


def test_red_sin_coordenadas_no_aporta_segmentos():
    red = network.parse_inp(INP_9377.split("[COORDINATES]")[0] + "[OPTIONS]\nUnits LPS\n")
    assert sm.red_a_latlon(red, 9377) == []


@pytest.mark.parametrize("objetivo,esperado", [(1234, 1000), (380, 200), (49, 20),
                                                (5.2, 5), (7600, 5000)])
def test_longitud_de_escala_redonda(objetivo, esperado):
    assert sm.escala_redonda(objetivo) == esperado


def test_figura_con_escala_norte_atribucion_y_red():
    g = sm.mapa_de_mosaico("zona", _mosaico())
    seg = sm.red_a_latlon(network.parse_inp(INP_9377), 9377)
    fig = sm.fig_localizacion(g, 4.0, -73.0, "Zona de estudio", segmentos=seg)
    textos = [t.get_text() for t in fig.axes[0].texts]
    assert "N" in textos
    assert any("OpenStreetMap" in t for t in textos)
    assert any(t.endswith(" m") or t.endswith(" km") for t in textos)
    assert len(fig.axes[0].lines) >= 2                            # tuberías + sitio


def test_mapa_general_marca_la_zona_de_estudio():
    general = sm.mapa_de_mosaico("general", _mosaico(z=12))
    zona = sm.mapa_de_mosaico("zona", _mosaico(z=15))
    fig = sm.fig_localizacion(general, 4.0, -73.0, "Localización general",
                              recuadro=sm.extension(zona))
    assert any(p.get_edgecolor()[:3] != (1, 1, 1) and not p.get_fill()
               for p in fig.axes[0].patches)                      # recuadro sin relleno
    lejos = sm.fig_localizacion(sm.mapa_de_mosaico("general", _mosaico(z=8)), 4.0, -73.0, "",
                                recuadro=sm.extension(zona))
    assert not any(not p.get_fill() for p in lejos.axes[0].patches)  # diminuto: se omite


def test_mapa_invalido_no_genera_figura():
    assert sm.fig_localizacion(None, 4.0, -73.0, "x") is None
    vacio = sm.mapa_de_mosaico("zona", _mosaico())
    vacio.img_b64 = ""
    assert sm.fig_localizacion(vacio, 4.0, -73.0, "x") is None

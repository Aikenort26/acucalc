"""Mapas de localización del proyecto: mosaicos guardados, superposición de la
red (reproyectada con pyproj desde el sistema del .inp a WGS84) y la figura
del informe con barra de escala, norte, coordenadas y atribución.

Todo trabaja sobre `MapaGuardado` (imagen ya descargada): el informe no
necesita conexión."""
import base64
import io
import math
from dataclasses import dataclass

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.ticker import MaxNLocator
from PIL import Image

from core import geo
from core.project import MapaGuardado

ANCHO_PX, ALTO_PX = 1000, 750          # tamaño de cada mosaico descargado

# Sistemas de coordenadas habituales de los .inp en Colombia.
EPSG_RED = {
    0: "No superponer la red",
    9377: "MAGNA-SIRGAS / Origen Nacional (EPSG:9377)",
    3116: "MAGNA-SIRGAS / Colombia Bogotá (EPSG:3116)",
    3115: "MAGNA-SIRGAS / Colombia Oeste (EPSG:3115)",
    3114: "MAGNA-SIRGAS / Colombia Oeste Oeste (EPSG:3114)",
    3117: "MAGNA-SIRGAS / Colombia Este Central (EPSG:3117)",
    3118: "MAGNA-SIRGAS / Colombia Este (EPSG:3118)",
    4326: "WGS84 geográficas, x = longitud, y = latitud (EPSG:4326)",
}

_TINTA = "#1f1f1f"
_SITIO = "#c62828"                     # un solo acento: el sitio y el recuadro de la zona
_RED = {"osm": ("#1a4f9c", "white"), "esri": ("#ffd23f", "#1f1f1f")}   # (trazo, halo)


@dataclass(frozen=True)
class Segmento:
    id: str
    puntos: tuple                      # ((lat, lon), (lat, lon))


def mapa_de_mosaico(nombre: str, m: geo.Mosaico) -> MapaGuardado:
    formato = geo.FUENTES[m.fuente].formato
    buf = io.BytesIO()
    if formato == "JPEG":
        m.imagen.convert("RGB").save(buf, "JPEG", quality=85)
    else:
        m.imagen.save(buf, "PNG", optimize=True)
    return MapaGuardado(nombre, m.fuente, m.z, m.px0, m.py0, m.imagen.width, m.imagen.height,
                        base64.b64encode(buf.getvalue()).decode())


def componer_mapas(ub, fetch=None, cache_dir=None) -> list[MapaGuardado]:
    """Descarga el mapa general y el de la zona de estudio (llamar solo desde
    un botón: usa la red)."""
    return [mapa_de_mosaico(nombre, geo.componer(ub.lat, ub.lon, z, ANCHO_PX, ALTO_PX,
                                                 ub.fuente, fetch=fetch, cache_dir=cache_dir))
            for nombre, z in (("general", ub.zoom_general), ("zona", ub.zoom_zona))]


def imagen_de(mapa: MapaGuardado) -> Image.Image:
    img = Image.open(io.BytesIO(base64.b64decode(mapa.img_b64)))
    img.load()
    return img


def _mosaico(mapa: MapaGuardado) -> geo.Mosaico:
    return geo.Mosaico(None, mapa.z, mapa.px0, mapa.py0, mapa.fuente)


def extension(mapa: MapaGuardado) -> tuple[float, float, float, float]:
    """(lat_min, lon_min, lat_max, lon_max) del mapa guardado."""
    m = _mosaico(mapa)
    lat_max, lon_min = m.a_latlon(0, 0)
    lat_min, lon_max = m.a_latlon(mapa.ancho, mapa.alto)
    return lat_min, lon_min, lat_max, lon_max


def red_a_latlon(net, epsg: int) -> list[Segmento]:
    """Tuberías del .inp como segmentos en WGS84 (las que tienen coordenadas
    en ambos nodos)."""
    nodos = {n.id: (n.x, n.y) for n in [*net.junctions.values(), *net.sources.values()]
             if n.x is not None and n.y is not None}
    if not nodos:
        return []
    if epsg == 4326:
        latlon = {k: (y, x) for k, (x, y) in nodos.items()}
    else:
        try:
            from pyproj import Transformer
        except ImportError as e:
            raise geo.GeoError("Para superponer la red instale pyproj.") from e
        tr = Transformer.from_crs(epsg, 4326, always_xy=True)
        latlon = {}
        for k, (x, y) in nodos.items():
            lon, lat = tr.transform(x, y)
            latlon[k] = (lat, lon)
    return [Segmento(p.id, (latlon[p.node1], latlon[p.node2])) for p in net.pipes
            if p.node1 in latlon and p.node2 in latlon]


def fraccion_dentro(mapa: MapaGuardado, segmentos: list[Segmento]) -> float:
    """Fracción de los nodos de la red que caen dentro del mapa (0 si el
    sistema de coordenadas elegido no es el del .inp)."""
    pts = {pt for s in segmentos for pt in s.puntos}
    if not pts:
        return 0.0
    la0, lo0, la1, lo1 = extension(mapa)
    return sum(la0 <= la <= la1 and lo0 <= lo <= lo1 for la, lo in pts) / len(pts)


def escala_redonda(objetivo_m: float) -> float:
    """Mayor longitud 1, 2 o 5 × 10^k que no supera el objetivo."""
    k = math.floor(math.log10(objetivo_m))
    for f in (5, 2, 1):
        if f * 10 ** k <= objetivo_m:
            return f * 10 ** k
    return 10 ** k


def _grados(v: float, pos: str, neg: str, dec: int) -> str:
    return f"{abs(v):.{dec}f}°{pos if v >= 0 else neg}"


def _caja(ax, x, y, txt, **kw):
    return ax.text(x, y, txt, color=_TINTA, bbox=dict(boxstyle="round,pad=0.25", fc="white",
                                                       ec="none", alpha=0.8), **kw)


def fig_localizacion(mapa: MapaGuardado | None, lat: float, lon: float, titulo: str = "",
                     segmentos: list[Segmento] | None = None,
                     recuadro: tuple | None = None):
    """Figura del mapa guardado con el sitio, la red y/o el recuadro de la zona
    de estudio; None si no hay imagen utilizable."""
    if mapa is None or not mapa.img_b64:
        return None
    try:
        img = imagen_de(mapa)
    except (OSError, ValueError):
        return None
    m = _mosaico(mapa)
    W, H = mapa.ancho, mapa.alto
    fig, ax = plt.subplots(figsize=(7.2, 7.2 * H / W))
    ax.imshow(img, extent=(0, W, H, 0), interpolation="lanczos")
    ax.set_xlim(0, W)
    ax.set_ylim(H, 0)

    # coordenadas en el marco
    la0, lo0, la1, lo1 = extension(mapa)
    dec = 3 if lo1 - lo0 < 0.1 else 2 if lo1 - lo0 < 2 else 1
    lons = [v for v in MaxNLocator(4).tick_values(lo0, lo1) if lo0 < v < lo1]
    lats = [v for v in MaxNLocator(4).tick_values(la0, la1) if la0 < v < la1]
    ax.set_xticks([m.a_pixel(lat, v)[0] for v in lons], [_grados(v, "E", "O", dec) for v in lons])
    ax.set_yticks([m.a_pixel(v, lon)[1] for v in lats], [_grados(v, "N", "S", dec) for v in lats])
    ax.tick_params(labelsize=7, colors=_TINTA, length=3)
    for s in ax.spines.values():
        s.set_color(_TINTA)
        s.set_linewidth(0.8)

    if segmentos:
        xs, ys = [], []
        for sg in segmentos:
            for la, lo in sg.puntos:
                x, y = m.a_pixel(la, lo)
                xs.append(x)
                ys.append(y)
            xs.append(None)
            ys.append(None)
        trazo, halo = _RED.get(mapa.fuente, _RED["osm"])
        ax.plot(xs, ys, color=halo, lw=3.2, solid_capstyle="round")
        ax.plot(xs, ys, color=trazo, lw=1.6, solid_capstyle="round", label="Red de distribución")
    if recuadro:
        r_la0, r_lo0, r_la1, r_lo1 = recuadro
        x0, y0 = m.a_pixel(r_la1, r_lo0)
        x1, y1 = m.a_pixel(r_la0, r_lo1)
        if min(x1 - x0, y1 - y0) > 14:        # más pequeño, lo tapa el marcador del sitio
            ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, ec=_SITIO, lw=1.8))
    cx, cy = m.a_pixel(lat, lon)
    ax.plot([cx], [cy], marker="o", ms=9, mfc=_SITIO, mec="white", mew=1.8, ls="none",
            label="Sitio del proyecto")

    # barra de escala (longitud real a la latitud del centro)
    mpp = geo.metros_por_pixel(lat, mapa.z)
    L = escala_redonda(0.22 * W * mpp)
    lpx = L / mpp
    x0, y0, alto_b = 0.04 * W, 0.93 * H, 0.012 * H
    ax.add_patch(Rectangle((x0 - 6, y0 - 0.07 * H), lpx + 12, 0.07 * H + alto_b + 6,
                           fc="white", ec="none", alpha=0.8))
    ax.add_patch(Rectangle((x0, y0), lpx / 2, alto_b, fc=_TINTA, ec=_TINTA, lw=0.8))
    ax.add_patch(Rectangle((x0 + lpx / 2, y0), lpx / 2, alto_b, fc="white", ec=_TINTA, lw=0.8))
    ax.text(x0 + lpx / 2, y0 - 0.012 * H, f"{L / 1000:g} km" if L >= 1000 else f"{L:g} m",
            ha="center", va="bottom", fontsize=8, color=_TINTA)

    # norte (Web Mercator: el norte es hacia arriba)
    xn, yn = 0.94 * W, 0.1 * H
    ax.annotate("", xy=(xn, yn), xytext=(xn, yn + 0.1 * H),
                arrowprops=dict(arrowstyle="-|>", color=_TINTA, lw=1.4, mutation_scale=14))
    _caja(ax, xn, yn - 0.01 * H, "N", ha="center", va="bottom", fontsize=10,
          fontweight="bold")

    _caja(ax, W - 6, H - 6, geo.FUENTES[mapa.fuente].atribucion, ha="right", va="bottom",
          fontsize=5.5)
    if titulo:
        ax.set_title(titulo, fontsize=10, color=_TINTA, loc="left")
    fig.tight_layout()
    return fig

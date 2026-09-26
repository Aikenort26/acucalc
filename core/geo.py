"""Teselas XYZ (Web Mercator, EPSG:3857) y búsqueda de lugares con Nominatim.

La red solo se usa cuando el usuario pulsa un botón: nada se descarga al
importar ni dentro de `report_ctx.build()`. El mosaico compuesto se guarda en
el proyecto y el informe se genera sin conexión. `fetch` y `fetch_json` se
inyectan para las pruebas.

Fuentes: OpenStreetMap (datos ODbL; política de uso de teselas: User-Agent
propio, sin descargas masivas) y Esri World Imagery (atribución obligatoria;
su uso está sujeto a los términos de Esri)."""
import io
import math
import os
import time
from dataclasses import dataclass
from pathlib import Path

import requests
from PIL import Image, UnidentifiedImageError

TESELA = 256
R_TIERRA = 6378137.0                    # radio del elipsoide WGS84 usado por EPSG:3857
LAT_MAX = 85.05112878                   # límite de Web Mercator
USER_AGENT = "ACUCALC/9 (diseño de acueductos; https://github.com/aikenort26/acucalc)"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
_INTERVALO = 1.0                        # política de Nominatim: máximo 1 petición por segundo
_ultima_consulta = 0.0


class GeoError(Exception):
    """Fallo de descarga o de consulta, con mensaje para el usuario."""


@dataclass(frozen=True)
class Fuente:
    nombre: str
    plantilla: str
    atribucion: str
    max_zoom: int
    formato: str                         # formato con que se guarda el mosaico


FUENTES = {
    "osm": Fuente("OpenStreetMap", "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
                  "© colaboradores de OpenStreetMap (ODbL)", 19, "PNG"),
    "esri": Fuente("Esri World Imagery",
                   "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/"
                   "MapServer/tile/{z}/{y}/{x}",
                   "Imagen © Esri — Fuente: Esri, Maxar, Earthstar Geographics y la "
                   "comunidad de usuarios SIG", 19, "JPEG"),
}


@dataclass(frozen=True)
class Lugar:
    nombre: str
    lat: float
    lon: float


def latlon_a_pixel(lat: float, lon: float, z: int) -> tuple[float, float]:
    """Píxel global (Web Mercator) de un punto WGS84 en el zoom z."""
    n = TESELA * 2 ** z
    phi = math.radians(max(-LAT_MAX, min(LAT_MAX, lat)))
    x = (lon + 180.0) / 360.0 * n
    y = (1.0 - math.log(math.tan(phi) + 1.0 / math.cos(phi)) / math.pi) / 2.0 * n
    return x, y


def pixel_a_latlon(px: float, py: float, z: int) -> tuple[float, float]:
    n = TESELA * 2 ** z
    lon = px / n * 360.0 - 180.0
    lat = math.degrees(math.atan(math.sinh(math.pi * (1.0 - 2.0 * py / n))))
    return lat, lon


def metros_por_pixel(lat: float, z: int) -> float:
    """Tamaño real de un píxel sobre el terreno a la latitud dada."""
    return 2 * math.pi * R_TIERRA * math.cos(math.radians(lat)) / (TESELA * 2 ** z)


def url_tesela(fuente: str, z: int, x: int, y: int) -> str:
    return FUENTES[fuente].plantilla.format(z=z, x=x, y=y)


def _motivo(e: Exception) -> str:
    """Causa de un fallo de red en palabras del usuario."""
    if isinstance(e, requests.exceptions.Timeout):
        return "tiempo de espera agotado"
    if isinstance(e, requests.exceptions.ConnectionError):
        return "sin conexión con el servidor"
    if isinstance(e, requests.exceptions.HTTPError) and e.response is not None:
        return f"el servidor respondió HTTP {e.response.status_code}"
    return str(e)[:120] or type(e).__name__


def descargar(url: str, timeout: float = 15.0) -> bytes:
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    r.raise_for_status()
    return r.content


def _cache_por_defecto() -> Path:
    base = os.environ.get("ACUCALC_CACHE") or Path.home() / ".cache" / "acucalc"
    return Path(base) / "teselas"


@dataclass
class Mosaico:
    """Imagen compuesta; (px0, py0) es el píxel global de su esquina superior
    izquierda en el zoom z (entero, para que imagen y coordenadas coincidan)."""
    imagen: Image.Image
    z: int
    px0: int
    py0: int
    fuente: str

    def a_pixel(self, lat: float, lon: float) -> tuple[float, float]:
        px, py = latlon_a_pixel(lat, lon, self.z)
        return px - self.px0, py - self.py0

    def a_latlon(self, x: float, y: float) -> tuple[float, float]:
        return pixel_a_latlon(x + self.px0, y + self.py0, self.z)


def _tesela(fuente: str, z: int, x: int, y: int, fetch, cache_dir: Path) -> Image.Image:
    ruta = cache_dir / fuente / str(z) / str(x) / f"{y}.img"
    if ruta.is_file():
        try:
            return Image.open(io.BytesIO(ruta.read_bytes())).convert("RGB")
        except (UnidentifiedImageError, OSError):
            ruta.unlink(missing_ok=True)
    try:
        datos = fetch(url_tesela(fuente, z, x, y))
    except Exception as e:  # noqa: BLE001 — cualquier fallo de red llega al usuario
        raise GeoError(f"No se pudieron descargar las teselas de {FUENTES[fuente].nombre} "
                       f"({_motivo(e)}). Revise la conexión a internet: los mapas se descargan una "
                       "vez y quedan guardados en el proyecto.") from e
    try:
        img = Image.open(io.BytesIO(datos)).convert("RGB")
    except (UnidentifiedImageError, OSError) as e:
        raise GeoError(f"El servidor de teselas de {FUENTES[fuente].nombre} no devolvió una "
                       "imagen; intente más tarde o cambie de fuente.") from e
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_bytes(datos)
    return img


def componer(lat: float, lon: float, z: int, ancho: int, alto: int, fuente: str = "osm",
             fetch=None, cache_dir: str | Path | None = None) -> Mosaico:
    """Mosaico de ancho×alto píxeles centrado en (lat, lon)."""
    f = FUENTES[fuente]
    if not 0 <= z <= f.max_zoom:
        raise ValueError(f"El zoom debe estar entre 0 y {f.max_zoom}.")
    fetch = fetch or descargar
    cache = Path(cache_dir) if cache_dir else _cache_por_defecto()
    cx, cy = latlon_a_pixel(lat, lon, z)
    px0, py0 = math.floor(cx - ancho / 2), math.floor(cy - alto / 2)
    n = 2 ** z
    img = Image.new("RGB", (ancho, alto), (224, 224, 224))
    for ty in range(px_a_tesela(py0), px_a_tesela(py0 + alto - 1) + 1):
        if not 0 <= ty < n:
            continue
        for tx in range(px_a_tesela(px0), px_a_tesela(px0 + ancho - 1) + 1):
            t = _tesela(fuente, z, tx % n, ty, fetch, cache)
            img.paste(t, (tx * TESELA - px0, ty * TESELA - py0))
    return Mosaico(img, z, px0, py0, fuente)


def px_a_tesela(p: int) -> int:
    return p // TESELA


def _respetar_limite() -> None:
    global _ultima_consulta
    espera = _INTERVALO - (time.monotonic() - _ultima_consulta)
    if espera > 0:
        time.sleep(espera)
    _ultima_consulta = time.monotonic()


def _json_nominatim(url: str, params: dict):
    r = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=15)
    r.raise_for_status()
    return r.json()


def buscar(texto: str, fetch_json=None, limite: int = 5, pais: str = "co") -> list[Lugar]:
    """Lugares que coinciden con el texto (Nominatim; una consulta por segundo)."""
    if not texto.strip():
        return []
    _respetar_limite()
    params = {"q": texto.strip(), "format": "jsonv2", "limit": limite,
              "accept-language": "es"}
    if pais:
        params["countrycodes"] = pais
    try:
        datos = (fetch_json or _json_nominatim)(NOMINATIM, params)
    except Exception as e:  # noqa: BLE001
        raise GeoError(f"No se pudo consultar Nominatim ({_motivo(e)}). Revise la conexión o ingrese "
                       "las coordenadas a mano.") from e
    return [Lugar(d.get("display_name", ""), float(d["lat"]), float(d["lon"])) for d in datos]

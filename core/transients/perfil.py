"""Perfil longitudinal de una conducción: abscisas horizontales, cota de
terreno y cota del eje de la tubería. La longitud de tubería se mide sobre el
eje, L = Σ √(Δs² + Δz²)."""
import math
import re
from dataclasses import dataclass

import numpy as np

_K = re.compile(r"^\s*[Kk]?\s*(\d+)\s*\+\s*(\d+(?:[.,]\d+)?)\s*$")


def abscisa(valor) -> float:
    """Abscisa en metros; acepta "K0+120.50", "0+120" o un número."""
    if isinstance(valor, (int, float, np.integer, np.floating)):
        return float(valor)
    txt = str(valor).strip()
    m = _K.match(txt)
    if m:
        return float(m.group(1)) * 1000 + float(m.group(2).replace(",", "."))
    return float(txt.replace(",", "."))


def formato_abscisa(s: float) -> str:
    """Abscisa en formato K0+120.50 (redondeada al centímetro)."""
    km, cm = divmod(int(round(s * 100)), 100000)
    return f"K{km}+{cm / 100:06.2f}"


@dataclass(frozen=True)
class Perfil:
    abscisa: tuple
    z_terreno: tuple
    z_eje: tuple

    def x_vertices(self) -> np.ndarray:
        s, z = np.asarray(self.abscisa), np.asarray(self.z_eje)
        return np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(s), np.diff(z)))])

    @property
    def longitud(self) -> float:
        return float(self.x_vertices()[-1])

    def z_en_x(self, x) -> np.ndarray:
        return np.interp(x, self.x_vertices(), self.z_eje)

    def terreno_en_x(self, x) -> np.ndarray:
        return np.interp(x, self.x_vertices(), self.z_terreno)

    def x_de_abscisa(self, s: float) -> float:
        return float(np.interp(s, self.abscisa, self.x_vertices()))

    def abscisa_de_x(self, x):
        """Abscisa horizontal del punto a la distancia x medida sobre la tubería."""
        return np.interp(x, self.x_vertices(), self.abscisa)

    def puntos_altos(self) -> list:
        """Abscisas de los máximos locales del eje (candidatos a ventosa)."""
        z = self.z_eje
        return [self.abscisa[i] for i in range(1, len(z) - 1) if z[i] > z[i - 1] and z[i] >= z[i + 1]]


def _columna(df, *claves):
    for c in df.columns:
        nombre = str(c).lower()
        if any(k in nombre for k in claves):
            return c
    return None


def cargar(df, cobertura: float | None = None, D_m: float | None = None) -> Perfil:
    """Perfil desde una tabla con columnas de abscisa, cota de terreno y
    (opcional) cota del eje o de clave. Sin cota del eje se calcula como
    terreno − cobertura − D/2."""
    c_s = _columna(df, "absc")
    c_t = _columna(df, "terreno")
    c_e = _columna(df, "eje", "clave", "tuber", "batea")
    if c_s is None or c_t is None:
        raise ValueError("El perfil debe tener columnas de abscisa y de cota de terreno.")
    datos = df[[c for c in (c_s, c_t, c_e) if c is not None]].dropna(subset=[c_s, c_t])
    s = [abscisa(v) for v in datos[c_s]]
    zt = [float(v) for v in datos[c_t]]
    if len(s) < 2:
        raise ValueError("El perfil necesita al menos dos puntos.")
    if any(b <= a for a, b in zip(s, s[1:])):
        raise ValueError("Las abscisas deben ser estrictamente crecientes.")
    if c_e is not None and datos[c_e].notna().all():
        ze = [float(v) for v in datos[c_e]]
    else:
        if not cobertura or not D_m:
            raise ValueError("Sin cota del eje se necesita la cobertura (profundidad a clave) "
                             "y el diámetro para calcularla.")
        ze = [z - cobertura - D_m / 2 for z in zt]
    return Perfil(tuple(s), tuple(zt), tuple(ze))


def recto(longitud: float, z_inicio: float, z_fin: float) -> Perfil:
    """Perfil de dos puntos con la longitud de tubería dada (sobre el eje)."""
    dz = z_fin - z_inicio
    if abs(dz) >= longitud:
        raise ValueError("El desnivel no puede ser mayor que la longitud de la tubería.")
    ds = math.sqrt(longitud ** 2 - dz ** 2)
    return Perfil((0.0, ds), (z_inicio, z_fin), (z_inicio, z_fin))

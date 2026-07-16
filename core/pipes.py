"""Catálogo normativo de tuberías (data/tuberias.json): dimensiones RDE/clase
por material, DN 50–1200. `base` indica si el DN es exterior (od) o interior
nominal (id). Espesor y k_elast alimentan el golpe de ariete."""
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "tuberias.json"

# material del catálogo → clave de rugosidad en data/ks.json
KS_KEY = {"PEAD PE100": "PEAD", "PVC-U": "PVC", "Hierro dúctil": "HD",
          "Acero comercial": "Acero comercial", "GRP": "GRP",
          "PVC-O": "PVC-O", "PVC biaxial": "PVC biaxial"}


@dataclass(frozen=True)
class PipeSpec:
    material: str
    serie: str
    dn: float
    unidad_dn: str    # "mm" | "in"
    od_mm: float
    e_mm: float
    id_mm: float
    k_elast: float
    nota: str = ""
    ks_mm: float = 0.0      # rugosidad absoluta
    pn_mca: float = 0.0     # presión nominal
    largo_m: float = 0.0    # longitud de presentación

    @property
    def dn_mm(self) -> float:
        return self.dn * 25.4 if self.unidad_dn == "in" else self.dn

    @property
    def dn_in(self) -> float:
        return self.dn if self.unidad_dn == "in" else self.dn / 25.4


@lru_cache
def _cat() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))


def materials() -> list[str]:
    return list(_cat().keys())


def series(material: str) -> list[str]:
    return list(_cat()[material]["series"].keys())


def diameters(material: str, serie: str) -> list[float]:
    return [row["dn"] for row in _cat()[material]["series"][serie]]


def pipe(material: str, serie: str, dn: float) -> PipeSpec:
    m = _cat()[material]
    for row in m["series"][serie]:
        if row["dn"] == dn:
            id_mm = (row["od_mm"] - 2 * row["e_mm"] if m["base"] == "od"
                     else float(row["dn"]))
            return PipeSpec(material, serie, row["dn"], m["unidad_dn"],
                            row["od_mm"], row["e_mm"], round(id_mm, 1),
                            m["k_elast"], m.get("nota", ""),
                            ks_mm=m.get("ks_mm", 0.0),
                            pn_mca=m.get("pn_mca", {}).get(serie, 0.0),
                            largo_m=m.get("largo_m", 0.0))
    raise KeyError(f"DN {dn} no existe en {material} {serie}")


def dn_label(spec_material: str, dn: float) -> str:
    u = _cat()[spec_material]["unidad_dn"]
    return f'{dn}"' if u == "in" else f"{dn:g} mm"


def serie_pn(material: str, serie: str) -> float:
    """Presión nominal [mca] de una serie/clase, 0 si no está catalogada."""
    return _cat()[material].get("pn_mca", {}).get(serie, 0.0)


def serie_label(material: str, serie: str) -> str:
    """Etiqueta de serie con su PN cuando existe: `RDE 11 (PN 163 mca)`.

    Muestra la presión nominal junto a la serie (nomenclatura tipo "PE100
    PN10") sin renombrar la clave del catálogo — así los proyectos guardados
    conservan su `cat_serie`."""
    pn = serie_pn(material, serie)
    return f"{serie} (PN {pn:.0f} mca)" if pn else serie


def suggest_dn(material: str, serie: str, q_m3s: float,
               v_max: float = 6.0, k_bresse: float = 1.2) -> float:
    """DN comercial propuesto: primer diámetro cuyo interno no baja del
    diámetro económico de Bresse (d = k·√Q) y cuya velocidad cumple
    V ≤ v_max (Art. 56 Res. 0330). Si ninguno alcanza el Bresse, devuelve
    el mayor DN que cumpla la velocidad."""
    import math
    d_bresse_mm = k_bresse * math.sqrt(max(q_m3s, 0.0)) * 1000.0
    candidato_v = None
    for dn in diameters(material, serie):
        spec = pipe(material, serie, dn)
        v = 4.0 * q_m3s / (math.pi * (spec.id_mm / 1000.0) ** 2)
        if v <= v_max:
            candidato_v = candidato_v or dn
            if spec.id_mm >= d_bresse_mm:
                return dn
            candidato_v = dn   # el mayor que cumple V, por si Bresse no se alcanza
    if candidato_v is not None:
        return candidato_v
    return diameters(material, serie)[-1]

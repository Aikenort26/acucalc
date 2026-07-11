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
          "Acero comercial": "Acero comercial", "GRP": "GRP"}


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

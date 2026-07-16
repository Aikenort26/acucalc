"""Catálogos de datos físicos y normativos (data/*.json)."""
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@dataclass(frozen=True)
class WaterProps:
    T: float      # °C
    rho: float    # kg/m³
    mu: float     # kg/(m·s)

    @property
    def nu(self) -> float:  # m²/s
        return self.mu / self.rho


@lru_cache
def _load(name: str):
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


def water_props(T: float) -> WaterProps:
    """Propiedades del agua interpoladas linealmente en temperatura."""
    tab = sorted(_load("agua.json"), key=lambda r: r["T"])
    T = min(max(T, tab[0]["T"]), tab[-1]["T"])
    for a, b in zip(tab, tab[1:]):
        if a["T"] <= T <= b["T"]:
            f = 0.0 if b["T"] == a["T"] else (T - a["T"]) / (b["T"] - a["T"])
            return WaterProps(T, a["rho"] + f * (b["rho"] - a["rho"]),
                              a["mu"] + f * (b["mu"] - a["mu"]))
    return WaterProps(T, tab[-1]["rho"], tab[-1]["mu"])


def roughness() -> dict[str, float]:
    """ks por material, en metros."""
    return {k: v / 1000.0 for k, v in _load("ks.json").items()}


def minor_loss_coefficients() -> dict[str, float]:
    return dict(_load("km.json"))


def dotacion_references() -> dict:
    return _load("dotaciones.json")


def riesgo_incendio() -> dict:
    """Catálogo de niveles de riesgo contra incendio (data/riesgo_incendio.json).

    Estructura: {"referencia": str, "niveles": {nivel: {"frac": float|None,
    "nota": str}}}. `frac` es la fracción del volumen de regulación que se
    reserva para incendio; `personalizado` la trae en None (el usuario la fija)."""
    return _load("riesgo_incendio.json")


def frac_riesgo_incendio(nivel: str) -> float | None:
    """Fracción de afectación por incendio del nivel dado, o None si el nivel
    es 'personalizado' o no existe (el llamador conserva su frac_incendio)."""
    niveles = riesgo_incendio()["niveles"]
    return niveles.get(nivel, {}).get("frac")

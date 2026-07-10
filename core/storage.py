"""Volumen de almacenamiento: Art. 81 Res. 0330 + curva integral + NSR-10 J."""
import math
from dataclasses import dataclass


def _round_up_5(v: float) -> int:
    return int(math.ceil(v / 5.0) * 5)


@dataclass(frozen=True)
class StorageResult:
    metodo: str
    v_regulacion: float
    v_incendio: float
    v_total: float
    v_total_redondeado: int
    frac_regulacion: float | None = None


def volume_art81(qmd_m3d: float, frac_regulacion: float = 1/3,
                 frac_incendio: float = 0.15, dias_reserva: float = 1) -> StorageResult:
    vreg = qmd_m3d * frac_regulacion
    vinc = vreg * frac_incendio
    vtot = (vreg + vinc) * dias_reserva
    return StorageResult("Art. 81 Res. 0330", vreg, vinc, vtot, _round_up_5(vtot))


def volume_curva_integral(qmd_m3d: float, factores_hora: list[float],
                          suministro_hora: list[int], frac_incendio: float = 0.15,
                          dias_reserva: float = 1) -> StorageResult:
    if len(factores_hora) != 24 or len(suministro_hora) != 24:
        raise ValueError("Se requieren 24 factores de consumo y 24 flags de suministro")
    total_f = sum(factores_hora)
    total_s = sum(suministro_hora)
    if total_s == 0:
        raise ValueError("La ventana de suministro no puede ser vacía")
    acum_dif, difs = 0.0, []
    for f, s in zip(factores_hora, suministro_hora):
        consumo = f / total_f
        suministro = s / total_s
        acum_dif += suministro - consumo
        difs.append(acum_dif)
    frac_reg = max(difs) - min(difs)
    vreg = frac_reg * qmd_m3d
    vinc = vreg * frac_incendio
    vtot = (vreg + vinc) * dias_reserva
    return StorageResult("Curva integral", vreg, vinc, vtot, _round_up_5(vtot), frac_reg)


def final_volume(a: StorageResult, b: StorageResult) -> int:
    return max(a.v_total_redondeado, b.v_total_redondeado)


@dataclass(frozen=True)
class TankDims:
    volumen: float
    altura: float
    diametro: float   # opción cilíndrica
    lado: float       # opción planta cuadrada


def tank_dimensions(volumen: float, altura: float) -> TankDims:
    d = math.sqrt(4.0 * volumen / (math.pi * altura))
    lado = math.sqrt(volumen / altura)
    return TankDims(volumen, altura, d, lado)

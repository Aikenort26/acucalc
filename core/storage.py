"""Volumen de almacenamiento: Art. 81 Res. 0330 + curva integral + NSR-10 J.

Incluye la cadena real de tanques: captación → PTAP (sin almacenamiento) →
tanque bajo → bombeo a caudal constante → tanque elevado → red. Cada tanque
regula con su propia curva de suministro/consumo (balance_curve).
"""
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


def balance_curve(supply_frac: list[float],
                  demand_frac: list[float]) -> tuple[float, list[float]]:
    """Fracción de regulación por curva integral: maxΔ−minΔ del acumulado
    (suministro − consumo). Ambas listas: 24 fracciones horarias que suman 1."""
    if len(supply_frac) != 24 or len(demand_frac) != 24:
        raise ValueError("Se requieren 24 fracciones horarias de suministro y consumo")
    acum, difs = 0.0, []
    for s, d in zip(supply_frac, demand_frac):
        acum += s - d
        difs.append(acum)
    return max(difs) - min(difs), difs


def _normalize(window: list[float], nombre: str) -> list[float]:
    total = sum(window)
    if total <= 0:
        raise ValueError(f"La ventana de {nombre} no puede ser vacía")
    return [w / total for w in window]


def volume_curva_integral(qmd_m3d: float, factores_hora: list[float],
                          suministro_hora: list[int], frac_incendio: float = 0.15,
                          dias_reserva: float = 1) -> StorageResult:
    if len(factores_hora) != 24 or len(suministro_hora) != 24:
        raise ValueError("Se requieren 24 factores de consumo y 24 flags de suministro")
    frac_reg, _ = balance_curve(_normalize(suministro_hora, "suministro"),
                                _normalize(factores_hora, "consumo"))
    vreg = frac_reg * qmd_m3d
    vinc = vreg * frac_incendio
    vtot = (vreg + vinc) * dias_reserva
    return StorageResult("Curva integral", vreg, vinc, vtot, _round_up_5(vtot), frac_reg)


@dataclass(frozen=True)
class TankBalance:
    nombre: str
    frac_regulacion: float
    q_entrada_lps: float     # caudal constante del bombeo/gravedad que lo alimenta
    horas_entrada: float
    v_regulacion: float
    v_incendio: float
    v_total: float
    v_total_redondeado: int


def tank_train(qmd_m3d: float, entradas: list[tuple[str, list[float]]],
               factores_consumo: list[float], frac_incendio: float = 0.15,
               dias_reserva: float = 1) -> list[TankBalance]:
    """Cadena de N tanques en serie. `entradas` = [(nombre, ventana_entrada[24])]
    en orden hidráulico. La salida de cada tanque es la ventana de entrada del
    siguiente (bombeo intermedio a caudal constante = QMD·24/h de esa ventana);
    la salida del último es el patrón horario de consumo de la población.
    Balance de regulación por tanque con `balance_curve`."""
    if not entradas:
        raise ValueError("Se requiere al menos un tanque")
    if len(factores_consumo) != 24:
        raise ValueError("Se requieren 24 factores de consumo")
    consumo = _normalize(factores_consumo, "consumo")
    qmd_lps = qmd_m3d / 86.4
    out = []
    for i, (nombre, ventana) in enumerate(entradas):
        supply = _normalize(ventana, f"entrada de '{nombre}'")
        if i + 1 < len(entradas):
            demand = _normalize(entradas[i + 1][1], f"entrada de '{entradas[i+1][0]}'")
        else:
            demand = consumo
        frac, _ = balance_curve(supply, demand)
        horas = sum(1 for w in ventana if w)
        vreg = frac * qmd_m3d
        vinc = vreg * frac_incendio
        vtot = (vreg + vinc) * dias_reserva
        out.append(TankBalance(nombre, frac, qmd_lps * 24.0 / horas if horas else 0.0,
                               float(horas), vreg, vinc, vtot, _round_up_5(vtot)))
    return out


@dataclass(frozen=True)
class ChainResult:
    bajo: StorageResult
    elevado: StorageResult
    total_redondeado: int


def tank_chain(qmd_m3d: float, factores_consumo: list[float],
               ventana_captacion: list[float], ventana_bombeo: list[float],
               frac_incendio: float = 0.15, dias_reserva: float = 1) -> ChainResult:
    """Cadena captación→tanque bajo→bombeo constante→tanque elevado→red.

    - Tanque bajo: suministro = captación constante en su ventana;
      consumo = bombeo constante en su ventana (Qb = QMD·24/h de bombeo).
    - Tanque elevado: suministro = bombeo constante; consumo = patrón horario
      de la población (factores).
    """
    if len(factores_consumo) != 24:
        raise ValueError("Se requieren 24 factores de consumo")
    capta = _normalize(ventana_captacion, "captación")
    bombeo = _normalize(ventana_bombeo, "bombeo")
    consumo = _normalize(factores_consumo, "consumo")

    def _tank(nombre: str, supply, demand) -> StorageResult:
        frac, _ = balance_curve(supply, demand)
        vreg = frac * qmd_m3d
        vinc = vreg * frac_incendio
        vtot = (vreg + vinc) * dias_reserva
        return StorageResult(nombre, vreg, vinc, vtot, _round_up_5(vtot), frac)

    bajo = _tank("Tanque bajo (captación vs bombeo)", capta, bombeo)
    elevado = _tank("Tanque elevado (bombeo vs consumo)", bombeo, consumo)
    return ChainResult(bajo, elevado,
                       bajo.v_total_redondeado + elevado.v_total_redondeado)


def final_volume(a: StorageResult, b: StorageResult) -> int:
    return max(a.v_total_redondeado, b.v_total_redondeado)


@dataclass(frozen=True)
class TankDims:
    volumen: float
    altura: float
    diametro: float   # opción cilíndrica
    lado: float       # opción planta cuadrada
    ancho: float      # opción rectangular (largo = ratio·ancho)
    largo: float


def tank_dimensions(volumen: float, altura: float, ratio: float = 1.0) -> TankDims:
    d = math.sqrt(4.0 * volumen / (math.pi * altura))
    lado = math.sqrt(volumen / altura)
    ancho = math.sqrt(volumen / (altura * ratio))
    return TankDims(volumen, altura, d, lado, ancho, ratio * ancho)

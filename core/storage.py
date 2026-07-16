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
class TankBalanceCheck:
    nombre: str
    v_asignado: float
    v_balance_req: float       # volumen de regulación requerido por el balance interno
    frac_balance: float
    horas_suministro: float
    horas_salida: float
    cumple: bool               # v_asignado >= v_balance_req


def tank_balance_check(nombre: str, qmd_m3d: float, ventana_suministro: list[float],
                       ventana_salida: list[float], v_asignado: float,
                       frac_incendio: float = 0.15, dias_reserva: float = 1) -> TankBalanceCheck:
    """Verifica el balance interno de UN tanque: dado su patrón horario de
    suministro (entrada) y de salida (consumo/bombeo hacia adelante), el volumen
    de regulación que exige (curva integral) vs el volumen que el usuario le
    asignó. No dimensiona ni reparte — solo verifica."""
    frac, _ = balance_curve(_normalize(ventana_suministro, f"suministro de '{nombre}'"),
                            _normalize(ventana_salida, f"salida de '{nombre}'"))
    vreg = frac * qmd_m3d
    vinc = vreg * frac_incendio
    v_req = (vreg + vinc) * dias_reserva
    horas_s = float(sum(1 for w in ventana_suministro if w))
    horas_o = float(sum(1 for w in ventana_salida if w))
    return TankBalanceCheck(nombre, v_asignado, v_req, frac, horas_s, horas_o,
                            v_asignado + 1e-9 >= v_req)


@dataclass(frozen=True)
class TankBalance:
    nombre: str
    frac_regulacion: float
    q_entrada_lps: float          # caudal constante del bombeo/gravedad que lo alimenta
    horas_entrada: float
    q_salida_lps: float | None    # caudal constante de salida; en el último tanque,
                                   # si se pasa qmh_lps, es el QMH de referencia (no constante)
    horas_salida: float | None    # None = último tanque (consumo variable de la red)
    v_regulacion: float
    v_incendio: float
    v_total: float
    v_total_redondeado: int


def tank_train(qmd_m3d: float, entradas: list[tuple[str, list[float]]],
               factores_consumo: list[float], frac_incendio: float = 0.15,
               dias_reserva: float = 1, qmh_lps: float | None = None) -> list[TankBalance]:
    """Cadena de N tanques en serie. `entradas` = [(nombre, ventana_entrada[24])]
    en orden hidráulico. La salida de cada tanque es la ventana de entrada del
    siguiente (bombeo intermedio a caudal constante = QMD·24/h de esa ventana);
    la salida del último es el patrón horario de consumo de la población (Q
    variable) — si se pasa `qmh_lps`, se reporta como referencia de pico
    horario (QMH), aunque el consumo real siga siendo variable hora a hora.
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
        es_ultimo = i + 1 >= len(entradas)
        if es_ultimo:
            demand = consumo
            horas_salida, q_salida = None, qmh_lps
        else:
            ventana_sig = entradas[i + 1][1]
            demand = _normalize(ventana_sig, f"entrada de '{entradas[i+1][0]}'")
            horas_salida = float(sum(1 for w in ventana_sig if w))
            q_salida = qmd_lps * 24.0 / horas_salida if horas_salida else 0.0
        frac, _ = balance_curve(supply, demand)
        horas = sum(1 for w in ventana if w)
        vreg = frac * qmd_m3d
        vinc = vreg * frac_incendio
        vtot = (vreg + vinc) * dias_reserva
        out.append(TankBalance(nombre, frac, qmd_lps * 24.0 / horas if horas else 0.0,
                               float(horas), q_salida, horas_salida,
                               vreg, vinc, vtot, _round_up_5(vtot)))
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


def round_up_step(value: float, step: float = 0.1) -> float:
    """Redondea hacia arriba al múltiplo de `step` (10 cm por defecto) — nunca
    subdimensiona: una dimensión constructiva real no puede ser menor a la
    calculada, solo igual o mayor."""
    return round(math.ceil(value / step - 1e-9) * step, 10)


@dataclass(frozen=True)
class ConstructiveTank:
    forma: str
    altura: float
    diametro: float | None = None    # circular
    lado: float | None = None        # cuadrado
    ancho: float | None = None       # rectangular
    largo: float | None = None       # rectangular
    volumen_real: float = 0.0        # con dimensiones redondeadas (≥ objetivo)


def dimensioned_tank(volumen_objetivo: float, altura: float, forma: str,
                     ratio: float = 1.0, step: float = 0.1) -> ConstructiveTank:
    """Dimensiones constructivas redondeadas a `step` m (10 cm por defecto,
    siempre hacia arriba) y el volumen real resultante para esa forma."""
    raw = tank_dimensions(volumen_objetivo, altura, ratio)
    h = round_up_step(altura, step)
    if forma == "circular":
        d = round_up_step(raw.diametro, step)
        return ConstructiveTank("circular", h, diametro=d,
                                volumen_real=math.pi / 4.0 * d**2 * h)
    if forma == "cuadrado":
        lado = round_up_step(raw.lado, step)
        return ConstructiveTank("cuadrado", h, lado=lado, volumen_real=lado**2 * h)
    ancho = round_up_step(raw.ancho, step)
    largo = round_up_step(raw.largo, step)
    return ConstructiveTank("rectangular", h, ancho=ancho, largo=largo,
                            volumen_real=ancho * largo * h)

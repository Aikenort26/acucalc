"""Transitorios hidráulicos por el método de las características (MOC).

Esquema de Wylie y Streeter con fricción de Darcy cuasi-estacionaria
semi-implícita. En cada sección, con B = a/(gA) y R = f·Δx/(2gDA²):

    C+ :  H_P = C_P − B_P·Q_P,   C_P = H_A + B·Q_A,   B_P = B + R·|Q_A|
    C− :  H_P = C_M + B_M·Q_P,   C_M = H_B − B·Q_B,   B_M = B + R·|Q_B|

Tuberías en serie con un paso de tiempo común (Courant = 1): la celeridad de
cada tramo se ajusta a L_i/(N_i·Δt) y se reporta el ajuste máximo. El estado
inicial es el permanente discreto del propio esquema (sin perturbación la
solución no se mueve). La cota del eje solo entra en la presión, p = H − z,
y en la verificación de vapor; no altera la ecuación de cantidad de
movimiento en forma H–Q.

No se modela la separación de columna (DVCM): si la presión baja de la de
vapor se reporta el instante y la abscisa, y lo que sigue deja de ser válido.
La bomba se representa con su curva homóloga en zona normal y válvula de
retención ideal; no se usan curvas de Suter (cuatro cuadrantes)."""
import math
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

G = 9.81
RHO = 998.2
MAX_PASOS = 200_000               # tope de pasos: evita que un dato extremo cuelgue la app


@dataclass(frozen=True)
class Tuberia:
    L: float        # longitud a lo largo del eje [m]
    D: float        # diámetro interno [m]
    a: float        # celeridad [m/s]
    f: float = 0.0  # factor de fricción de Darcy (cuasi-estacionario)

    @property
    def area(self) -> float:
        return math.pi * self.D ** 2 / 4


# ------------------------------------------------------------ fronteras

@dataclass(frozen=True)
class Embalse:
    H: float


@dataclass(frozen=True)
class Valvula:
    """Válvula en el extremo aguas abajo que descarga a un nivel H_d. τ(t) es
    la apertura relativa (1 = la del régimen de diseño)."""
    tau: Callable[[float], float]
    H_d: float


@dataclass(frozen=True)
class CaudalPrescrito:
    Q: Callable[[float], float]


@dataclass(frozen=True)
class ExtremoCerrado:
    pass


@dataclass(frozen=True)
class CurvaBomba:
    """H = A0 + A1·Q + A2·Q² a velocidad nominal (Q en m³/s, H en m)."""
    A0: float
    A1: float
    A2: float

    @classmethod
    def por_puntos(cls, puntos) -> "CurvaBomba":
        q, h = zip(*puntos)
        a2, a1, a0 = np.polyfit(q, h, 2)
        return cls(float(a0), float(a1), float(a2))

    def H(self, Q: float, alfa: float = 1.0) -> float:
        return alfa ** 2 * self.A0 + alfa * self.A1 * Q + self.A2 * Q ** 2


@dataclass(frozen=True)
class Hidroneumatico:
    """Cámara de aire a la salida de la bomba. Gas politrópico
    (H + H_bar − z)·V^n = cte; orificio con pérdida C_orificio·Q|Q|."""
    V_aire0: float                 # volumen de aire en régimen permanente [m³]
    n: float = 1.2                 # 1.0 isotérmico ... 1.4 adiabático
    C_orificio: float = 0.0        # [s²/m⁵]
    z: float = 0.0                 # cota de la conexión [m]
    H_bar: float = 10.33           # carga barométrica [m]


@dataclass(frozen=True)
class Bomba:
    """Bomba en el extremo aguas arriba, succionando de un nivel H_succion,
    con válvula de retención ideal (cierra en la primera inversión y no
    reabre en una parada). modo: parada_instantanea | parada_inercia | arranque."""
    H_succion: float
    modo: str = "parada_instantanea"
    curva: CurvaBomba | None = None
    n_rpm: float = 0.0
    inercia: float = 0.0           # momento de inercia bomba + motor [kg·m²]
    eta: float = 0.75              # eficiencia (constante) para el par
    t_arranque: float = 0.0        # tiempo hasta velocidad nominal [s]
    hidroneumatico: Hidroneumatico | None = None


@dataclass(frozen=True)
class Config:
    tuberias: list
    aguas_arriba: object           # Embalse | Bomba
    aguas_abajo: object            # Valvula | Embalse | CaudalPrescrito | ExtremoCerrado
    Q0: float | None               # caudal de régimen [m³/s]; None = punto de operación de la bomba
    t_fin: float
    N_min: int = 20                # tramos de malla en la tubería de menor L/a
    reposo: bool = False           # arranque/apertura: la línea parte en reposo
    z_de_x: Callable | None = None # cota del eje a lo largo de la tubería
    h_vapor_rel: float | None = None  # umbral de vapor como presión manométrica [m]
    monitor: list = field(default_factory=list)   # abscisas (a lo largo) a registrar


@dataclass(frozen=True)
class MocResult:
    t: np.ndarray
    x: np.ndarray
    z: np.ndarray
    H_inicial: np.ndarray
    Hmax: np.ndarray
    Hmin: np.ndarray
    H_arriba: np.ndarray
    Q_arriba: np.ndarray
    H_abajo: np.ndarray
    Q_abajo: np.ndarray
    dt: float
    N: list
    ajuste_a_pct: float
    Q0: float
    cavitacion: tuple | None
    monitor: dict
    alpha: np.ndarray | None = None
    V_aire: np.ndarray | None = None

    @property
    def pmax(self) -> np.ndarray:
        return self.Hmax - self.z

    @property
    def pmin(self) -> np.ndarray:
        return self.Hmin - self.z


# ------------------------------------------------------------ utilidades

def _raiz_positiva(a2: float, a1: float, a0: float) -> float | None:
    """Mayor raíz real ≥ 0 de a2·Q² + a1·Q + a0 = 0 (None si no hay)."""
    if abs(a2) < 1e-14:
        if abs(a1) < 1e-14:
            return None
        q = -a0 / a1
        return q if q >= 0 else None
    disc = a1 * a1 - 4 * a2 * a0
    if disc < 0:
        return None
    r = sorted(((-a1 - math.sqrt(disc)) / (2 * a2), (-a1 + math.sqrt(disc)) / (2 * a2)))
    pos = [q for q in r if q >= 0]
    return pos[-1] if pos else None


def punto_operacion(curva: CurvaBomba, H_estatica: float, R_total: float) -> float:
    """Q ≥ 0 con curva(Q) = H_estatica + R_total·Q²."""
    q = _raiz_positiva(curva.A2 - R_total, curva.A1, curva.A0 - H_estatica)
    if q is None or q <= 0:
        raise ValueError("La curva de la bomba no alcanza la altura estática: no hay punto "
                         "de operación.")
    return q


# ------------------------------------------------------------ simulación

def run(cfg: Config) -> MocResult:
    tubos = cfg.tuberias
    dt = min(t.L / t.a for t in tubos) / cfg.N_min
    N = [max(1, round(t.L / (t.a * dt))) for t in tubos]
    a_aj = [t.L / (n * dt) for t, n in zip(tubos, N)]
    ajuste = max(abs(aa - t.a) / t.a for aa, t in zip(a_aj, tubos)) * 100
    B = [aa / (G * t.area) for aa, t in zip(a_aj, tubos)]
    R = [t.f * (t.L / n) / (2 * G * t.D * t.area ** 2) for t, n in zip(tubos, N)]
    R_total = sum(r * n for r, n in zip(R, N))
    up, down = cfg.aguas_arriba, cfg.aguas_abajo
    bomba = up if isinstance(up, Bomba) else None

    # ---- caudal y cabezas de régimen
    Q0 = cfg.Q0
    if bomba and bomba.curva and isinstance(down, Embalse) and not cfg.reposo:
        Q0 = punto_operacion(bomba.curva, down.H - bomba.H_succion, R_total)
    if Q0 is None:
        raise ValueError("Falta el caudal de régimen.")
    q_ini = 0.0 if cfg.reposo else Q0
    perdidas = [r * q_ini * abs(q_ini) for r in R]
    H, Q = [], []
    if isinstance(up, Embalse):
        h = up.H
        for n, dh in zip(N, perdidas):
            H.append(h - dh * np.arange(n + 1))
            h = H[-1][-1]
    else:
        h_fin = down.H if isinstance(down, Embalse) else getattr(down, "H_d", 0.0)
        h = h_fin + sum(dh * n for dh, n in zip(perdidas, N))
        for n, dh in zip(N, perdidas):
            H.append(h - dh * np.arange(n + 1))
            h = H[-1][-1]
    Q = [np.full(n + 1, q_ini) for n in N]

    cv = 0.0
    if isinstance(down, Valvula):
        dh_val = (H[-1][-1] if not cfg.reposo else up.H - R_total * Q0 * Q0) - down.H_d
        if dh_val <= 0:
            raise ValueError("La carga disponible no alcanza para el caudal de diseño en la "
                             "válvula (pérdida en la válvula ≤ 0).")
        cv = Q0 * Q0 / (2 * dh_val)

    # ---- malla y cotas
    x = np.concatenate([np.linspace(sum(t.L for t in tubos[:i]), sum(t.L for t in tubos[:i + 1]),
                                    n + 1)[(1 if i else 0):] for i, (t, n) in enumerate(zip(tubos, N))])
    z = cfg.z_de_x(x) if cfg.z_de_x else np.zeros_like(x)

    def plano(Hs):
        return np.concatenate([h[(1 if i else 0):] for i, h in enumerate(Hs)])

    H_ini = plano(H)
    Hmax, Hmin = H_ini.copy(), H_ini.copy()
    idx_mon = {xm: int(np.argmin(np.abs(x - xm))) for xm in cfg.monitor}
    monitor = {xm: [H_ini[i]] for xm, i in idx_mon.items()}
    pasos = int(math.ceil(cfg.t_fin / dt - 1e-9))
    if pasos > MAX_PASOS:
        raise ValueError(f"La simulación requiere {pasos:,} pasos de tiempo (máximo "
                         f"{MAX_PASOS:,}, Δt = {dt:.4g} s): reduzca el tiempo a simular, los "
                         "tramos de malla o una los tramos muy cortos.")
    t_serie = [0.0]
    Hu, Qu, Hd_, Qd_ = [H[0][0]], [Q[0][0]], [H[-1][-1]], [Q[-1][-1]]
    alfa = 0.0 if (bomba and bomba.modo == "arranque") else 1.0
    alfas = [alfa] if bomba and bomba.modo in ("parada_inercia", "arranque") else None
    retencion_cerrada = bool(cfg.reposo and bomba)
    vaso = bomba.hidroneumatico if bomba else None
    if vaso:
        V_aire, Qs = vaso.V_aire0, 0.0
        C_gas = (H[0][0] + vaso.H_bar - vaso.z) * V_aire ** vaso.n
        V_serie = [V_aire]
    cav = None
    omega_r = 2 * math.pi * bomba.n_rpm / 60 if bomba else 0.0

    for paso in range(1, pasos + 1):
        t = paso * dt
        Hn = [h.copy() for h in H]
        Qn = [q.copy() for q in Q]
        # interiores
        for i in range(len(tubos)):
            if N[i] < 2:
                continue
            HA, QA = H[i][:-2], Q[i][:-2]
            HB, QB = H[i][2:], Q[i][2:]
            CP, BP = HA + B[i] * QA, B[i] + R[i] * np.abs(QA)
            CM, BM = HB - B[i] * QB, B[i] + R[i] * np.abs(QB)
            Qn[i][1:-1] = (CP - CM) / (BP + BM)
            Hn[i][1:-1] = (CP * BM + CM * BP) / (BP + BM)
        # uniones en serie
        for i in range(len(tubos) - 1):
            CP = H[i][-2] + B[i] * Q[i][-2]
            BP = B[i] + R[i] * abs(Q[i][-2])
            CM = H[i + 1][1] - B[i + 1] * Q[i + 1][1]
            BM = B[i + 1] + R[i + 1] * abs(Q[i + 1][1])
            qp = (CP - CM) / (BP + BM)
            hp = (CP * BM + CM * BP) / (BP + BM)
            Qn[i][-1] = Qn[i + 1][0] = qp
            Hn[i][-1] = Hn[i + 1][0] = hp
        # aguas arriba
        CM = H[0][1] - B[0] * Q[0][1]
        BM = B[0] + R[0] * abs(Q[0][1])
        if isinstance(up, Embalse):
            Hn[0][0] = up.H
            Qn[0][0] = (up.H - CM) / BM
        else:
            if bomba.modo == "arranque":
                alfa = min(1.0, t / bomba.t_arranque) if bomba.t_arranque > 0 else 1.0

            def q_bomba(CM_ef):
                """Caudal de la bomba contra C− (con la retención)."""
                if bomba.modo == "parada_instantanea" or (retencion_cerrada and bomba.modo != "arranque"):
                    return 0.0
                c = bomba.curva
                q = _raiz_positiva(c.A2, alfa * c.A1 - BM,
                                   bomba.H_succion + alfa ** 2 * c.A0 - CM_ef)
                return 0.0 if q is None else q

            if vaso:
                def residuo(qs):
                    qb = q_bomba(CM + BM * qs)
                    hp = CM + BM * (qb + qs)
                    v = V_aire + 0.5 * (Qs + qs) * dt
                    if v <= 0:
                        return -C_gas
                    return (hp + vaso.C_orificio * qs * abs(qs) + vaso.H_bar - vaso.z) * v ** vaso.n - C_gas
                lo = -(2 * V_aire / dt + Qs) * 0.999999
                hi = max(1e-6, abs(Qs) * 2 + Q0)
                while residuo(hi) < 0:
                    hi *= 2
                from scipy.optimize import brentq
                qs = brentq(residuo, lo, hi, xtol=1e-14, rtol=1e-14, maxiter=200)
                qb = q_bomba(CM + BM * qs)
                V_aire += 0.5 * (Qs + qs) * dt
                Qs = qs
                V_serie.append(V_aire)
                qp = qb + qs
            else:
                qb = q_bomba(CM)
                qp = qb
            if bomba.modo in ("parada_inercia",) and qb <= 0:
                retencion_cerrada = True
            Qn[0][0] = qp
            Hn[0][0] = CM + BM * qp
            if bomba.modo == "parada_inercia":
                if alfa > 0 and qb > 0:
                    h_b = Hn[0][0] - bomba.H_succion
                    par = RHO * G * qb * h_b / (bomba.eta * alfa * omega_r)
                    alfa = max(0.0, alfa - par / (bomba.inercia * omega_r) * dt)
                alfas.append(alfa)
            elif bomba.modo == "arranque":
                alfas.append(alfa)
        # aguas abajo
        CP = H[-1][-2] + B[-1] * Q[-1][-2]
        BP = B[-1] + R[-1] * abs(Q[-1][-2])
        if isinstance(down, Valvula):
            tau = max(0.0, down.tau(t))
            c = cv * tau * tau
            dh = CP - down.H_d
            if c == 0:
                qp = 0.0
            elif dh >= 0:
                qp = -c * BP + math.sqrt((c * BP) ** 2 + 2 * c * dh)
            else:
                qp = c * BP - math.sqrt((c * BP) ** 2 - 2 * c * dh)
            Qn[-1][-1], Hn[-1][-1] = qp, CP - BP * qp
        elif isinstance(down, Embalse):
            Hn[-1][-1] = down.H
            Qn[-1][-1] = (CP - down.H) / BP
        elif isinstance(down, CaudalPrescrito):
            qp = down.Q(t)
            Qn[-1][-1], Hn[-1][-1] = qp, CP - BP * qp
        else:
            Qn[-1][-1], Hn[-1][-1] = 0.0, CP
        H, Q = Hn, Qn
        hp = plano(H)
        np.maximum(Hmax, hp, out=Hmax)
        np.minimum(Hmin, hp, out=Hmin)
        if cav is None and cfg.h_vapor_rel is not None:
            bajo = np.nonzero(hp - z < cfg.h_vapor_rel)[0]
            if bajo.size:
                cav = (t, float(x[bajo[0]]))
        for xm, i in idx_mon.items():
            monitor[xm].append(hp[i])
        t_serie.append(t)
        Hu.append(H[0][0]); Qu.append(Q[0][0]); Hd_.append(H[-1][-1]); Qd_.append(Q[-1][-1])

    return MocResult(np.array(t_serie), x, z, H_ini, Hmax, Hmin, np.array(Hu), np.array(Qu),
                     np.array(Hd_), np.array(Qd_), dt, N, ajuste, Q0, cav,
                     {k: np.array(v) for k, v in monitor.items()},
                     np.array(alfas) if alfas is not None else None,
                     np.array(V_serie) if vaso else None)

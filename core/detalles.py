"""Detalles típicos para el informe: zanja, estación de bombeo y tanque.

Son esquemas constructivos, no planos: la zanja se dibuja a escala con las
dimensiones que da el proyectista (la app no asume valores de norma y, si
falta un dato, no hay figura); la estación de bombeo es un esquema sin escala
armado con los tramos y accesorios del sistema; el tanque es un corte con sus
niveles calculados como volumen / área en planta."""
import math
import textwrap
from dataclasses import dataclass

import matplotlib.pyplot as plt
from matplotlib.patches import Arc, Circle, Polygon, Rectangle

from core import storage

TINTA = "#1f1f1f"
TINTA_2 = "#5b5b5b"
TUBO = "#0e7490"
AGUA = "#cfe4ee"
AGUA_RESERVA = "#8fbcd4"
SUELO = "#b08a5a"
CAPAS = {"cama": "#efe3c4", "atraque": "#e2dccb", "relleno": "#ece6d8", "pavimento": "#a7a7a7"}
HATCH = {"cama": "....", "atraque": "xx", "relleno": "//", "pavimento": ""}


def _cota(ax, p1, p2, texto, lado="centro", fontsize=7.5):
    """Línea de cota con flechas en los extremos y el texto al centro."""
    ax.annotate("", xy=p1, xytext=p2,
                arrowprops=dict(arrowstyle="<|-|>", color=TINTA_2, lw=0.8, mutation_scale=7,
                                shrinkA=0, shrinkB=0))
    xm, ym = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
    vertical = abs(p1[0] - p2[0]) < 1e-9
    ha = {"izq": "right", "der": "left"}.get(lado, "center")
    ax.text(xm, ym, texto, ha=ha if vertical else "center", va="center" if vertical else "bottom",
            fontsize=fontsize, color=TINTA, rotation=0,
            bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.85))


# ---------------------------------------------------------------- zanja
def validar_zanja(z) -> list[str]:
    """Datos faltantes o incoherentes (lista vacía = se puede dibujar)."""
    err = []
    if z.ancho_fondo <= 0:
        err.append("Falta el ancho de fondo de la zanja.")
    if z.profundidad <= 0:
        err.append("Falta la profundidad de la zanja (de la rasante al fondo).")
    if z.d_ext_mm <= 0:
        err.append("Falta el diámetro exterior de la tubería.")
    if min(z.cama, z.atraque, z.pavimento, z.talud) < 0:
        err.append("Las dimensiones no pueden ser negativas.")
    if err:
        return err
    D = z.d_ext_mm / 1000
    if D >= z.ancho_fondo:
        err.append(f"La tubería (Ø ext. {D:.2f} m) no cabe en el ancho de fondo "
                   f"({z.ancho_fondo:.2f} m).")
    ocupado = z.cama + D + z.atraque
    disponible = z.profundidad - z.pavimento
    if ocupado > disponible + 1e-9:
        err.append(f"La cama, la tubería y el relleno seleccionado ({ocupado:.2f} m) superan la "
                   f"profundidad disponible bajo el pavimento ({disponible:.2f} m).")
    return err


def cobertura(z) -> float:
    """Distancia de la clave de la tubería a la rasante [m]."""
    return z.profundidad - z.cama - z.d_ext_mm / 1000


def ancho_superior(z) -> float:
    return z.ancho_fondo + 2 * z.talud * z.profundidad


def fig_zanja(z):
    """Corte transversal de la zanja típica, a escala; None si faltan datos."""
    if validar_zanja(z):
        return None
    B, H, t, D = z.ancho_fondo, z.profundidad, z.talud, z.d_ext_mm / 1000
    xl = lambda y: -B / 2 - t * y       # noqa: E731 — pared izquierda a la altura y
    xr = lambda y: B / 2 + t * y        # noqa: E731
    W = ancho_superior(z) / 2 + 0.35 * max(B, H)
    fig, ax = plt.subplots(figsize=(7.6, 4.8))

    # terreno natural a ambos lados
    for lado in (-1, 1):
        borde = [(xl(0), 0), (xl(H), H)] if lado < 0 else [(xr(0), 0), (xr(H), H)]
        ax.add_patch(Polygon([(lado * W, -0.12 * H), (lado * W, H), borde[1], borde[0],
                              (borde[0][0], -0.12 * H)], closed=True, fc="#f6f0e4",
                             ec="#d8c9ad", hatch="\\\\", lw=0, zorder=0))
    ax.add_patch(Rectangle((xl(0), -0.12 * H), B, 0.12 * H, fc="#f6f0e4", ec="#d8c9ad",
                           hatch="\\\\", lw=0, zorder=0))

    def franja(y0, y1, capa, nombre, material):
        if y1 - y0 <= 1e-9:
            return
        ax.add_patch(Polygon([(xl(y0), y0), (xr(y0), y0), (xr(y1), y1), (xl(y1), y1)],
                             closed=True, fc=CAPAS[capa], ec="#8f8f8f", lw=0.6,
                             hatch=HATCH[capa], zorder=1))
        texto = f"{nombre}: {material}" if material else nombre
        ym = (y0 + y1) / 2
        ax.annotate("\n".join(textwrap.wrap(texto, 34)), xy=(xr(ym) - 0.05 * B, ym),
                    xytext=(W * 1.05, ym), va="center", ha="left", fontsize=7.5, color=TINTA,
                    arrowprops=dict(arrowstyle="-", color=TINTA_2, lw=0.6))

    y_cama, y_atr = z.cama, z.cama + D + z.atraque
    franja(0, y_cama, "cama", "Cama", z.mat_cama)
    franja(y_cama, y_atr, "atraque", "Relleno seleccionado", z.mat_atraque)
    franja(y_atr, H - z.pavimento, "relleno", "Relleno", z.mat_relleno)
    franja(H - z.pavimento, H, "pavimento", "Pavimento", "")

    # tubería
    ax.add_patch(Circle((0, z.cama + D / 2), D / 2, fc="white", ec=TUBO, lw=1.8, zorder=3))
    ax.text(0, z.cama + D / 2, f"Ø ext.\n{z.d_ext_mm:.0f} mm", ha="center", va="center",
            fontsize=6.5, color=TINTA, zorder=4)

    # rasante
    ax.plot([-W, W], [H, H], color=SUELO, lw=1.6, zorder=2)
    ax.plot([xl(0), xl(H)], [0, H], color=TINTA, lw=1.1, zorder=2)
    ax.plot([xr(0), xr(H)], [0, H], color=TINTA, lw=1.1, zorder=2)
    ax.plot([xl(0), xr(0)], [0, 0], color=TINTA, lw=1.1, zorder=2)

    # cotas
    _cota(ax, (xl(0), -0.07 * H), (xr(0), -0.07 * H), f"{B:.2f} m")
    if t > 0:
        _cota(ax, (xl(H), H + 0.08 * H), (xr(H), H + 0.08 * H), f"{ancho_superior(z):.2f} m")
        ax.text(xr(H * 0.55) + 0.04 * max(B, H), H * 0.55, f"talud {t:g}H:1V", fontsize=7,
                color=TINTA, ha="left", va="center", rotation=math.degrees(math.atan2(1, t)),
                rotation_mode="anchor",
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.85))
    x_H = xl(H) - 0.12 * max(B, H) / 2
    _cota(ax, (x_H, 0), (x_H, H), f"{H:.2f} m", lado="izq")
    _cota(ax, (0, z.cama + D), (0, H), f"{cobertura(z):.2f} m\ncobertura")
    x_c = -B / 2 + 0.06 * B
    x_d = D / 2 + 0.08 * B
    if z.cama > 0:
        _cota(ax, (x_d, 0), (x_d, z.cama), f"{z.cama:.2f} m", lado="der", fontsize=6.5)
    if z.atraque > 0:
        _cota(ax, (x_d, z.cama + D), (x_d, y_atr), f"{z.atraque:.2f} m", lado="der",
              fontsize=6.5)
    if z.pavimento > 0:
        _cota(ax, (-x_c, H - z.pavimento), (-x_c, H), f"{z.pavimento:.2f} m", lado="izq",
              fontsize=6.5)

    ax.set_xlim(-W - 0.2 * max(B, H), W * 1.9)
    ax.set_ylim(-0.2 * H, H * 1.2)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------- tanque
@dataclass(frozen=True)
class NivelesTanque:
    area: float              # planta de una unidad [m²]
    h_util: float            # altura útil constructiva [m]
    h_max: float             # nivel máximo = volumen asignado / área
    h_incendio: float        # tope de la reserva de incendio
    borde_libre: float
    h_muro: float
    ancho_corte: float       # dimensión horizontal del corte [m]
    v_unidad: float
    v_incendio: float


def niveles_tanque(t, frac_incendio: float) -> NivelesTanque:
    """Niveles de una unidad del tanque. La reserva de incendio es la fracción
    frac/(1+frac) del volumen asignado (V = (V_reg + V_inc)·días con
    V_inc = frac·V_reg, Art. 81) y ocupa el fondo."""
    n = max(int(t.cantidad), 1)
    v = t.volumen / n
    ct = storage.dimensioned_tank(v, t.altura, t.forma, t.ratio)
    area = ct.volumen_real / ct.altura
    v_inc = v * frac_incendio / (1 + frac_incendio)
    ancho = ct.diametro if ct.forma == "circular" else ct.lado if ct.forma == "cuadrado" else ct.ancho
    return NivelesTanque(area, ct.altura, v / area, v_inc / area, t.borde_libre,
                         ct.altura + t.borde_libre, ancho, v, v_inc)


def _separar(ys: list, altos: list) -> list:
    """Posiciones de rótulo a partir de las alturas reales: de abajo hacia
    arriba, cada rótulo se aparta del anterior la mitad de la suma de sus
    altos (rótulos centrados verticalmente)."""
    orden = sorted(range(len(ys)), key=lambda i: ys[i])
    pos = list(ys)
    for a, b in zip(orden, orden[1:]):
        pos[b] = max(pos[b], pos[a] + (altos[a] + altos[b]) / 2)
    return pos


def fig_tanque(t, frac_incendio: float):
    """Corte del tanque con sus niveles; None sin volumen o altura. La escala
    vertical se exagera (y se declara) cuando el tanque es muy ancho."""
    if t.volumen <= 0 or t.altura <= 0:
        return None
    nv = niveles_tanque(t, frac_incendio)
    A = nv.ancho_corte
    k = 0.42 * A / nv.h_muro                     # exageración vertical (solo si es notoria)
    k = k if k >= 1.25 else 1.0
    Hm = nv.h_muro * k
    e = max(0.035 * A, 0.15)                     # espesor dibujado de muros y losa
    fig, ax = plt.subplots(figsize=(7.6, 4.0))
    y0 = 0.0
    if t.tipo_constructivo == "elevado":
        y0 = 0.75 * Hm
        for xp in (0.1 * A, 0.9 * A - e):
            ax.add_patch(Rectangle((xp, 0), e, y0 - e, fc="#d9d9d9", ec=TINTA_2, lw=0.8))
        ax.text(A / 2, (y0 - e) / 2, "Torre / pedestal", ha="center", va="center", fontsize=7,
                color=TINTA_2)
        y_terr = 0.0
    elif t.tipo_constructivo == "enterrado":
        y_terr = y0 + Hm
    elif t.tipo_constructivo == "semienterrado":
        y_terr = y0 + Hm / 2
    else:
        y_terr = y0 - e
    # terreno solo por fuera del tanque (enterrado/semienterrado con relleno a los lados)
    for x_a, x_b in ((-0.35 * A, -e), (A + e, 1.12 * A)):
        if y_terr > y0 - e:
            ax.add_patch(Rectangle((x_a, y0 - e), x_b - x_a, y_terr - y0 + e, fc="#f6f0e4",
                                   ec="#d8c9ad", hatch="\\\\", lw=0))
        ax.plot([x_a, x_b], [y_terr, y_terr], color=SUELO, lw=1.6)
    if t.tipo_constructivo == "elevado":
        ax.plot([-e, A + e], [y_terr, y_terr], color=SUELO, lw=1.6)
    # losa, muros, agua y reserva de incendio
    for r in ((-e, y0 - e, A + 2 * e, e), (-e, y0, e, Hm), (A, y0, e, Hm)):
        ax.add_patch(Rectangle(r[:2], r[2], r[3], fc="#bdbdbd", ec=TINTA_2, lw=0.8, zorder=3))
    ax.add_patch(Rectangle((0, y0), A, nv.h_max * k, fc=AGUA, ec="none", zorder=1))
    if nv.h_incendio > 0:
        ax.add_patch(Rectangle((0, y0), A, nv.h_incendio * k, fc=AGUA_RESERVA, ec="#5f93ad",
                               hatch="//", lw=0, zorder=2))

    niveles = [(nv.h_max, f"Nivel máximo +{nv.h_max:.2f} m")]
    if nv.h_incendio > 0:
        niveles.append((nv.h_incendio, f"Nivel mínimo de operación +{nv.h_incendio:.2f} m\n"
                                       "(tope de la reserva de incendio)"))
    niveles.append((0.0, "Fondo ±0.00 m"))
    if nv.borde_libre > 0:
        niveles.insert(0, (nv.h_muro, f"Corona del muro +{nv.h_muro:.2f} m\n"
                                      f"(Borde libre {nv.borde_libre:.2f} m)"))
    ys = [y0 + h * k for h, _ in niveles]
    pos = _separar(ys, [0.1 * Hm * (txt.count("\n") + 1.2) for _, txt in niveles])
    x_txt = A + e + 0.16 * A
    for (h, txt), y, yt in zip(niveles, ys, pos):
        if 0 < h <= nv.h_max + 1e-9:
            ax.plot([0, A], [y, y], color=TUBO, lw=0.9, ls="--", zorder=4)
            ax.plot([A * 0.9], [y + 0.035 * Hm], marker="v", color=TUBO, ms=6, zorder=5)
        ax.plot([A + e, A + e + 0.06 * A, x_txt - 0.02 * A], [y, yt, yt], color=TINTA_2, lw=0.6)
        ax.text(x_txt, yt, txt, ha="left", va="center", fontsize=7.5, color=TINTA)
    _cota(ax, (-e - 0.12 * A, y0), (-e - 0.12 * A, y0 + nv.h_util * k),
          f"{nv.h_util:.2f} m\nútil", lado="izq", fontsize=7)
    dim = "Ø" if t.forma == "circular" else "Lado" if t.forma == "cuadrado" else "Ancho"
    _cota(ax, (0, y0 - e - 0.08 * Hm), (A, y0 - e - 0.08 * Hm), f"{dim} {A:.2f} m")
    n = max(int(t.cantidad), 1)
    ax.text(A / 2, y0 + (nv.h_max + nv.h_incendio) * k / 2,
            f"V = {nv.v_unidad:.0f} m³" + (f" por unidad ({n} unidades)" if n > 1 else "")
            + (f"\nreserva de incendio {nv.v_incendio:.0f} m³" if nv.v_incendio > 0 else ""),
            ha="center", va="center", fontsize=7.5, color=TINTA, zorder=6,
            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.7))
    nota = f"{t.tipo_constructivo.capitalize()}, planta {t.forma}"
    if k > 1.05:
        nota += f" · escala vertical ×{k:.1f}"
    ax.set_title(f"{t.nombre}\n{nota}", fontsize=9, color=TINTA, loc="left")
    ax.set_xlim(-0.45 * A, 2.25 * A)
    ax.set_ylim(min(0.0, y0 - e) - 0.22 * Hm, max(pos[0], y0 + Hm) + 0.12 * Hm)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.tight_layout()
    return fig


# ------------------------------------------------------- estación de bombeo
def accesorios_por_lado(s) -> dict:
    """Accesorios del sistema por lado (succión / impulsión), con las entradas
    al inicio y la salida al final."""
    tipo_tramo = {t.nombre: t.tipo for t in s.tramos}
    lados = {"succion": [], "impulsion": []}
    for a in s.accesorios:
        lados["succion" if tipo_tramo.get(a.tramo) == "succion" else "impulsion"].append(a)
    for k, lista in lados.items():
        lista.sort(key=lambda a: (0 if a.tipo.lower().startswith("entrada") else
                                  2 if a.tipo.lower() == "salida" else 1))
    return lados


def _simbolo(ax, tipo: str, x: float, y: float, s: float = 0.22):
    k = tipo.lower()
    if "válvula" in k or "valvula" in k:
        izq = Polygon([(x - s, y + 0.6 * s), (x - s, y - 0.6 * s), (x, y)], closed=True,
                      fc="white", ec=TINTA, lw=1.0, zorder=5)
        der = Polygon([(x + s, y + 0.6 * s), (x + s, y - 0.6 * s), (x, y)], closed=True,
                      fc=TINTA if "cheque" in k or "retención" in k else "white", ec=TINTA,
                      lw=1.0, zorder=5)
        ax.add_patch(izq)
        ax.add_patch(der)
        if "compuerta" in k:
            ax.plot([x, x], [y, y + 1.2 * s], color=TINTA, lw=1.0, zorder=5)
            ax.plot([x - 0.5 * s, x + 0.5 * s], [y + 1.2 * s] * 2, color=TINTA, lw=1.2, zorder=5)
        elif "mariposa" in k:
            ax.plot([x - 0.35 * s, x + 0.35 * s], [y - 0.5 * s, y + 0.5 * s], color=TINTA,
                    lw=1.2, zorder=6)
        elif "globo" in k:
            ax.add_patch(Circle((x, y), 0.18 * s, fc=TINTA, ec=TINTA, zorder=6))
        elif "cheque" in k or "retención" in k:
            ax.annotate("", xy=(x + 0.6 * s, y + 1.0 * s), xytext=(x - 0.6 * s, y + 1.0 * s),
                        arrowprops=dict(arrowstyle="-|>", color=TINTA, lw=0.8,
                                        mutation_scale=7))
    elif "codo" in k:
        ax.add_patch(Arc((x - 0.9 * s, y), 1.8 * s, 2.4 * s, theta1=0, theta2=90, color=TINTA,
                         lw=1.6, zorder=5))
        ax.plot([x - 0.9 * s, x - 0.9 * s], [y + 1.1 * s, y + 1.3 * s], color=TINTA, lw=1.6,
                zorder=5)
        ax.plot([x - 0.1 * s, x + 0.1 * s], [y, y], color=TINTA, lw=2.4, zorder=5)
    elif "tee" in k:
        ax.plot([x, x], [y, y + 0.9 * s], color=TUBO, lw=2.2, zorder=4)
        ax.plot([x - 0.3 * s, x + 0.3 * s], [y + 0.9 * s] * 2, color=TINTA, lw=1.0, zorder=5)
    elif "yee" in k:
        ax.plot([x, x + 0.7 * s], [y, y + 0.7 * s], color=TUBO, lw=2.2, zorder=4)
    elif "unión" in k or "union" in k:
        for dx in (-0.08, 0.08):
            ax.plot([x + dx, x + dx], [y - 0.5 * s, y + 0.5 * s], color=TINTA, lw=1.4, zorder=5)
    elif k.startswith("entrada"):
        if "acampanada" in k:
            ax.plot([x - 0.5 * s, x - 0.1], [y - 0.7 * s, y - 0.05], color=TUBO, lw=1.6)
            ax.plot([x + 0.5 * s, x + 0.1], [y - 0.7 * s, y - 0.05], color=TUBO, lw=1.6)
        else:
            ax.plot([x - 0.3 * s, x + 0.3 * s], [y, y], color=TINTA, lw=1.4, zorder=5)
    elif k == "salida":
        ax.annotate("", xy=(x, y + 0.8), xytext=(x, y),
                    arrowprops=dict(arrowstyle="-|>", color=TUBO, lw=2.0, mutation_scale=12))
    else:
        ax.add_patch(Rectangle((x - 0.5 * s, y - 0.5 * s), s, s, fc="white", ec=TINTA,
                               lw=1.0, zorder=5))


def _rotulo(a) -> str:
    base = f"{a.cantidad}× {a.tipo}" if a.cantidad > 1 else a.tipo
    return "\n".join(textwrap.wrap(base, 16))


def fig_estacion(s):
    """Esquema (sin escala) de la estación de bombeo con sus accesorios."""
    if not s.tramos:
        return None
    lados = accesorios_por_lado(s)
    fig, ax = plt.subplots(figsize=(8.4, 4.6))
    y_t, y_l = 4.0, 5.1                      # terreno y cota de la tubería horizontal
    sumergible = s.tipo_bomba == "sumergible"
    # pozo o cámara de succión
    ax.add_patch(Rectangle((0.4, 0.6), 2.2, y_t - 0.6, fc="#f3f3f3", ec=TINTA_2, lw=1.2))
    ax.add_patch(Rectangle((0.42, 0.62), 2.16, 2.4, fc=AGUA, ec="none"))
    ax.plot([1.9], [3.1], marker="v", color=TUBO, ms=6)
    ax.text(1.5, 0.35, "Pozo / cámara de succión", ha="center", va="top", fontsize=7.5,
            color=TINTA)
    ax.plot([0, 12.2], [y_t, y_t], color=SUELO, lw=1.6)
    x_b = 1.5 if sumergible else 5.0
    y_b = 1.3 if sumergible else y_l
    # tuberías
    if sumergible:
        ax.plot([1.5, 1.5, 11.0, 11.0], [y_b, y_l, y_l, 6.6], color=TUBO, lw=2.6,
                solid_joinstyle="round", zorder=3)
    else:
        ax.plot([1.5, 1.5, x_b], [1.2, y_l, y_l], color=TUBO, lw=2.6,
                solid_joinstyle="round", zorder=3)
        ax.plot([x_b, 11.0, 11.0], [y_l, y_l, 6.6], color=TUBO, lw=2.6,
                solid_joinstyle="round", zorder=3)
        ax.add_patch(Rectangle((x_b - 0.55, y_t), 1.1, y_l - y_t - 0.3, fc="#d9d9d9",
                               ec=TINTA_2, lw=0.8))
    ax.add_patch(Circle((x_b, y_b), 0.3, fc="#fde9d9", ec="#b45309", lw=1.4, zorder=6))
    ax.text(x_b, y_b, "B", ha="center", va="center", fontsize=8, weight="bold", zorder=7)
    if sumergible:
        ax.text(x_b + 0.42, y_b + 0.1, "Bomba sumergible", ha="left", va="bottom",
                fontsize=7.5, color=TINTA)
    else:
        ax.text(x_b, y_l + 0.42, "Bomba de superficie", ha="center", va="bottom",
                fontsize=7.5, color=TINTA)

    def repartir(accs, x0, x1, y):
        normales = [a for a in accs if not a.tipo.lower().startswith("entrada")
                    and a.tipo.lower() != "salida"]
        paso = (x1 - x0) / (len(normales) + 1) if normales else 0
        for i, a in enumerate(normales):
            x = x0 + paso * (i + 1)
            _simbolo(ax, a.tipo, x, y)
            arriba = i % 2 == 1
            ax.text(x, y + 0.55 if arriba else y - 0.45, _rotulo(a), ha="center",
                    va="bottom" if arriba else "top", fontsize=6.5, color=TINTA)
        for a in accs:
            if a.tipo.lower().startswith("entrada"):
                xe, ye = (1.5, 1.2) if not sumergible else (1.5, y_b - 0.35)
                _simbolo(ax, a.tipo, xe, ye)
                ax.text(xe + 0.35, ye - 0.05, _rotulo(a), ha="left", va="top", fontsize=6.5,
                        color=TINTA)
            elif a.tipo.lower() == "salida":
                _simbolo(ax, a.tipo, 11.0, 6.6)
                ax.text(11.25, 7.1, _rotulo(a), ha="left", va="center", fontsize=6.5,
                        color=TINTA)

    if sumergible:
        repartir(lados["succion"] + lados["impulsion"], 2.0, 10.6, y_l)
    else:
        repartir(lados["succion"], 1.8, x_b - 0.45, y_l)
        repartir(lados["impulsion"], x_b + 0.45, 10.6, y_l)
        ax.text((1.5 + x_b) / 2, y_l + 1.45, "Succión", ha="center", fontsize=8, color=TINTA,
                weight="bold")
    ax.text((x_b + 11.0) / 2 + (1.0 if sumergible else 0), y_l + 1.45, "Impulsión",
            ha="center", fontsize=8, color=TINTA, weight="bold")
    ax.text(11.2, 6.3, "A tanque / red", ha="left", va="center", fontsize=7.5, color=TINTA)
    def _nombre(t):
        tipo = "succión" if t.tipo == "succion" else "impulsión"
        return t.nombre if t.nombre.lower().startswith(tipo[:4]) else f"{t.nombre} ({tipo})"
    tramos = "\n".join(
        f"{_nombre(t)}: L = {t.L:.1f} m, "
        f"D int. = {t.D_mm:.1f} mm, {t.cat_material or t.material}" for t in s.tramos)
    ax.text(3.0, 2.8, tramos + (f"\nAltura estática He = {s.he:.2f} m" if s.he else "")
            + "\nEsquema sin escala", ha="left", va="top", fontsize=7, color=TINTA_2)
    ax.set_xlim(0, 13.2)
    ax.set_ylim(0, 7.8)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(s.nombre, fontsize=9, color=TINTA, loc="left")
    fig.tight_layout()
    return fig

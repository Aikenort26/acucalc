"""Figuras del reporte, generadas desde el modelo (matplotlib headless).

Cada función devuelve una Figure lista para savefig; el llamador decide ruta y
dpi. Ninguna función depende de Streamlit ni de session_state.

Todas las figuras fuerzan el estilo claro de matplotlib (`default`) — las
páginas de la app usan `dark_background` para la vista en pantalla, y sin este
blindaje una figura del PDF podía heredar el fondo negro y volver invisibles
las líneas negras (bug reportado con la curva del sistema)."""
import functools

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from core.population import Projection

_METODO_LABEL = {"aritmetico": "Aritmético", "geometrico": "Geométrico",
                 "exponencial": "Exponencial", "wappaus": "Wappaus",
                 "res0844": "Res. 0844/2018"}


def _light(fn):
    """Fuerza el estilo de la figura sin importar el estado global de
    matplotlib: claro por defecto (reporte PDF), oscuro si se pasa `dark=True`
    (vista en la app). Evita el bug de figuras negras en el PDF."""
    @functools.wraps(fn)
    def wrapper(*args, dark: bool = False, **kwargs):
        with plt.style.context("dark_background" if dark else "default"):
            fig = fn(*args, **kwargs)
            if dark:
                fig.patch.set_alpha(0)
                for ax in fig.axes:
                    ax.set_facecolor("none")
            return fig
    return wrapper


@_light
def fig_poblacion(proj: Projection, metodo: str, flotante_pct: float = 0.0):
    """Proyección por los 5 métodos + promedio; método adoptado resaltado."""
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    finals = {}
    for m, s in proj.series.items():
        anos, vals = zip(*s)
        lw = 2.4 if m == metodo else 1.1
        ax.plot(anos, vals, lw=lw, label=_METODO_LABEL.get(m, m)
                + (" (adoptado)" if m == metodo else ""))
        finals[m] = vals
    prom = np.mean(list(finals.values()), axis=0)
    ax.plot(anos, prom, "k--", lw=1.2, label="Promedio")
    if flotante_pct > 0:
        tot = [v * (1 + flotante_pct) for v in finals[metodo]]
        ax.plot(anos, tot, ":", lw=2.0,
                label=f"Adoptado + {flotante_pct:.0%} flotante")
    ax.set_xlabel("Año"); ax.set_ylabel("Población [hab]")
    ax.grid(alpha=0.3); ax.legend(fontsize=8)
    fig.tight_layout()
    return fig


@_light
def fig_metodos(deviations: dict[str, float], sugerido: str):
    """Barras de desviación de cada método vs el promedio."""
    fig, ax = plt.subplots(figsize=(7, 4))
    metodos = list(deviations)
    vals = [deviations[m] * 100 for m in metodos]
    colores = ["#0E7490" if m == sugerido else "#9CB4BF" for m in metodos]
    ax.bar([_METODO_LABEL.get(m, m) for m in metodos], vals, color=colores)
    ax.axhline(0, color="k", lw=0.8)
    ax.set_ylabel("Desviación vs promedio [%]")
    ax.set_title("Comparación de métodos de proyección "
                 f"(menor desviación: {_METODO_LABEL.get(sugerido, sugerido)})",
                 fontsize=10)
    ax.grid(alpha=0.3, axis="y")
    plt.setp(ax.get_xticklabels(), rotation=15, ha="right")
    fig.tight_layout()
    return fig


@_light
def fig_caudales(serie: list[tuple[int, float, float, float]]):
    """Qmed/QMD/QMH [L/s] vs años. serie = [(año, qmed, qmd, qmh)]."""
    fig, ax = plt.subplots(figsize=(8.5, 4.5))
    anos = [s[0] for s in serie]
    ax.plot(anos, [s[1] for s in serie], label="$Q_{med}$")
    ax.plot(anos, [s[2] for s in serie], label="QMD")
    ax.plot(anos, [s[3] for s in serie], label="QMH")
    ax.set_xlabel("Año"); ax.set_ylabel("Caudal [L/s]")
    ax.grid(alpha=0.3); ax.legend()
    fig.tight_layout()
    return fig


def _acum(v):
    out, s = [], 0.0
    for x in v:
        s += x
        out.append(s)
    return out


@_light
def fig_balance_train(pares: list[tuple[str, list[float], list[float]]]):
    """Curvas acumuladas entrada vs salida para N tanques.
    pares = [(nombre, entrada[24], salida[24])] — se normalizan."""
    n = lambda v: [x / sum(v) for x in v]
    horas = list(range(24))
    cnt = max(len(pares), 1)
    fig, axes = plt.subplots(1, cnt, figsize=(5.5 * cnt, 4), squeeze=False)
    for ax, (nombre, entrada, salida) in zip(axes[0], pares):
        ax.plot(horas, _acum(n(entrada)), label="Entrada (suministro)")
        ax.plot(horas, _acum(n(salida)), label="Salida (consumo)")
        ax.set_title(nombre, fontsize=10)
        ax.set_xlabel("Hora"); ax.set_ylabel("Fracción acumulada del día")
        ax.grid(alpha=0.3); ax.legend(fontsize=8)
    fig.tight_layout()
    return fig


@_light
def fig_balance(capta: list[float], bombeo: list[float], consumo: list[float]):
    """Curvas acumuladas de suministro/consumo por tanque (bajo y elevado).
    Entradas: 24 valores horarios (se normalizan)."""
    n = lambda v: [x / sum(v) for x in v]
    capta, bombeo, consumo = n(capta), n(bombeo), n(consumo)
    horas = list(range(24))
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4))
    axes[0].plot(horas, _acum(capta), label="Suministro (captación)")
    axes[0].plot(horas, _acum(bombeo), label="Consumo (bombeo)")
    axes[0].set_title("Tanque bajo")
    axes[1].plot(horas, _acum(bombeo), label="Suministro (bombeo)")
    axes[1].plot(horas, _acum(consumo), label="Consumo (población)")
    axes[1].set_title("Tanque elevado")
    for ax in axes:
        ax.set_xlabel("Hora"); ax.set_ylabel("Fracción acumulada del día")
        ax.grid(alpha=0.3); ax.legend(fontsize=8)
    fig.tight_layout()
    return fig


@_light
def fig_sistema(sys_lps: list[tuple[float, float]],
                bombas: list[dict], qb_lps: float, hd: float, titulo: str = ""):
    """Curva del sistema + curvas de bombas + punto de diseño y de operación.
    bombas = [{"nombre", "fit": CurveFit, "op": (q, h)|None, "e_fit": CurveFit|None}].
    Si alguna bomba trae e_fit se añade un panel inferior Q-η."""
    con_eta = any(b.get("e_fit") for b in bombas)
    if con_eta:
        fig, (ax, ax2) = plt.subplots(2, 1, figsize=(8.5, 7.5), sharex=True,
                                      height_ratios=[2, 1])
    else:
        fig, ax = plt.subplots(figsize=(8.5, 5))
        ax2 = None
    ax.plot([q for q, _ in sys_lps], [h for _, h in sys_lps], "--",
            color="#1D4ED8", lw=2.2, label="Curva del sistema")
    ax.plot(qb_lps, hd, "r*", ms=16, zorder=5,
            label=f"Punto de diseño ({qb_lps:.1f} L/s, {hd:.1f} m)")
    y_vals = [h for _, h in sys_lps] + [hd]
    q_vals = [q for q, _ in sys_lps] + [qb_lps]
    for b in bombas:
        fit = b["fit"]
        qs = np.linspace(fit.q_min, fit.q_max, 100)
        hs = [fit(q) for q in qs]
        linea, = ax.plot(qs, hs, lw=1.6, label=b["nombre"])
        y_vals += hs; q_vals += [fit.q_min, fit.q_max]
        if b.get("op"):
            ax.plot(*b["op"], "o", ms=8, color=linea.get_color())
            y_vals.append(b["op"][1]); q_vals.append(b["op"][0])
        e_fit = b.get("e_fit")
        if ax2 is not None and e_fit:
            qs_e = np.linspace(e_fit.q_min, e_fit.q_max, 100)
            ax2.plot(qs_e, [e_fit(q) for q in qs_e], lw=1.6,
                     color=linea.get_color(), label=b["nombre"])
            if b.get("op"):
                ax2.plot(b["op"][0], e_fit(b["op"][0]), "o", ms=8,
                         color=linea.get_color())
    # guías punteadas del punto de diseño a los ejes, con anotación (Q, H)
    ax.plot([qb_lps, qb_lps], [0, hd], ":", color="#DC2626", lw=1.1, zorder=4)
    ax.plot([0, qb_lps], [hd, hd], ":", color="#DC2626", lw=1.1, zorder=4)
    ax.annotate(f"({qb_lps:.1f}, {hd:.1f})", (qb_lps, hd),
                textcoords="offset points", xytext=(8, 8), fontsize=8,
                color="#DC2626")
    ax.set_xlim(0, max(q_vals) * 1.03)
    ax.set_ylim(0, max(y_vals) * 1.08)
    ax.set_ylabel("H [m]")
    if ax2 is not None:
        ax2.set_xlabel("Q [L/s]"); ax2.set_ylabel("η [-]")
        ax2.grid(alpha=0.3); ax2.legend(fontsize=7)
    else:
        ax.set_xlabel("Q [L/s]")
    if titulo:
        ax.set_title(titulo, fontsize=10)
    ax.grid(alpha=0.3); ax.legend(fontsize=8)
    fig.tight_layout()
    return fig


GROUND_Y = 0.34   # nivel de terreno común a todo el esquema, en coords de eje [0,1]


def _dibujar_terreno(ax, x0=0.0, x1=1.0, y=GROUND_Y):
    ax.plot([x0, x1], [y, y], color="#8B5E34", lw=2, zorder=3)
    n = int((x1 - x0) / 0.02)
    for i in range(n):
        xa = x0 + i * 0.02
        ax.plot([xa, xa - 0.008], [y, y - 0.015], color="#8B5E34", lw=0.8, zorder=3)


def _dibujar_bomba(ax, x, y, tipo_bomba: str):
    """Símbolo de bomba: círculo con 'B'. tipo_bomba solo cambia la etiqueta —
    la posición (en pozo bajo terreno o a nivel de superficie) la decide quien
    llama esta función."""
    ax.add_patch(plt.Circle((x, y), 0.028, fc="#FDE9D9", ec="#B45309", lw=1.4, zorder=6))
    ax.text(x, y, "B", ha="center", va="center", fontsize=8, weight="bold", zorder=7)
    etiqueta = "Bomba\nsumergible" if tipo_bomba == "sumergible" else "Bomba de\nsuperficie"
    ax.text(x, y - 0.10, etiqueta, ha="center", va="top", fontsize=7)


def _dibujar_pozo(ax, x, w, y_fondo, y_terreno, tipo_bomba: str):
    """Pozo perforado con revestimiento; bomba sumergible cerca del fondo si
    tipo_bomba=='sumergible', o succión desde el pozo si es de superficie."""
    ax.add_patch(plt.Rectangle((x, y_fondo), w, y_terreno - y_fondo, fc="#EFEFEF",
                               ec="#6B7280", lw=1.2, zorder=2))
    ax.plot([x, x], [y_fondo, y_terreno], color="#6B7280", lw=1.5, zorder=3)
    ax.plot([x + w, x + w], [y_fondo, y_terreno], color="#6B7280", lw=1.5, zorder=3)
    cx = x + w / 2
    if tipo_bomba == "sumergible":
        _dibujar_bomba(ax, cx, y_fondo + 0.04, "sumergible")
    else:
        ax.plot([cx, cx], [y_fondo + 0.02, y_terreno], color="#0E7490", lw=1.3,
                ls=":", zorder=4)
        _dibujar_bomba(ax, cx, y_terreno + 0.05, "superficie")
    ax.text(cx, y_fondo - 0.03, "Pozo", ha="center", va="top", fontsize=8)


def _dibujar_tanque(ax, x, w, tipo_constructivo: str, forma: str, cantidad: int,
                    nombre: str, y_terreno=GROUND_Y, h_tanque=0.30):
    """Dibujo tipo corte constructivo del tanque según su tipo:
    superficial (apoyado en el terreno), enterrado (bajo tierra con tapa de
    acceso), semienterrado (mitad enterrado) o elevado (sobre torre/pedestal).
    `forma` solo anota la planta (circular/cuadrado/rectangular) en la etiqueta."""
    hatch = "////"
    if tipo_constructivo == "elevado":
        torre_h = 0.32
        base_y = y_terreno + torre_h
        ax.plot([x + w * 0.15, x + w * 0.15], [y_terreno, base_y],
                color="#6B7280", lw=2.2, zorder=2)
        ax.plot([x + w * 0.85, x + w * 0.85], [y_terreno, base_y],
                color="#6B7280", lw=2.2, zorder=2)
        ax.add_patch(plt.Rectangle((x, base_y), w, h_tanque, fc="#DCE9EF",
                                   ec="#0E7490", lw=1.5, zorder=5))
        y_centro = base_y + h_tanque / 2
    elif tipo_constructivo == "enterrado":
        base_y = y_terreno - h_tanque
        ax.add_patch(plt.Rectangle((x - 0.02, base_y - 0.02), w + 0.04,
                                   h_tanque + 0.02 + (y_terreno - base_y - h_tanque),
                                   fc="#EAD9BE", ec="none", hatch=hatch,
                                   alpha=0.5, zorder=1))
        ax.add_patch(plt.Rectangle((x, base_y), w, h_tanque, fc="#DCE9EF",
                                   ec="#0E7490", lw=1.5, zorder=2))
        ax.add_patch(plt.Rectangle((x + w * 0.4, y_terreno - 0.015, ), w * 0.2, 0.015,
                                   fc="#9CA3AF", ec="#374151", lw=0.8, zorder=3))
        y_centro = base_y + h_tanque / 2
    elif tipo_constructivo == "semienterrado":
        base_y = y_terreno - h_tanque / 2
        ax.add_patch(plt.Rectangle((x - 0.02, base_y - 0.02), w + 0.04,
                                   y_terreno - base_y + 0.02, fc="#EAD9BE",
                                   ec="none", hatch=hatch, alpha=0.5, zorder=1))
        ax.add_patch(plt.Rectangle((x, base_y), w, h_tanque, fc="#DCE9EF",
                                   ec="#0E7490", lw=1.5, zorder=2))
        y_centro = base_y + h_tanque / 2
    else:  # superficial
        base_y = y_terreno
        ax.add_patch(plt.Rectangle((x, base_y), w, 0.03, fc="#9CA3AF",
                                   ec="#374151", lw=0.8, zorder=2))   # losa
        ax.add_patch(plt.Rectangle((x, base_y + 0.03), w, h_tanque, fc="#DCE9EF",
                                   ec="#0E7490", lw=1.5, zorder=3))
        y_centro = base_y + 0.03 + h_tanque / 2
    etiqueta = f"{nombre}\n({tipo_constructivo}, {forma}" + (f" ×{cantidad})" if cantidad > 1 else ")")
    ax.text(x + w / 2, y_centro, etiqueta, ha="center", va="center", fontsize=7.5, zorder=6)
    return x + w / 2   # centro horizontal, para conectar flechas


@_light
def fig_esquema(sistemas: list[dict], tanques: list) -> "plt.Figure":
    """Esquema constructivo del sistema: capta (pozo/superficial) → PTAP →
    tanque[0] (tipo_constructivo/forma/cantidad) → bomba → tanque[1] → … → red.

    `sistemas`: [{"tipo_bomba": "sumergible"|"superficie"}, …] en orden.
    `tanques`: [TankSpec, …] en orden hidráulico (puede ser vacío)."""
    n_etapas = 2 + len(tanques)          # captación+PTAP + N tanques
    fig, ax = plt.subplots(figsize=(2.6 * max(n_etapas, 3), 3.8))
    ax.axis("off")
    _dibujar_terreno(ax)

    def flecha(x0, y0, x1, y1):
        ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                    arrowprops=dict(arrowstyle="-|>", color="#0E7490", lw=1.6), zorder=4)

    tipo_bomba_0 = sistemas[0]["tipo_bomba"] if sistemas else "superficie"
    ancho_paso = 1.0 / max(n_etapas, 1)
    x = 0.02

    if tipo_bomba_0 == "sumergible":
        _dibujar_pozo(ax, x, ancho_paso * 0.6, GROUND_Y - 0.28, GROUND_Y, "sumergible")
    else:
        ax.add_patch(plt.Rectangle((x, GROUND_Y), ancho_paso * 0.6, 0.16,
                                   fc="#E8F1F5", ec="#0E7490", lw=1.4, zorder=5))
        ax.text(x + ancho_paso * 0.3, GROUND_Y + 0.08, "Captación\nsuperficial",
                ha="center", va="center", fontsize=7.5)
    x_prev = x + ancho_paso * 0.6
    x += ancho_paso
    flecha(x_prev, GROUND_Y + 0.08, x, GROUND_Y + 0.08)

    ax.add_patch(plt.Rectangle((x, GROUND_Y), ancho_paso * 0.6, 0.16, fc="#F5F0E6",
                               ec="#0E7490", lw=1.4, zorder=5))
    ax.text(x + ancho_paso * 0.3, GROUND_Y + 0.08, "PTAP\n(sin\nalmacén.)",
           ha="center", va="center", fontsize=7)
    x_prev = x + ancho_paso * 0.6
    x += ancho_paso

    for i, t in enumerate(tanques):
        tipo_bomba_i = (sistemas[i]["tipo_bomba"] if i < len(sistemas) and i > 0
                        else (tipo_bomba_0 if i == 0 else "superficie"))
        if i > 0:
            cx = x_prev + 0.02
            _dibujar_bomba(ax, cx, GROUND_Y + 0.05, tipo_bomba_i)
            flecha(x_prev, GROUND_Y + 0.05, cx - 0.03, GROUND_Y + 0.05)
            x_prev = cx + 0.03
        else:
            flecha(x_prev, GROUND_Y + 0.08, x, GROUND_Y + 0.08)
            x_prev = x
        w = ancho_paso * 0.7
        cx_tanque = _dibujar_tanque(ax, x_prev, w, t.tipo_constructivo, t.forma,
                                    t.cantidad, t.nombre)
        x_prev = x_prev + w
        x += ancho_paso

    flecha(x_prev, GROUND_Y + 0.08, min(x_prev + ancho_paso * 0.5, 0.97), GROUND_Y + 0.08)
    ax.text(min(x_prev + ancho_paso * 0.5, 0.97) + 0.02, GROUND_Y + 0.08, "Red",
           ha="left", va="center", fontsize=9, weight="bold")

    ax.set_xlim(0, 1)
    ax.set_ylim(GROUND_Y - 0.4, GROUND_Y + 0.75)
    fig.tight_layout()
    return fig

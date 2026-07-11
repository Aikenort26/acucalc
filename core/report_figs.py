"""Figuras del reporte, generadas desde el modelo (matplotlib headless).

Cada función devuelve una Figure lista para savefig; el llamador decide ruta y
dpi. Ninguna función depende de Streamlit ni de session_state."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from core.population import Projection

_METODO_LABEL = {"aritmetico": "Aritmético", "geometrico": "Geométrico",
                 "exponencial": "Exponencial", "wappaus": "Wappaus",
                 "res0844": "Res. 0844/2018"}


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


def fig_sistema(sys_lps: list[tuple[float, float]],
                bombas: list[dict], qb_lps: float, hd: float, titulo: str = ""):
    """Curva del sistema + curvas de bombas + punto de diseño y de operación.
    bombas = [{"nombre", "fit": CurveFit, "op": (q, h) | None}]."""
    fig, ax = plt.subplots(figsize=(8.5, 5))
    ax.plot([q for q, _ in sys_lps], [h for _, h in sys_lps], "k--", lw=2,
            label="Curva del sistema")
    ax.plot(qb_lps, hd, "r*", ms=16, zorder=5,
            label=f"Punto de diseño ({qb_lps:.1f} L/s, {hd:.1f} m)")
    for b in bombas:
        fit = b["fit"]
        qs = np.linspace(fit.q_min, fit.q_max, 100)
        ax.plot(qs, [fit(q) for q in qs], lw=1.6, label=b["nombre"])
        if b.get("op"):
            ax.plot(*b["op"], "o", ms=8)
    ax.set_xlabel("Q [L/s]"); ax.set_ylabel("H [m]")
    if titulo:
        ax.set_title(titulo, fontsize=10)
    ax.grid(alpha=0.3); ax.legend(fontsize=8)
    fig.tight_layout()
    return fig


def fig_esquema(tipo_bomba: str = "superficie", cadena: bool = True):
    """Esquema del sistema: captación→PTAP→tanque bajo→bomba→tanque elevado→red."""
    fig, ax = plt.subplots(figsize=(10, 3.6))
    ax.axis("off")

    def caja(x, y, w, h, texto, fc="#E8F1F5"):
        ax.add_patch(plt.Rectangle((x, y), w, h, fc=fc, ec="#0E7490", lw=1.4))
        ax.text(x + w / 2, y + h / 2, texto, ha="center", va="center", fontsize=9)

    def flecha(x0, y0, x1, y1):
        ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                    arrowprops=dict(arrowstyle="-|>", color="#0E7490", lw=1.6))

    if tipo_bomba == "sumergible":
        caja(0.02, 0.15, 0.13, 0.5, "Pozo con\nbomba\nsumergible", fc="#DCE9EF")
    else:
        caja(0.02, 0.3, 0.13, 0.35, "Captación")
    flecha(0.15, 0.48, 0.22, 0.48)
    caja(0.22, 0.3, 0.13, 0.35, "PTAP\n(sin almacen.)")
    flecha(0.35, 0.48, 0.42, 0.48)
    if cadena:
        caja(0.42, 0.3, 0.13, 0.35, "Tanque bajo")
        flecha(0.55, 0.48, 0.60, 0.48)
        simbolo = "Bomba\nsumergible" if tipo_bomba == "sumergible" else "Bomba de\nsuperficie"
        circ = plt.Circle((0.635, 0.48), 0.045, fc="#FDE9D9", ec="#B45309", lw=1.4)
        ax.add_patch(circ)
        ax.text(0.635, 0.48, "B", ha="center", va="center", fontsize=10, weight="bold")
        ax.text(0.635, 0.24, simbolo, ha="center", va="center", fontsize=8)
        flecha(0.68, 0.48, 0.73, 0.48)
        caja(0.73, 0.42, 0.13, 0.45, "Tanque\nelevado", fc="#DCE9EF")
        flecha(0.86, 0.55, 0.93, 0.55)
        ax.text(0.955, 0.55, "Red", ha="center", va="center", fontsize=10)
    else:
        caja(0.42, 0.3, 0.2, 0.35, "Tanque de\nalmacenamiento")
        flecha(0.62, 0.48, 0.72, 0.48)
        ax.text(0.76, 0.48, "Red", ha="center", va="center", fontsize=10)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    fig.tight_layout()
    return fig

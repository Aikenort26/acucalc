"""Mapa de la red de distribución (estilo EPANET, minimalista): nodos, tramos,
tanques/reservorios y bombas, coloreados por presión o velocidad usando el
resultado del solver GGA propio (`core/network.solve`). Sin dependencias
externas nuevas — solo matplotlib, ya presente."""
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import cm, colors
from matplotlib.collections import LineCollection

# paleta acorde al tema de la app (verde+azul)
_VERDE = "#22C55E"
_AZUL = "#38BDF8"
_AZUL_HONDO = "#0EA5E9"
_ROJO = "#F87171"


def tiene_coordenadas(net_) -> bool:
    """True si al menos un nodo trae coordenadas del [COORDINATES]."""
    todos = list(net_.junctions.values()) + list(net_.sources.values())
    return any(n.x is not None and n.y is not None for n in todos)


def _pos_auto(net_) -> dict:
    """Posiciones de respaldo cuando el INP no trae [COORDINATES]: layout radial
    determinista (BFS desde la primera fuente). No es un layout bonito, pero
    permite ver la topología en vez de no mostrar nada."""
    adj: dict = {}
    for p in net_.pipes:
        adj.setdefault(p.node1, set()).add(p.node2)
        adj.setdefault(p.node2, set()).add(p.node1)
    origen = next(iter(net_.sources), None) or next(iter(net_.junctions))
    nivel = {origen: 0}
    cola = [origen]
    while cola:
        actual = cola.pop(0)
        for vecino in adj.get(actual, ()):
            if vecino not in nivel:
                nivel[vecino] = nivel[actual] + 1
                cola.append(vecino)
    por_nivel: dict = {}
    for nid, lv in nivel.items():
        por_nivel.setdefault(lv, []).append(nid)
    pos = {}
    for lv, nodos in por_nivel.items():
        for i, nid in enumerate(sorted(nodos)):
            ang = 2 * math.pi * i / max(len(nodos), 1)
            pos[nid] = (lv * math.cos(ang), lv * math.sin(ang))
    # nodos sueltos sin conexión
    for nid in list(net_.junctions) + list(net_.sources):
        pos.setdefault(nid, (0.0, 0.0))
    return pos


def _posiciones(net_) -> dict:
    if tiene_coordenadas(net_):
        pos = {}
        for nid, n in {**net_.junctions, **net_.sources}.items():
            if n.x is not None and n.y is not None:
                pos[nid] = (n.x, n.y)
        # completa los que no traían coord con el layout automático
        if len(pos) < len(net_.junctions) + len(net_.sources):
            auto = _pos_auto(net_)
            for nid in list(net_.junctions) + list(net_.sources):
                pos.setdefault(nid, auto[nid])
        return pos
    return _pos_auto(net_)


def fig_red(net_, resultado=None, colorear: str = "presion", dark: bool = True):
    """Dibuja la red. Si `resultado` (NetworkResult) viene dado, colorea los
    tramos por velocidad o los nodos por presión (`colorear` in
    {"presion", "velocidad"}). Logos minimalistas: triángulo=reservorio,
    cuadrado=tanque, círculo=nodo de consumo."""
    pos = _posiciones(net_)
    fondo = "#0B1416" if dark else "white"
    tinta = "#EAF6F2" if dark else "#0B1416"
    fig, ax = plt.subplots(figsize=(8.5, 6.0))
    fig.patch.set_facecolor(fondo)
    ax.set_facecolor(fondo)

    # ---- tramos ----
    segmentos, valores = [], []
    for p in net_.pipes:
        if p.node1 in pos and p.node2 in pos:
            segmentos.append([pos[p.node1], pos[p.node2]])
            if resultado is not None and colorear == "velocidad":
                valores.append(abs(resultado.velocities.get(p.id, 0.0)))
    if segmentos and valores:
        norm = colors.Normalize(vmin=min(valores), vmax=max(max(valores), 0.1))
        lc = LineCollection(segmentos, cmap=plt.get_cmap("cool"),
                            norm=norm, linewidths=2.6)
        lc.set_array(_np_array(valores))
        ax.add_collection(lc)
        cb = fig.colorbar(lc, ax=ax, fraction=0.04, pad=0.02)
        cb.set_label("Velocidad [m/s]", color=tinta)
        cb.ax.tick_params(colors=tinta)
    else:
        for seg in segmentos:
            (x1, y1), (x2, y2) = seg
            ax.plot([x1, x2], [y1, y2], color=_AZUL_HONDO, lw=2.2, zorder=1)

    # ---- nodos de consumo ----
    if resultado is not None and colorear == "presion":
        presiones = {jid: resultado.heads.get(jid, 0.0) - j.elevation
                     for jid, j in net_.junctions.items()}
        vals = list(presiones.values()) or [0.0]
        norm = colors.Normalize(vmin=min(vals), vmax=max(vals))
        cmap = plt.get_cmap("RdYlGn")
        for jid, j in net_.junctions.items():
            if jid in pos:
                x, y = pos[jid]
                ax.scatter([x], [y], s=90, c=[cmap(norm(presiones[jid]))],
                           edgecolors=tinta, linewidths=0.8, zorder=3)
        sm = cm.ScalarMappable(norm=norm, cmap=cmap)
        sm.set_array([])
        cb = fig.colorbar(sm, ax=ax, fraction=0.04, pad=0.02)
        cb.set_label("Presión [m]", color=tinta)
        cb.ax.tick_params(colors=tinta)
    else:
        for jid in net_.junctions:
            if jid in pos:
                x, y = pos[jid]
                ax.scatter([x], [y], s=70, c=_VERDE, edgecolors=tinta,
                           linewidths=0.8, zorder=3)

    # ---- fuentes: triángulo=reservorio, cuadrado=tanque ----
    for sid, s in net_.sources.items():
        if sid in pos:
            x, y = pos[sid]
            marcador = "^" if s.tipo == "reservorio" else "s"
            ax.scatter([x], [y], s=220, marker=marcador, c=_AZUL,
                       edgecolors=tinta, linewidths=1.4, zorder=4)
            ax.annotate(sid, (x, y), textcoords="offset points", xytext=(8, 8),
                        color=tinta, fontsize=8, fontweight="bold")

    ax.set_title("Red de distribución", color=tinta, fontsize=13, fontweight="bold")
    ax.set_aspect("equal", adjustable="datalim")
    ax.axis("off")
    fig.tight_layout()
    return fig


def _np_array(vals):
    import numpy as np
    return np.array(vals)

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


def fig_red(net_, resultado=None, colorear: str = "presion", dark: bool = True,
            escala: float = 1.0):
    """Dibuja la red. Si `resultado` (NetworkResult) viene dado, colorea los
    tramos por velocidad o los nodos por presión (`colorear` in
    {"presion", "velocidad"}). Logos minimalistas: triángulo=reservorio,
    cuadrado=tanque, círculo=nodo de consumo.

    `escala` multiplica el tamaño de nodos, fuentes y grosor de tramos: en una
    red densa (cientos de nodos) los marcadores por defecto se enciman y tapan
    la topología; en una red pequeña se ven diminutos. El área del marcador va
    con `escala²` (matplotlib usa área en `s`) para que el cambio de tamaño se
    perciba lineal."""
    escala = max(float(escala), 0.1)
    area = escala ** 2
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
                            norm=norm, linewidths=2.6 * escala)
        lc.set_array(_np_array(valores))
        ax.add_collection(lc)
        cb = fig.colorbar(lc, ax=ax, fraction=0.04, pad=0.02)
        cb.set_label("Velocidad [m/s]", color=tinta)
        cb.ax.tick_params(colors=tinta)
    else:
        for seg in segmentos:
            (x1, y1), (x2, y2) = seg
            ax.plot([x1, x2], [y1, y2], color=_AZUL_HONDO, lw=2.2 * escala, zorder=1)

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
                ax.scatter([x], [y], s=90 * area, c=[cmap(norm(presiones[jid]))],
                           edgecolors=tinta, linewidths=0.8 * escala, zorder=3)
        sm = cm.ScalarMappable(norm=norm, cmap=cmap)
        sm.set_array([])
        cb = fig.colorbar(sm, ax=ax, fraction=0.04, pad=0.02)
        cb.set_label("Presión [m]", color=tinta)
        cb.ax.tick_params(colors=tinta)
    else:
        for jid in net_.junctions:
            if jid in pos:
                x, y = pos[jid]
                ax.scatter([x], [y], s=70 * area, c=_VERDE, edgecolors=tinta,
                           linewidths=0.8 * escala, zorder=3)

    # ---- fuentes: triángulo=reservorio, cuadrado=tanque ----
    for sid, s in net_.sources.items():
        if sid in pos:
            x, y = pos[sid]
            marcador = "^" if s.tipo == "reservorio" else "s"
            ax.scatter([x], [y], s=220 * area, marker=marcador, c=_AZUL,
                       edgecolors=tinta, linewidths=1.4 * escala, zorder=4)
            ax.annotate(sid, (x, y), textcoords="offset points", xytext=(8, 8),
                        color=tinta, fontsize=8 * escala, fontweight="bold")

    ax.set_title("Red de distribución", color=tinta, fontsize=13, fontweight="bold")
    ax.set_aspect("equal", adjustable="datalim")
    ax.axis("off")
    fig.tight_layout()
    return fig


def _np_array(vals):
    import numpy as np
    return np.array(vals)


# ---------------------------------------------------------------- Plotly

# Rampa secuencial de un solo tono (azul) para magnitudes: presión y velocidad.
_RAMPA = ["#cfe2f7", "#a4c8ef", "#78ade6", "#4f92dc", "#2a78d6", "#1f5fae", "#164783"]
_BANDAS_V = [0.0, 0.3, 0.6, 1.0, 1.5, 2.0, 3.0, math.inf]


def _texto_nodo(jid, j, presion=None) -> str:
    t = f"<b>{jid}</b><br>Cota {j.elevation:.2f} m<br>Demanda {j.demand:.3f} L/s"
    return t + (f"<br>Presión {presion:.2f} m" if presion is not None else "")


def fig_red_plotly(net_, resultado=None, colorear: str = "presion", escala: float = 1.0,
                   oscuro: bool = True, p_min: float | None = None):
    """Mapa interactivo (zoom, paneo, hover) de la red. Tuberías en una sola
    traza WebGL con separadores `None` (rápido en redes de miles de tramos);
    con resultado, nodos coloreados por presión o tramos agrupados en bandas
    de velocidad (rampa secuencial de un tono: en fondo oscuro, lo alto es lo
    claro). Los nodos bajo `p_min` van en su propia traza de estado (rojo, ✕)."""
    import plotly.graph_objects as go
    pos = _posiciones(net_)
    escala = max(float(escala), 0.1)
    rampa = _RAMPA[::-1] if oscuro else _RAMPA
    borde = "#0e1117" if oscuro else "#ffffff"
    fig = go.Figure()

    def segmentos(tubos):
        xs, ys = [], []
        for p in tubos:
            (x0, y0), (x1, y1) = pos[p.node1], pos[p.node2]
            xs += [x0, x1, None]
            ys += [y0, y1, None]
        return xs, ys

    if resultado is not None and colorear == "velocidad":
        vel = {p.id: abs(resultado.velocities.get(p.id, 0.0)) for p in net_.pipes}
        for i, (a, b) in enumerate(zip(_BANDAS_V[:-1], _BANDAS_V[1:])):
            tubos = [p for p in net_.pipes if a <= vel[p.id] < b]
            if not tubos:
                continue
            xs, ys = segmentos(tubos)
            nombre = f"V {a:g}–{b:g} m/s" if b != math.inf else f"V ≥ {a:g} m/s"
            fig.add_trace(go.Scattergl(x=xs, y=ys, mode="lines", name=nombre,
                                       line=dict(color=rampa[i], width=2.5 * escala),
                                       hoverinfo="skip"))
    else:
        xs, ys = segmentos(net_.pipes)
        fig.add_trace(go.Scattergl(x=xs, y=ys, mode="lines", name="Tuberías",
                                   line=dict(color="#8a8f98", width=1.8 * escala),
                                   hoverinfo="skip"))

    # puntos medios invisibles: dan el hover de cada tramo
    mx, my, mtxt = [], [], []
    for p in net_.pipes:
        (x0, y0), (x1, y1) = pos[p.node1], pos[p.node2]
        mx.append((x0 + x1) / 2)
        my.append((y0 + y1) / 2)
        t = f"<b>{p.id}</b><br>L {p.length:.1f} m · D {p.diameter_mm:.1f} mm"
        if resultado is not None:
            t += (f"<br>Q {resultado.flows.get(p.id, 0.0):.2f} L/s"
                  f"<br>V {abs(resultado.velocities.get(p.id, 0.0)):.2f} m/s")
        mtxt.append(t)
    fig.add_trace(go.Scattergl(x=mx, y=my, mode="markers", name="Tramos",
                               marker=dict(size=8 * escala, opacity=0), hovertext=mtxt,
                               hoverinfo="text", showlegend=False))

    jids = list(net_.junctions)
    pres = ([resultado.heads.get(j, 0.0) - net_.junctions[j].elevation for j in jids]
            if resultado is not None else None)
    marcador = dict(size=8 * escala, line=dict(width=1, color=borde))
    if pres is not None and colorear == "presion":
        marcador.update(color=pres, colorscale=[[i / 6, c] for i, c in enumerate(rampa)],
                        colorbar=dict(title="Presión [m]", thickness=12), showscale=True)
    else:
        marcador.update(color="#2a78d6")
    fig.add_trace(go.Scattergl(
        x=[pos[j][0] for j in jids], y=[pos[j][1] for j in jids], mode="markers",
        name="Nodos", marker=marcador, hoverinfo="text",
        hovertext=[_texto_nodo(j, net_.junctions[j], pres[i] if pres else None)
                   for i, j in enumerate(jids)]))

    if pres is not None and p_min is not None:
        bajo = [i for i, v in enumerate(pres) if v < p_min]
        if bajo:
            fig.add_trace(go.Scattergl(
                x=[pos[jids[i]][0] for i in bajo], y=[pos[jids[i]][1] for i in bajo],
                mode="markers", name=f"Bajo P mín. ({p_min:.0f} m)",
                marker=dict(symbol="x", size=12 * escala, color="#e34948"),
                hoverinfo="text",
                hovertext=[_texto_nodo(jids[i], net_.junctions[jids[i]], pres[i]) for i in bajo]))

    for tipo, nombre, simbolo, color in (("reservorio", "Reservorios", "triangle-up", "#1baf7a"),
                                         ("tanque", "Tanques", "square", "#eb6834")):
        fuentes = [s for s in net_.sources.values() if s.tipo == tipo]
        if fuentes:
            fig.add_trace(go.Scatter(
                x=[pos[s.id][0] for s in fuentes], y=[pos[s.id][1] for s in fuentes],
                mode="markers+text", name=nombre, text=[s.id for s in fuentes],
                textposition="top center",
                marker=dict(symbol=simbolo, size=14 * escala, color=color,
                            line=dict(width=1, color=borde)),
                hovertext=[f"<b>{s.id}</b><br>{tipo.capitalize()} · cabeza {s.head:.2f} m"
                           for s in fuentes], hoverinfo="text"))

    fig.update_layout(
        height=560, margin=dict(l=10, r=10, t=30, b=10), dragmode="pan",
        hovermode="closest", legend=dict(orientation="h", y=1.02, x=0),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False,
                   scaleanchor="x", scaleratio=1))
    return fig

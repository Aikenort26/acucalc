import time

import pytest

from core import epanet_engine as ee
from core import network as net
from core import network_map as nm
from tests.test_network import INP_COORDS


def _trazas(fig):
    return {t.name: t for t in fig.data}


def test_topologia_tuberias_en_una_traza_con_separadores():
    red = net.parse_inp(INP_COORDS)
    fig = nm.fig_red_plotly(red)
    t = _trazas(fig)
    tub = t["Tuberías"]
    assert list(tub.x).count(None) == len(red.pipes)          # un None por tramo
    assert len(tub.x) == 3 * len(red.pipes)
    assert fig.layout.yaxis.scaleanchor == "x"                  # escala 1:1
    nodos = t["Nodos"]
    assert len(nodos.x) == len(red.junctions)
    assert any("J2" in h and "cota" in h.lower() for h in nodos.hovertext)
    assert "Reservorios" in t and "Tanques" in t


def test_colorea_por_presion_con_resultado():
    red = net.parse_inp(INP_COORDS)
    res = net.solve(red)
    fig = nm.fig_red_plotly(red, res, colorear="presion")
    nodos = _trazas(fig)["Nodos"]
    esperadas = [res.heads[j] - red.junctions[j].elevation for j in red.junctions]
    assert list(nodos.marker.color) == pytest.approx(esperadas)
    assert any("presión" in h.lower() for h in nodos.hovertext)


def test_colorea_por_velocidad_agrupa_tramos_en_bandas():
    red = net.parse_inp(INP_COORDS)
    res = net.solve(red)
    fig = nm.fig_red_plotly(red, res, colorear="velocidad")
    bandas = [t for t in fig.data if t.name and t.name.startswith("V ")]
    assert bandas and sum(list(t.x).count(None) for t in bandas) == len(red.pipes)


def _malla(n):
    j, p, c = [], [], []
    for r in range(n):
        for k in range(n):
            j.append(f"N{r}_{k} 10 0.1"); c.append(f"N{r}_{k} {k} {r}")
            if k + 1 < n: p.append(f"H{r}_{k} N{r}_{k} N{r}_{k+1} 100 100 130")
            if r + 1 < n: p.append(f"V{r}_{k} N{r}_{k} N{r+1}_{k} 100 100 130")
    p.append("PR R1 N0_0 100 300 130"); c.append("R1 -1 0")
    return ("[JUNCTIONS]\n" + "\n".join(j) + "\n[RESERVOIRS]\nR1 60\n[PIPES]\n" + "\n".join(p)
            + "\n[COORDINATES]\n" + "\n".join(c) + "\n[OPTIONS]\nUnits LPS\n")


def test_red_grande_se_construye_rapido():
    red = net.parse_inp(_malla(50))                            # ~4 900 tramos
    t0 = time.perf_counter()
    nm.fig_red_plotly(red)
    assert time.perf_counter() - t0 < 1.0


def test_nodos_bajo_p_min_en_traza_de_estado():
    red = net.parse_inp(INP_COORDS)
    res = net.solve(red)
    pres = {j: res.heads[j] - red.junctions[j].elevation for j in red.junctions}
    umbral = sorted(pres.values())[0] + 1e-6              # el de menor presión queda debajo
    fig = nm.fig_red_plotly(red, res, colorear="presion", p_min=umbral)
    t = _trazas(fig)
    bajo = t[f"Bajo P mín. ({umbral:.0f} m)"]
    assert len(bajo.x) == 1 and bajo.marker.symbol == "x"


def test_rampa_invertida_en_modo_oscuro():
    red = net.parse_inp(INP_COORDS)
    res = net.solve(red)
    claro = nm.fig_red_plotly(red, res, colorear="presion", oscuro=False)
    oscuro = nm.fig_red_plotly(red, res, colorear="presion", oscuro=True)
    esc_c = _trazas(claro)["Nodos"].marker.colorscale
    esc_o = _trazas(oscuro)["Nodos"].marker.colorscale
    assert esc_c[0][1] == esc_o[-1][1] and esc_c[-1][1] == esc_o[0][1]

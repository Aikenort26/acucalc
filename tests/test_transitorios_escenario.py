import pytest

from core import project as pj
from core.transients import escenario as esc


def _proyecto(escenario="cierre_valvula", pn=100.0, perfil=None, **kw):
    p = pj.Project(nombre="T", temperatura=20.0)
    tc = p.transitorios
    tc.perfil = perfil or [(0.0, 100.0, 99.0), (1000.0, 60.0, 59.0)]
    tc.tramos = [pj.TramoTransitorio(1000.0, D_mm=200.0, e_mm=9.6, material="PVC", pn_mca=pn)]
    tc.escenario = escenario
    tc.q0_lps, tc.h_arriba, tc.h_abajo, tc.tc = 30.0, 100.0, 60.0, 1.0
    for k, v in kw.items():
        setattr(tc, k, v)
    return p


def test_cierre_de_valvula_resumen_y_comparacion():
    r = esc.ejecutar(_proyecto())
    metodos = [c["metodo"] for c in r.comparacion]
    assert metodos[:3] == ["MOC (perfil real, con fricción)",
                           "Allievi (conducción equivalente sin fricción)",
                           "Joukowsky (maniobra instantánea)"]
    moc_dh, allievi_dh, jouk = (c["dh"] for c in r.comparacion[:3])
    # con fricción el empaquetamiento de la línea suma hasta la pérdida de régimen
    hf = 100.0 - r.moc.H_abajo[0]
    assert jouk < moc_dh <= jouk + hf + 1e-6 and 0 < allievi_dh <= jouk * 1.001
    assert r.resumen["clasificacion"] == "rápida"            # Tc = 1 s < 2L/a
    assert r.resumen["p_max"] > r.resumen["p_min"]
    assert r.tramos[0].a == pytest.approx(9900 / (48.3 + 18.0 * 200 / 9.6) ** 0.5)


def test_pn_excedida_genera_recomendacion():
    r = esc.ejecutar(_proyecto(pn=20.0))
    assert r.verificacion_pn[0]["cumple"] is False
    assert any("PN" in t for t in r.recomendaciones)


def test_maniobra_lenta_incluye_michaud():
    r = esc.ejecutar(_proyecto(tc=20.0))
    assert r.resumen["clasificacion"] == "lenta"
    assert any(c["metodo"].startswith("Michaud") for c in r.comparacion)


def test_parada_de_bomba_con_curva_del_proyecto():
    p = _proyecto("parada_bomba", h_arriba=5.0, h_abajo=45.0, bomba="S · B",
                  modo_parada="instantanea",
                  perfil=[(0.0, 5.0, 4.0), (600.0, 30.0, 29.0), (1000.0, 45.0, 44.0)])
    s = pj.PumpSystemData(nombre="S")
    s.bombas = [pj.PumpData("B", puntos_qh=[(0, 70), (30, 60), (60, 30)])]
    s.bomba_seleccionada = "B"
    p.bombeos = [s]
    r = esc.ejecutar(p)
    assert 0.030 < r.Q0 < 0.050                            # punto de operación de la curva
    assert r.comparacion[0]["dh"] < 0                      # depresión en la bomba
    assert r.moc.cavitacion is not None                    # el punto alto cae a vapor
    assert any("separación de columna" in t for t in r.recomendaciones)


def test_sin_tramos_es_error():
    p = _proyecto()
    p.transitorios.tramos = []
    with pytest.raises(ValueError, match="tramo"):
        esc.ejecutar(p)


def test_tramos_deben_cubrir_el_perfil():
    p = _proyecto()
    p.transitorios.tramos[0].hasta_abscisa = 500.0
    with pytest.raises(ValueError, match="cubrir"):
        esc.ejecutar(p)


def _con_bomba(p):
    s = pj.PumpSystemData(nombre="S")
    s.bombas = [pj.PumpData("B", puntos_qh=[(0, 70), (30, 60), (60, 30)])]
    s.bomba_seleccionada = "B"
    p.bombeos = [s]
    return p


def test_arranque_solo_requiere_el_tiempo_de_arranque():
    # la velocidad sigue la rampa prescrita: rpm, eficiencia e inercia no intervienen
    p = _con_bomba(_proyecto("arranque_bomba", h_arriba=5.0, h_abajo=45.0, bomba="S · B",
                             n_rpm=0.0, eta=0.0, inercia=0.0, t_arranque=5.0,
                             perfil=[(0.0, 5.0, 4.0), (1000.0, 45.0, 44.0)]))
    r = esc.ejecutar(p)
    assert r.comparacion[0]["dh"] > 0                      # sobrepresión en la bomba
    assert r.moc.Q_arriba[0] == 0.0 and r.moc.Q_arriba[-1] > 0.030
    p.transitorios.t_arranque = 0.0
    with pytest.raises(ValueError, match="tiempo de arranque"):
        esc.ejecutar(p)


def test_hidroneumatico_reporta_expansion_del_aire_y_atenua_la_depresion():
    base = dict(h_arriba=5.0, h_abajo=45.0, bomba="S · B", modo_parada="instantanea",
                perfil=[(0.0, 5.0, 4.0), (1000.0, 45.0, 44.0)])
    sin = esc.ejecutar(_con_bomba(_proyecto("parada_bomba", **base)))
    con = esc.ejecutar(_con_bomba(_proyecto("hidroneumatico", v_aire=0.3, **base)))
    assert con.resumen["v_aire_max"] > 0.3                 # el aire se expande al vaciarse
    assert con.comparacion[0]["dh"] > sin.comparacion[0]["dh"]   # menos depresión
    assert any("volumen total del tanque" in t for t in con.recomendaciones)
    assert "v_aire_max" not in sin.resumen


def test_perfil_con_cota_de_eje_tambien_exige_abscisas_crecientes():
    p = _proyecto(perfil=[(1000.0, 100.0, 99.0), (0.0, 60.0, 59.0)])
    with pytest.raises(ValueError, match="crecientes"):
        esc.ejecutar(p)


def test_simulacion_demasiado_larga_es_error_y_no_se_cuelga():
    with pytest.raises(ValueError, match="pasos de tiempo"):
        esc.ejecutar(_proyecto(t_sim=1e9))

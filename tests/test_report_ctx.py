import base64

from core import project as pj
from core import report
from core import report_ctx


def _logo_png_b64() -> str:
    # PNG 1x1 blanco válido (evita depender de Pillow para generar el fixture)
    raw = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
        "+A8AAQUBAScY42YAAAAASUVORK5CYII=")
    return base64.b64encode(raw).decode()


def _proyecto_minimo() -> pj.Project:
    p = pj.Project(nombre="Demo", municipio="Demo", altitud=100, temperatura=20.0)
    p.censo = [(2018, 1000), (2019, 1010)]
    p.poblacion.p0, p.poblacion.metodo = 1000.0, "res0844"
    p.demanda.dneta = 120.0
    return p


def test_latex_escape_caracteres_especiales():
    assert report_ctx.latex_escape("T&B_1 50% #3 {x} ~y ^z") == \
        r"T\&B\_1 50\% \#3 \{x\} \textasciitilde{}y \textasciicircum{}z"


def test_latex_escape_unicode_fragil():
    assert report_ctx.latex_escape("Pozo → red, Ø 200 mm, 10×2") == \
        r"Pozo $\to$ red, \O{} 200 mm, 10$\times$2"
    assert report_ctx.latex_escape("Sistema — bombeo “crudo”") == \
        "Sistema --- bombeo ``crudo''"


def test_latex_escape_griegas_y_punto_medio():
    assert report_ctx.latex_escape("S · B, τ = 0, η 0.8, ΔH, α, ρ") == \
        r"S \textperiodcentered{} B, $\tau$ = 0, $\eta$ 0.8, $\Delta$H, $\alpha$, $\rho$"


def test_latex_escape_backslash_primero():
    # el backslash debe escaparse antes que los demas simbolos, o se duplica
    assert report_ctx.latex_escape("100\\%") == r"100\textbackslash{}\%"


def test_latex_escape_cubre_tanques_balance():
    """Regresion (spec review): bal.nombre (storage.TankBalance, generado por
    la cadena de tanques) viene del mismo TankSpec.nombre que tanques_ctx,
    pero es un flujo independiente hacia el contexto — build() debe
    escaparlo igual que en tanques_ctx, no solo ahi.

    Tambien cubre p.fecha (hallazgo de code review): texto libre del usuario
    que se interpola crudo en main.tex.j2 (\\date{\\VAR{fecha}}) — debe
    salir escapado del contexto igual que los demas campos de usuario."""
    p = pj.Project(nombre="Test", municipio="M", departamento="D",
                   consultor="C", fecha="15% de julio", altitud=100,
                   temperatura=20.0)
    p.censo = [(2010, 1000), (2020, 1200)]
    p.poblacion = pj.PopulationConfig(p0=1200, year0=2024, horizon_year=2030,
                                      metodo="aritmetico")
    p.demanda = pj.DemandConfig(dneta=100.0)
    p.almacenamiento.factores_hora = [1.0] * 24
    p.almacenamiento.tanques = [pj.TankSpec("T&B_1", entrada_ini=5, entrada_fin=14)]

    ctx, _ = report_ctx.build(p)

    assert ctx["tanques_balance"]
    assert ctx["tanques_balance"][0]["nombre"] == report_ctx.latex_escape("T&B_1")
    assert ctx["fecha"] == report_ctx.latex_escape("15% de julio")


def _sistema_con_bomba(n_unidades: int = 1, arreglo: str = "paralelo",
                       n1_nominal: float = 0.0, n2_objetivo: float = 0.0) -> pj.Project:
    p = _proyecto_minimo()
    p.almacenamiento.factores_hora = [1.0] * 24
    sistema = pj.PumpSystemData(nombre="Bombeo 1", horas=10.0, he=20.0)
    sistema.tramos = [pj.SegmentData("Impulsion", "impulsion", 100.0, 100.0, "PEAD")]
    sistema.bombas = [pj.PumpData(
        nombre="Bomba X",
        puntos_qh=[(0.0, 40.0), (5.0, 30.0), (10.0, 15.0)],
        puntos_qe=[(0.0, 0.1), (5.0, 0.5), (10.0, 0.3)],
        n_unidades=n_unidades, arreglo=arreglo,
        n1_nominal=n1_nominal, n2_objetivo=n2_objetivo)]
    p.bombeos = [sistema]
    return p


def test_bombas_tab_refleja_arreglo_por_bomba():
    """Cierra el gap del code review: ningún test ejercía el camino de la
    transformación (afinidad/arreglo) a través de report_ctx.build() — solo
    la UI de la página 6 lo hacía manualmente. bombas_tab debe reflejar el
    arreglo configurado en la PumpData persistida y su Q_op debe diferir del
    de la misma bomba sin arreglo (2 en paralelo -> mismo H, mayor Q)."""
    ctx_nominal, _ = report_ctx.build(_sistema_con_bomba(n_unidades=1))
    ctx_paralelo, _ = report_ctx.build(_sistema_con_bomba(n_unidades=2, arreglo="paralelo"))

    tab_nominal = ctx_nominal["sistemas"][0]["bombas"][0]
    tab_paralelo = ctx_paralelo["sistemas"][0]["bombas"][0]

    assert tab_nominal["arreglo"] == "nominal"
    assert tab_paralelo["arreglo"] == "2$\\times$paralelo"
    assert tab_paralelo["q_op"] != tab_nominal["q_op"]


def test_bombas_tab_etiqueta_arreglo_no_incluye_n2_espurio():
    """Hallazgo Minor del code review: cuando solo cambia n_unidades (sin
    afinidad activa), la etiqueta no debe mostrar '@ N$_2$=0'."""
    ctx, _ = report_ctx.build(_sistema_con_bomba(n_unidades=2, arreglo="serie"))
    arreglo = ctx["sistemas"][0]["bombas"][0]["arreglo"]
    assert arreglo == "2$\\times$serie"
    assert "N$_2$" not in arreglo


def test_bombas_tab_etiqueta_solo_afinidad_sin_prefijo_de_unidades():
    ctx, _ = report_ctx.build(_sistema_con_bomba(n1_nominal=1750.0, n2_objetivo=3500.0))
    arreglo = ctx["sistemas"][0]["bombas"][0]["arreglo"]
    assert arreglo == "@ N$_2$=3500"
    assert "$\\times$" not in arreglo


def test_logo_entra_al_diccionario_de_figuras_y_se_copia(tmp_path):
    p = _proyecto_minimo()
    p.logo_cliente_b64 = _logo_png_b64()
    ctx, figuras = report_ctx.build(p)
    assert "logo_cliente" in figuras
    assert ctx["logo_cliente"] == "logo_cliente.png"
    out = report.render(ctx, tmp_path)
    assert (out / "figures" / "logo_cliente.png").exists()


def test_curva_de_bomba_seleccionada_entra_al_anexo(tmp_path):
    """WP-B1: la bomba seleccionada del sistema (bomba_seleccionada) con
    imagen_b64 debe entrar en figuras (para que report.render la copie) y en
    ctx['anexos_curvas'] (para que la plantilla la incluya como anexo)."""
    p = _sistema_con_bomba()
    p.bombeos[0].bombas[0].imagen_b64 = _logo_png_b64()
    p.bombeos[0].bomba_seleccionada = "Bomba X"
    ctx, figuras = report_ctx.build(p)

    assert "curva_0_0" in figuras
    assert ctx["anexos_curvas"] == [
        {"sistema": "Bombeo 1", "bomba": "Bomba X", "fig": "curva_0_0.png"}]
    out = report.render(ctx, tmp_path)
    assert (out / "figures" / "curva_0_0.png").exists()


def test_sin_bomba_seleccionada_no_hay_anexo():
    p = _sistema_con_bomba()
    p.bombeos[0].bombas[0].imagen_b64 = _logo_png_b64()
    # bomba_seleccionada queda vacía (default)
    ctx, figuras = report_ctx.build(p)
    assert ctx["anexos_curvas"] == []
    assert "curva_0_0" not in figuras


def test_bomba_seleccionada_sin_imagen_no_hay_anexo():
    p = _sistema_con_bomba()
    p.bombeos[0].bomba_seleccionada = "Bomba X"   # sin imagen_b64
    ctx, figuras = report_ctx.build(p)
    assert ctx["anexos_curvas"] == []


# ---------- v8: patrón horario, autoría y cita del DANE ----------

def test_patron_horario_llega_al_contexto():
    """Antes `factores_hora` se usaba para calcular el volumen del tanque pero
    nunca se documentaba: no aparecía ni una vez en la plantilla, así que el
    lector no podía reproducir el dimensionamiento."""
    p = _proyecto_minimo()
    p.almacenamiento.factores_hora = [0.6, 1.6] + [1.0] * 22
    p.almacenamiento.suministro_hora = [1] * 10 + [0] * 14
    ctx, _ = report_ctx.build(p)
    assert len(ctx["patron_horas"]) == 24
    assert ctx["patron_pico"] == "1.60"
    assert ctx["patron_valle"] == "0.60"
    assert ctx["patron_suma"] == "24.20"
    assert ctx["patron_horas"][0] == {"hora": "00", "factor": "0.60", "suministro": "sí"}
    assert ctx["patron_horas"][23]["suministro"] == "no"


def test_sin_patron_el_contexto_no_lo_inventa():
    p = _proyecto_minimo()
    p.almacenamiento.factores_hora = []
    ctx, _ = report_ctx.build(p)
    assert ctx["patron_horas"] == []
    assert ctx["patron_pico"] is None


def test_patron_sin_ventana_de_suministro_marca_guion():
    p = _proyecto_minimo()
    p.almacenamiento.factores_hora = [1.0] * 24
    p.almacenamiento.suministro_hora = []
    ctx, _ = report_ctx.build(p)
    assert {h["suministro"] for h in ctx["patron_horas"]} == {"—"}


def test_referencias_base_y_bibtex_del_usuario():
    p = _proyecto_minimo()
    p.bibtex_usuario = (
        "@book{mio2024, author={Ortega, Aiken}, title={Estudio de suelos}, year={2024}}\n"
        "@misc{dane, author={{DANE}}, title={Serie corregida}, year={2024}}")
    refs = {r["key"]: r for r in report_ctx.build(p)[0]["referencias"]}
    assert "res0330" in refs and "wylie1993" in refs
    assert refs["mio2024"]["texto"].startswith("Ortega, A. (2024).")
    assert "Serie corregida" in refs["dane"]["texto"]      # la del usuario reemplaza


def test_pob_es_dane_distingue_la_fuente():
    p = _proyecto_minimo()
    p.poblacion.fuente = "dane"
    assert report_ctx.build(p)[0]["pob_es_dane"] is True
    p.poblacion.fuente = "manual"
    assert report_ctx.build(p)[0]["pob_es_dane"] is False


def test_autor_de_la_app_va_al_contexto():
    ctx, _ = report_ctx.build(_proyecto_minimo())
    assert ctx["autor"] == "Aiken H. Ortega-Heredia"


# --- WP3 v9: marca ACUCALC y mapa de la red en el informe -------------------

from pathlib import Path

INP_RED = """[JUNCTIONS]
J1 10 0
J2 8 0

[RESERVOIRS]
R1 50

[PIPES]
P1 R1 J1 200 150 130
P2 J1 J2 150 100 130

[COORDINATES]
J1 100 200
J2 150 200
R1 0 200

[OPTIONS]
Units LPS
Headloss H-W
"""


def test_logo_acucalc_en_figuras_y_portada(tmp_path):
    ctx, figuras = report_ctx.build(_proyecto_minimo())
    assert ctx["logo_acucalc"] == "acucalc_logo.png"
    assert Path(figuras["acucalc_logo"]).is_file()
    tex = (report.render(ctx, tmp_path / "out") / "main.tex").read_text(encoding="utf-8")
    assert "figures/acucalc_logo.png" in tex
    assert (tmp_path / "out" / "figures" / "acucalc_logo.png").is_file()


def test_mapa_de_red_en_informe(tmp_path):
    p = _proyecto_minimo()
    p.red_inp = INP_RED
    ctx, figuras = report_ctx.build(p)
    assert ctx["red"]["fig"] == "red.png"
    assert Path(figuras["red"]).is_file()
    tex = (report.render(ctx, tmp_path / "out") / "main.tex").read_text(encoding="utf-8")
    assert "figures/red.png" in tex


def test_sin_red_en_informe_no_hay_mapa():
    p = _proyecto_minimo()
    p.red_inp, p.red_en_informe = INP_RED, False
    ctx, figuras = report_ctx.build(p)
    assert ctx["red"] is None and "red" not in figuras


def test_texto_red_declara_qmh_como_condicion_de_diseno(tmp_path):
    """Art. 47: la red de distribución se diseña con QMH; el QMD es la demanda
    base que se reparte por longitud."""
    p = _proyecto_minimo()
    p.red_inp = INP_RED
    ctx, _ = report_ctx.build(p)
    tex = (report.render(ctx, tmp_path / "o") / "main.tex").read_text(encoding="utf-8")
    assert "que es la condición de diseño de la red" not in tex
    assert "QMH" in tex[tex.index(r"\section{Red de distribución}"):]


def _con_bombeo(tipo_bomba="superficie"):
    p = _proyecto_minimo()
    s = pj.PumpSystemData(nombre="Captación", horas=12, he=25.0, eficiencia=0.7,
                          tipo_bomba=tipo_bomba, z_succion=3.0, npsh_r=4.0, margen_npsh=0.5)
    s.tramos = [pj.SegmentData("Succión", "succion", 6.0, 102.2, "PVC"),
                pj.SegmentData("Impulsión", "impulsion", 300.0, 79.5, "PEAD", e_mm=5.3)]
    p.bombeos = [s]
    return p


def test_npsh_en_el_informe(tmp_path):
    ctx, _ = report_ctx.build(_con_bombeo())
    n = ctx["sistemas"][0]["npsh"]
    assert n["cumple"] == "Sí" and float(n["npsh_d"]) > 4.5
    assert n["npsh_r"] == "4.00" and n["margen"] == "0.50"
    tex = (report.render(ctx, tmp_path) / "main.tex").read_text(encoding="utf-8")
    assert "NPSH disponible" in tex and r"\cite{iapws2012}" in tex and r"\cite{iso2533}" in tex


def test_npsh_no_aplica_a_sumergible():
    ctx, _ = report_ctx.build(_con_bombeo("sumergible"))
    assert ctx["sistemas"][0]["npsh"] is None


# --- WP6 v9: resultados hidráulicos de la red en el informe ------------------

from core import epanet_engine as _ee

_con_epanet = __import__("pytest").mark.skipif(not _ee.disponible(), reason="sin EPANET")


@_con_epanet
def test_red_estatico_qmh_y_eps_en_el_informe(tmp_path):
    p = _proyecto_minimo()
    p.red_inp = INP_RED
    p.almacenamiento.factores_hora = [1.0] * 23 + [1.6]
    ctx, figuras = report_ctx.build(p)
    e = ctx["red"]["estatico"]
    assert e["motor"].startswith("EPANET") and e["cumple"] in ("Sí", "No")
    assert e["multiplicador"] == f"{ctx['k2']:.2f}" and e["nodo_p_min"] in ("J1", "J2")
    assert ctx["red"]["eps"]["hora"] is not None
    assert "red_presion" in figuras and "red_eps" in figuras
    tex = (report.render(ctx, tmp_path) / "main.tex").read_text(encoding="utf-8")
    assert r"\cite{rossman2020}" in tex and "figures/red_eps.png" in tex
    assert "no converge de forma" not in tex          # la limitación vieja ya no aplica


def test_red_sin_k2_usa_multiplicador_1():
    p = _proyecto_minimo()
    p.red_inp, p.red_aplicar_k2, p.red_motor = INP_RED, False, "gga"
    e = report_ctx.build(p)[0]["red"]["estatico"]
    assert e["multiplicador"] == "1.00" and e["motor"] == _ee.MOTOR_GGA


def test_balance_red_de_tanques_en_el_informe(tmp_path):
    from core import tank_network as tn
    p = _proyecto_minimo()
    alm = p.almacenamiento
    alm.factores_hora = [1.0] * 24
    alm.suministro_hora = [1 if 5 <= h <= 14 else 0 for h in range(24)]
    alm.tanques = [pj.TankSpec("Bajo", "bajo", "circular", 40, 3, entrada_ini=5, entrada_fin=14),
                   pj.TankSpec("Elevado", "elevado", "circular", 20, 3, entrada_ini=0,
                               entrada_fin=23)]
    alm.modo_balance = "red"
    alm.zonas, alm.enlaces = tn.config_inicial(alm)
    ctx, figuras = report_ctx.build(p)
    b = ctx["balance_red"]
    assert [t["nombre"] for t in b["tanques"]] == ["Bajo", "Elevado"]
    assert "balance_red" in figuras and b["fig"] == "balance_red.png"
    tex = (report.render(ctx, tmp_path) / "main.tex").read_text(encoding="utf-8")
    assert "Balance de masas entre tanques" in tex and "Captación" in tex


def test_modo_por_tanque_no_genera_balance_red():
    assert report_ctx.build(_proyecto_minimo())[0]["balance_red"] is None


def _con_transitorio(escenario="cierre_valvula", **kw):
    p = _proyecto_minimo()
    tc = p.transitorios
    tc.perfil = [(0.0, 100.0, 99.0), (400.0, 90.0, 89.0), (1000.0, 60.0, 59.0)]
    tc.tramos = [pj.TramoTransitorio(1000.0, D_mm=200.0, e_mm=9.6, material="PVC", pn_mca=100.0)]
    tc.escenario = escenario
    tc.q0_lps, tc.h_arriba, tc.h_abajo, tc.tc = 30.0, 100.0, 60.0, 1.0
    for k, v in kw.items():
        setattr(tc, k, v)
    return p


def test_transitorio_en_el_informe(tmp_path):
    ctx, figuras = report_ctx.build(_con_transitorio())
    t = ctx["transitorio"]
    assert t["metodos"][0]["metodo"].startswith("MOC") and len(t["metodos"]) >= 3
    assert t["tramos"][0]["a"] and t["pn"][0]["cumple"] in ("Sí", "No")
    assert t["fig_perfil"] == "transitorio_perfil.png" and "transitorio_perfil" in figuras
    assert "transitorio_tiempo" in figuras
    assert t["resumen"]["s_p_max"].startswith("K")
    tex = (report.render(ctx, tmp_path) / "main.tex").read_text(encoding="utf-8")
    sec = tex[tex.index(r"\section{Transitorios hidráulicos}"):]
    import re
    citadas = {k.strip() for g in re.findall(r"\\cite\{([^}]*)\}", sec) for k in g.split(",")}
    assert {"wylie1993", "chaudhry2014", "allievi1925", "joukowsky1904"} <= citadas
    assert "figures/transitorio_perfil.png" in sec and "Allievi" in sec


def test_transitorio_fuera_del_informe_o_sin_perfil():
    assert report_ctx.build(_con_transitorio(en_informe=False))[0]["transitorio"] is None
    assert report_ctx.build(_proyecto_minimo())[0]["transitorio"] is None


def test_transitorio_con_datos_invalidos_documenta_el_error(tmp_path):
    ctx, figuras = report_ctx.build(_con_transitorio(q0_lps=0.0))
    assert "caudal" in ctx["transitorio"]["error"] and "transitorio_perfil" not in figuras
    tex = (report.render(ctx, tmp_path) / "main.tex").read_text(encoding="utf-8")
    assert r"\section{Transitorios hidráulicos}" in tex

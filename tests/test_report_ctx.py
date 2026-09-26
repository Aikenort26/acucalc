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


def test_referencia_dane_tiene_key_titulo_oficial_y_url():
    """La serie del DANE es el insumo de toda la proyección: debe citarse con su
    título oficial y su URL, y tener `key` para la referencia cruzada."""
    dane = next(r for r in report_ctx.REFERENCIAS if r["key"] == "dane")
    assert ("Proyecciones y retroproyecciones de población municipal para el "
            "periodo 1985-2017 y 2018-2042 con base en el CNPV 2018") in dane["cita"]
    assert dane["url"].startswith("https://www.dane.gov.co/")


def test_todas_las_referencias_tienen_key_unica():
    keys = [r["key"] for r in report_ctx.REFERENCIAS]
    assert all(keys), "una referencia sin key rompe su \label{ref:}"
    assert len(keys) == len(set(keys)), "keys duplicadas colisionan en \label"


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

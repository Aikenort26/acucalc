from core import project as pj
from core import report_ctx


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

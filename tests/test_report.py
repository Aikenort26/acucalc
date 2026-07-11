import shutil
from core import report

CTX = {
    "nombre": "El Salado", "municipio": "El Carmen de Bolívar",
    "departamento": "Bolívar", "corregimiento": "El Salado",
    "consultor": "Aiken Ortega", "fecha": "2026-07-10",
    "altitud": 150, "temperatura": 20.0,
    "pob_metodo": "res0844", "pob_justificacion": "Retorno poblacional",
    "pob_final": "1,602", "horizonte": 2051,
    "pob_tipo": "corregimiento/vereda",
    "pob_fuente": ("proyecciones oficiales DANE — El Carmen de Bolívar (Bolívar), "
                   "área Cabecera Municipal, serie 2018–2042"),
    "year0": 2026, "flotante_pct": "10",
    "dneta": "80", "dneta_modo": "usos", "dneta_justificacion": "",
    "dbruta": "88.9", "perdidas": "10", "k1": 1.3, "k2": 1.6,
    "qmed": "1.648", "qmd": "2.142", "qmh": "3.428",
    "componentes": [("Captación subterránea", "2.142"), ("Red de distribución", "3.428")],
    "caudales_anuales": [
        {"ano": 2026, "pob": "1,400", "qmed": "1.440", "qmd": "1.872", "qmh": "2.996"},
        {"ano": 2051, "pob": "1,602", "qmed": "1.648", "qmd": "2.142", "qmh": "3.428"}],
    "usar_cadena": True,
    "tanques_balance": [
        {"nombre": "T. bajo", "horas": "24", "q_entrada": "21.49", "frac": "0.0417", "v": 30},
        {"nombre": "T. elevado", "horas": "10", "q_entrada": "51.57", "frac": "0.5167", "v": 110}],
    "v_art81": "—", "v_curva": "—", "v_final": 140,
    "tanques": [{"nombre": "T. bajo", "tipo": "bajo", "forma": "rectangular",
                 "dim": "3.00 × 4.50 m", "volumen": "30", "altura": "2.50"},
                {"nombre": "T. elevado", "tipo": "elevado", "forma": "circular",
                 "dim": "Ø 7.48 m", "volumen": "110", "altura": "2.50"}],
    "sistemas": [{
        "nombre": "Captación→T.Bajo", "tipo_bomba": "sumergible", "horas": "10",
        "qb": "5.14", "hd": "74.35", "eficiencia": 0.734,
        "potencia_kw": "5.10", "potencia_hp": "6.84",
        "tramos": [{"nombre": "Impulsión", "L": "284.8", "D_mm": "79.5",
                    "material": "PEAD", "V": "1.04", "hf": "3.756", "hl": "0.798"}],
        "bombas": [{"nombre": "Bomba A", "q_op": "5.30", "h_op": "74.50",
                    "eta_op": "0.490", "bep_q": "7.80", "desv_bep": "-32.1",
                    "p_hp": "6.90",
                    "h_eq": "$H = -0.2817Q^2 +1.1244Q +32.094$",
                    "e_eq": "$\\eta = -0.008639Q^2 +0.11837Q -0.0554$"}],
        "bomba_seleccionada": "Bomba A", "fig": ""}],
    "figuras": {},   # sin archivos en el test — los \BLOCK{if} deben omitir las figuras
}


def test_render_tex(tmp_path):
    out = report.render(CTX, tmp_path)
    tex = (out / "main.tex").read_text(encoding="utf-8")
    assert "El Salado" in tex
    assert "Resolución 0330" in tex
    assert "\\VAR{" not in tex and "\\BLOCK{" not in tex   # sin variables sin resolver
    assert "2.142" in tex                                   # QMD
    assert "Bomba A" in tex
    assert "proyecciones oficiales DANE" in tex             # fuente censal
    assert "Captación→T.Bajo" in tex                        # sistema de bombeo
    assert "tren de tanques" in tex.lower()                 # cadena de tanques
    assert "51.57" in tex                                   # Q de entrada por tanque
    assert "flotante" in tex.lower()                        # población flotante
    assert "includegraphics" not in tex                     # sin figuras si figuras={}


def test_render_crea_zip(tmp_path):
    out = report.render(CTX, tmp_path)
    z = report.make_zip(out)
    assert z.exists() and z.suffix == ".zip"


def test_compilacion_detecta_latex(tmp_path):
    out = report.render(CTX, tmp_path)
    pdf, log = report.compile_pdf(out)
    if shutil.which("pdflatex") or shutil.which("latexmk"):
        assert pdf is not None and pdf.exists()
        assert log                                     # log siempre disponible
    else:
        assert pdf is None and "PATH" in log


def test_compilacion_fallida_da_log(tmp_path):
    import shutil as sh
    if not (sh.which("pdflatex") or sh.which("latexmk")):
        return
    (tmp_path / "main.tex").write_text(r"\documentclass{article}\begin{document}"
                                       r"\errmessage{fallo}\end{document}",
                                       encoding="utf-8")
    pdf, log = report.compile_pdf(tmp_path)
    assert log        # hay diagnóstico aunque falle o no genere PDF

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
        {"nombre": "T. bajo", "horas": "24", "q_entrada": "21.49",
         "horas_salida": "10", "q_salida": "51.57",
         "frac": "0.0417", "v": 30},
        {"nombre": "T. elevado", "horas": "10", "q_entrada": "51.57",
         "horas_salida": "—", "q_salida": "51.57 (pico QMH)",
         "frac": "0.5167", "v": 110}],
    "v_art81": "—", "v_curva": "—", "v_final": 140,
    "tanques": [{"nombre": "T. bajo", "tipo": "bajo", "tipo_constructivo": "semienterrado",
                 "forma": "rectangular", "cantidad": 1,
                 "dim": "3.00 × 4.50 m", "volumen": "30", "volumen_real": "31.2",
                 "altura": "2.50"},
                {"nombre": "T. elevado", "tipo": "elevado", "tipo_constructivo": "elevado",
                 "forma": "circular", "cantidad": 2,
                 "dim": "Ø 7.48 m", "volumen": "110", "volumen_real": "112.4",
                 "altura": "2.50"}],
    "sistemas": [{
        "nombre": "Captación→T.Bajo", "tipo_bomba": "sumergible", "horas": "10",
        "qb": "5.14", "hd": "74.35", "eficiencia": 0.734,
        "potencia_kw": "5.10", "potencia_hp": "6.84",
        "tramos": [{"nombre": "Impulsión", "L": "284.8", "D_mm": "79.5",
                    "material": "PEAD", "V": "1.04", "hf": "3.756", "hl": "0.798"}],
        "bombas": [{"nombre": "Bomba A", "q_op": "5.30", "h_op": "74.50",
                    "eta_op": "0.490", "bep_q": "7.80", "desv_bep": "-32.1",
                    "p_hp": "6.90", "arreglo": "nominal",
                    "h_eq": "$H = -0.2817Q^2 +1.1244Q +32.094$",
                    "e_eq": "$\\eta = -0.008639Q^2 +0.11837Q -0.0554$"}],
        "bomba_seleccionada": "Bomba A", "fig": ""}],
    "figuras": {},   # sin archivos en el test — los \BLOCK{if} deben omitir las figuras
    "logo_cliente": None, "logo_consultor": None,
    "referencias": [{"cita": "Resolución 0330 de 2017, MVCT."},
                    {"cita": "Decreto 1575 de 2007."}],
    "red": None,
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
    assert "proyectista" in tex.lower()                     # aviso de revisión profesional
    assert "Recomendaciones y limitaciones" in tex
    assert "Resolución 0330 de 2017, MVCT." in tex          # referencias
    assert "listoffigures" in tex and "listoftables" in tex
    assert "semienterrado" in tex and "112.4" in tex        # tipo constructivo + V real
    assert "Arreglo" in tex                                  # columna de arreglo por bomba


def test_render_tex_con_red(tmp_path):
    ctx_con_red = dict(CTX)
    ctx_con_red["red"] = {
        "n_nodos": 2, "n_tuberias": 2,
        "demandas": [{"nodo": "J1", "q": "15.000"}, {"nodo": "J2", "q": "10.000"}],
        "optimizacion": {"material": "PEAD PE100", "serie": "RDE 21", "avisos": [],
                         "tuberias": [{"id": "P1", "dn0": "50", "dn1": "63"}]},
    }
    out = report.render(ctx_con_red, tmp_path)
    tex = (out / "main.tex").read_text(encoding="utf-8")
    assert "Red de distribución" in tex and "J1" in tex and "63" in tex


def test_render_crea_zip(tmp_path):
    out = report.render(CTX, tmp_path)
    z = report.make_zip(out)
    assert z.exists() and z.suffix == ".zip"


def _hay_motor_latex():
    return bool(shutil.which("tectonic") or shutil.which("pdflatex")
                or shutil.which("latexmk"))


def test_compilacion_detecta_latex(tmp_path):
    out = report.render(CTX, tmp_path)
    pdf, log = report.compile_pdf(out)
    if _hay_motor_latex():
        assert pdf is not None and pdf.exists()
        assert log                                     # log siempre disponible
    else:
        assert pdf is None and "PATH" in log


def test_compilacion_fallida_da_log(tmp_path):
    if not _hay_motor_latex():
        return
    (tmp_path / "main.tex").write_text(r"\documentclass{article}\begin{document}"
                                       r"\errmessage{fallo}\end{document}",
                                       encoding="utf-8")
    pdf, log = report.compile_pdf(tmp_path)
    assert log                       # hay diagnóstico aunque falle o no genere PDF
    assert "[motor:" in log          # el log identifica el motor usado (no '(sin log)')


def test_compilacion_sin_motor_da_mensaje(tmp_path, monkeypatch):
    """Sin ningún motor en el PATH el log explica qué falta (no queda vacío)."""
    monkeypatch.setattr(report.shutil, "which", lambda _name: None)
    pdf, log = report.compile_pdf(tmp_path)
    assert pdf is None
    assert "PATH" in log and "tectonic" in log


def test_compilacion_captura_stderr(tmp_path, monkeypatch):
    """Un motor que falla escribiendo SOLO a stderr (y sin crear main.log) debe
    reflejarse en el log — regresión del bug '(sin log)' que ignoraba stderr."""
    monkeypatch.setattr(report.shutil, "which",
                        lambda name: "/fake/latexmk" if name == "latexmk" else None)

    class _Res:
        returncode = 1
        stdout = b""
        stderr = b"Can't locate Perl module ... latexmk aborting"

    monkeypatch.setattr(report.subprocess, "run", lambda *a, **k: _Res())
    pdf, log = report.compile_pdf(tmp_path)
    assert pdf is None
    assert "Perl" in log and "STDERR" in log

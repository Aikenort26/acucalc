import shutil
from core import report

CTX = {
    "nombre": "El Salado", "municipio": "El Carmen de Bolívar",
    "departamento": "Bolívar", "corregimiento": "El Salado",
    "consultor": "Aiken Ortega", "fecha": "2026-07-10",
    "altitud": 150, "temperatura": 20.0,
    "pob_metodo": "Res. 0844 de 2018", "pob_justificacion": "Retorno poblacional",
    "pob_final": 1601.8, "horizonte": 2051, "censo": [(2018, 50848), (2042, 58864)],
    "pob_tipo": "corregimiento/vereda",
    "pob_fuente": ("proyecciones oficiales DANE — El Carmen de Bolívar (Bolívar), "
                   "área Cabecera Municipal, serie 2018–2042"),
    "year0": 2026,
    "dneta": 80.0, "dneta_modo": "usos", "dneta_justificacion": "",
    "dbruta": 88.89, "perdidas": 10.0, "k1": 1.3, "k2": 1.6,
    "qmed": 1.648, "qmd": 2.142, "qmh": 3.428,
    "componentes": [("Captación subterránea", 2.142), ("Red de distribución", 3.428)],
    "v_art81": 75, "v_curva": 110, "v_final": 110,
    "qb": 5.142, "hd": 74.24, "potencia_kw": 5.10, "potencia_hp": 6.84,
    "eficiencia": 0.734, "horas_bombeo": 10,
    "tramos": [{"nombre": "Impulsión", "L": 284.8, "D_mm": 79.5,
                "material": "PEAD", "hf": 3.64, "hl": 0.80, "V": 1.04}],
    "bomba_seleccionada": "Bomba A", "bombas": [
        {"nombre": "Bomba A", "q_op": 5.3, "h_op": 74.5, "eta_op": 0.49,
         "bep_q": 7.8, "desv_bep": -32.1, "p_hp": 6.9}],
    "figuras": {},   # nombre -> ruta relativa; vacío en test
}


def test_render_tex(tmp_path):
    out = report.render(CTX, tmp_path)
    tex = (out / "main.tex").read_text(encoding="utf-8")
    assert "El Salado" in tex
    assert "Resolución 0330" in tex
    assert "\\VAR{" not in tex and "\\BLOCK{" not in tex   # sin variables sin resolver
    assert "2.142" in tex          # QMD
    assert "Bomba A" in tex
    assert "proyecciones oficiales DANE" in tex   # fuente censal en el reporte


def test_render_crea_zip(tmp_path):
    out = report.render(CTX, tmp_path)
    z = report.make_zip(out)
    assert z.exists() and z.suffix == ".zip"


def test_compilacion_detecta_latex(tmp_path):
    out = report.render(CTX, tmp_path)
    if shutil.which("pdflatex") or shutil.which("latexmk"):
        pdf = report.compile_pdf(out)
        assert pdf is not None and pdf.exists()
    else:
        assert report.compile_pdf(out) is None

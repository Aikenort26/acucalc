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
    "tanques_balance": [
        {"nombre": "T. bajo", "horas_suministro": "24", "horas_salida": "10",
         "frac": "0.0417", "v_asignado": "30", "v_req": "8.9", "cumple": "Sí"},
        {"nombre": "T. elevado", "horas_suministro": "10", "horas_salida": "24",
         "frac": "0.5167", "v_asignado": "110", "v_req": "110.0", "cumple": "Sí"}],
    "v_art81": 75, "v_curva": 110, "v_gobierna": "Curva integral",
    "v_asignado_total": "140", "v_final": 140,
    "riesgo_nivel": "Medio", "riesgo_pct": "20",
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
        "ariete": [{"nombre": "Impulsión", "c": "215.90", "dh": "22.83",
                    "h_total": "97.18", "pn": "82", "fs": "0.84", "uso": "118.5",
                    "margen": "-18.5", "cumple": "No"}],
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
    assert "Volumen total por norma" in tex                 # flujo norma-first
    assert "balance interno" in tex                         # verificación por tanque
    assert "Curva integral" in tex                          # criterio gobernante
    assert "flotante" in tex.lower()                        # población flotante
    assert "includegraphics" not in tex                     # sin figuras si figuras={}
    assert "proyectista" in tex.lower()                     # aviso de revisión profesional
    assert "Recomendaciones y limitaciones" in tex
    assert "Resolución 0330 de 2017, MVCT." in tex          # referencias
    assert "listoffigures" in tex and "listoftables" in tex
    assert "Medio" in tex and "20\\%" in tex                # nivel de riesgo incendio (WP-2b)
    assert "factor de seguridad" in tex.lower()             # golpe de ariete FS (WP-2c)
    assert "215.90" in tex                                  # celeridad del tramo
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


def test_demandas_van_en_longtable_de_3_columnas(tmp_path):
    """La tabla de demandas tiene una fila por nodo (cientos en una red real).
    Como `tabular` dentro de `table[H]` no se partía entre páginas y LaTeX la
    desbordaba ("Float too large"). Debe ser `longtable` (se parte, repite
    encabezado) y agruparse de a 3 nodos por fila."""
    ctx_con_red = dict(CTX)
    ctx_con_red["red"] = {
        "n_nodos": 7, "n_tuberias": 6,
        "demandas": [{"nodo": f"N{i}", "q": f"{i}.00"} for i in range(7)],
        "optimizacion": None,
    }
    tex = (report.render(ctx_con_red, tmp_path) / "main.tex").read_text(encoding="utf-8")
    assert r"\begin{longtable}" in tex
    assert r"\endhead" in tex                    # encabezado repetido por página
    assert r"\begin{table}[H]" not in tex.split("Demandas asignadas")[1][:200]
    # 7 nodos agrupados de a 3 → 3 filas (la última con un solo nodo)
    cuerpo = tex.split(r"\endlastfoot")[1].split(r"\end{longtable}")[0]
    assert cuerpo.count(r"\\") == 3
    for i in range(7):                            # ningún nodo se pierde al agrupar
        assert f"N{i}" in cuerpo


def test_seccion_red_explica_la_longitud_aferente(tmp_path):
    """El informe debe explicar CÓMO se reparte el caudal, no solo volcar la
    tabla: es lo que el lector necesita para entender qué se hizo."""
    ctx_con_red = dict(CTX)
    ctx_con_red["red"] = {"n_nodos": 1, "n_tuberias": 1,
                          "demandas": [{"nodo": "N1", "q": "1.00"}],
                          "optimizacion": None}
    tex = (report.render(ctx_con_red, tmp_path) / "main.tex").read_text(encoding="utf-8")
    assert r"L_i \;=\; \frac{1}{2} \sum_{j \in \Omega_i} L_{ij}" in tex
    assert "longitud aferente" in tex


def test_referencias_llevan_label_y_url_va_en_url_macro(tmp_path):
    """Las referencias necesitan \\label para que el texto las cite con \\ref.
    La URL va en \\url{} aparte: dentro del texto corrido no parte y se salía
    del margen (medido: 154 pt de Overfull)."""
    ctx = dict(CTX)
    ctx["referencias"] = [
        {"key": "res0330", "cita": "Resolución 0330 de 2017, MVCT."},
        {"key": "dane", "cita": "DANE. Proyecciones de población.",
         "url": "https://www.dane.gov.co/index.php/estadisticas-por-tema"},
    ]
    tex = (report.render(ctx, tmp_path) / "main.tex").read_text(encoding="utf-8")
    assert r"\label{ref:res0330}" in tex
    assert r"\label{ref:dane}" in tex
    assert r"\url{https://www.dane.gov.co/index.php/estadisticas-por-tema}" in tex
    # sin `url`, no debe emitirse un \url{} vacío
    assert r"\url{}" not in tex


def test_patron_horario_se_documenta_en_el_informe(tmp_path):
    """El patrón gobierna el volumen del tanque; si no se documenta, el lector
    no puede reproducir el cálculo."""
    ctx = dict(CTX)
    ctx["patron_horas"] = [{"hora": f"{h:02d}", "factor": "1.00", "suministro": "sí"}
                           for h in range(24)]
    ctx["patron_pico"], ctx["patron_valle"], ctx["patron_suma"] = "1.60", "0.60", "24.00"
    tex = (report.render(ctx, tmp_path) / "main.tex").read_text(encoding="utf-8")
    assert "Patrón horario de consumo adoptado" in tex
    assert r"\label{tab:patron}" in tex
    assert "1.60" in tex and "24.00" in tex


def test_sin_patron_no_aparece_la_seccion(tmp_path):
    """CTX base no trae patron_horas: la sección no debe emitirse vacía."""
    tex = (report.render(dict(CTX), tmp_path) / "main.tex").read_text(encoding="utf-8")
    assert "Patrón horario de consumo adoptado" not in tex


def test_indices_en_paginas_separadas(tmp_path):
    tex = (report.render(dict(CTX), tmp_path) / "main.tex").read_text(encoding="utf-8")
    orden = tex.split(r"\tableofcontents")[1].split(r"\section{")[0]
    assert orden.count(r"\clearpage") == 3      # tras TOC, tras LOF y tras LOT
    assert orden.index(r"\listoffigures") < orden.index(r"\listoftables")


def test_render_tex_sin_anexos_curvas_omite_seccion(tmp_path):
    """CTX no trae 'anexos_curvas' (ctx.get / Undefined jinja) — la sección
    de anexo de curvas no debe aparecer."""
    out = report.render(CTX, tmp_path)
    tex = (out / "main.tex").read_text(encoding="utf-8")
    assert "Anexo: curvas de bombas" not in tex


def test_render_tex_con_anexos_curvas(tmp_path):
    ctx_con_curvas = dict(CTX)
    ctx_con_curvas["anexos_curvas"] = [
        {"sistema": "Captación→T.Bajo", "bomba": "Bomba A", "fig": "curva_0_0.png"}]
    out = report.render(ctx_con_curvas, tmp_path)
    tex = (out / "main.tex").read_text(encoding="utf-8")
    assert "Anexo: curvas de bombas" in tex
    assert "curva_0_0.png" in tex
    assert "Bomba A" in tex


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
    """Sin ningún motor (ni PATH ni tectonic.exe local) el log explica qué falta."""
    monkeypatch.setattr(report.shutil, "which", lambda _name: None)
    monkeypatch.setattr(report, "_APP_DIR", tmp_path)   # carpeta sin tectonic.exe
    pdf, log = report.compile_pdf(tmp_path)
    assert pdf is None
    assert "Tectonic" in log


def test_find_engine_prefiere_tectonic_local(tmp_path, monkeypatch):
    """Un tectonic.exe soltado en la carpeta de la app gana al PATH."""
    (tmp_path / "tectonic.exe").write_bytes(b"stub")
    monkeypatch.setattr(report, "_APP_DIR", tmp_path)
    monkeypatch.setattr(report.shutil, "which",
                        lambda name: "/usr/bin/pdflatex" if name == "pdflatex" else None)
    name, exe = report._find_engine()
    assert name == "tectonic" and exe == str(tmp_path / "tectonic.exe")


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


def test_engine_cmd_enable_installer_solo_en_miktex(monkeypatch):
    """`--enable-installer` es una opción de MiKTeX (auto-instala paquetes que
    falten). TeX Live (lo que trae Streamlit Cloud/Linux) no la reconoce y
    pdflatex aborta con 'Unrecognized option' — la compilación entera se
    rompería en producción aunque funcionara en el MiKTeX local del usuario.
    La flag debe depender del motor detectado, no ir siempre."""
    monkeypatch.setattr(report.subprocess, "run",
                        lambda *a, **k: type("R", (), {"returncode": 0,
                                            "stdout": b"MiKTeX-pdfTeX 4.27 (MiKTeX 26.5)",
                                            "stderr": b""})())
    cmd, runs = report._engine_cmd("pdflatex", "pdflatex")
    assert "--enable-installer" in cmd
    assert runs == 2

    monkeypatch.setattr(report.subprocess, "run",
                        lambda *a, **k: type("R", (), {"returncode": 0,
                                            "stdout": b"pdfTeX 3.141592653-2.6-1.40.25 (TeX Live 2023)",
                                            "stderr": b""})())
    cmd, runs = report._engine_cmd("pdflatex", "pdflatex")
    assert "--enable-installer" not in cmd
    assert runs == 2


def test_engine_cmd_pdflatex_sin_poder_consultar_version_no_revienta(monkeypatch):
    """Si `pdflatex --version` falla por lo que sea (permisos, timeout), no debe
    tumbar la compilación entera — se asume TeX Live (opción más segura, la
    flag de más se omite en vez de arriesgar un motor desconocido)."""
    def _boom(*a, **k):
        raise FileNotFoundError("no se pudo consultar la versión")
    monkeypatch.setattr(report.subprocess, "run", _boom)
    cmd, runs = report._engine_cmd("pdflatex", "pdflatex")
    assert "--enable-installer" not in cmd
    assert runs == 2

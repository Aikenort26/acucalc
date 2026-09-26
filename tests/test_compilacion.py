"""Compilación real de una memoria con todas las secciones activas: el log no
debe tener errores, secuencias indefinidas, citas o referencias sin definir
ni cajas que se salgan del margen. Se omite si no hay motor LaTeX."""
import base64
import io
import re

import pytest
from PIL import Image

from core import project as pj, report, report_ctx, study_map as sm

INP = """[JUNCTIONS]
J1 60 0.5
J2 58 0.5
J3 57 0.5

[RESERVOIRS]
R1 110

[PIPES]
P1 R1 J1 300 150 130
P2 J1 J2 200 100 130
P3 J2 J3 150 100 130
P4 J1 J3 250 100 130

[COORDINATES]
R1 4999700 2000000
J1 5000000 2000000
J2 5000150 2000100
J3 5000100 1999850

[OPTIONS]
Units LPS
Headloss H-W

[END]
"""


def _png(color=(120, 160, 120), lado=256):
    buf = io.BytesIO()
    Image.new("RGB", (lado, lado), color).save(buf, "PNG")
    return buf.getvalue()


def _proyecto_completo(tmp_path) -> pj.Project:
    p = pj.Project(nombre="Acueducto de prueba", municipio="San Jacinto",
                   departamento="Bolívar", consultor="Consultor & Cía.", fecha="2026-09-26",
                   altitud=200, temperatura=27.0)
    p.censo = [(2018, 2000), (2020, 2100), (2022, 2200)]
    p.poblacion.p0, p.poblacion.year0, p.poblacion.horizon_year = 2200.0, 2022, 2047
    p.poblacion.metodo = "geometrico"
    p.demanda.dneta = 120.0
    alm = p.almacenamiento
    alm.tanques = [pj.TankSpec("Tanque elevado", "elevado", "circular", 150, 3.0,
                               entrada_ini=5, entrada_fin=14, tipo_constructivo="elevado",
                               borde_libre=0.3)]
    s = pj.PumpSystemData(nombre="Pozo → Tanque", horas=12, he=35.0, eficiencia=0.7,
                          tipo_bomba="superficie", z_succion=3.0, npsh_r=4.0, margen_npsh=0.5)
    s.tramos = [pj.SegmentData("Succión", "succion", 6.0, 102.2, "PVC"),
                pj.SegmentData("Impulsión", "impulsion", 1200.0, 79.5, "PEAD", e_mm=5.3)]
    s.accesorios = [pj.AccessoryData("Entrada boca acampanada", 1, "Succión"),
                    pj.AccessoryData("Válvula de cheque", 1, "Impulsión"),
                    pj.AccessoryData("Válvula de compuerta", 1, "Impulsión"),
                    pj.AccessoryData("Salida", 1, "Impulsión")]
    s.bombas = [pj.PumpData("B-1", puntos_qh=[(0, 70), (5, 62), (10, 45)])]
    s.bomba_seleccionada = "B-1"
    p.bombeos = [s]
    tc = p.transitorios
    tc.perfil = [(0.0, 100.0, None), (500.0, 118.0, None), (1200.0, 133.0, None)]
    tc.cobertura = 1.0
    tc.tramos = [pj.TramoTransitorio(1200.0, "PEAD PE100", "RDE 21", 90)]
    tc.escenario, tc.bomba = "hidroneumatico", "Pozo → Tanque · B-1"
    tc.h_arriba, tc.h_abajo, tc.v_aire = 97.0, 136.0, 0.3
    p.red_inp = INP
    ub = p.ubicacion
    ub.lat, ub.lon, ub.zoom_general, ub.zoom_zona, ub.epsg_red = 4.0, -73.0, 9, 16, 9377
    ub.mapas = sm.componer_mapas(ub, fetch=lambda url: _png(), cache_dir=tmp_path / "t")
    p.zanja = pj.ZanjaConfig(d_ext_mm=90.0, ancho_fondo=0.5, profundidad=1.2, talud=0.2,
                             cama=0.1, atraque=0.3, mat_cama="Arena",
                             nota="dimensiones de prueba")
    e = pj.EstudioPrevio(id="s1", tipo="suelos",
                         texto="Arcillas CL al 50% & limos [@res0330].\n\nSegundo párrafo.")
    e.tablas = [pj.TablaEstudio("Sondeos", "Sondeo,Prof. [m]\nS-1,1.5\nS-2,3.0\n")]
    e.figuras = [pj.FiguraEstudio("Perfil", base64.b64encode(_png(lado=300)).decode(), "Lab")]
    p.estudios = [e]
    return p


def _motor():
    return report._find_engine()[1]


@pytest.mark.skipif(_motor() is None, reason="sin motor LaTeX en el equipo")
def test_memoria_completa_compila_limpia(tmp_path):
    ctx, _ = report_ctx.build(_proyecto_completo(tmp_path))
    for clave in ("localizacion", "estudios", "transitorio", "red", "detalles"):
        assert ctx[clave], clave
    # las secciones se calcularon de verdad (no como error documentado)
    assert ctx["transitorio"]["error"] is None and ctx["red"]["estatico"]
    assert ctx["localizacion"]["con_red"] and ctx["sistemas"][0]["npsh"]
    out = report.render(ctx, tmp_path / "memoria")
    pdf, cola = report.compile_pdf(out)
    assert pdf is not None and pdf.exists(), cola
    log = (out / "main.log").read_text(encoding="latin-1")
    problemas = {
        "error": re.findall(r"^! .*", log, flags=re.M),
        "indefinida": re.findall(r"Undefined control sequence", log),
        "cita": re.findall(r"Citation .* undefined", log),
        "referencia": re.findall(r"Reference .* undefined", log),
        "overfull": re.findall(r"Overfull \\hbox.*", log),
    }
    assert not any(problemas.values()), problemas

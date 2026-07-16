"""Convención de decimales (WP-2a) — incluye el comportamiento real de
redondeo del formato de Python, que es lo que ve el usuario en pantalla y en
el reporte."""
import math

from core import formato as fm


def test_decimales_por_magnitud():
    # 2 decimales: caudales, alturas, potencias, pérdidas, velocidades, diámetros
    assert fm.fmt_q(5.141621) == "5.14"
    assert fm.fmt_h(69.8) == "69.80"
    assert fm.fmt_p(12.3456) == "12.35"
    assert fm.fmt_v(1.036) == "1.04"
    assert fm.fmt_d(79.5) == "79.50"
    assert fm.fmt_perdida(0.0123) == "0.01"
    assert fm.fmt_vol(123.456) == "123.46"


def test_coeficiente_de_friccion_cinco_decimales():
    assert fm.fmt_coef(0.0123456) == "0.01235"
    assert fm.fmt_coef(0.02) == "0.02000"


def test_fmt_num_generico():
    assert fm.fmt_num(1.23456, 0) == "1"
    assert fm.fmt_num(1.23456, 3) == "1.235"


def test_none_y_nan_devuelven_marcador():
    # `f"{nan:.2f}"` da "nan": sin esta guarda se colaría al reporte LaTeX.
    assert fm.fmt_q(None) == fm.NA
    assert fm.fmt_q(float("nan")) == fm.NA
    assert fm.fmt_h(float("inf")) == fm.NA
    assert fm.fmt_p("no es un número") == fm.NA
    assert fm.fmt_q(None, na="—/—") == "—/—"


def test_acepta_enteros_y_strings_numericos():
    assert fm.fmt_q(5) == "5.00"
    assert fm.fmt_h("69.8") == "69.80"


def test_redondeo_correcto_hacia_arriba_y_hacia_abajo():
    assert fm.fmt_q(1.234) == "1.23"
    assert fm.fmt_q(1.236) == "1.24"
    assert fm.fmt_h(-1.236) == "-1.24"


def test_redondeo_es_al_par_sobre_el_valor_binario_real():
    """Documenta el redondeo real de Python (no es half-up).

    Python redondea al par más cercano sobre el valor *binario* del float, no
    sobre el decimal escrito en el código. Se fija aquí para que nadie
    "arregle" un supuesto bug de ±0.01 en la última cifra: es el mismo
    criterio de `round()` y de `DataFrame.style.format`, así que pantalla y
    reporte siempre coinciden.
    """
    # 0.125 y 0.375 SÍ son exactos en binario → empate → gana el vecino par.
    assert fm.fmt_q(0.125) == "0.12"      # 2 es par
    assert fm.fmt_q(0.375) == "0.38"      # 8 es par
    # Estos NO son empates reales: su valor binario cae de un lado del medio.
    assert fm.fmt_q(0.135) == "0.14"      # 0.135 ≈ 0.13500000000000000888 (>)
    assert fm.fmt_q(2.675) == "2.67"      # 2.675 ≈ 2.67499999999999982   (<)
    assert fm.fmt_q(1.005) == "1.00"      # 1.005 ≈ 1.00499999999999989   (<)


def test_formatear_no_altera_el_valor():
    """El helper solo produce texto: nunca debe redondear el dato de cálculo."""
    q = 5.141621
    assert fm.fmt_q(q) == "5.14"
    assert q == 5.141621


def test_spec_para_pandas():
    assert fm.spec(2) == "{:.2f}"
    assert fm.spec(fm.DEC_COEF) == "{:.5f}"
    assert fm.SP_VELOCIDAD == "{:.2f}" and fm.SP_COEF == "{:.5f}"
    # el spec de pandas y el fmt_* deben coincidir cifra por cifra
    assert fm.SP_CAUDAL.format(5.141621) == fm.fmt_q(5.141621)


def test_pages_common_reexporta_los_mismos_helpers():
    """La UI debe usar exactamente los helpers de core/formato (una sola
    fuente de verdad); si `pages_common` los redefiniera, pantalla y reporte
    volverían a poder discrepar."""
    import pages_common as pc
    assert pc.fmt_q is fm.fmt_q and pc.fmt_h is fm.fmt_h
    assert pc.fmt_p is fm.fmt_p and pc.fmt_v is fm.fmt_v
    assert pc.fmt_d is fm.fmt_d and pc.fmt_perdida is fm.fmt_perdida
    assert pc.fmt_coef is fm.fmt_coef and pc.fmt_vol is fm.fmt_vol


def test_report_ctx_usa_los_mismos_helpers():
    """El reporte importa de core/formato, no de pages_common (capas)."""
    from core import report_ctx
    assert report_ctx.fm is fm


def test_constantes_de_la_regla():
    dos_decimales = (fm.DEC_CAUDAL, fm.DEC_ALTURA, fm.DEC_POTENCIA,
                     fm.DEC_PERDIDA, fm.DEC_VELOCIDAD, fm.DEC_DIAMETRO,
                     fm.DEC_VOLUMEN)
    assert all(d == 2 for d in dos_decimales)
    assert fm.DEC_COEF == 5

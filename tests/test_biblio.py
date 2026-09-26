import json
from pathlib import Path

import pytest

from core import biblio

BIB = r"""
@book{wylie1993,
  author = {Wylie, E. Benjamin and Streeter, Victor L. and Suo, Lisheng},
  title = {Fluid Transients in Systems},
  publisher = {Prentice Hall}, address = {Englewood Cliffs, NJ}, year = {1993}}
@article{perez2020,
  author = {P{\'e}rez-G{\'o}mez, Jos{\'e} Mar{\'\i}a and {de la Cruz}, Ana},
  title = {Golpe de ariete en l{\'\i}neas de 100\% PVC \& PEAD},
  journal = {Revista de Hidr{\'a}ulica}, volume = {12}, number = {3},
  pages = {45--60}, year = {2020}, doi = {10.1234/rh.2020.3}}
@misc{res0330x,
  author = {{Ministerio de Vivienda, Ciudad y Territorio}},
  title = {Resoluci{\'o}n 0330 de 2017}, year = {2017},
  url = {https://www.minvivienda.gov.co/}}
"""


def _por_clave(refs):
    return {r.key: r for r in refs}


def test_parse_bibtex_campos_y_acentos():
    refs, errores = biblio.parse_bibtex(BIB)
    assert not errores
    r = _por_clave(refs)
    assert r["wylie1993"].tipo == "book"
    assert r["wylie1993"].autor == "Wylie, E. B., Streeter, V. L. y Suo, L."
    assert r["wylie1993"].editorial == "Prentice Hall"
    assert r["wylie1993"].lugar == "Englewood Cliffs, NJ"
    a = r["perez2020"]
    assert a.autor == "Pérez-Gómez, J. M. y de la Cruz, A."
    assert a.titulo == "Golpe de ariete en líneas de 100% PVC & PEAD"
    assert a.revista == "Revista de Hidráulica" and a.paginas == "45–60"
    assert a.doi == "10.1234/rh.2020.3"


def test_autor_institucional_no_se_parte_por_la_coma():
    r = _por_clave(biblio.parse_bibtex(BIB)[0])
    assert r["res0330x"].autor == "Ministerio de Vivienda, Ciudad y Territorio"


def test_clave_invalida_se_reporta_y_no_se_importa():
    refs, errores = biblio.parse_bibtex("@misc{mala clave, title={x}, year=2020}\n"
                                        "@misc{buena, title={y}, year=2021}")
    assert [r.key for r in refs] == ["buena"]
    assert errores and "mala clave" in errores[0]


def test_formatear_libro_escapa_y_enfatiza_titulo():
    r = _por_clave(biblio.parse_bibtex(BIB)[0])
    t = biblio.formatear(r["wylie1993"])
    assert t == (r"Wylie, E. B., Streeter, V. L. y Suo, L. (1993). "
                 r"\emph{Fluid Transients in Systems}. Englewood Cliffs, NJ: Prentice Hall.")


def test_formatear_articulo_escapa_caracteres_especiales():
    r = _por_clave(biblio.parse_bibtex(BIB)[0])
    t = biblio.formatear(r["perez2020"])
    assert r"100\% PVC \& PEAD" in t
    assert r"\emph{Revista de Hidráulica}, 12(3), 45--60" in t
    assert "doi" not in t.lower()          # el DOI va por url_de(), en \url{}


def test_url_de_prioriza_url_y_si_no_doi():
    r = _por_clave(biblio.parse_bibtex(BIB)[0])
    assert biblio.url_de(r["res0330x"]) == "https://www.minvivienda.gov.co/"
    assert biblio.url_de(r["perez2020"]) == "https://doi.org/10.1234/rh.2020.3"
    assert biblio.url_de(r["wylie1993"]) == ""


def test_citas_convierte_marcas_y_reporta_faltantes():
    latex, faltan = biblio.citas("Según [@wylie1993] y [@a; @b], el 5% & más [@nope].",
                                 {"wylie1993", "a", "b"})
    assert latex == r"Según \cite{wylie1993} y \cite{a,b}, el 5\% \& más [@nope]."
    assert faltan == ["nope"]


def test_citas_sin_marcas_solo_escapa():
    assert biblio.citas("50% de_1", set()) == (r"50\% de\_1", [])


def test_biblioteca_base_claves_unicas_y_campos_minimos():
    refs = biblio.biblioteca_base()
    claves = [r.key for r in refs]
    assert len(claves) == len(set(claves))
    assert {"res0330", "res0844", "dec1575", "nsr10j", "t740", "cra750", "dane",
            "wylie1993", "chaudhry2014", "allievi1925", "joukowsky1904",
            "rossman2020", "kyriakou2023", "iapws2012", "iso2533"} <= set(claves)
    for r in refs:
        assert r.key and r.titulo and r.anio, r.key
        assert biblio.CLAVE_RE.match(r.key)


def test_dane_conserva_titulo_oficial_y_url():
    dane = {r.key: r for r in biblio.biblioteca_base()}["dane"]
    assert ("Proyecciones y retroproyecciones de población municipal para el periodo "
            "1985-2017 y 2018-2042 con base en el CNPV 2018") in dane.titulo
    assert dane.url.startswith("https://www.dane.gov.co/")


def test_bibitems_latex():
    refs = biblio.parse_bibtex(BIB)[0]
    items = biblio.bibitems(refs)
    assert [i["key"] for i in items] == ["wylie1993", "perez2020", "res0330x"]
    assert items[2]["url"] == "https://www.minvivienda.gov.co/"
    assert items[0]["texto"].startswith("Wylie")

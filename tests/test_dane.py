import pytest
from core import dane
from tests.test_population import CENSO


def test_serie_golden_el_carmen():
    s = dane.series("Bolívar", "El Carmen de Bolívar", "Cabecera Municipal")
    assert s == CENSO   # misma serie usada en la memoria DIS-ACU-SALADO


def test_catalogos_navegacion():
    dptos = dane.departamentos()
    assert "Bolívar" in dptos and "Antioquia" in dptos
    mpios = dane.municipios("Bolívar")
    assert "El Carmen de Bolívar" in mpios and "San Jacinto" in mpios
    assert set(dane.areas()) == {"Cabecera Municipal",
                                 "Centros Poblados y Rural Disperso", "Total"}


def test_meta():
    m = dane.meta()
    assert m["anos"] == [2018, 2042]
    assert m["municipios"] > 1100


def test_update_from_file_csv(tmp_path, monkeypatch):
    # dataset sintético mínimo con el mismo encabezado DANE
    f = tmp_path / "dane_nuevo.csv"
    f.write_text(
        "basura,,,,,,\n"
        "DP,DPNOM,DPMP,MPIO,AÑO,ÁREA GEOGRÁFICA,Población\n"
        "13,Bolívar,13001,Cartagena,2018,Total,1000000\n"
        "13,Bolívar,13001,Cartagena,2019,Total,1010000\n",
        encoding="utf-8")
    monkeypatch.setattr(dane, "CSV", tmp_path / "dane.csv.gz")
    monkeypatch.setattr(dane, "META", tmp_path / "dane_meta.json")
    dane._cache.clear()
    m = dane.update_from_file(f)
    assert m["filas"] == 2 and m["anos"] == [2018, 2019]
    assert dane.series("Bolívar", "Cartagena", "Total") == [(2018, 1000000), (2019, 1010000)]
    dane._cache.clear()


def test_update_from_file_invalido(tmp_path, monkeypatch):
    f = tmp_path / "malo.csv"
    f.write_text("a,b,c\n1,2,3\n", encoding="utf-8")
    monkeypatch.setattr(dane, "CSV", tmp_path / "dane.csv.gz")
    monkeypatch.setattr(dane, "META", tmp_path / "dane_meta.json")
    with pytest.raises(ValueError):
        dane.update_from_file(f)
    dane._cache.clear()

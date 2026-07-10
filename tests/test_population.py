import pytest
from core import population as pop

# Censo DANE El Carmen de Bolívar (cabecera), hoja CAUDALES DIS-ACU-SALADO
CENSO = [(2018, 50848), (2019, 52021), (2020, 53339), (2021, 54152), (2022, 54718),
         (2023, 55270), (2024, 55843), (2025, 56338), (2026, 56746), (2027, 57109),
         (2028, 57433), (2029, 57720), (2030, 57968), (2031, 58209), (2032, 58402),
         (2033, 58556), (2034, 58677), (2035, 58786), (2036, 58859), (2037, 58919),
         (2038, 58938), (2039, 58941), (2040, 58947), (2041, 58923), (2042, 58864)]


def test_tasas_promedio_golden():
    r = pop.growth_rates(CENSO)
    assert abs(r.aritmetica - 0.001805) < 2e-5
    assert abs(r.geometrica - 0.001737) < 2e-5
    assert abs(r.exponencial - 0.006100) < 2e-5
    assert abs(r.wappaus - 0.001732) < 2e-5


def test_tasas_fila_2018():
    rows = pop.growth_rate_rows(CENSO)
    r0 = rows[0]
    assert abs(r0.aritmetica - 0.006569) < 2e-5
    assert abs(r0.geometrica - 0.006118) < 2e-5
    assert abs(r0.exponencial - 0.022807) < 2e-5
    assert abs(r0.wappaus - 0.006089) < 2e-5


def test_censo_insuficiente():
    with pytest.raises(ValueError):
        pop.growth_rates([(2020, 1000)])


def test_proyeccion_golden_salado():
    # El Excel de El Salado calcula "Aritmético" con una tasa que decae año a
    # año (se aplana cerca de 2051, igual que el censo fuente) en vez de una
    # tasa constante — no se replica esa recursión por simplicidad; ACUCALC
    # usa el método aritmético estándar P = P0*(1+k*tau) con k = tasa
    # promedio, por eso el valor final difiere del Excel (1464.576) mientras
    # que geométrico/exponencial/Wappaus/Res.0844 sí coinciden.
    r = pop.growth_rates(CENSO)
    proj = pop.project(p0=1400, year0=2024, horizon_year=2051, rates=r, tasa_res0844=0.005)
    fin = proj.series  # dict método -> list[(año, hab)]
    assert abs(fin["aritmetico"][-1][1] - 1468.239) < 0.05
    assert abs(fin["geometrico"][-1][1] - 1467.153) < 0.05
    assert abs(fin["exponencial"][-1][1] - 1650.634) < 0.05
    assert abs(fin["wappaus"][-1][1] - 1467.033) < 0.05
    assert abs(fin["res0844"][-1][1] - 1601.813) < 0.05


def test_proyeccion_wappaus_2025():
    r = pop.growth_rates(CENSO)
    proj = pop.project(1400, 2024, 2051, r, 0.005)
    assert abs(proj.series["wappaus"][1][1] - 1402.427) < 0.05


def test_desviaciones():
    # Desviaciones recalculadas contra el modelo aritmético lineal (ver nota
    # en test_proyeccion_golden_salado); difieren de los valores crudos del
    # Excel (res0844: 0.04591, exponencial: 0.07413) por la misma razón.
    r = pop.growth_rates(CENSO)
    proj = pop.project(1400, 2024, 2051, r, 0.005)
    dev = proj.deviations
    assert abs(dev["res0844"] - 0.04627) < 1e-3
    assert abs(dev["exponencial"] - 0.07816) < 1e-3

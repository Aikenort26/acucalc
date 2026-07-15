import numpy as np
import pytest
from core import curves as cv


def test_calibracion_lineal():
    cal = cv.AxisCalibration(px1=100, val1=0.0, px2=500, val2=40.0, log=False)
    assert abs(cal.to_data(100) - 0.0) < 1e-9
    assert abs(cal.to_data(300) - 20.0) < 1e-9
    assert abs(cal.to_data(500) - 40.0) < 1e-9


def test_calibracion_log():
    cal = cv.AxisCalibration(px1=0, val1=1.0, px2=300, val2=1000.0, log=True)
    assert abs(cal.to_data(100) - 10.0) < 1e-6
    assert abs(cal.to_data(200) - 100.0) < 1e-4


def test_calibracion_invalida():
    with pytest.raises(ValueError):
        cv.AxisCalibration(px1=100, val1=0, px2=100, val2=40, log=False)
    with pytest.raises(ValueError):
        cv.AxisCalibration(px1=0, val1=-1, px2=10, val2=10, log=True)


def test_pixel_a_datos():
    calx = cv.AxisCalibration(0, 0.0, 600, 12.0, False)      # Q L/s
    caly = cv.AxisCalibration(400, 0.0, 0, 40.0, False)      # H m (y invertida)
    q, h = cv.pixel_to_data((300, 100), calx, caly)
    assert abs(q - 6.0) < 1e-9
    assert abs(h - 30.0) < 1e-9


PUMP_QH = [(2.914167, 33.21), (4.041833, 31.90), (5.113333, 30.16), (6.467, 27.54),
           (7.454667, 24.93), (8.837667, 20.46), (9.883, 15.67), (10.306833, 13.49)]
PUMP_QE = [(2.914167, 0.256596), (4.041833, 0.341851), (5.113333, 0.408886),
           (6.467, 0.472209), (7.454667, 0.49274), (8.837667, 0.479414),
           (9.883, 0.410606), (10.306833, 0.368642)]


def test_ajuste_qh():
    fit = cv.fit_curve(PUMP_QH, degree=2)
    assert fit.r2 > 0.99
    assert abs(fit(5.113333) - 30.16) < 0.6      # pasa cerca de los puntos
    assert fit(0.0) > fit(fit.q_max)              # H decrece con Q (curva típica de bomba)
    assert fit(0.0) > 0.0


def test_bep():
    bep = cv.best_efficiency_point(PUMP_QE, degree=2)
    assert 7.3 < bep.q < 8.6
    assert 0.47 < bep.e < 0.52


def test_punto_de_operacion():
    fit = cv.fit_curve(PUMP_QH, degree=2)
    # sistema sintético: H = 20 + 0.12·Q² (Q en L/s)
    sistema = [(q / 10, 20 + 0.12 * (q / 10) ** 2) for q in range(0, 120)]
    op = cv.operating_point(fit, sistema)
    assert op is not None
    q_op, h_op = op
    assert abs(h_op - (20 + 0.12 * q_op**2)) < 0.05
    assert abs(fit(q_op) - h_op) < 0.05
    assert 6.5 < q_op < 7.5


def test_punto_de_operacion_sin_cruce():
    fit = cv.fit_curve(PUMP_QH, degree=2)
    sistema = [(q / 10, 69.8 + 0.2 * (q / 10) ** 2) for q in range(0, 120)]
    assert cv.operating_point(fit, sistema) is None


def test_fit_pocos_puntos():
    with pytest.raises(ValueError):
        cv.fit_curve([(1, 1), (2, 2)], degree=2)


def _synthetic_curve_image():
    """Imagen 400x600 blanca con parábola roja y rejilla gris."""
    img = np.full((400, 600, 3), 255, dtype=np.uint8)
    for x in range(0, 600, 50):
        img[:, x] = (200, 200, 200)
    for y in range(0, 400, 50):
        img[y, :] = (200, 200, 200)
    for px in range(50, 550):
        py = int(50 + 300 * ((px - 50) / 500) ** 2)
        img[max(py - 2, 0):py + 3, px] = (255, 0, 0)   # RGB rojo
    return img


def test_deteccion_color():
    img = _synthetic_curve_image()
    pts = cv.detect_curve_by_color(img, target_rgb=(255, 0, 0), tolerance=60, n_points=20)
    assert 15 <= len(pts) <= 20
    # los puntos siguen la parábola: y crece con x
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    assert xs == sorted(xs)
    assert ys[-1] > ys[0] + 200


def test_deteccion_sin_match():
    img = np.full((100, 100, 3), 255, dtype=np.uint8)
    assert cv.detect_curve_by_color(img, (255, 0, 0), 40, 10) == []


def test_scale_points_afinidad():
    # Q∝N, H∝N² — r = N2/N1 = 2
    assert cv.scale_points([(10.0, 50.0), (20.0, 40.0)], 2.0) == [(20.0, 200.0), (40.0, 160.0)]


def test_combine_parallel_mismo_h_suma_q():
    assert cv.combine_parallel([(10.0, 50.0), (20.0, 40.0)], 3) == \
        [(30.0, 50.0), (60.0, 40.0)]


def test_combine_series_mismo_q_suma_h():
    assert cv.combine_series([(10.0, 50.0), (20.0, 40.0)], 2) == \
        [(10.0, 100.0), (20.0, 80.0)]


def test_combine_n_invalido():
    with pytest.raises(ValueError):
        cv.combine_parallel([(10.0, 50.0)], 0)


_QH = [(10.0, 50.0), (20.0, 40.0)]
_QE = [(10.0, 0.5), (20.0, 0.4)]


def test_apply_pump_transform_no_op_por_defecto():
    # n1_nominal=0, n2_objetivo=0, n_unidades=1 -> sin transformación
    qh, qe = cv.apply_pump_transform(_QH, _QE, 0.0, 0.0, 1, "paralelo")
    assert qh == _QH and qe == _QE


def test_apply_pump_transform_solo_afinidad():
    # r = N2/N1 = 2: Q*r, H*r² ; eficiencia solo se desplaza en Q
    qh, qe = cv.apply_pump_transform(_QH, _QE, 1750.0, 3500.0, 1, "paralelo")
    assert qh == cv.scale_points(_QH, 2.0)
    assert qe == [(20.0, 0.5), (40.0, 0.4)]


def test_apply_pump_transform_solo_arreglo_paralelo():
    qh, qe = cv.apply_pump_transform(_QH, _QE, 0.0, 0.0, 3, "paralelo")
    assert qh == cv.combine_parallel(_QH, 3)
    assert qe == [(30.0, 0.5), (60.0, 0.4)]      # Q de eficiencia también ×n en paralelo


def test_apply_pump_transform_solo_arreglo_serie():
    qh, qe = cv.apply_pump_transform(_QH, _QE, 0.0, 0.0, 2, "serie")
    assert qh == cv.combine_series(_QH, 2)
    assert qe == _QE                              # en serie Q de eficiencia no se multiplica


def test_apply_pump_transform_afinidad_y_arreglo_combinados():
    # primero afinidad (r=2), luego arreglo paralelo ×3
    qh, qe = cv.apply_pump_transform(_QH, _QE, 1750.0, 3500.0, 3, "paralelo")
    esperado_qh = cv.combine_parallel(cv.scale_points(_QH, 2.0), 3)
    assert qh == esperado_qh
    assert qe == [(60.0, 0.5), (120.0, 0.4)]


def test_apply_pump_transform_n2_igual_a_n1_no_aplica_afinidad():
    qh, qe = cv.apply_pump_transform(_QH, _QE, 3500.0, 3500.0, 1, "paralelo")
    assert qh == _QH and qe == _QE

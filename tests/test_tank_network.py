import pytest

from core import storage
from core import tank_network as tn
from core.project import TankSpec

PATRON = list(storage.DEFAULT_PATTERN)
QMD = 2.14234                       # L/s (golden El Salado)
QMD_M3D = QMD * 86.4


def test_ventana_con_cruce_de_medianoche():
    assert tn.ventana(22, 2) == tuple(1 if h >= 22 or h <= 2 else 0 for h in range(24))
    assert sum(tn.ventana(5, 14)) == 10


def test_equivale_a_la_verificacion_por_tanque():
    t = TankSpec("Tanque elevado", "elevado", "circular", 110, 2.5, 1.0,
                 entrada_ini=5, entrada_fin=14, salida_ini=6, salida_fin=22)
    tanques, zonas, enlaces = tn.desde_tankspecs([t])
    r = tn.resolver(tanques, zonas, enlaces, QMD, PATRON, frac_incendio=0.15, dias_reserva=1)
    b = r.tanque("Tanque elevado")
    ref = storage.tank_balance_check("Tanque elevado", QMD_M3D, t.entrada_flags(),
                                     t.salida_flags(), 110, 0.15, 1)
    assert b.v_req == pytest.approx(ref.v_balance_req, rel=1e-9)
    assert b.cumple == ref.cumple and b.cierra


def test_dos_tanques_en_serie():
    tanques = [tn.Tanque("Bajo", 200), tn.Tanque("Elevado", 200)]
    zonas = [tn.Zona("Pueblo", 1.0)]
    enlaces = [tn.Enlace("Pozo", "Bajo", "bombeo", tn.ventana(5, 14)),
               tn.Enlace("Bajo", "Elevado", "bombeo", tn.ventana(0, 23)),
               tn.Enlace("Elevado", "Pueblo", "gravedad")]
    r = tn.resolver(tanques, zonas, enlaces, QMD, PATRON, 0.0, 1)
    # Bajo: entra en 10 h lo que sale de forma continua en 24 h
    esperado, _ = storage.balance_curve([w / 10 for w in tn.ventana(5, 14)], [1 / 24] * 24)
    assert r.tanque("Bajo").v_reg == pytest.approx(esperado * QMD_M3D, rel=1e-9)
    # Elevado: entra continuo, sale con el patrón horario
    esp2, _ = storage.balance_curve([1 / 24] * 24, [f / sum(PATRON) for f in PATRON])
    assert r.tanque("Elevado").v_reg == pytest.approx(esp2 * QMD_M3D, rel=1e-9)
    assert r.caudal("Bajo", "Elevado") == pytest.approx(QMD, rel=1e-9)
    assert r.caudal("Pozo", "Bajo") == pytest.approx(QMD * 24 / 10, rel=1e-9)


def test_dos_tanques_en_paralelo_mitad_de_volumen():
    uno = tn.resolver([tn.Tanque("T", 500)], [tn.Zona("Z", 1.0)],
                      [tn.Enlace("F", "T", "bombeo", tn.ventana(6, 17)),
                       tn.Enlace("T", "Z", "gravedad")], QMD, PATRON, 0.15, 1)
    dos = tn.resolver([tn.Tanque("A", 250), tn.Tanque("B", 250)],
                      [tn.Zona("ZA", 0.5), tn.Zona("ZB", 0.5)],
                      [tn.Enlace("F", "A", "bombeo", tn.ventana(6, 17)),
                       tn.Enlace("F", "B", "bombeo", tn.ventana(6, 17)),
                       tn.Enlace("A", "ZA", "gravedad"), tn.Enlace("B", "ZB", "gravedad")],
                      QMD, PATRON, 0.15, 1)
    v1 = uno.tanque("T").v_req
    assert dos.tanque("A").v_req == pytest.approx(v1 / 2, rel=1e-9)
    assert dos.tanque("B").v_req == pytest.approx(v1 / 2, rel=1e-9)


def test_caudal_explicito_no_se_reescala_y_se_reporta_el_desbalance():
    r = tn.resolver([tn.Tanque("T", 100)], [tn.Zona("Z", 1.0)],
                    [tn.Enlace("F", "T", "bombeo", tn.ventana(0, 9), caudal_lps=4.0),
                     tn.Enlace("T", "Z", "gravedad")], QMD, PATRON, 0.0, 1)
    b = r.tanque("T")
    assert r.caudal("F", "T") == 4.0
    assert b.cierre_diario_m3 == pytest.approx(4.0 * 3.6 * 10 - QMD_M3D, rel=1e-9)
    assert not b.cierra and any("no cierra" in a for a in r.avisos)


def test_dos_entradas_auto_al_mismo_tanque_es_error():
    with pytest.raises(ValueError, match="auto"):
        tn.resolver([tn.Tanque("T", 100)], [tn.Zona("Z", 1.0)],
                    [tn.Enlace("F1", "T", "bombeo", tn.ventana(0, 9)),
                     tn.Enlace("F2", "T", "bombeo", tn.ventana(10, 19)),
                     tn.Enlace("T", "Z", "gravedad")], QMD, PATRON, 0.0, 1)


def test_ciclo_es_error():
    with pytest.raises(ValueError, match="ciclo"):
        tn.resolver([tn.Tanque("A", 1), tn.Tanque("B", 1)], [tn.Zona("Z", 1.0)],
                    [tn.Enlace("A", "B", "bombeo", tn.ventana(0, 23)),
                     tn.Enlace("B", "A", "bombeo", tn.ventana(0, 23)),
                     tn.Enlace("B", "Z", "gravedad")], QMD, PATRON, 0.0, 1)


def test_niveles_y_sugerido():
    r = tn.resolver([tn.Tanque("T", 5)], [tn.Zona("Z", 1.0)],
                    [tn.Enlace("F", "T", "bombeo", tn.ventana(5, 14)),
                     tn.Enlace("T", "Z", "gravedad")], QMD, PATRON, 0.15, 1)
    b = r.tanque("T")
    assert len(b.volumen_h) == 25 and min(b.volumen_h) == pytest.approx(0.0, abs=1e-9)
    assert max(b.volumen_h) == pytest.approx(b.v_reg, rel=1e-9)
    assert b.v_sugerido >= b.v_req and b.v_sugerido % 5 == 0
    assert not b.cumple and b.horas_rebose            # 5 m³ asignados no alcanzan


def test_config_inicial_encadena_tanques_y_resuelve():
    from core.project import StorageConfig
    alm = StorageConfig(tanques=[TankSpec("Bajo", "bajo", "circular", 300, 3, entrada_ini=5,
                                          entrada_fin=14),
                                 TankSpec("Elevado", "elevado", "circular", 150, 3,
                                          entrada_ini=0, entrada_fin=23)])
    alm.zonas, alm.enlaces = tn.config_inicial(alm)
    assert [(e.origen, e.destino) for e in alm.enlaces] == [
        ("Captación", "Bajo"), ("Bajo", "Elevado"), ("Elevado", "Población")]
    r = tn.resolver(*tn.desde_config(alm), QMD, PATRON, 0.15, 1)
    assert all(b.cierra for b in r.tanques)

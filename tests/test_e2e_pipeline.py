"""Pipeline de integración El Salado: proyecto completo → report_ctx.build
(mismo código que usa la página 7) → render LaTeX. Cubre el flujo end-to-end
sin Streamlit. Usa report_ctx.build directamente (no reconstruye el contexto
a mano) para no desincronizarse cuando el contexto cambia."""
from core import dane, demand, population as pop, pumping as pu
from core import report, report_ctx
from core import project as pj

FACTORES = [0.6,0.7,0.8,0.9,1,1.2,1.6,1.2,1,1.1,1.1,1.2,1.1,1.1,1,1.1,1.2,1.1,0.9,0.9,0.9,0.8,0.8,0.7]
BOMBEO = [1 if 5 <= h <= 14 else 0 for h in range(24)]
PUMP_QH = [(2.914167, 33.21), (4.041833, 31.90), (5.113333, 30.16), (6.467, 27.54),
           (7.454667, 24.93), (8.837667, 20.46), (9.883, 15.67), (10.306833, 13.49)]


def _proyecto_salado() -> pj.Project:
    p = pj.Project(nombre="El Salado", municipio="El Carmen de Bolívar",
                   departamento="Bolívar", corregimiento="El Salado",
                   consultor="Test", fecha="2026-07-10", altitud=150, temperatura=20.0)
    p.censo = dane.series("Bolívar", "El Carmen de Bolívar", "Cabecera Municipal")
    p.poblacion = pj.PopulationConfig(
        p0=1400, year0=2024, horizon_year=2051, tasa_res0844=0.005,
        metodo="res0844", tipo="corregimiento", fuente="dane",
        dpto="Bolívar", mpio="El Carmen de Bolívar", area="Cabecera Municipal")
    p.demanda = pj.DemandConfig(modo="usos", dneta=80.0, perdidas=0.10, k1=1.3, k2=1.6)
    p.almacenamiento.factores_hora = FACTORES
    p.almacenamiento.suministro_hora = BOMBEO
    p.almacenamiento.ventana_captacion = [1] * 24
    p.almacenamiento.tanques = [
        pj.TankSpec("Tanque elevado", "elevado", "circular", 110, 2.5, 1.0,
                   entrada_ini=5, entrada_fin=14, tipo_constructivo="elevado",
                   salida_ini=6, salida_fin=22),
    ]
    sistema = pj.PumpSystemData(nombre="Pozo→T.Elevado", horas=10, he=69.8,
                                eficiencia=0.73413, tipo_bomba="sumergible")
    sistema.tramos = [pj.SegmentData("Impulsión", "impulsion", 284.8, 79.5, "PEAD",
                                     e_mm=5.3)]
    sistema.bombas = [pj.PumpData(nombre="Bomba catálogo", puntos_qh=PUMP_QH)]
    sistema.bomba_seleccionada = "Bomba catálogo"
    p.bombeos = [sistema]
    return p


def test_pipeline_completo(tmp_path):
    p = _proyecto_salado()
    cfg = p.poblacion

    # golden memoria: población y caudales
    rates = pop.growth_rates(p.censo)
    proj = pop.project(cfg.p0, cfg.year0, cfg.horizon_year, rates, cfg.tasa_res0844)
    pob_final = proj.series[cfg.metodo][-1][1]
    assert abs(pob_final - 1601.813) < 0.05
    flows = demand.flows(pob_final, p.demanda.dneta, p.demanda.perdidas,
                         p.demanda.k1, p.demanda.k2)
    assert abs(flows.qmd_lps - 2.14234) < 1e-3

    # bombeo: esta bomba (H<35 m) no alcanza la Hd≈74 m del sistema — sin cruce
    s = p.bombeos[0]
    qb = pu.q_bombeo(flows.qmd_lps, s.horas)
    sistema = pu.PumpSystem(
        tramos=[pu.Segment(t.nombre, t.tipo, t.L, t.D_mm / 1000, t.material)
                for t in s.tramos],
        accesorios=[], he=s.he, temperatura=p.temperatura, eficiencia=s.eficiencia)
    r = pu.solve(sistema, qb / 1000)
    assert 70 < r.hd < 80

    # contexto del reporte: mismo pipeline que usa la página 7 y los scripts demo
    ctx, figuras = report_ctx.build(p)
    # El reporte formatea los caudales con la convención de 2 decimales
    # (WP-2a, core/formato.fmt_q): "2.14". La tolerancia refleja esa precisión.
    assert abs(float(ctx["qmd"]) - 2.14234) < 5e-3
    # flujo norma-first: v_final = max(art81 QMD/3, curva integral) = 110 (golden)
    assert ctx["v_final"] == 110 and ctx["v_curva"] == 110 and ctx["v_gobierna"] == "Curva integral"
    assert ctx["tanques_balance"] and ctx["tanques_balance"][0]["v_asignado"] == "110"
    assert len(figuras) == 6   # poblacion, metodos, caudales, balance, esquema, sistema_1

    out = report.render(ctx, tmp_path / "memoria")
    tex = (out / "main.tex").read_text(encoding="utf-8")
    assert "\\VAR{" not in tex and "\\BLOCK{" not in tex
    # el nombre trae una flecha unicode fragil; report_ctx.build() debe
    # escaparla a la forma LaTeX robusta (ver latex_escape en report_ctx.py)
    assert "Pozo$\\to$T.Elevado" in tex
    assert "Pozo→T.Elevado" not in tex
    assert (out / "figures" / "poblacion.png").exists()
    assert (out / "figures" / "esquema.png").exists()
    z = report.make_zip(out)
    assert z.exists()

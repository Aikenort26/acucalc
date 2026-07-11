"""Pipeline de integración El Salado: proyecto completo → recomputo (como la
página 7) → figuras → render LaTeX. Cubre el flujo end-to-end sin Streamlit."""
from core import curves as cvs, dane, demand, population as pop, pumping as pu
from core import report, report_figs as rf, storage
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
    sistema = pj.PumpSystemData(nombre="Pozo→T.Elevado", horas=10, he=69.8,
                                eficiencia=0.73413, tipo_bomba="sumergible")
    sistema.tramos = [pj.SegmentData("Impulsión", "impulsion", 284.8, 79.5, "PEAD",
                                     e_mm=5.3)]
    sistema.bombas = [pj.PumpData(nombre="Bomba catálogo", puntos_qh=PUMP_QH)]
    p.bombeos = [sistema]
    return p


def test_pipeline_completo(tmp_path):
    p = _proyecto_salado()
    cfg = p.poblacion

    # población (golden memoria)
    rates = pop.growth_rates(p.censo)
    proj = pop.project(cfg.p0, cfg.year0, cfg.horizon_year, rates, cfg.tasa_res0844)
    serie = proj.series[cfg.metodo]
    pob_final = serie[-1][1]
    assert abs(pob_final - 1601.813) < 0.05

    # caudales (golden memoria)
    flows = demand.flows(pob_final, p.demanda.dneta, p.demanda.perdidas,
                         p.demanda.k1, p.demanda.k2)
    assert abs(flows.qmd_lps - 2.14234) < 1e-3
    serie_q = demand.flows_series(serie, p.demanda.dneta, p.demanda.perdidas,
                                  p.demanda.k1, p.demanda.k2)
    assert len(serie_q) == len(serie)

    # almacenamiento en cadena (elevado golden 110 m³)
    chain = storage.tank_chain(flows.qmd_lps * 86.4, FACTORES, [1] * 24, BOMBEO,
                               0.15, 1)
    assert chain.elevado.v_total_redondeado == 110

    # bombeo + punto de operación de la bomba digitalizada
    s = p.bombeos[0]
    qb = pu.q_bombeo(flows.qmd_lps, s.horas)
    sistema = pu.PumpSystem(
        tramos=[pu.Segment(t.nombre, t.tipo, t.L, t.D_mm / 1000, t.material)
                for t in s.tramos],
        accesorios=[], he=s.he, temperatura=p.temperatura, eficiencia=s.eficiencia)
    r = pu.solve(sistema, qb / 1000)
    assert 70 < r.hd < 80
    sys_lps = [(q * 1000, h) for q, h in pu.system_curve(sistema, qb * 1.5 / 1000, 30)]
    fit = cvs.fit_curve(s.bombas[0].puntos_qh, 2)
    # esta bomba (H<35 m) no alcanza la Hd≈74 m del sistema — sin cruce
    assert cvs.operating_point(fit, sys_lps) is None

    # figuras + render (sin depender de sesión)
    figdir = tmp_path / "figs"
    figdir.mkdir()
    figs = {}
    for name, fig in [
            ("poblacion", rf.fig_poblacion(proj, cfg.metodo)),
            ("metodos", rf.fig_metodos(proj.deviations, pop.suggest_method(proj))),
            ("caudales", rf.fig_caudales([(t, fr.qmed_lps, fr.qmd_lps, fr.qmh_lps)
                                          for t, fr in serie_q])),
            ("balance", rf.fig_balance([1] * 24, BOMBEO, FACTORES)),
            ("esquema", rf.fig_esquema("sumergible", True))]:
        fp = figdir / f"{name}.png"
        fig.savefig(fp, dpi=100)
        figs[name] = str(fp)

    ctx = {
        "nombre": p.nombre, "municipio": p.municipio, "departamento": p.departamento,
        "corregimiento": p.corregimiento, "consultor": p.consultor, "fecha": p.fecha,
        "altitud": p.altitud, "temperatura": p.temperatura,
        "pob_metodo": cfg.metodo, "pob_justificacion": "", "pob_final": f"{pob_final:,.0f}",
        "horizonte": cfg.horizon_year, "pob_tipo": "corregimiento/vereda",
        "pob_fuente": "proyecciones oficiales DANE", "year0": cfg.year0,
        "flotante_pct": "", "dneta": "80", "dneta_modo": "usos",
        "dneta_justificacion": "", "dbruta": f"{flows.dbruta:.1f}", "perdidas": "10",
        "k1": flows.k1, "k2": flows.k2, "qmed": f"{flows.qmed_lps:.3f}",
        "qmd": f"{flows.qmd_lps:.3f}", "qmh": f"{flows.qmh_lps:.3f}",
        "componentes": [(k, f"{v:.3f}") for k, v in
                        demand.design_flows_by_component(flows).items()],
        "caudales_anuales": [], "usar_cadena": True,
        "v_bajo": chain.bajo.v_total_redondeado,
        "v_elevado": chain.elevado.v_total_redondeado,
        "v_art81": "—", "v_curva": "—", "v_final": chain.total_redondeado,
        "tanques": [], "sistemas": [{
            "nombre": s.nombre, "tipo_bomba": s.tipo_bomba, "horas": "10",
            "qb": f"{qb:.2f}", "hd": f"{r.hd:.2f}", "eficiencia": s.eficiencia,
            "potencia_kw": f"{r.potencia_kw:.2f}", "potencia_hp": f"{r.potencia_hp:.2f}",
            "tramos": [], "bombas": [], "bomba_seleccionada": "—", "fig": ""}],
        "figuras": figs,
    }
    out = report.render(ctx, tmp_path / "memoria")
    tex = (out / "main.tex").read_text(encoding="utf-8")
    assert "\\VAR{" not in tex and "\\BLOCK{" not in tex
    assert "Pozo→T.Elevado" in tex
    assert (out / "figures" / "poblacion.png").exists()
    assert (out / "figures" / "esquema.png").exists()
    z = report.make_zip(out)
    assert z.exists()

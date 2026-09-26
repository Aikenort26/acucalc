"""Construye el contexto del reporte recalculando TODO desde el proyecto.

Mismo pipeline que usa la página 7 de la app: población → caudales →
almacenamiento → sistemas de bombeo → figuras. Reproducible desde el JSON
del proyecto, sin Streamlit ni session_state."""
import base64
import tempfile
from pathlib import Path

import matplotlib.pyplot as plt

from core import biblio, curves as cvs, demand, network, pipeline, pipes, population as pop, pumping as pu
from core import formato as fm, network_map as nm, report_figs as rf, storage
from core.latex import latex_escape
from core.project import Project

LOGO_ACUCALC = Path(__file__).resolve().parent.parent / "assets" / "acucalc_logo.png"

# Autor de la aplicación ACUCALC (distinto del `consultor` del proyecto, que es
# quien firma cada memoria). Va a la sección "Acerca de ACUCALC" del informe.
AUTOR_APP = "Aiken H. Ortega-Heredia"

# Un patrón horario de consumo (y su ventana de suministro) debe traer las 24
# horas del día: `core/storage.volume_curva_integral` lo exige y las figuras lo
# asumen.
HORAS_DIA = 24

def referencias(p: Project) -> list[biblio.Ref]:
    """Biblioteca base + BibTeX del usuario; una clave del usuario igual a una
    de la base la reemplaza (permite corregir una entrada base)."""
    propias = biblio.parse_bibtex(p.bibtex_usuario)[0] if p.bibtex_usuario.strip() else []
    claves = {r.key for r in propias}
    return [r for r in biblio.biblioteca_base() if r.key not in claves] + propias


def build(p: Project) -> tuple[dict, dict]:
    """Devuelve (ctx para la plantilla LaTeX, dict figuras nombre→ruta png).

    Requiere: nombre, censo (≥2), población base y método seleccionados."""
    cfg = p.poblacion
    diseno = pipeline.design_flows(p) if p.nombre else None
    if diseno is None:
        raise ValueError("Faltan datos mínimos: nombre, censo, población base, "
                         "método y dotación neta")

    # ---------- población y caudales ----------
    proj, serie_total = diseno.proj, diseno.serie_total
    pob_final, flows = diseno.pob_final, diseno.flows
    serie_q = demand.flows_series(serie_total, p.demanda.dneta, p.demanda.perdidas,
                                  p.demanda.k1, p.demanda.k2)
    comp = demand.design_flows_by_component(flows)
    qmd_m3d = flows.qmd_lps * 86.4

    # ---------- almacenamiento ----------
    # Flujo norma-first: volumen total = max(Art.81 QMD/3, curva integral de la
    # comunidad). Los tanques los define el usuario (volumen asignado + ventanas);
    # la app verifica el balance interno de cada uno, no reparte.
    alm = p.almacenamiento
    a = storage.volume_art81(qmd_m3d, alm.frac_regulacion, alm.frac_incendio,
                             alm.dias_reserva)

    # Un patrón horario solo es utilizable si trae las 24 horas: `storage` lo
    # exige y las figuras lo asumen. Se valida UNA vez y "patrón inválido" pasa
    # a ser equivalente a "sin patrón" en todo el reporte — volumen, figura y
    # tabla. Antes solo se atrapaba el ValueError del volumen, y un patrón de
    # otra longitud (un JSON viejo o editado a mano) reventaba más adelante en
    # `fig_balance_train` con un error de matplotlib incomprensible
    # ("x and y must have same first dimension").
    patron_ok = len(alm.factores_hora) == HORAS_DIA
    suministro_ok = len(alm.suministro_hora) == HORAS_DIA

    b = None
    if patron_ok and suministro_ok:
        try:
            b = storage.volume_curva_integral(qmd_m3d, alm.factores_hora,
                                              alm.suministro_hora, alm.frac_incendio,
                                              alm.dias_reserva)
        except ValueError:
            b = None
    v_final = storage.final_volume(a, b) if b else a.v_total_redondeado
    gobierna = ("Art. 81 (QMD/3)" if not b or a.v_total_redondeado >= b.v_total_redondeado
                else "Curva integral")

    # ---------- patrón horario de consumo (documentación en el informe) ----------
    patron_horas: list = []
    patron_pico = patron_valle = patron_suma = None
    if patron_ok:
        patron_horas = [
            {"hora": f"{h:02d}",
             "factor": f"{f:.2f}",
             # 1/0 de la ventana de suministro de la comunidad, si está definida
             "suministro": ("sí" if alm.suministro_hora[h] else "no")
                           if suministro_ok else "—"}
            for h, f in enumerate(alm.factores_hora)]
        patron_pico = f"{max(alm.factores_hora):.2f}"
        patron_valle = f"{min(alm.factores_hora):.2f}"
        # La media de los 24 factores debe rondar 1.0 (= QMD), así que su suma
        # ronda 24; se reporta para que el lector verifique la normalización.
        patron_suma = f"{sum(alm.factores_hora):.2f}"

    # verificación de balance interno por tanque (suministro=entrada, salida=salida)
    tanques_balance = []
    for t in alm.tanques:
        try:
            chk = storage.tank_balance_check(t.nombre, qmd_m3d, t.entrada_flags(),
                                             t.salida_flags(), t.volumen,
                                             alm.frac_incendio, alm.dias_reserva)
        except ValueError:
            continue
        tanques_balance.append({
            "nombre": latex_escape(chk.nombre),
            "horas_suministro": f"{chk.horas_suministro:.0f}",
            "horas_salida": f"{chk.horas_salida:.0f}",
            "frac": f"{chk.frac_balance:.4f}",
            "v_asignado": f"{chk.v_asignado:.0f}",
            "v_req": fm.fmt_vol(chk.v_balance_req),
            "cumple": "Sí" if chk.cumple else "No"})
    v_asignado_total = sum(t.volumen for t in alm.tanques)

    # ---------- figuras ----------
    figdir = Path(tempfile.mkdtemp())
    figuras: dict[str, str] = {}

    def _save(fig, name):
        fp = figdir / f"{name}.png"
        fig.savefig(fp, dpi=150, bbox_inches="tight")
        plt.close(fig)
        figuras[name] = str(fp)

    _save(rf.fig_poblacion(proj, cfg.metodo, cfg.flotante_pct), "poblacion")
    _save(rf.fig_metodos(proj.deviations, pop.suggest_method(proj)), "metodos")
    _save(rf.fig_caudales([(t, fr.qmed_lps, fr.qmd_lps, fr.qmh_lps)
                           for t, fr in serie_q]), "caudales")
    # Mismo guard de 24 horas que el volumen y la tabla del patrón: la figura
    # grafica los factores contra un eje de 24 horas y con otra longitud
    # reventaba el build entero.
    if patron_ok and suministro_ok:
        _save(rf.fig_balance_train([("Comunidad", alm.suministro_hora, alm.factores_hora)]),
              "balance")
    sistemas_bomba_ctx = ([{"tipo_bomba": s.tipo_bomba} for s in p.bombeos]
                         or [{"tipo_bomba": "superficie"}])
    _save(rf.fig_esquema(sistemas_bomba_ctx, alm.tanques), "esquema")

    # ---------- imágenes b64 embebidas (logos, curvas de bomba) ----------
    def _save_b64_image(b64: str, name: str) -> str | None:
        if not b64:
            return None
        raw = base64.b64decode(b64)
        ext = "jpg" if raw[:3] == b"\xff\xd8\xff" else "png"
        fp = figdir / f"{name}.{ext}"
        fp.write_bytes(raw)
        figuras[name] = str(fp)
        return fp.name

    logo_cliente = _save_b64_image(p.logo_cliente_b64, "logo_cliente")
    figuras["acucalc_logo"] = str(LOGO_ACUCALC)
    logo_consultor = _save_b64_image(p.logo_consultor_b64, "logo_consultor")

    # ---------- sistemas de bombeo ----------
    sistemas_ctx = []
    for i, s in enumerate(p.bombeos):
        if not s.tramos:
            continue
        qb_lps = pu.q_bombeo(flows.qmd_lps, s.horas)
        he = s.he + (5.0 if s.sumar_5m_ras else 0.0)
        sistema = pu.PumpSystem(
            tramos=[pu.Segment(t.nombre, t.tipo, t.L, t.D_mm / 1000, t.material)
                    for t in s.tramos],
            accesorios=[pu.Accessory(a2.tipo, a2.cantidad, a2.tramo)
                        for a2 in s.accesorios],
            he=he, temperatura=p.temperatura, eficiencia=s.eficiencia)
        r = pu.solve(sistema, qb_lps / 1000)
        # ---------- golpe de ariete: FS por tramo (WP-2c) ----------
        # Usa Hd del sistema completo (criterio conservador, igual que la app).
        ariete_tab = []
        for t, tr in zip(s.tramos, r.tramos):
            if not t.e_mm:
                continue
            k_el, pn_t = pipes.k_elast_tramo(t)
            pn_t = pn_t or 0.0     # tramo manual: sin PN en el reporte (se evalúa en la app)
            ar = pu.ariete_tramo(t.nombre, t.D_mm / 1000, t.e_mm / 1000, k_el,
                                 tr.V, r.hd, pn_t)
            ariete_tab.append({
                "nombre": latex_escape(t.nombre), "c": fm.fmt_v(ar.c),
                "dh": fm.fmt_h(ar.dh), "h_total": fm.fmt_h(ar.h_total),
                "pn": f"{ar.pn:.0f}" if ar.pn else "—",
                "fs": fm.fmt_num(ar.fs, 2), "uso": fm.fmt_num(ar.uso_pct, 1),
                "margen": fm.fmt_num(ar.margen_pct, 1),
                "cumple": ("Sí" if ar.cumple else
                           ("No" if ar.cumple is False else "—"))})
        q_max_lps = max(qb_lps * 1.5, max((bb.puntos_qh[-1][0] for bb in s.bombas
                                           if len(bb.puntos_qh) >= 3), default=0.0))
        sys_lps = [(q * 1000, h) for q, h in
                   pu.system_curve(sistema, max(q_max_lps / 1000, 1e-4), n=30)]
        bombas_fig, bombas_tab = [], []
        for bb in s.bombas:
            if len(bb.puntos_qh) < 3:
                continue
            qh_t, qe_t = cvs.apply_pump_transform(
                bb.puntos_qh, bb.puntos_qe, bb.n1_nominal, bb.n2_objetivo,
                bb.n_unidades, bb.arreglo)
            fit = cvs.fit_curve(qh_t, 2)
            op = cvs.operating_point(fit, sys_lps)
            e_fit = cvs.fit_curve(qe_t, 2) if len(qe_t) >= 3 else None
            bep = cvs.best_efficiency_point(qe_t, 2) if e_fit else None
            eta = e_fit(op[0]) if (op and e_fit) else float("nan")
            pot = (998.29 * 9.81 * op[0] / 1000 * op[1] / eta / 745.7
                   if op and eta and eta > 0 else float("nan"))
            afinidad_activa = bb.n1_nominal > 0 and bb.n2_objetivo not in (0, bb.n1_nominal)
            partes_arr = []
            if bb.n_unidades > 1:
                partes_arr.append(f"{bb.n_unidades}$\\times${bb.arreglo}")
            if afinidad_activa:
                partes_arr.append(f"@ N$_2$={bb.n2_objetivo:.0f}")
            arreglo_txt = " ".join(partes_arr) if partes_arr else "nominal"
            bombas_fig.append({"nombre": bb.nombre, "fit": fit, "op": op, "e_fit": e_fit})
            A, B, C = fit.coeffs
            bombas_tab.append({
                "nombre": latex_escape(bb.nombre), "arreglo": arreglo_txt,
                "h_eq": f"$H = {A:+.4f}Q^2 {B:+.4f}Q {C:+.3f}$",
                "e_eq": (f"$\\eta = {e_fit.coeffs[0]:+.6f}Q^2 "
                         f"{e_fit.coeffs[1]:+.5f}Q {e_fit.coeffs[2]:+.4f}$"
                         if e_fit else "---"),
                "q_op": fm.fmt_q(op[0]) if op else "—",
                "h_op": fm.fmt_h(op[1]) if op else "—",
                "eta_op": f"{eta:.3f}" if eta == eta else "—",   # η: fracción 0-1, .3f a propósito
                "bep_q": fm.fmt_q(bep.q) if bep else "—",
                "desv_bep": f"{(op[0] - bep.q) / bep.q * 100:.1f}" if (op and bep) else "—",
                "p_hp": fm.fmt_p(pot) if pot == pot else "—"})
        npsh_ctx = None
        if s.tipo_bomba != "sumergible":
            n = pu.npsh_sistema(r, p.altitud, p.temperatura, s.z_succion, s.npsh_r,
                                s.margen_npsh)
            npsh_ctx = {
                "patm": fm.fmt_perdida(n.patm_m), "pv": fm.fmt_perdida(n.pv_m),
                "z": fm.fmt_perdida(n.z_succion), "perdidas": fm.fmt_perdida(n.perdidas_succion),
                "npsh_d": fm.fmt_h(n.npsh_d),
                "npsh_r": fm.fmt_h(n.npsh_r) if n.npsh_r else "—",
                "margen": fm.fmt_h(n.margen),
                "cumple": "—" if n.cumple is None else ("Sí" if n.cumple else "No")}
        fig_name = f"sistema_{i + 1}"
        _save(rf.fig_sistema(sys_lps, bombas_fig, qb_lps, r.hd, s.nombre), fig_name)
        sistemas_ctx.append({
            "nombre": latex_escape(s.nombre), "tipo_bomba": s.tipo_bomba,
            "horas": f"{s.horas:.0f}",
            "qb": fm.fmt_q(qb_lps), "hd": fm.fmt_h(r.hd), "eficiencia": s.eficiencia,
            "potencia_kw": fm.fmt_p(r.potencia_kw), "potencia_hp": fm.fmt_p(r.potencia_hp),
            "tramos": [{"nombre": latex_escape(t.segment.nombre), "L": fm.fmt_h(t.segment.L),
                        "D_mm": fm.fmt_d(t.segment.D * 1000),
                        "material": t.segment.material,
                        "V": fm.fmt_v(t.V), "hf": fm.fmt_perdida(t.hf),
                        "hl": fm.fmt_perdida(t.hl)}
                       for t in r.tramos],
            "bombas": bombas_tab,
            "ariete": ariete_tab,
            "npsh": npsh_ctx,
            "bomba_seleccionada": latex_escape(s.bomba_seleccionada or "—"),
            "fig": f"{fig_name}.png"})

    # ---------- anexo: curvas de bombas seleccionadas (imagen original del catálogo) ----------
    anexos_curvas = []
    for i, s in enumerate(p.bombeos):
        if not s.bomba_seleccionada:
            continue
        for j, bb in enumerate(s.bombas):
            if bb.nombre != s.bomba_seleccionada or not bb.imagen_b64:
                continue
            fig_curva = _save_b64_image(bb.imagen_b64, f"curva_{i}_{j}")
            if fig_curva:
                anexos_curvas.append({
                    "sistema": latex_escape(s.nombre),
                    "bomba": latex_escape(bb.nombre),
                    "fig": fig_curva})
            break

    # ---------- tanques ----------
    tanques_ctx = []
    for t in alm.tanques:
        v_unitario_obj = (t.volumen or 1.0) / max(t.cantidad, 1)
        ct = storage.dimensioned_tank(v_unitario_obj, t.altura, t.forma, t.ratio)
        dim = (f"Ø {fm.fmt_d(ct.diametro)} m" if ct.forma == "circular"
               else f"lado {fm.fmt_d(ct.lado)} m" if ct.forma == "cuadrado"
               else f"{fm.fmt_d(ct.ancho)} × {fm.fmt_d(ct.largo)} m")
        tanques_ctx.append({
            "nombre": latex_escape(t.nombre), "tipo": t.tipo,
            "tipo_constructivo": t.tipo_constructivo,
            "forma": t.forma, "cantidad": t.cantidad, "dim": dim,
            "altura": fm.fmt_h(ct.altura), "volumen": f"{t.volumen:.0f}",
            "volumen_real": fm.fmt_vol(ct.volumen_real * t.cantidad)})

    # ---------- red de distribución (opcional) ----------
    red_ctx = None
    if p.red_inp and p.red_en_informe:
        try:
            red = network.parse_inp(p.red_inp)
            demandas = network.assign_demands_by_length(red, flows.qmd_lps)
            for jid, q in demandas.items():
                red.junctions[jid].demand = q
            # El reparto conserva el QMD (Σ q_i = QMD); se reporta el total
            # asignado para que el lector lo verifique contra el QMD del informe.
            q_asignado = sum(demandas.values())
            red_ctx = {
                "n_nodos": len(red.junctions), "n_tuberias": len(red.pipes),
                # La plantilla la agrupa de a 3 por fila con el filtro `batch`
                # de Jinja y la imprime en un `longtable`: una fila por nodo
                # generaba una tabla de cientos de filas en una red real.
                "demandas": [{"nodo": latex_escape(jid), "q": fm.fmt_q(q)}
                             for jid, q in demandas.items()],
                "q_asignado": fm.fmt_q(q_asignado),
                "optimizacion": None,
                "fig": "red.png",
            }
            _save(nm.fig_red(red, dark=False), "red")
            # La optimización de diámetros (heurística iterativa, hasta 30
            # resoluciones densas del sistema) queda deliberadamente fuera del
            # reporte: para una red grande bloqueaba la generación del PDF sin
            # dar señal de progreso (el botón de la página 8 no llegaba a
            # aparecer). Se hace en la página 7 (Red), interactiva, con su
            # propio botón; el reporte solo documenta la red y la asignación
            # de demandas, que es O(nodos+tuberías) y siempre rápida.
        except ValueError:
            red_ctx = None

    # ---------- contexto ----------
    paso = max(1, len(serie_q) // 26)
    ctx = {
        "nombre": latex_escape(p.nombre), "municipio": latex_escape(p.municipio),
        "departamento": latex_escape(p.departamento),
        "corregimiento": latex_escape(p.corregimiento or p.municipio),
        "consultor": latex_escape(p.consultor), "fecha": latex_escape(p.fecha),
        "altitud": p.altitud, "temperatura": p.temperatura,
        "pob_metodo": cfg.metodo, "pob_justificacion": latex_escape(cfg.justificacion),
        "pob_final": f"{pob_final:,.0f}", "horizonte": cfg.horizon_year,
        "pob_tipo": ("cabecera municipal" if cfg.tipo == "municipio"
                     else "corregimiento/vereda"),
        "pob_fuente": (f"{latex_escape(cfg.mpio)} ({latex_escape(cfg.dpto)}), "
                       f"área {latex_escape(cfg.area)}, "
                       f"serie {p.censo[0][0]}–{p.censo[-1][0]}"
                       if cfg.fuente == "dane" else "censo ingresado manualmente"),
        # Distingue la fuente para que la plantilla cite el título oficial del
        # DANE (con su referencia cruzada) solo cuando la serie sea realmente
        # del DANE, y no cuando el censo se haya tecleado a mano.
        "pob_es_dane": cfg.fuente == "dane",
        "year0": cfg.year0,
        "flotante_pct": f"{cfg.flotante_pct * 100:.0f}" if cfg.flotante_pct else "",
        "dneta": f"{p.demanda.dneta:.0f}", "dneta_modo": p.demanda.modo,
        "dneta_justificacion": latex_escape(p.demanda.justificacion),
        "dbruta": f"{flows.dbruta:.1f}", "perdidas": f"{flows.perdidas * 100:.0f}",
        "k1": flows.k1, "k2": flows.k2,
        "qmed": fm.fmt_q(flows.qmed_lps), "qmd": fm.fmt_q(flows.qmd_lps),
        "qmh": fm.fmt_q(flows.qmh_lps),
        "componentes": [(k, fm.fmt_q(v)) for k, v in comp.items()],
        "caudales_anuales": [
            {"ano": t, "pob": f"{pob_t:,.0f}", "qmed": fm.fmt_q(fr.qmed_lps),
             "qmd": fm.fmt_q(fr.qmd_lps), "qmh": fm.fmt_q(fr.qmh_lps)}
            for (t, fr), (_, pob_t) in list(zip(serie_q, serie_total))[::paso]],
        "tanques_balance": tanques_balance,
        "v_art81": a.v_total_redondeado,
        "v_curva": b.v_total_redondeado if b else "—",
        "v_gobierna": gobierna,
        "v_asignado_total": f"{v_asignado_total:.0f}",
        "v_final": v_final,
        "riesgo_nivel": latex_escape((alm.nivel_riesgo or "personalizado").capitalize()),
        "riesgo_pct": f"{alm.frac_incendio * 100:.0f}",
        # Patrón horario de consumo y ventana de suministro: gobiernan el volumen
        # de regulación por curva integral y, más adelante, la demanda en
        # simulación de periodo extendido. Antes se usaban para calcular pero
        # nunca se documentaban, así que el lector no podía reproducir el
        # dimensionamiento del tanque.
        "patron_horas": patron_horas,
        "patron_pico": patron_pico,
        "patron_valle": patron_valle,
        "patron_suma": patron_suma,
        "tanques": tanques_ctx,
        "sistemas": sistemas_ctx,
        "figuras": figuras,
        "logo_cliente": logo_cliente,
        "logo_consultor": logo_consultor,
        "logo_acucalc": LOGO_ACUCALC.name,
        "referencias": biblio.bibitems(referencias(p)),
        # Autoría de la aplicación (no del proyecto: eso es `consultor`).
        "autor": AUTOR_APP,
        "red": red_ctx,
        "anexos_curvas": anexos_curvas,
    }
    return ctx, figuras

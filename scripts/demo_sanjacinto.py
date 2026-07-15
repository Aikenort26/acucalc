"""Prueba E2E: memoria completa para la cabecera municipal de San Jacinto.

Caso: captación en pozo (40 m de altura estática + 30 m horizontales) en PEAD
8", tanque semienterrado + elevado con bomba intermedia, todas las bombas a
10 h/día, dotación 110 L/hab/d, sin pérdidas ni K1/K2 (=1.0). Bomba candidata:
KSB WKL 125 Ø320 a 1750 rpm (curva digitalizada del catálogo).

Genera saves/Acueducto_San_Jacinto.acucalc.json (abrible en la app) y
output/memoria_sanjacinto.pdf.
"""
import base64
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import dane, pipes, population as pop, project as pj, report, report_ctx

OUT = Path(__file__).resolve().parent.parent / "output"
SAVES = Path(__file__).resolve().parent.parent / "saves"

# ---------- proyecto ----------
p = pj.Project(nombre="Acueducto San Jacinto", municipio="San Jacinto",
               departamento="Bolívar", corregimiento="",
               consultor="Aguas de Bolívar S.A. E.S.P.", fecha="2026-07-11",
               altitud=200, temperatura=27.0)

# logo sintético (PNG 1x1) para probar end-to-end la portada con logo (Task 2)
LOGO_PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
    "+A8AAQUBAScY42YAAAAASUVORK5CYII=")
p.logo_cliente_b64 = base64.b64encode(LOGO_PNG_1X1).decode()

cfg = p.poblacion
cfg.tipo, cfg.fuente = "municipio", "dane"
cfg.dpto, cfg.mpio, cfg.area = "Bolívar", "San Jacinto", "Cabecera Municipal"
p.censo = dane.series(cfg.dpto, cfg.mpio, cfg.area)
cfg.year0 = p.censo[-1][0]                 # último año DANE (2042)
cfg.p0 = float(dict(p.censo)[cfg.year0])
cfg.horizon_year = cfg.year0 + 25          # periodo de diseño Art. 40
cfg.flotante_pct = 0.0

rates = pop.growth_rates(p.censo)
proj = pop.project(cfg.p0, cfg.year0, cfg.horizon_year, rates, cfg.tasa_res0844)
cfg.metodo = pop.suggest_method(proj)
cfg.justificacion = ("Método con menor desviación absoluta respecto al promedio "
                     "de los cinco métodos evaluados con las tasas del municipio.")

# dotación 110 L/hab/d, sin pérdidas ni mayoración (QMD = QMH = Qmed)
p.demanda.modo = "manual"
p.demanda.dneta = 110.0
p.demanda.perdidas = 0.0
p.demanda.k1 = 1.0
p.demanda.k2 = 1.0
p.demanda.referencia = "res0844_2018"
p.demanda.justificacion = ("Dotación de 110 L/hab/d adoptada para la cabecera "
                           "municipal; no se consideran pérdidas técnicas ni "
                           "coeficientes de mayoración por solicitud del análisis.")

# almacenamiento: cadena pozo→bajo→elevado. Todas las bombas 10 h; el bombeo
# intermedio arranca 1 h después de la captación (6-15 vs 5-14).
alm = p.almacenamiento
alm.factores_hora = [0.6, 0.7, 0.8, 0.9, 1, 1.2, 1.6, 1.2, 1, 1.1, 1.1, 1.2,
                     1.1, 1.1, 1, 1.1, 1.2, 1.1, 0.9, 0.9, 0.9, 0.8, 0.8, 0.7]
alm.ventana_captacion = [1 if 5 <= h <= 14 else 0 for h in range(24)]
alm.suministro_hora = [1 if 6 <= h <= 15 else 0 for h in range(24)]
alm.usar_cadena = True

# bomba candidata: KSB WKL 125, rodete Ø320, 1750 rpm (digitalizada del catálogo)
WKL = pj.PumpData(
    nombre="WKL 125 Ø320 (1750 rpm)", fabricante="KSB", modelo="WKL 125",
    puntos_qh=[(25, 57), (40, 55), (50, 53), (63, 50), (75, 46), (85, 42),
               (95, 37), (100, 33)],
    puntos_qe=[(25, 0.60), (35, 0.70), (45, 0.75), (55, 0.80), (63, 0.83),
               (80, 0.81), (90, 0.77), (100, 0.70)])

spec = pipes.pipe("PEAD PE100", "RDE 21", 200)     # 8" ≈ OD 200 mm

s1 = pj.PumpSystemData(nombre="Pozo → Tanque bajo", horas=10.0, he=40.0,
                       eficiencia=0.80, tipo_bomba="sumergible")
s1.tramos = [pj.SegmentData("Tramo 1", "impulsion", 70.0, spec.id_mm, "PEAD",
                            cat_material="PEAD PE100", cat_serie="RDE 21",
                            cat_dn=200, e_mm=spec.e_mm)]
s1.accesorios = [pj.AccessoryData("Válvula de cheque", 1, "Tramo 1"),
                 pj.AccessoryData("Salida", 1, "Tramo 1")]
s1.bombas = [WKL]
s1.bomba_seleccionada = WKL.nombre

s2 = pj.PumpSystemData(nombre="Tanque bajo → Tanque elevado", horas=10.0, he=20.0,
                       eficiencia=0.80, tipo_bomba="superficie")
s2.tramos = [pj.SegmentData("Tramo 1", "impulsion", 20.0, spec.id_mm, "PEAD",
                            cat_material="PEAD PE100", cat_serie="RDE 21",
                            cat_dn=200, e_mm=spec.e_mm)]
s2.accesorios = [pj.AccessoryData("Válvula de cheque", 1, "Tramo 1"),
                 pj.AccessoryData("Válvula de compuerta", 1, "Tramo 1"),
                 pj.AccessoryData("Salida", 1, "Tramo 1")]
s2.bombas = [pj.PumpData(nombre=WKL.nombre, fabricante="KSB", modelo="WKL 125",
                         puntos_qh=list(WKL.puntos_qh), puntos_qe=list(WKL.puntos_qe))]
s2.bomba_seleccionada = WKL.nombre
p.bombeos = [s1, s2]

# tren de tanques: semienterrado (entrada = pozo 5-14) + elevado (bombeo 6-15);
# los volúmenes los asigna automáticamente el balance de cada tanque
alm.tanques = [
    pj.TankSpec("Tanque semienterrado", "bajo", "rectangular", 0, 2.5, 1.5, 5, 14),
    pj.TankSpec("Tanque elevado", "elevado", "circular", 0, 2.5, 1.0, 6, 15),
]

ctx, figuras = report_ctx.build(p)
SAVES.mkdir(exist_ok=True)
pj.save(p, SAVES / "Acueducto_San_Jacinto.acucalc.json")

out = report.render(ctx, Path(tempfile.mkdtemp()) / "memoria")
pdf, log_tail = report.compile_pdf(out)

FOLDER = OUT / "San_Jacinto_Cabecera_Municipal"
CURVAS = FOLDER / "curvas_bombas"
CURVAS.mkdir(parents=True, exist_ok=True)
if pdf:
    shutil.copy(pdf, FOLDER / "Informe_Acueducto_San_Jacinto.pdf")
z = report.make_zip(out)
shutil.copy(z, FOLDER / "Informe_Acueducto_San_Jacinto_LaTeX.zip")
for nombre, ruta in figuras.items():
    shutil.copy(ruta, CURVAS / f"{nombre}.png")

print(f"Censo DANE {cfg.mpio} ({cfg.area}): {p.censo[0]} … {p.censo[-1]}")
print(f"Población base {cfg.year0}: {cfg.p0:,.0f} hab · método: {cfg.metodo}")
print(f"Población diseño {cfg.horizon_year}: {ctx['pob_final']} hab")
print(f"Qmed=QMD=QMH: {ctx['qmd']} L/s (dotación 110, sin pérdidas, K=1)")
for tb in ctx["tanques_balance"]:
    print(f"Tanque '{tb['nombre']}': entrada {tb['horas']} h · Q {tb['q_entrada']} L/s "
          f"· frac {tb['frac']} · V {tb['v']} m³")
print(f"Volumen total: {ctx['v_final']} m³")
for s in ctx["sistemas"]:
    print(f"Sistema '{s['nombre']}': Qb={s['qb']} L/s · Hd={s['hd']} m · "
          f"{s['potencia_hp']} HP · bombas: "
          + "; ".join(f"{b['nombre']}: Q_op={b['q_op']} L/s H_op={b['h_op']} m "
                      f"η={b['eta_op']}" for b in s["bombas"]))
print(f"Carpeta de salida: {FOLDER}")
print(f"PDF: {'OK -> Informe_Acueducto_San_Jacinto.pdf' if pdf else 'NO COMPILO'}")
print(f"Curvas de bombas: {len(figuras)} PNG en curvas_bombas/")
if not pdf:
    print(log_tail[-800:])

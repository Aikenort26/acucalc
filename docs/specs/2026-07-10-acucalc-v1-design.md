# ACUCALC v1 — Diseño

**Fecha:** 2026-07-10 · **Estado:** aprobado con ajustes del usuario (pendiente revisión final del spec)
**Autor del diseño:** sesión de brainstorming con Aiken Ortega-Heredia

## 1. Contexto y objetivo

Aiken diseña sistemas de acueducto (Aguas de Bolívar / Ingenova) con memorias de cálculo Excel
(`DIS-ACU-SALADO.xlsx`, `MEMORIAS_HIDRAULICAS_v0.xlsx` San Jacinto, etc.). El Excel es frágil:
hojas ocultas con curvas de bomba digitadas a mano, solo 1-2 impulsiones/succiones modificables,
sin trazabilidad normativa, reporte manual en DOCX/LaTeX.

**ACUCALC** reemplaza ese flujo: app web local (Streamlit) que hace la memoria de cálculo completa
de un acueducto según la **Resolución 0330 de 2017** (MVCT) y genera el reporte LaTeX.

- Carpeta: `02_PROYECTOS\ACUCALC\` (vault). Futuro repo GitHub: `acucalc`.
- Referencias de patrón: HIDROCALC (app hermana, mismo esqueleto core/pages/tests).
- Ejecución del plan: subagentes **Sonnet 5**; planeación/revisión con Fable 5.

## 2. Alcance

**v1:** proyecto (metadatos + guardar/cargar JSON), población, dotación/caudales,
almacenamiento, bombeo multi-tramo, digitalizador de curvas de bomba + comparación multi-bomba,
reporte LaTeX Res 0330.

**v2 (fuera de alcance ahora):** prueba de bombeo Cooper-Jacob, red de distribución,
desarenador/desinfección, bombas en paralelo/serie, costos, pase de diseño UI con ui-ux-pro-max.

## 3. Arquitectura

Patrón HIDROCALC: `core/` puro (sin Streamlit, 100% testeable) + `pages/` (UI) + estado en
`st.session_state` sincronizado con un **archivo de proyecto JSON versionado**.

```
ACUCALC/
├── app.py                  # entry point Streamlit (config, navegación, tema)
├── core/
│   ├── population.py       # tasas (aritmético, geométrico, exponencial, Wappaus) + proyecciones + desviaciones
│   ├── demand.py           # dotación (3 modos), pérdidas, dotación bruta, Qmed/QMD/QMH, caudales por componente
│   ├── storage.py          # volumen Art 81, curva integral (patrón horario), incendio NSR-10 J, predimensionado tanques
│   ├── hydraulics.py       # Colebrook-White, Darcy-Weisbach, propiedades agua(T), catálogos ks y km
│   ├── pumping.py          # Qb, Bresse, tramos múltiples, pérdidas acumuladas, Hd, potencia, NPSH, curva sistema, ariete, paneles
│   ├── curves.py           # calibración de ejes (lineal/log), px→datos, detección por color (OpenCV), ajuste polinómico, BEP, punto de operación
│   ├── project.py          # dataclasses del modelo + serialización JSON (schema_version) + validaciones
│   └── report.py           # jinja2 → proyecto .tex; detección pdflatex/latexmk; compilación o ZIP Overleaf
├── pages/
│   ├── 1_Proyecto.py       # metadatos, guardar/cargar JSON
│   ├── 2_Poblacion.py
│   ├── 3_Caudales.py
│   ├── 4_Almacenamiento.py
│   ├── 5_Bombeo.py
│   ├── 6_Curvas_de_bomba.py
│   └── 7_Reporte.py
├── templates/latex/        # main.tex.j2, secciones .tex.j2, Reference.bib base
├── data/                   # ks.json, km.json, agua_temperatura.json, dotaciones.json (Res 0330/0844/mínimo vital)
├── tests/                  # pytest, golden tests El Salado
├── requirements.txt, run.bat, README.md, .gitignore
└── docs/specs/             # este documento
```

Cada módulo core expone funciones puras `entrada → resultado (dataclass)`; las páginas solo
orquestan UI y llaman al core. Ninguna página contiene fórmulas.

## 4. Modelo de datos (proyecto JSON)

Un único `Proyecto` serializable con `schema_version`. Contiene: metadatos (nombre, municipio,
corregimiento, departamento, consultor, fecha, altitud m.s.n.m., temperatura del agua °C), censo, configuración y resultados seleccionados de
cada módulo, lista de tramos y accesorios, lista de bombas (con imagen embebida base64 + puntos
calibrados/digitalizados), selección final de bomba, opciones de reporte. Guardar/cargar desde la
página Proyecto. Los resultados derivados se recalculan al cargar (no se confía en valores cacheados).

## 5. Módulos

### 5.1 Población
- Entrada: serie censal (tabla editable, pegar desde Excel, o CSV DANE).
- Tasas por método: aritmético, geométrico, exponencial, Wappaus (fórmulas de la memoria Salado).
- Proyección a horizonte editable (default 25 años, Art 40 Res 0330) por los 4 métodos + método
  Res 0844 de 2018 (tasa tope editable, default 0.5%).
- Población base local: viviendas × hab/vivienda (como Salado: 350×4) o valor directo.
- Tabla + gráfico de las 5 series; tabla de desviaciones vs promedio; selección de método con
  campo de justificación (texto que fluye al reporte). Población flotante opcional.

### 5.2 Dotación y caudales *(ajuste del usuario integrado)*
Tres modos de dotación neta, siempre editable y con sustento normativo explícito:
1. **Por altitud** (Art 43 Res 0330): ≤1000 msnm→140, 1000–2000→130, >2000→120 L/hab/d.
2. **Por tabla de usos de la comunidad** (como la memoria Salado): tabla editable
   actividad/dotación mín/máx/adoptada (tomar, lavar ropa, cocinar, descarga baño, aseo, ducha,
   loza, +filas libres) → suma = dotación neta adoptada.
3. **Valor manual sustentado**: campo numérico + selector de referencia normativa
   (Res 0844/2018 esquemas diferenciales rurales; conceptos CRA; mínimo vital —
   jurisprudencia T-740/2011 y desarrollo distrital ~50 L/hab/d) + texto de justificación.
   Las referencias viven en `data/dotaciones.json` con cita completa; la justificación fluye al reporte.

Luego: pérdidas técnicas % (alerta si >25%, Art 44) → dotación bruta = neta/(1−p) →
Qmed, QMD (K1 default 1.3), QMH (K2 default 1.6), editables con cita Par. 2 Art. 47 →
proyección de caudales año a año hasta el horizonte → tabla de caudales de diseño por componente
según tipo de captación (Art 47: cap. superficial 2×QMD, cap. subterránea 1×QMD, desarenador,
aducción, conducción, tanque = QMD; red = QMH).

### 5.3 Almacenamiento
- Metodología A: volumen de regulación Art 81 + incendio (nivel de riesgo NSR-10 Título J,
  % de afectación) + días de reserva.
- Metodología B: curva integral con patrón horario de consumo y ventana de suministro editables
  (default: patrón de la memoria Salado, suministro 10 h).
- Volumen final = máx(A, B), redondeado a múltiplo de 5 m³.
- Predimensionado de tanques: N tanques (elevado/semienterrado), volumen, altura, diámetro o
  lados, niveles mín/máx. Notas de borde libre (+0.30 m) en el reporte.

### 5.4 Bombeo multi-tramo *(pedido central del usuario)*
- **Tramos ilimitados**: lista dinámica "agregar tramo" → nombre, tipo (succión/impulsión),
  longitud, diámetro comercial, material (ks de catálogo editable). Elimina la limitación del
  Excel de 1-2 impulsiones fijas.
- **Accesorios ilimitados**: lista dinámica "agregar accesorio" → tipo (catálogo km completo de la
  memoria: válvulas globo/mariposa/cheque/compuerta, codos, tees, yees, uniones, entradas, salida),
  cantidad, tramo asociado (hereda D y V del tramo).
- Q bombeo = QMD × 24 / horas de bombeo (editable).
- Por tramo: V, Re, f (Colebrook-White), hf (Darcy-Weisbach) con propiedades del agua a la
  temperatura del proyecto; hl por accesorio con la V de su tramo. **Tabla acumulada de pérdidas**
  visible → la potencia final refleja la suma exacta de todas las pérdidas.
- Altura estática (+5 m opcional, RAS Título B 9.4.11) → Hd = He + Σhf + Σhl →
  potencia P = ρgQHd/η (η editable) en kW y HP; resumen "bomba mínima requerida Q/H/P".
- **Curva del sistema**: barrido 0→120% Qb sumando todos los tramos/accesorios (alimenta el módulo de curvas).
- Auxiliares: diámetro económico de Bresse (sugerencia por tramo), NPSH disponible,
  golpe de ariete (celeridad por material/espesor del tramo crítico, sobrepresión vs PN),
  pre-cálculo de paneles solares (potencia panel, FS, número y área).

### 5.5 Digitalizador de curvas + multi-bomba *(módulo aparte; ajuste del usuario integrado)*
Funcionalidad tipo **WebPlotDigitizer (automeris.io)** pero **implementación propia**
(WebPlotDigitizer es AGPL-3.0: no se copia ni adapta su código — solo se replica el concepto).
- Cargar imagen del catálogo (png/jpg; PDF se exporta a imagen fuera de la app en v1). Calibración: 2 puntos por eje con valores
  conocidos; soporte de escala logarítmica; unidades de entrada (L/s, L/min, m³/h, GPM)
  convertidas a L/s y m internamente.
- **Híbrido**: (a) detección automática de la curva por color dominante (OpenCV) como propuesta
  inicial; (b) modo manual por clicks (`streamlit-image-coordinates`) para añadir/mover/borrar
  puntos. La tabla de puntos siempre es editable a mano. El manual funciona siempre; el automático es asistencia.
- Series por bomba: Q-H (obligatoria) y Q-E (opcional). Ajuste polinómico (H: grado 2 tipo
  a−bQ²; E: grado 2-3) con R² visible.
- **BEP** = máximo de la curva de eficiencia ajustada.
- **Multi-bomba**: se guardan N bombas (nombre, modelo, fabricante). Gráfico conjunto curva del
  sistema + curvas de todas las bombas; puntos de operación por intersección numérica.
  Tabla comparativa: Q_op, H_op, η(Q_op), % desviación respecto al BEP, potencia absorbida.
  Selección de bomba definitiva (fluye al reporte). El módulo es genérico: puede digitalizar
  cualquier gráfica, pero su integración primaria es el punto de operación.

### 5.6 Reporte LaTeX Res 0330
- Genera **proyecto LaTeX completo**: main.tex + secciones + Reference.bib + figuras matplotlib
  (proyección de población, curva integral, curvas bomba-sistema, esquema de pérdidas) en `figures/`.
- Estructura fusionada del DOCX Retiro + LaTeX San Jacinto, priorizada según la Res 0330:
  portada → introducción → objetivos → marco referencial (localización, vías, clima, topografía,
  uso del suelo, socioeconomía) → marco teórico (métodos usados, con ecuaciones) → marco legal
  (Res 0330/2017, Res 0844/2018, Decreto 1575/2007, NSR-10 J, CRA, mínimo vital) →
  población → demanda y caudales → almacenamiento → bombeo → selección de bomba (con curvas) →
  conclusiones → referencias.
- Cada resultado numérico citando artículo/numeral aplicado (los strings normativos viven en las
  plantillas, no en el core).
- Compilación: detecta `latexmk`/`pdflatex` en PATH → PDF automático; si no hay LaTeX,
  entrega ZIP del proyecto listo para Overleaf.
- La prosa fija de las plantillas pasa por **Humanizer** antes de congelarse (regla del vault).

## 6. UI

Streamlit multipage, flujo secuencial 1→7 con indicadores de completitud por página.
Tema minimalista: `config.toml` custom + fuente embebida localmente (Inter o IBM Plex Sans,
sin CDN) + CSS sobrio. El pase de diseño fino se hará después de la v1 funcional con
**ui-ux-pro-max** (decisión del usuario). Números con unidades siempre visibles; tablas de
resultados exportables (CSV) por página.

## 7. Manejo de errores y validaciones

- Validaciones normativas no bloqueantes con cita: V fuera de [0.5, 6] m/s en impulsión (Art 56),
  pérdidas >25% (Art 44), dotación fuera de rango del Art 43 sin justificación, η∉(0,1),
  NPSH margen <0.5 m, sobrepresión > PN del tramo.
- El core nunca lanza excepciones por entradas incompletas: devuelve resultados parciales +
  lista de problemas (`issues: list[str]`) que la UI muestra.
- Carga de JSON con versión distinta: migración o mensaje claro, nunca crash.
- Digitalizador: si la detección automática falla, degrada a manual sin error visible.

## 8. Testing

- pytest sobre `core/` (sin Streamlit). TDD por módulo (RED-GREEN-REFACTOR, metodología Superpowers).
- **Golden tests El Salado** (valores de `DIS-ACU-SALADO.xlsx`): tasa Res 0844 → población 2051
  ≈ 1601.8 hab; QMD ≈ 2.142 L/s; QMH ≈ 3.428 L/s; volumen tanque = 110 m³; Qb ≈ 5.142 L/s;
  d Bresse ≈ 69.1 mm; hf ≈ 3.642 m; hl ≈ 1.396 m; Hd ≈ 74.84 m; P ≈ 6.90 HP; celeridad ≈ 238.9 m/s.
- Tests del digitalizador: transformaciones px→datos con calibraciones sintéticas (lineal y log),
  ajuste e intersección con curvas conocidas analíticamente.
- Test de reporte: el .tex generado compila (si hay LaTeX en el entorno de test) o al menos
  renderiza sin variables sin resolver.

## 9. Ejecución y distribución

- `run.bat`: crea venv si no existe, instala requirements, lanza `streamlit run app.py`.
- README con instalación limpia (Python 3.11+).
- Repo GitHub `acucalc` (crear al final de v1; push solo con confirmación del usuario).
  El repo vive en `02_PROYECTOS\ACUCALC\` — al hacer `git init` ahí, añadir la carpeta al
  `.gitignore` del vault para evitar repos anidados.
- Licencia del repo: MIT (sin código AGPL de WebPlotDigitizer).

## 10. Dependencias

`streamlit`, `streamlit-image-coordinates`, `numpy`, `pandas`, `matplotlib`, `scipy` (ajustes e
intersecciones), `opencv-python-headless` (detección de curva), `jinja2`, `pillow`. LaTeX externo opcional.

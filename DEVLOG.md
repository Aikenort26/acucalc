# 📋 DEVLOG — Historial de desarrollo inter-agente

> **Propósito:** Este archivo es el canal de comunicación entre **Claude Code** y **Antigravity (Gemini)**.
> Cada agente DEBE leerlo al inicio de una sesión y actualizarlo al final.
> El formato es estricto para que ambos lo parseen sin ambigüedad.

---

## Convenciones

- Cada entrada es un bloque `## [FECHA] — [TÍTULO]` en orden **cronológico inverso** (lo más reciente arriba).
- Campos obligatorios: `Agente`, `Rama`, `Cambios`, `Tests`, `Pendientes`.
- Campo opcional: `Decisiones`, `Contexto`, `Notas`.
- Las entradas NO se editan retroactivamente. Si algo cambia, se crea una entrada nueva.
- Los pendientes se copian/referencian en la entrada siguiente si se resuelven.

---

## Plantilla de entrada

```markdown
## [YYYY-MM-DD HH:MM] — Título descriptivo del trabajo

**Agente:** Claude Code | Antigravity
**Rama:** main | feature/xxx
**Sesión:** breve contexto de qué pidió el usuario

### Cambios realizados
- archivo: descripción del cambio

### Tests
- `pytest -v` → N passed, M failed (o "no ejecutados")
- Tests nuevos: lista

### Decisiones tomadas
- Decisión: razón

### Pendientes (TODO)
- [ ] Tarea pendiente 1
- [ ] Tarea pendiente 2

### Contexto para el siguiente agente
Párrafo libre con contexto crítico que el otro agente necesita saber.
```

---

## Entradas

## [2026-07-17] — v8 bloques A+B: informe dentro de márgenes + bug de reparto de demandas

**Agente:** Claude Code
**Rama:** main (merge de acucalc-v8, worktree eliminado tras merge)
**Sesión:** Usuario reportó 11 pendientes tras usar el informe LaTeX real (tablas fuera de margen, mapa sin zoom, patrón de consumo no documentado, faltaba cita DANE, sin sección de autoría). Se ejecutaron los bloques A (trivial: índices, portada, escala de iconos) y B (informe: márgenes, patrón, citas, aviso de no-convergencia).

### Cambios realizados
- `templates/latex/main.tex.j2`: `longtable`+`tabularx`+`xurl`+`emergencystretch`; tabla de demandas por nodo (antes 1 fila/nodo desbordaba el flotante) ahora se parte en 3 columnas con encabezado repetido; tablas de 8 columnas (ariete, bombas) a `\small`/`\footnotesize`; índices en páginas separadas; sección nueva "Acerca de ACUCALC" (autoría, límites, no-convergencia del solver); fórmula de longitud aferente derivada; patrón horario de 24 factores documentado; referencias con `\label`/`\ref` reales + cita DANE oficial
- `core/network.py::assign_demands_by_length`: **bug de cálculo corregido** — dividía por la longitud TOTAL de la red pero solo acumulaba aferencia en nodos de consumo, dejando ~0.38% del QMD sin asignar (medido en red real de 478 nodos). Ahora Σq_i = QMD exacto
- `core/report_ctx.py`: patrón ≠24h ya no revienta el build (bug preexistente, más grave de lo reportado); `HORAS_DIA` como guarda única
- `core/network_map.py`: parámetro `escala` en `fig_red` (área ∝ escala²)
- `pages/7_Red.py`: `st.error` visible cuando el solver no converge (antes decía "Convergió" incondicionalmente)

### Tests
- `pytest -v` → 235 passed, 0 failed (era 214 antes del bloque)
- Nuevos: guardas de patrón horario, escala de iconos, reparto de demandas (incl. test e2e build→render con red que casi no existía y habría dejado desaparecer la tabla en silencio)

### Decisiones tomadas
- Reparto por longitud aferente normalizado a 100% del QMD (confirmado con el usuario, no es cosmético — cambia resultados de proyectos ya entregados)
- Zoom/pan real del mapa (Plotly) diferido al bloque D — solo se hizo escala de iconos en A
- Verificación exigida: compilar el PDF real del proyecto ACU-SAN JACINTO y leer el log de LaTeX (0 Overfull, 0 Float too large, 0 refs sin resolver), no solo inspección visual

### Pendientes (TODO)
- [ ] Bloque C: mapa de red al informe, marca ACUCALC + portada hidráulica (SVG ya creado en `assets/`, sin commitear), calibración de curvas en una sola pantalla, LICENSE GPL-3.0
- [ ] Bloque D: mapa Plotly con zoom/pan/hover, UI general
- [ ] Bloque E (bloqueado): solver de red no converge en redes grandes — precondición de periodo extendido

### Contexto para el siguiente agente
`assign_demands_by_length` cambió de contrato (ya no divide por longitud total de la red, sino por la aferencia de los nodos) — si tocas ese módulo, el test viejo que codificaba el bug fue corregido, no lo reviertas. La sección "Acerca de ACUCALC" en la plantilla es el lugar correcto para documentar nuevas limitaciones conocidas.

## [2026-07-16 11:15] — v7: 16 ítems de feedback de uso real (bugs + features)

**Agente:** Claude Code
**Rama:** main (merge de `acucalc-v7`, worktree ya eliminado)
**Sesión:** Usuario reportó 16 problemas/mejoras tras usar la app en un caso real (proyecto ACU-SAN JACINTO). Dos premisas del usuario resultaron falsas al explorar el código ("solo hay PE100" — ya había 5 materiales/186 DN; "quitaste el botón de borrar puntos" — nunca existió, `git log -S` lo confirmó) — se investigó antes de implementar en vez de tomar el reporte al pie de la letra.

### Cambios realizados
- `pages_common.py`, `core/formato.py` [NUEVO]: `f_num`/`i_num`/`fila_incompleta` (guardas NaN — `x or default` no protege contra NaN, `bool(float('nan')) is True`); `sel_state()` (selectbox con key estable, evita re-montaje al cambiar el modelo); convención única de decimales (`fmt_q/h/p/v/d/perdida/vol/coef`) compartida entre pantalla y reporte
- `pages/7_Red.py`, `pages/5_Bombeo.py`: 3 causas raíz del bug "escribo y se pierde" (widgets sin key, `session_state` pisado en cada rerun, keys derivadas de nombres mutables)
- `data/riesgo_incendio.json` [NUEVO], `core/project.py`: nivel de riesgo contra incendio (bajo 15%/medio 20%/alto 25%, valores del usuario) reemplaza el % libre
- `core/pumping.py::ArieteResult`: factor de seguridad de golpe de ariete (FS y % de uso, separados sin ambigüedad)
- `data/tuberias.json`: + PVC-O y PVC biaxial (referencial, marcado para verificar con fabricante)
- `core/project.py::migrate_pump_cal_v7`: calibración de curvas con X compartido entre Q-H/Q-η (8→6 clicks)
- `core/curves.py::suggest_n2`: sugerencia de N₂ objetivo (nunca auto-aplica)
- `core/pump_catalog.py`: export de bombas ahora aplica la transformada N2/afinidad/arreglo (antes exportaba la curva nominal — bug real) + normalizado a 10 puntos + coeficientes
- `components/digitizer/index.html`, `pages/6_Curvas_de_bomba.py`: `@st.fragment` + `scope="fragment"` en botones internos (rerun completo por cada click de ajuste), cache de decode, drag de la cruz en la lupa, altura fija de imagen (PDF vertical ya no empuja los controles fuera de pantalla)
- `core/curves.py::detect_curve_by_color`: reescrito (distancia euclidiana + bbox del rectángulo calibrado + clustering por conectividad — la versión vieja mezclaba la curva con líneas de rejilla)
- `core/network.py::write_inp_pipes`: el `.inp` exportado ahora sí lleva diámetros optimizados y rugosidad recalculada (antes solo la demanda se reescribía — bug real, dos botones servían el mismo payload)
- `core/network_map.py` [NUEVO]: mapa de la red (nodos/tramos/fuentes) coloreado por presión/velocidad con el solver GGA propio — sin integrar EPANET real (decisión del usuario, sin wheels garantizados en Python 3.14)
- `core/network.py::write_inp_pump_curves`: exporta `[CURVES]`/`[PUMPS]` al `.inp` con la curva transformada — solo exportación, el solver interno sigue asumiendo cabeza fija

### Tests
- `pytest -v` → 213 passed (152 baseline v6 + 61 nuevos), 0 failed

### Decisiones tomadas
- Nivel de riesgo bajo/medio/alto: valores 15/20/25% dictados por el usuario, no inventados (entregable de ingeniería real)
- Mapa de red con solver propio, no EPANET real
- Autodetección: pen/mask de automeris quedó explícitamente fuera de alcance (baja prioridad, "si no pesa mucho")
- Ítem 16 (curvas→INP): solo exportación, el GGA interno no se modifica
- `report_ctx.build()` sigue recalculando `optimize_diameters` en cada build del reporte (no reusa `session_state` de la página 7) — es el diseño intencional del módulo (recalcula siempre desde el `Project` persistido, nunca confía en estado vivo), no un bug pendiente

### Pendientes (TODO)
- [ ] Pen/mask de pintado para la autodetección (baja prioridad, explícitamente diferido)
- [ ] Validar con catálogo real de fabricante los valores referenciales de PVC-O/biaxial marcados como estimados

### Contexto para el siguiente agente
Todo el trabajo se hizo en worktree `acucalc-v7` (ya eliminado tras el merge), con revisión independiente de spec-compliance y de calidad de código antes de mergear (2 gaps de spec detectados y corregidos: `st.rerun()` sin `scope="fragment"` en varios botones dentro del fragment del digitalizador, y la altura fija de imagen del ítem 8 que nunca se había implementado). `PumpData.cal` cambió de forma otra vez (v6→v7): ver `migrate_pump_cal_v7` en `core/project.py` para el historial completo de migraciones si tocas ese campo.

## [2026-07-16 10:29] — Integración de skills de terceros al flujo inter-agente

**Agente:** Antigravity
**Rama:** main
**Sesión:** Usuario pidió integrar las skills de `D:\CLAUDE CODE\04_SKILLS_TERCEROS` al flujo de desarrollo de ACUCALC.

### Cambios realizados
- `CLAUDE.md` [MOD]: agregada sección "Skills de terceros disponibles" con 12 skills referenciadas
- `.agents/AGENTS.md` [MOD]: agregada sección equivalente para Antigravity con 10 skills referenciadas

### Tests
- No ejecutados (cambios de configuración de agentes, no de código)

### Decisiones tomadas
- Se clasificaron ~300 skills en 3 niveles: 🟢 altamente relevantes (12), 🟡 moderadamente (9), 🔴 no relevantes (resto)
- Solo se referenciaron en CLAUDE.md/AGENTS.md las skills 🟢 (directamente aplicables al stack Python/Streamlit/pytest)
- Las skills de `superpowers/` cubren flujo de desarrollo (TDD, plans, debugging, verification)
- Las skills de `ECC/` cubren patrones de código (Python patterns, testing, error handling, git)
- Skills de frontend JS/React, mobile, DevOps, crypto, etc. se descartaron por irrelevantes al stack
- No se copiaron archivos de skills al repo — se referencian por ruta absoluta a `04_SKILLS_TERCEROS`

### Pendientes (TODO)
- [ ] Hacer `git push` para que IDX y Claude Code tengan los cambios
- [ ] Continuar con el plan de desarrollo (siguiente WP del plan v5 o crear plan v7)
- [ ] Verificar que Claude Code lee correctamente las skills al iniciar sesión

### Contexto para el siguiente agente
Se integraron 12 skills de terceros relevantes al proyecto. Las más importantes:
- **superpowers:test-driven-development** — refuerza el TDD del proyecto
- **superpowers:verification-before-completion** — obliga a correr pytest antes de declarar completado
- **superpowers:systematic-debugging** — debugging estructurado con root cause analysis
- **ECC:python-patterns** — patrones de Python idiomático (dataclasses, type hints, PEP 8)
- **ECC:python-testing** — referencia completa de pytest (fixtures, mocking, parametrización)
Las skills NO están dentro del repo, sino en `D:\CLAUDE CODE\04_SKILLS_TERCEROS\`. Ambos agentes las referencian por ruta absoluta.

## [2026-07-16 10:12] — Inicialización del DEVLOG + config IDX

**Agente:** Antigravity
**Rama:** main
**Sesión:** Usuario solicitó configurar Google Project IDX y crear sistema de changelog inter-agente.

### Cambios realizados
- `.idx/dev.nix` [NEW]: configuración de Google Project IDX (Python 3.11, venv auto, Streamlit preview con `app.py`)
- `DEVLOG.md` [NEW]: este archivo — canal de comunicación entre agentes
- `CLAUDE.md` [NEW]: instrucciones para Claude Code (leer/actualizar DEVLOG)
- `.agents/AGENTS.md` [NEW]: instrucciones para Antigravity (leer/actualizar DEVLOG)

### Tests
- No ejecutados (cambios de infraestructura, no de código)

### Decisiones tomadas
- Entry point de Streamlit es `app.py` (no `Home.py`): verificado en el repo
- DEVLOG en raíz del proyecto (no en docs/): acceso inmediato para ambos agentes
- Orden cronológico inverso: lo más reciente siempre arriba
- Formato Markdown estructurado: parseable por ambos agentes sin ambigüedad

### Pendientes (TODO)
- [ ] Hacer `git push` para que IDX pueda leer el repo
- [ ] Verificar que IDX construye el venv correctamente al abrir el workspace
- [ ] Continuar con el plan de desarrollo v7 (siguiente WP)

### Contexto para el siguiente agente
El proyecto ACUCALC es una app Streamlit para diseño de acueductos según la Resolución 0330/2017 de Colombia.
Estructura: `core/` (lógica pura, dataclasses, sin Streamlit) + `pages/` (UI Streamlit) + `tests/` (pytest).
El repo tiene 18 archivos de test. El plan de implementación más reciente es `docs/plans/2026-07-15-acucalc-v5.md`.
El tema visual es dark con verde (#22C55E) sobre fondo oscuro (#0B1416).
Hay commits sin pushear en `main` (al menos el de `.idx/dev.nix`).

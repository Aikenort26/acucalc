# ACUCALC — Instrucciones para Antigravity (Gemini)

## Protocolo de sesión obligatorio

### Al INICIAR una sesión:
1. **Lee `DEVLOG.md`** completo (especialmente la entrada más reciente).
2. Identifica los **Pendientes (TODO)** de la última entrada.
3. Revisa la **rama** activa y el estado de git (`git status`, `git log -5`).
4. Si el último agente fue Claude Code, revisa los archivos que modificó con `git diff`.

### Al FINALIZAR una sesión:
1. **Agrega una entrada nueva** al inicio de la sección `## Entradas` en `DEVLOG.md`.
2. Usa el formato de la plantilla definida en el DEVLOG (fecha, agente, rama, cambios, tests, pendientes, contexto).
3. Pon `**Agente:** Antigravity`.
4. Haz commit del DEVLOG junto con tus cambios.

## Arquitectura del proyecto

- **`core/`** — Lógica pura, dataclasses, sin imports de Streamlit. 100% testeable con pytest.
- **`pages/`** — UI Streamlit. Solo orquesta, no contiene lógica de negocio.
- **`tests/`** — pytest. Convención: `test_{modulo}.py` espeja `core/{modulo}.py`.
- **`components/`** — Componentes web embebidos (HTML/JS).
- **`templates/`** — Templates Jinja2 para el reporte LaTeX.
- **`docs/plans/`** — Planes de implementación versionados por fecha.
- **Entry point:** `app.py` (NO Home.py).

## Convenciones de código

- Commits descriptivos en español: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`.
- Tests primero (TDD): escribe el test que falla, luego implementa.
- Q interno en m³/s salvo en módulos que trabajan en L/s (pumping, curves).
- Diámetros en mm en dataclasses públicas.
- `report_ctx.build()` es la única fuente de verdad del reporte.

## Skills de terceros disponibles

Ubicación base: `D:\CLAUDE CODE\04_SKILLS_TERCEROS\`

Antes de implementar features, debugging o planes, **lee el SKILL.md** correspondiente:

### Flujo de desarrollo (Superpowers)
- **test-driven-development** → `superpowers/skills/test-driven-development/SKILL.md`
- **executing-plans** → `superpowers/skills/executing-plans/SKILL.md`
- **verification-before-completion** → `superpowers/skills/verification-before-completion/SKILL.md`
- **systematic-debugging** → `superpowers/skills/systematic-debugging/SKILL.md`
- **writing-plans** → `superpowers/skills/writing-plans/SKILL.md`

### Patrones Python (ECC)
- **python-patterns** → `ECC/skills/python-patterns/SKILL.md`
- **python-testing** → `ECC/skills/python-testing/SKILL.md`
- **coding-standards** → `ECC/skills/coding-standards/SKILL.md`
- **error-handling** → `ECC/skills/error-handling/SKILL.md`
- **git-workflow** → `ECC/skills/git-workflow/SKILL.md`

## Otros agentes

- **Claude Code** también trabaja en este proyecto. Lee `CLAUDE.md` si necesitas entender sus instrucciones.
- La comunicación entre agentes es a través de **`DEVLOG.md`** exclusivamente.

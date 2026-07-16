# ACUCALC

App web local (Streamlit) para diseño de sistemas de acueducto según la
**Resolución 0330 de 2017** del Ministerio de Vivienda, Ciudad y Territorio
de Colombia. Reemplaza el flujo de memorias de cálculo en Excel: proyección
de población, dotación y caudales de diseño, volumen de almacenamiento,
sistema de bombeo multi-tramo, digitalización de curvas de bomba y punto de
operación, y generación de la memoria técnica en LaTeX.

> ⚠️ **Aviso — revisión profesional obligatoria.** ACUCALC entrega un
> predimensionamiento automatizado según la metodología de la Resolución 0330
> de 2017. **Toda la información que produce esta aplicación — resultados en
> pantalla, memoria PDF/LaTeX y este mismo repositorio — debe ser revisada,
> verificada y validada por el ingeniero proyectista responsable** antes de
> usarse en diseño definitivo, construcción u operación de un sistema real.
> No reemplaza el diseño estructural/geotécnico detallado, el análisis de
> transitorios hidráulicos con software especializado, ni el juicio
> profesional del responsable del proyecto. Ver la sección "Recomendaciones y
> limitaciones" que la app agrega automáticamente a cada memoria generada.

## Flujo de trabajo (8 páginas)

1. **Proyecto** — metadatos, guardar/cargar (`.acucalc.json`)
2. **Población** — proyecciones oficiales **DANE** embebidas (todos los municipios,
   2018–2042, filtro departamento/municipio/área, actualizable subiendo el archivo
   DANE nuevo) o censo manual; flujo diferenciado municipio (continúa desde el
   último año DANE) vs corregimiento (tasas municipales sobre población base local
   con año base ajustable); tasas por año, proyección por 5 métodos + promedio,
   método sugerido por menor desviación
3. **Caudales** — dotación neta (3 modos), pérdidas, Qmed/QMD/QMH; K1/K2
   automáticos según el tamaño de la población proyectada (Par. 2 Art. 47)
4. **Almacenamiento** — tren de N tanques en serie con ventana de entrada por
   tanque: cada uno balancea su curva integral (la salida es la entrada del
   siguiente; la del último, el consumo de la población) y su volumen se asigna
   automáticamente; el caudal de cada bombeo intermedio sale de las horas de su
   ventana; patrón horario cargable desde Excel/CSV; predimensionado con formas
   circular/cuadrada/rectangular (o tanque único Art. 81 + curva integral)
5. **Bombeo** — N sistemas nombrados, cada uno un paquete completo: tramos con
   catálogo normativo de tuberías (RDE/clase, DN50–1200: PEAD, PVC-U en
   pulgadas, hierro dúctil K9/C, acero, GRP) con **DN propuesto** (Bresse +
   V ≤ 6 m/s Art. 56) y edición posterior; accesorios con Km visible; potencia;
   golpe de ariete verificado automáticamente contra la **PN de cada tramo**
   con recomendación de protecciones; arreglos paralelo/serie y leyes de afinidad
6. **Curvas de bomba** — por sistema: digitalizador con **lupa en tiempo real**,
   crosshair, auto-avance de calibración y puntos marcados sobre la imagen;
   entrada manual Q-H/Q-η; regresiones H=A·Q²+B·Q+C y η=D·Q²+E·Q+F con
   coeficientes y R²; doble gráfica Q-H/Q-η con punto de diseño (Qb, Hd) y de
   operación; **catálogo de bombas desde Excel** con ranking por eficiencia
7. **Red de distribución** — carga de red desde archivo **EPANET .inp**
   ([JUNCTIONS]/[RESERVOIRS]/[TANKS]/[PIPES]); asignación automática de
   demandas por longitud aferente a partir del QMD calculado en la página 3;
   optimización de diámetros por material/serie normativos con restricciones
   de velocidad máxima y presión mín./máx.; solver hidráulico propio
   (Global Gradient Algorithm reducido a cabezas nodales, Hazen-Williams o
   Darcy-Weisbach) implementado en `core/network.py`; exporta INP con
   demandas asignadas y CSV de demandas
8. **Reporte** — memoria LaTeX recalculada íntegramente desde el proyecto, con
   6 figuras generadas (proyección, comparación de métodos, caudales anuales,
   balance de tanques, curvas de bombeo por sistema y esquema del sistema);
   compila a PDF si hay LaTeX instalado

## Normativa implementada

| Artículo / norma | Módulo |
|---|---|
| Art. 40 Res. 0330/2017 — periodo de diseño | `core/population.py` |
| Res. 0844/2018 — tasa máxima rural | `core/population.py` |
| Art. 43 Res. 0330/2017 — dotación neta por altitud | `core/demand.py` |
| Art. 44 Res. 0330/2017 — pérdidas técnicas máx. 25% | `core/demand.py` |
| Art. 47 Res. 0330/2017 — K1/K2 y caudales por componente | `core/demand.py` |
| Art. 56 Res. 0330/2017 — velocidad en impulsión | `core/pumping.py` |
| Art. 81 Res. 0330/2017 — volumen de regulación | `core/storage.py` |
| NSR-10 Título J — volumen contra incendio | `core/storage.py` |
| RAS Título B 9.4.11 — margen de altura estática | `pages/5_Bombeo.py` |

Referencias adicionales de dotación (Res. 0844/2018, conceptos CRA, mínimo
vital constitucional) en `data/dotaciones.json`.

## Instalación

**Windows:** doble clic en `run.bat` (crea el entorno virtual, instala
dependencias y arranca la app).

**Manual:**
```
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt
.venv/Scripts/streamlit run app.py
```

### Motor LaTeX para compilar la memoria (PDF)

La app compila el PDF con el primer motor que encuentra, en este orden:
**Tectonic → pdflatex → latexmk**.

**Recomendado: Tectonic** — un motor LaTeX autocontenido (un solo binario, sin
Perl ni prompts de MiKTeX; descarga y cachea los paquetes que necesita la
primera vez). Es la vía más confiable para "compilar desde la web sin fallar".
Dos formas de tenerlo:

1. **Solo copia el binario en la carpeta de ACUCALC:** descarga
   `tectonic.exe` desde
   [releases de Tectonic](https://github.com/tectonic-typesetting/tectonic/releases)
   (archivo `…x86_64-pc-windows-msvc.zip`), extrae `tectonic.exe` y déjalo en la
   raíz del proyecto (junto a `app.py`). ACUCALC lo detecta ahí sin tocar el
   `PATH`.
2. **O instálalo en el PATH** con Scoop (`scoop install tectonic`), Conda
   (`conda install -c conda-forge tectonic`) o Cargo (`cargo install tectonic`).

**Alternativa: MiKTeX/TeX Live** — `pdflatex` o `latexmk` en el `PATH`. Nota: si
solo tienes `latexmk` de MiKTeX puede fallar por falta de Perl; ACUCALC ahora
prefiere `pdflatex` sobre `latexmk` y muestra el error real (stdout + stderr +
`main.log`) si algo falla. Sin ningún motor instalado, la app entrega el
proyecto como `.zip` listo para subir a Overleaf.

## Ejecución permanente local

**Opción recomendada — servidor que no se cierra:** doble clic en
`run_persistente.bat`. Prepara el entorno y lanza el servidor **desacoplado de
la consola** (vía `run_persistente.vbs`, oculto): la app queda en
`http://localhost:8501` **aunque cierres la ventana o la consola**. Para
detenerlo, doble clic en `detener_acucalc.bat` (mata el proceso del puerto
8501). El autosave sigue guardando en la ruta de proyecto que definas en la
página 1, así que no pierdes el trabajo aunque reinicies el equipo.

**Opción simple:** `run.bat` — la app corre mientras esa consola esté abierta;
se cierra si cierras la consola.

- **Acceso directo / inicio con Windows:** crea un acceso directo a
  `run_persistente.bat` en el escritorio o en la carpeta de inicio
  (`shell:startup`) para arrancarla con un doble clic o al iniciar sesión.
- **Inicio automático con el Programador de tareas:** `Programador de tareas`
  → *Crear tarea básica* → desencadenador *Al iniciar sesión* → acción
  *Iniciar un programa* → apuntar a `run_persistente.bat` con "Iniciar en" la
  carpeta del proyecto.

## Compartir en la web

Tres formas gratuitas de exponer la app, de más simple/temporal a más
permanente:

1. **Túnel temporal (`cloudflared`):** con la app corriendo localmente,
   `cloudflared tunnel --url http://localhost:8501` entrega una URL pública
   mientras esa consola esté abierta — ideal para compartir "por unas horas"
   sin desplegar nada. No requiere cuenta.
2. **Streamlit Community Cloud:** gratis y permanente, se conecta
   directamente al repo de GitHub del proyecto; la app se "duerme" tras un
   periodo de inactividad y despierta al primer acceso.
3. **Hugging Face Spaces:** gratis, alternativa a Streamlit Cloud con
   soporte nativo para apps Streamlit vía `app.py` + `requirements.txt`
   (los mismos que ya tiene este repo).

## Tests

```
.venv/Scripts/python -m pytest -v
```

Más de 130 tests cubren toda la lógica de `core/` (sin Streamlit), incluyendo golden
tests contra los valores reales de la memoria de cálculo de El Salado
(`docs/specs/2026-07-10-acucalc-v1-design.md`). Dos desviaciones deliberadas
frente al Excel original están documentadas en `docs/plans/2026-07-10-acucalc-v1.md`
("Nota de consistencia"): el método aritmético de población usa tasa
constante en vez de recursiva, y las pérdidas hidráulicas usan siempre la
velocidad del diámetro comercial del tramo (no la del diámetro económico de Bresse).

## Estructura del repo

```
ACUCALC/
├── app.py                  # entry point Streamlit
├── core/                   # lógica pura, testeada con pytest
│   ├── catalogs.py         # agua, rugosidades, accesorios, dotaciones
│   ├── hydraulics.py       # Colebrook-White, Darcy-Weisbach
│   ├── population.py       # tasas y proyección de población
│   ├── demand.py           # dotación y caudales de diseño
│   ├── storage.py          # volumen de almacenamiento y tanques
│   ├── pumping.py          # bombeo multi-tramo, Bresse, ariete, arreglos/afinidad
│   ├── curves.py           # digitalizador de curvas (implementación propia)
│   ├── project.py          # modelo de proyecto + JSON versionado
│   └── report.py           # generador de memoria LaTeX
├── pages/                  # 8 páginas Streamlit (solo UI, sin fórmulas)
├── templates/latex/        # plantilla Jinja2 de la memoria (Res. 0330)
├── data/                   # catálogos JSON (agua, ks, km, dotaciones)
├── tests/                  # +130 tests pytest
├── docs/specs/, docs/plans/ # spec de diseño y plan de implementación
├── requirements.txt, run.bat
└── LICENSE
```

## Licencia

MIT — ver `LICENSE`. El digitalizador de curvas (`core/curves.py`,
`components/digitizer/`) es una implementación propia.

# ACUCALC

App web local (Streamlit) para diseño de sistemas de acueducto según la
**Resolución 0330 de 2017** del Ministerio de Vivienda, Ciudad y Territorio
de Colombia. Reemplaza el flujo de memorias de cálculo en Excel: proyección
de población, dotación y caudales de diseño, volumen de almacenamiento,
sistema de bombeo multi-tramo, digitalización de curvas de bomba y punto de
operación, y generación de la memoria técnica en LaTeX.

## Flujo de trabajo (7 páginas)

1. **Proyecto** — metadatos, guardar/cargar (`.acucalc.json`)
2. **Población** — proyecciones oficiales **DANE** embebidas (todos los municipios,
   2018–2042, filtro departamento/municipio/área, actualizable subiendo el archivo
   DANE nuevo) o censo manual; flujo diferenciado municipio (continúa desde el
   último año DANE) vs corregimiento (tasas municipales sobre población base local
   con año base ajustable); tasas por año, proyección por 5 métodos + promedio,
   método sugerido por menor desviación
3. **Caudales** — dotación neta (3 modos), pérdidas, Qmed/QMD/QMH; K1/K2
   automáticos según el tamaño de la población proyectada (Par. 2 Art. 47)
4. **Almacenamiento** — volumen (Art. 81 + curva integral), predimensionado de tanques
5. **Bombeo** — tramos y accesorios ilimitados, pérdidas acumuladas, potencia, ariete, paneles
6. **Curvas de bomba** — digitalización de catálogos, BEP, comparación multi-bomba
7. **Reporte** — memoria LaTeX estructurada, compilación a PDF si hay LaTeX instalado

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

Para compilar la memoria a PDF directamente desde la app se necesita
`pdflatex` o `latexmk` en el `PATH` (MiKTeX o TeX Live). Sin LaTeX instalado,
la app entrega el proyecto como `.zip` listo para subir a Overleaf.

## Tests

```
.venv/Scripts/python -m pytest -v
```

53 tests cubren toda la lógica de `core/` (sin Streamlit), incluyendo golden
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
│   ├── pumping.py          # bombeo multi-tramo, Bresse, ariete, paneles
│   ├── curves.py           # digitalizador de curvas (tipo WebPlotDigitizer)
│   ├── project.py          # modelo de proyecto + JSON versionado
│   └── report.py           # generador de memoria LaTeX
├── pages/                  # 7 páginas Streamlit (solo UI, sin fórmulas)
├── templates/latex/        # plantilla Jinja2 de la memoria (Res. 0330)
├── data/                   # catálogos JSON (agua, ks, km, dotaciones)
├── tests/                  # 53 tests pytest
├── docs/specs/, docs/plans/ # spec de diseño y plan de implementación
├── requirements.txt, run.bat
└── LICENSE
```

## Licencia

MIT — ver `LICENSE`. El digitalizador de curvas (`core/curves.py`) es una
implementación propia inspirada conceptualmente en
[WebPlotDigitizer](https://automeris.io/) (AGPL-3.0); no reutiliza su código.

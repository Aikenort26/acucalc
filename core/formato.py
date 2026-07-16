"""Convención única de decimales de ACUCALC (WP-2a).

Regla del proyecto (definida por el usuario):

- **2 decimales** para caudales, alturas, potencias, pérdidas, velocidades,
  diámetros y volúmenes calculados.
- **5 decimales** para coeficientes de fricción y números similares de muchos
  decimales.

Este módulo es la **única fuente de verdad**: lo usan tanto la UI (vía
`pages_common`, que lo re-exporta) como el reporte LaTeX (`core.report_ctx`).
Antes de WP-2a el mismo número se imprimía con 1, 2 o 3 decimales según el
sitio — pantalla y reporte llegaban a mostrar valores distintos del mismo
cálculo. Cualquier formateo nuevo de estas magnitudes debe pasar por aquí.

`core/` no puede importar de `pages_common` (invertiría las capas: la lógica
pura dependería de la UI), por eso los helpers viven en `core/` y es
`pages_common` quien los re-exporta.

Excepciones deliberadas que NO usan estos helpers (documentadas aquí para que
no se "corrijan" por error):

- Población: `,.0f` (habitantes, no hay medios habitantes).
- Tasas de crecimiento: `.6f`; desviaciones entre métodos: `+.4%`.
- Reynolds: `,.0f` (adimensional de orden 1e5).
- DN nominal: `.0f` mm y `.2f` in — el DN es una etiqueta comercial.
- Eficiencia η: `.3f` (fracción 0-1, la tercera cifra es significativa).
- Fracción de balance: `.4f`.
- Horas, días y volúmenes *asignados* por el usuario: `.0f`.
- Exportación CSV de demandas: `.4f` (intercambio de datos, no lectura humana).

Nota sobre el redondeo (verificado en `tests/test_formato.py`): el
mini-lenguaje de formato de Python redondea **al par más cercano**
(*banker's rounding*) sobre el valor binario *real* del float, no sobre su
representación decimal escrita. Consecuencias prácticas:

- `f"{0.125:.2f}"` → `"0.12"` (0.125 es exacto en binario; empate → al par).
- `f"{0.135:.2f}"` → `"0.14"` (0.135 en binario es 0.13500000000000000888…,
  o sea *no* es empate: redondea hacia arriba por ser mayor que el medio).
- `f"{2.675:.2f}"` → `"2.67"` (2.675 en binario es 2.67499999999999982…).

Es el mismo criterio que usa `round()` y que aplica `DataFrame.style.format`,
así que pantalla y reporte coinciden siempre. Para magnitudes de ingeniería
(caudales, alturas) la diferencia es de ±0.005 en la última cifra mostrada y
no afecta ningún cálculo: **solo se formatea la salida, nunca se redondea el
valor que entra a un cálculo posterior**.
"""
import math

# ---------- decimales por magnitud ----------
DEC_CAUDAL = 2       # L/s, m³/s
DEC_ALTURA = 2       # m (altura estática, dinámica, geométrica)
DEC_POTENCIA = 2     # kW, HP
DEC_PERDIDA = 2      # m (hf, hl, Σ pérdidas)
DEC_VELOCIDAD = 2    # m/s
DEC_DIAMETRO = 2     # mm, m
DEC_VOLUMEN = 2      # m³ (volúmenes calculados; los asignados van a .0f)
DEC_COEF = 5         # f de Darcy y coeficientes de muchos decimales

NA = "—"


def fmt_num(valor, decimales: int, na: str = NA) -> str:
    """Formatea `valor` con `decimales` cifras. `None`/`NaN` → `na`.

    La guarda de NaN es necesaria: `f"{float('nan'):.2f}"` produce `"nan"`,
    que se colaría al reporte LaTeX y a la pantalla como texto basura en vez
    de como el marcador de dato faltante.
    """
    if valor is None:
        return na
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return na
    if math.isnan(v) or math.isinf(v):
        return na
    return f"{v:.{decimales}f}"


def fmt_q(valor, na: str = NA) -> str:
    """Caudal [L/s] — 2 decimales."""
    return fmt_num(valor, DEC_CAUDAL, na)


def fmt_h(valor, na: str = NA) -> str:
    """Altura [m] — 2 decimales."""
    return fmt_num(valor, DEC_ALTURA, na)


def fmt_p(valor, na: str = NA) -> str:
    """Potencia [kW | HP] — 2 decimales."""
    return fmt_num(valor, DEC_POTENCIA, na)


def fmt_v(valor, na: str = NA) -> str:
    """Velocidad [m/s] — 2 decimales."""
    return fmt_num(valor, DEC_VELOCIDAD, na)


def fmt_d(valor, na: str = NA) -> str:
    """Diámetro [mm] — 2 decimales."""
    return fmt_num(valor, DEC_DIAMETRO, na)


def fmt_perdida(valor, na: str = NA) -> str:
    """Pérdida de carga [m] — 2 decimales."""
    return fmt_num(valor, DEC_PERDIDA, na)


def fmt_vol(valor, na: str = NA) -> str:
    """Volumen calculado [m³] — 2 decimales."""
    return fmt_num(valor, DEC_VOLUMEN, na)


def fmt_coef(valor, na: str = NA) -> str:
    """Coeficiente de fricción (f de Darcy) y similares — 5 decimales."""
    return fmt_num(valor, DEC_COEF, na)


def spec(decimales: int) -> str:
    """Formato estilo pandas (`'{:.2f}'`) para `DataFrame.style.format`.

    Evita el `.style.format(precision=N)` global, que aplicaba el mismo N a
    todas las columnas numéricas de la tabla sin distinguir magnitudes.
    """
    return f"{{:.{decimales}f}}"


# Atajos para `DataFrame.style.format` — misma convención que los `fmt_*`.
SP_CAUDAL = spec(DEC_CAUDAL)
SP_ALTURA = spec(DEC_ALTURA)
SP_POTENCIA = spec(DEC_POTENCIA)
SP_PERDIDA = spec(DEC_PERDIDA)
SP_VELOCIDAD = spec(DEC_VELOCIDAD)
SP_DIAMETRO = spec(DEC_DIAMETRO)
SP_VOLUMEN = spec(DEC_VOLUMEN)
SP_COEF = spec(DEC_COEF)

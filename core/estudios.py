"""Estudios previos: secciones editables de la memoria (población, aspectos
sociales y económicos, topografía, suelos, materiales…) con texto citado
[@clave], tablas cargadas desde CSV/Excel y figuras (imagen o la primera
página de un PDF)."""
import io
from pathlib import Path

import pandas as pd
from PIL import Image, UnidentifiedImageError

from core import biblio
from core.imagenes import reducir_a_b64
from core.latex import latex_escape

TIPOS = {
    "poblacion": "Estudio de población",
    "social": "Aspectos sociales",
    "economico": "Aspectos económicos",
    "topografia": "Topografía",
    "suelos": "Estudio de suelos",
    "materiales": "Materiales",
    "otro": "Otro estudio",
}
MAX_COLUMNAS = 8          # más columnas no caben legibles en el ancho de la página
MAX_FILAS = 500


def tabla_de_archivo(nombre: str, raw: bytes):
    """TablaEstudio desde un CSV (separador detectado, UTF-8 o Latin-1) o la
    primera hoja de un Excel."""
    from core.project import TablaEstudio
    try:
        if nombre.lower().endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(raw))
        else:
            try:
                txt = raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                txt = raw.decode("latin-1")
            df = pd.read_csv(io.StringIO(txt), sep=None, engine="python")
    except (ValueError, pd.errors.ParserError, OSError) as e:
        raise ValueError(f"No se pudo leer la tabla «{nombre}»: {e}") from e
    df = df.dropna(how="all").dropna(axis=1, how="all")
    if df.empty:
        raise ValueError(f"La tabla «{nombre}» está vacía.")
    if df.shape[1] > MAX_COLUMNAS:
        raise ValueError(f"La tabla «{nombre}» tiene {df.shape[1]} columnas; el máximo es "
                         f"{MAX_COLUMNAS} para que quepa en la página: divídala.")
    if len(df) > MAX_FILAS:
        raise ValueError(f"La tabla «{nombre}» tiene {len(df)} filas; el máximo es {MAX_FILAS} "
                         "(para series largas, anexe el archivo y resuma aquí).")
    return TablaEstudio(Path(nombre).stem, df.to_csv(index=False))


def tabla_df(t, como_texto: bool = False) -> pd.DataFrame:
    if not t.csv.strip():
        return pd.DataFrame()
    return pd.read_csv(io.StringIO(t.csv), dtype=str if como_texto else None,
                       keep_default_na=not como_texto)


def figura_de_archivo(nombre: str, raw: bytes) -> str:
    """Base64 de la figura: una imagen se reduce; de un PDF se rasteriza la
    primera página."""
    if nombre.lower().endswith(".pdf") or raw[:5] == b"%PDF-":
        try:
            import pypdfium2 as pdfium
            doc = pdfium.PdfDocument(raw)
            img = doc[0].render(scale=2.0).to_pil()
        except Exception as e:  # noqa: BLE001 — cualquier PDF ilegible
            raise ValueError(f"No se pudo leer el PDF «{nombre}»: {e}") from e
        buf = io.BytesIO()
        img.convert("RGB").save(buf, "PNG", optimize=True)
        raw = buf.getvalue()
    else:
        try:
            Image.open(io.BytesIO(raw)).verify()
        except (UnidentifiedImageError, OSError) as e:
            raise ValueError(f"«{nombre}» no es una imagen ni un PDF.") from e
    return reducir_a_b64(raw)


def _es_numero(v: str) -> bool:
    try:
        float(v.replace(",", "."))
        return True
    except ValueError:
        return False


def _tabla_ctx(t) -> dict | None:
    df = tabla_df(t, como_texto=True)
    if df.empty:
        return None
    columnas = [str(c) for c in df.columns]
    filas = [[str(v).strip() for v in fila] for fila in df.itertuples(index=False)]
    alineacion = []
    for j in range(len(columnas)):
        valores = [f[j] for f in filas if f[j]]
        alineacion.append("r" if valores and all(_es_numero(v) for v in valores) else "l")
    return {"titulo": latex_escape(t.titulo), "encabezados": [latex_escape(c) for c in columnas],
            "filas": [[latex_escape(v) for v in f] for f in filas], "alineacion": alineacion,
            # ancho de cada columna p{} en fracción del renglón, descontando el
            # espacio entre columnas (2·tabcolsep ≈ 0.03 del ancho de texto)
            "ancho": f"{0.97 * (1 - 0.03 * (len(columnas) - 1)) / len(columnas):.3f}"}


def contexto(estudios: list, claves: set, guardar) -> tuple[list, list]:
    """Secciones para la plantilla y claves citadas que no existen.
    `guardar(b64, nombre)` escribe una figura y devuelve su nombre de archivo."""
    salida, faltantes = [], []
    for e in estudios:
        if not e.en_informe or not (e.texto.strip() or e.tablas or e.figuras):
            continue
        parrafos = []
        for bloque in (b.strip() for b in e.texto.replace("\r\n", "\n").split("\n\n")):
            if bloque:
                latex, malas = biblio.citas(" ".join(bloque.split("\n")), claves)
                parrafos.append(latex)
                faltantes.extend(k for k in malas if k not in faltantes)
        figuras = []
        for k, f in enumerate((f for f in e.figuras if f.img_b64), 1):
            archivo = guardar(f.img_b64, f"estudio_{e.id}_{k}")
            if archivo:
                figuras.append({"archivo": archivo, "leyenda": latex_escape(f.leyenda),
                                "fuente": latex_escape(f.fuente)})
        salida.append({
            "titulo": latex_escape(e.titulo.strip() or TIPOS.get(e.tipo, TIPOS["otro"])),
            "parrafos": parrafos,
            "tablas": [c for c in (_tabla_ctx(t) for t in e.tablas) if c],
            "figuras": figuras,
        })
    return salida, faltantes

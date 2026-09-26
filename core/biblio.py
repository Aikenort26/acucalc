"""Referencias bibliográficas: biblioteca base, importación BibTeX y formato
LaTeX (lista numérica `thebibliography` + `\\cite`, sin biber/bibtex, así que
compila igual con pdflatex, tectonic o MiKTeX)."""
import json
import re
from dataclasses import dataclass, fields
from pathlib import Path

from core.latex import latex_escape

DATA = Path(__file__).resolve().parent.parent / "data" / "referencias.json"

# Una clave va dentro de \cite{} y \bibitem{}: sin espacios, comas ni llaves.
CLAVE_RE = re.compile(r"^[A-Za-z0-9_:.\-]+$")
# Marca de cita en texto libre del usuario: [@clave] o [@a; @b].
_MARCA_RE = re.compile(r"\[@([A-Za-z0-9_:.\-]+(?:\s*;\s*@[A-Za-z0-9_:.\-]+)*)\]")

_TIPOS_LIBRO = {"book", "inbook", "manual", "techreport", "phdthesis", "mastersthesis",
                "misc", "norma", "online", "unpublished", "booklet"}


@dataclass(frozen=True)
class Ref:
    key: str
    tipo: str = "misc"          # tipo de entrada BibTeX (book, article, ...) o "norma"
    autor: str = ""             # ya formateado para mostrar: "Apellido, N. y Otro, M."
    titulo: str = ""
    anio: str = ""
    editorial: str = ""         # publisher / institution / organization / school
    revista: str = ""           # journal / booktitle
    volumen: str = ""
    numero: str = ""
    paginas: str = ""
    lugar: str = ""
    edicion: str = ""
    url: str = ""
    doi: str = ""
    nota: str = ""


def _decodificar(s: str) -> str:
    from pylatexenc.latex2text import LatexNodes2Text
    return LatexNodes2Text().latex_to_text(s).strip()


def _iniciales(nombres: list[str]) -> str:
    ini = []
    for n in nombres:
        partes = [p for p in _decodificar(n).split("-") if p]
        ini.append("-".join(p[0].upper() + "." for p in partes))
    return " ".join(ini)


def _nombre(np) -> str:
    apellido = _decodificar(" ".join(np.von + np.last))
    if not np.first:                        # autor institucional o nombre único
        return apellido
    return f"{apellido}, {_iniciales(np.first)}"


def unir_autores(nombres: list[str]) -> str:
    if len(nombres) <= 1:
        return "".join(nombres)
    return ", ".join(nombres[:-1]) + " y " + nombres[-1]


_MAPA = {"title": "titulo", "year": "anio", "journal": "revista", "booktitle": "revista",
         "volume": "volumen", "number": "numero", "pages": "paginas", "address": "lugar",
         "edition": "edicion", "url": "url", "doi": "doi", "note": "nota",
         "howpublished": "nota", "publisher": "editorial", "institution": "editorial",
         "organization": "editorial", "school": "editorial"}


def parse_bibtex(texto: str) -> tuple[list[Ref], list[str]]:
    """(referencias válidas, errores legibles). Una entrada con clave inválida
    o sin título se reporta y se omite; nunca lanza por el contenido."""
    import bibtexparser
    from bibtexparser import middlewares as m
    lib = bibtexparser.parse_string(
        texto, append_middleware=[m.SeparateCoAuthors(), m.SplitNameParts()])
    refs, errores = [], [f"Bloque no reconocido: {b.raw.strip()[:60]}…"
                         for b in lib.failed_blocks]
    for e in lib.entries:
        if not CLAVE_RE.match(e.key):
            errores.append(f"Clave inválida '{e.key}': use letras, números, _ : . -")
            continue
        datos = {"key": e.key, "tipo": e.entry_type.lower()}
        for campo, destino in _MAPA.items():
            if campo in e.fields_dict and destino not in datos:
                datos[destino] = _decodificar(str(e[campo]))
        personas = e.fields_dict.get("author") or e.fields_dict.get("editor")
        if personas is not None:
            datos["autor"] = unir_autores([_nombre(n) for n in personas.value])
        if not datos.get("titulo"):
            errores.append(f"'{e.key}': falta el título")
            continue
        refs.append(Ref(**datos))
    return refs, errores


def formatear(r: Ref) -> str:
    """Texto LaTeX de la entrada (ya escapado), estilo autor–año:
    libro/norma/informe → Autor (año). \\emph{Título}. Lugar: Editorial. Nota.
    artículo → Autor (año). Título. \\emph{Revista}, vol(núm), págs.
    La URL/DOI no va aquí: la plantilla la pone en \\url{} (ver `url_de`)."""
    e = latex_escape
    partes = [f"{e(r.autor)} ({e(r.anio)})." if r.autor else f"({e(r.anio)})."]
    if r.tipo in _TIPOS_LIBRO or not r.revista:
        titulo = rf"\emph{{{e(r.titulo)}}}"
        if r.edicion:
            titulo += f" ({e(r.edicion)}.ª ed.)" if r.edicion.isdigit() else f" ({e(r.edicion)})"
        partes.append(titulo + ".")
        pub = ": ".join(x for x in (e(r.lugar), e(r.editorial)) if x)
        if pub:
            partes.append(pub + ".")
    else:
        partes.append(f"{e(r.titulo)}.")
        rev = rf"\emph{{{e(r.revista)}}}"
        if r.volumen:
            rev += f", {e(r.volumen)}" + (f"({e(r.numero)})" if r.numero else "")
        if r.paginas:
            rev += f", {e(r.paginas)}"
        partes.append(rev + ".")
    if r.nota:
        partes.append(f"{e(r.nota)}.")
    return " ".join(partes)


def url_de(r: Ref) -> str:
    if r.url:
        return r.url
    return f"https://doi.org/{r.doi}" if r.doi else ""


def citas(texto: str, claves: set[str]) -> tuple[str, list[str]]:
    """Escapa `texto` para LaTeX y convierte cada marca [@clave] (o [@a; @b]) en
    \\cite{...}. Una marca con alguna clave desconocida queda como texto
    literal y sus claves se devuelven en `faltantes`, para avisar al usuario
    en vez de producir una cita rota en el PDF."""
    salida, faltantes, pos = [], [], 0
    for m in _MARCA_RE.finditer(texto):
        salida.append(latex_escape(texto[pos:m.start()]))
        ks = [k.strip().lstrip("@") for k in m.group(1).split(";")]
        malas = [k for k in ks if k not in claves]
        if malas:
            faltantes.extend(malas)
            salida.append(latex_escape(m.group(0)))
        else:
            salida.append(r"\cite{" + ",".join(ks) + "}")
        pos = m.end()
    salida.append(latex_escape(texto[pos:]))
    return "".join(salida), faltantes


def biblioteca_base() -> list[Ref]:
    validos = {f.name for f in fields(Ref)}
    datos = json.loads(DATA.read_text(encoding="utf-8"))
    return [Ref(**{k: v for k, v in d.items() if k in validos}) for d in datos]


def bibitems(refs: list[Ref]) -> list[dict]:
    """Entradas listas para la plantilla: {key, texto, url}."""
    return [{"key": r.key, "texto": formatear(r), "url": url_de(r)} for r in refs]

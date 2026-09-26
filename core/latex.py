"""Escape de texto de usuario para LaTeX."""

_LATEX_MAP = [
    ("\\", r"\textbackslash{}"),
    ("&", r"\&"), ("%", r"\%"), ("$", r"\$"), ("#", r"\#"),
    ("_", r"\_"), ("{", r"\{"), ("}", r"\}"),
    ("~", r"\textasciitilde{}"), ("^", r"\textasciicircum{}"),
    ("→", r"$\to$"), ("×", r"$\times$"), ("Ø", r"\O{}"),
    ("—", "---"), ("–", "--"), ("−", "$-$"),
    ("“", "``"), ("”", "''"), ("‘", "`"), ("’", "'"),
    ("°", r"\textdegree{}"), ("²", r"\textsuperscript{2}"), ("³", r"\textsuperscript{3}"),
    ("≤", r"$\leq$"), ("≥", r"$\geq$"), ("±", r"$\pm$"), ("µ", r"$\mu$"), ("μ", r"$\mu$"),
    ("·", r"\textperiodcentered{}"), ("τ", r"$\tau$"), ("η", r"$\eta$"), ("Δ", r"$\Delta$"),
    ("α", r"$\alpha$"), ("ρ", r"$\rho$"),
]

_LATEX_ESCAPE_TABLE = dict(_LATEX_MAP)


def latex_escape(s: str) -> str:
    """Escapa un string de usuario para LaTeX y normaliza unicode frágil
    (flechas, multiplicación, Ø, guiones, comillas tipográficas, grados,
    superíndices) a su forma ASCII/LaTeX robusta — necesario porque el
    `main.tex` generado puede ser reabierto y re-guardado externamente en un
    encoding no-UTF8 (bug reportado: tildes y unicode se corrompen a U+FFFD
    tras ese re-guardado; el ASCII sobrevive).

    Se traduce carácter por carácter (no con `.replace()` encadenado) porque
    varios reemplazos insertan `{`/`}` literales (p.ej. `\\` ->
    `\textbackslash{}`); un `.replace()` en cadena volvería a escapar esas
    llaves recién insertadas y las duplicaría."""
    if not s:
        return s
    return "".join(_LATEX_ESCAPE_TABLE.get(ch, ch) for ch in s)

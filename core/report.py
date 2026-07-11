"""Genera el proyecto LaTeX de la memoria (estructura Res 0330) y lo compila."""
import shutil
import subprocess
import zipfile
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

TEMPLATES = Path(__file__).resolve().parent.parent / "templates" / "latex"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES)),
    block_start_string=r"\BLOCK{", block_end_string="}",
    variable_start_string=r"\VAR{", variable_end_string="}",
    comment_start_string=r"\#{", comment_end_string="}",
    autoescape=False, trim_blocks=True, lstrip_blocks=True,
)


def render(ctx: dict, out_dir: str | Path) -> Path:
    """Renderiza main.tex + copia figuras a out_dir/figures. Devuelve out_dir."""
    out = Path(out_dir)
    (out / "figures").mkdir(parents=True, exist_ok=True)
    tex = _env.get_template("main.tex.j2").render(**ctx)
    (out / "main.tex").write_text(tex, encoding="utf-8")
    for name, src in (ctx.get("figuras") or {}).items():
        shutil.copy(src, out / "figures" / Path(src).name)
    return out


def compile_pdf(project_dir: Path) -> tuple[Path | None, str]:
    """Compila con latexmk o pdflatex (2 pasadas) si están en PATH.

    Devuelve (ruta del PDF o None, cola del log LaTeX para diagnóstico).
    En MiKTeX se habilita la autoinstalación de paquetes faltantes."""
    exe = shutil.which("latexmk")
    if exe:
        cmd = [exe, "-pdf", "-interaction=nonstopmode", "main.tex"]
        runs = 1
    else:
        exe = shutil.which("pdflatex")
        if not exe:
            return None, "No se encontró latexmk ni pdflatex en el PATH."
        cmd = [exe, "-interaction=nonstopmode", "--enable-installer", "main.tex"]
        runs = 2
    salida = ""
    for _ in range(runs):
        try:
            res = subprocess.run(cmd, cwd=project_dir, capture_output=True,
                                 timeout=600)
            salida = (res.stdout or b"").decode("utf-8", errors="replace")
        except subprocess.TimeoutExpired:
            return None, "La compilación superó los 10 minutos (timeout)."
    log_file = project_dir / "main.log"
    if log_file.exists():
        salida = log_file.read_text(encoding="utf-8", errors="replace")
    log_tail = salida[-3000:] if salida else ""
    pdf = project_dir / "main.pdf"
    return (pdf if pdf.exists() else None), log_tail


def make_zip(project_dir: Path) -> Path:
    """ZIP del proyecto LaTeX (listo para Overleaf)."""
    z = project_dir.with_suffix(".zip")
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as f:
        for path in project_dir.rglob("*"):
            if path.is_file() and path.suffix != ".zip":
                f.write(path, path.relative_to(project_dir))
    return z

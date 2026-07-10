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


def compile_pdf(project_dir: Path) -> Path | None:
    """Compila con latexmk o pdflatex (2 pasadas) si están en PATH."""
    exe = shutil.which("latexmk")
    if exe:
        cmd = [exe, "-pdf", "-interaction=nonstopmode", "main.tex"]
        runs = 1
    else:
        exe = shutil.which("pdflatex")
        if not exe:
            return None
        cmd = [exe, "-interaction=nonstopmode", "main.tex"]
        runs = 2
    for _ in range(runs):
        subprocess.run(cmd, cwd=project_dir, capture_output=True, timeout=300)
    pdf = project_dir / "main.pdf"
    return pdf if pdf.exists() else None


def make_zip(project_dir: Path) -> Path:
    """ZIP del proyecto LaTeX (listo para Overleaf)."""
    z = project_dir.with_suffix(".zip")
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as f:
        for path in project_dir.rglob("*"):
            if path.is_file() and path.suffix != ".zip":
                f.write(path, path.relative_to(project_dir))
    return z

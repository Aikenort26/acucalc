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


def _engine_cmd(exe_name: str, exe: str) -> tuple[list[str], int]:
    """Comando y nº de pasadas para cada motor LaTeX soportado."""
    if exe_name == "tectonic":
        # autocontenido: descarga/cachea paquetes solo, sin Perl ni prompts.
        return [exe, "--outdir", ".", "main.tex"], 1
    if exe_name == "latexmk":
        return [exe, "-pdf", "-interaction=nonstopmode", "main.tex"], 1
    # pdflatex directo (2 pasadas para refs); MiKTeX auto-instala paquetes.
    return [exe, "-interaction=nonstopmode", "--enable-installer", "main.tex"], 2


def compile_pdf(project_dir: Path) -> tuple[Path | None, str]:
    """Compila el proyecto LaTeX con el primer motor disponible en el PATH.

    Orden de preferencia: tectonic (autocontenido, más confiable) → pdflatex
    (evita la dependencia de Perl de latexmk) → latexmk. Devuelve (ruta del PDF
    o None, cola del log para diagnóstico).

    Captura SIEMPRE stdout **y stderr** (antes solo stdout, por eso un fallo de
    latexmk sin Perl se veía como '(sin log)'), y ante cualquier excepción del
    subprocess devuelve el mensaje real — nunca un log vacío silencioso."""
    for exe_name in ("tectonic", "pdflatex", "latexmk"):
        exe = shutil.which(exe_name)
        if exe:
            break
    else:
        return None, "No se encontró ningún motor LaTeX (tectonic/pdflatex/latexmk) en el PATH."

    cmd, runs = _engine_cmd(exe_name, exe)
    salida = f"[motor: {exe_name} — {exe}]\n"
    for _ in range(runs):
        try:
            res = subprocess.run(cmd, cwd=project_dir, capture_output=True,
                                 timeout=600)
        except subprocess.TimeoutExpired:
            return None, salida + "La compilación superó los 10 minutos (timeout)."
        except Exception as e:  # FileNotFoundError, PermissionError, etc.
            return None, salida + f"No se pudo ejecutar {exe_name}: {type(e).__name__}: {e}"
        out = (res.stdout or b"").decode("utf-8", errors="replace")
        err = (res.stderr or b"").decode("utf-8", errors="replace")
        salida = (f"[motor: {exe_name} — {exe} — código de salida {res.returncode}]\n"
                  + out + ("\n--- STDERR ---\n" + err if err.strip() else ""))

    log_file = project_dir / "main.log"
    if log_file.exists():
        # main.log tiene el diagnóstico detallado de LaTeX; lo priorizamos pero
        # conservamos el stderr del motor (donde latexmk reporta 'Perl not found').
        log_txt = log_file.read_text(encoding="utf-8", errors="replace")
        salida = salida + "\n--- main.log ---\n" + log_txt
    log_tail = salida[-4000:] if salida.strip() else ""
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

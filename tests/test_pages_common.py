from pathlib import Path

from core.project import Project
from pages_common import resolve_save_path


def test_resolve_vacio_devuelve_none():
    assert resolve_save_path(Project(nombre="X")) is None


def test_resolve_archivo_json_se_usa_tal_cual():
    p = Project(nombre="X", ruta_guardado=r"C:\d\mi_proyecto.acucalc.json")
    assert resolve_save_path(p) == Path(r"C:\d\mi_proyecto.acucalc.json")


def test_resolve_carpeta_agrega_nombre_slug():
    p = Project(nombre="San Jacinto", ruta_guardado=r"C:\d\Proyectos")
    assert resolve_save_path(p) == Path(r"C:\d\Proyectos") / "San_Jacinto.acucalc.json"


def test_resolve_quita_comillas_envolventes():
    p = Project(nombre="X", ruta_guardado='"C:\\d\\p.acucalc.json"')
    assert resolve_save_path(p) == Path(r"C:\d\p.acucalc.json")

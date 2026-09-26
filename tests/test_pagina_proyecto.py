"""Regresión: abrir un proyecto guardado desde la página Proyecto no debe
dejar en los widgets los valores del proyecto anterior (el nombre se borraba y
departamento/municipio volvían al primero de la lista, pisando el modelo)."""
import uuid

from streamlit.testing.v1 import AppTest

from core import project as pj
from pages_common import SAVES_DIR


def _cargado():
    p = pj.Project(nombre="Acueducto San Jacinto", consultor="Aguas de Bolívar",
                   fecha="2026-07-11", altitud=200, temperatura=27.0)
    p.poblacion.dpto, p.poblacion.mpio, p.poblacion.tipo = "Bolívar", "San Jacinto", "municipio"
    p.departamento, p.municipio = "Bolívar", "San Jacinto"
    return p


def test_abrir_guardado_refleja_valores_en_widgets():
    SAVES_DIR.mkdir(exist_ok=True)
    nombre = f"zz_test_{uuid.uuid4().hex[:8]}.acucalc.json"
    f = SAVES_DIR / nombre
    pj.save(_cargado(), f)
    try:
        at = AppTest.from_file("../pages/1_Proyecto.py", default_timeout=30)
        at.run()                                        # sesión con proyecto vacío
        assert not at.exception
        at.selectbox(key="w_sel_save").select(nombre).run()
        [b for b in at.button if b.label == "📂 Abrir guardado"][0].click().run()
        assert not at.exception
        assert at.text_input(key="w_txt_nombre").value == "Acueducto San Jacinto"
        assert at.text_input(key="w_txt_consultor").value == "Aguas de Bolívar"
        assert at.selectbox(key="w_sel_dpto").value == "Bolívar"
        assert at.selectbox(key="w_sel_mpio").value == "San Jacinto"
        p = at.session_state["project"]
        assert p.nombre == "Acueducto San Jacinto"
        assert (p.departamento, p.municipio) == ("Bolívar", "San Jacinto")
        assert p.altitud == 200
    finally:
        f.unlink(missing_ok=True)

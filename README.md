# ACUCALC

App web local (Streamlit) para diseño de sistemas de acueducto según la
Resolución 0330 de 2017 (MVCT, Colombia): proyección de población, caudales,
almacenamiento, bombeo multi-tramo, digitalización de curvas de bombas y
reporte LaTeX.

## Uso
`run.bat` (Windows) o:

    python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
    .venv/Scripts/streamlit run app.py

## Tests
`pytest`

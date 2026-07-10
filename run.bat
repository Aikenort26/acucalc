@echo off
cd /d "%~dp0"
if not exist .venv (py -3.11 -m venv .venv || python -m venv .venv)
call .venv\Scripts\activate.bat
pip install -q -r requirements.txt
streamlit run app.py

@echo off
rem ACUCALC persistente: prepara el entorno y lanza el servidor DESACOPLADO.
rem La app queda en http://localhost:8501 aunque cierres esta ventana o la consola.
cd /d "%~dp0"
if not exist .venv (py -3 -m venv .venv || python -m venv .venv)
call .venv\Scripts\activate.bat
echo Instalando/actualizando dependencias...
pip install -q -r requirements.txt
echo.
echo Lanzando ACUCALC en segundo plano (persistente)...
wscript "%~dp0run_persistente.vbs"
echo Esperando a que el servidor levante...
timeout /t 6 >nul
start "" http://localhost:8501
echo.
echo  ACUCALC esta corriendo en http://localhost:8501
echo  Sobrevive al cierre de esta ventana. Para detenerlo: detener_acucalc.bat
echo.
timeout /t 4 >nul

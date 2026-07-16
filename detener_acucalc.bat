@echo off
rem Detiene el servidor ACUCALC persistente (el que ocupa el puerto 8501).
rem Primero deja una senal para que el bucle de auto-reinicio de
rem run_persistente.vbs NO lo vuelva a levantar, y despues mata el proceso.
cd /d "%~dp0"
echo. > "%~dp0.detener_acucalc"
echo Deteniendo ACUCALC (puerto 8501)...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr :8501 ^| findstr LISTENING') do (
    echo   matando PID %%p
    taskkill /f /pid %%p >nul 2>&1
)
echo Listo. Si seguia abierto en el navegador, recargalo para confirmar.
timeout /t 3 >nul

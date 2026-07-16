' Lanza ACUCALC (Streamlit) de forma PERSISTENTE y OCULTA.
' El proceso se desacopla de cualquier consola: cerrar la ventana NO lo detiene.
' Lo invoca run_persistente.bat (que ya preparó el entorno .venv).
' Para detenerlo: ejecuta detener_acucalc.bat o usa el Administrador de tareas.
Set sh  = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
base = fso.GetParentFolderName(WScript.ScriptFullName)
py   = base & "\.venv\Scripts\python.exe"
cmd  = "cmd /c """"" & py & """ -m streamlit run """ & base & "\app.py"" --server.headless true"""
' 0 = ventana oculta ; False = no esperar (se desacopla y esta señal muere aquí)
sh.Run cmd, 0, False

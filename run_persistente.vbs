' Lanza ACUCALC (Streamlit) de forma PERSISTENTE y OCULTA.
' El proceso se desacopla de cualquier consola: cerrar la ventana NO lo detiene.
' Ademas, si el servidor cae por cualquier causa, este script lo vuelve a levantar.
' Lo invoca run_persistente.bat (que ya preparo el entorno .venv).
' Para detenerlo de verdad: detener_acucalc.bat (deja una senal que rompe el bucle).
Set sh  = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
base     = fso.GetParentFolderName(WScript.ScriptFullName)
py       = base & "\.venv\Scripts\python.exe"
stopFlag = base & "\.detener_acucalc"

' --server.fileWatcherType none: este es un servidor de trabajo, no de desarrollo.
' Con el watcher activo, cualquier cambio en el codigo fuente (un git pull o un
' merge mientras la app corre) recarga el script y puede tumbar el proceso en
' plena sesion de trabajo.
cmd = "cmd /c """"" & py & """ -m streamlit run """ & base & "\app.py"" " & _
      "--server.headless true --server.fileWatcherType none"""

' Limpia una senal vieja: si no, el primer arranque se apagaria solo.
If fso.FileExists(stopFlag) Then fso.DeleteFile stopFlag

Do
    ' 0 = ventana oculta ; True = esperar. Si Run retorna, el servidor murio.
    sh.Run cmd, 0, True
    If fso.FileExists(stopFlag) Then
        fso.DeleteFile stopFlag
        Exit Do                  ' parada pedida por el usuario: no relanzar
    End If
    WScript.Sleep 3000           ' se cayo solo: espera y vuelve a levantarlo
Loop

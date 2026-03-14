Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
mado_root = fso.GetParentFolderName(WScript.ScriptFullName)
venv_python = mado_root & "\.venv\Scripts\pythonw.exe"
desktop_py = mado_root & "\desktop_window.py"

If fso.FileExists(venv_python) Then
    WshShell.Run Chr(34) & venv_python & Chr(34) & " " & Chr(34) & desktop_py & Chr(34), 0, False
Else
    WshShell.Run "pythonw " & Chr(34) & desktop_py & Chr(34), 0, False
End If

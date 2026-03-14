Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
batPath = fso.GetParentFolderName(WScript.ScriptFullName) & "\run_backend.bat"
WshShell.Run Chr(34) & batPath & Chr(34), 0, False

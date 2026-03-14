@echo off
chcp 65001 >nul 2>&1
title Local Claude Code

:: Ollamaサーバーが動いてるか確認（なければ起動）
tasklist | find "ollama.exe" >nul
if errorlevel 1 (
    echo Ollamaサーバーを起動します...
    start "" "C:\Program Files\Ollama\ollama.exe" serve
    echo Ollama 起動待機中...
    timeout /t 5 /nobreak >nul
)

cd /d "%~dp0"

:: Claude Code 起動
echo Claude Code を起動します...
claude --continue
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Claude Code の起動に失敗しました。
    echo   - claude コマンドがインストールされているか確認してください
    echo   - PATH に claude が含まれているか確認してください
    echo.
    pause
    exit /b 1
)

pause
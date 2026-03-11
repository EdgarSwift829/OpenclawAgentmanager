@echo off
title Local Claude Code

:: Ollamaサーバーが動いてるか確認（なければ起動）
tasklist | find "ollama.exe" >nul
if errorlevel 1 (
    echo Ollamaサーバーを起動します...
    start "" "C:\Program Files\Ollama\ollama.exe" serve
    timeout /t 5 /nobreak >nul
)

cd /d "%~dp0"
ollama launch claude --model qwen2.5-coder:14b-instruct-q5_k_m
claude --continue
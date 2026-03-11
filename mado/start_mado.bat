@echo off
chcp 65001 >nul 2>&1
title MADO - Multi-Agent Dev Orchestrator

echo ============================================
echo   MADO Startup
echo ============================================
echo.

:: ── Step 1: Environment Auto-Setup ───────────────
echo [1/3] 環境チェック＋自動セットアップ中...
python "%~dp0check_env.py"
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] 環境セットアップに失敗しました。上記のエラーを確認してください。
    pause
    exit /b 1
)

echo.

:: ── Determine venv python path ───────────────────
set "VENV_DIR=%~dp0.venv"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"
set "VENV_ACTIVATE=%VENV_DIR%\Scripts\activate.bat"

:: Fall back to global python if venv doesn't exist
if exist "%VENV_PYTHON%" (
    echo   [venv] %VENV_DIR% を使用します
    set "PYTHON_CMD=%VENV_PYTHON%"
) else (
    echo   [warn] venv が見つかりません — グローバル python を使用します
    set "PYTHON_CMD=python"
)

echo.

:: ── Step 2: Start Backend ────────────────────────
echo [2/3] バックエンド起動中 (http://localhost:8000) ...
start "MADO Backend" cmd /c ""%~dp0backend\run_backend.bat" || (echo. & echo [ERROR] バックエンドの起動に失敗しました & pause)"
timeout /t 3 /nobreak >nul

:: ── Step 3: Start Frontend + Desktop Window ─────────
echo [3/3] フロントエンド＋デスクトップウィンドウ起動中...
start "MADO Desktop" cmd /c ""%PYTHON_CMD%" "%~dp0desktop_window.py"" || (echo. & echo [ERROR] デスクトップウィンドウの起動に失敗しました & pause)

echo.
echo ============================================
echo   MADO 起動完了（デスクトップモード）
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:3001
echo   Health:   http://localhost:8000/api/health
echo ============================================
echo.
:: 成功時は自動で閉じる（3秒後）
echo 3秒後にこのウィンドウは自動で閉じます...
timeout /t 3 /nobreak >nul
exit /b 0

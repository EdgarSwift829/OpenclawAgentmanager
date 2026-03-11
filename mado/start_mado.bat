@echo off
chcp 65001 >nul 2>&1
title MADO - Multi-Agent Dev Orchestrator

echo ============================================
echo   MADO Startup
echo ============================================
echo.

:: ── Step 1: Environment Check ──────────────────
echo [1/3] 環境チェック中...
python "%~dp0check_env.py"
if %ERRORLEVEL% neq 0 (
    echo.
    echo 環境チェックに失敗しました。上記のエラーを確認してください。
    pause
    exit /b 1
)

echo.

:: ── Step 2: Start Backend ──────────────────────
echo [2/3] バックエンド起動中 (http://localhost:8000) ...
pushd "%~dp0backend"
start "MADO Backend" cmd /k "python -m uvicorn mado.backend.api.main:app --host 0.0.0.0 --port 8000 --reload"
popd
timeout /t 3 /nobreak >nul

:: ── Step 3: Start Frontend ─────────────────────
echo [3/3] フロントエンド起動中 (http://localhost:3000) ...
pushd "%~dp0frontend"
start "MADO Frontend" cmd /k "npm run dev"
popd

echo.
echo ============================================
echo   MADO 起動完了
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:3000
echo   Health:   http://localhost:8000/api/health
echo ============================================
echo.
echo このウィンドウは閉じて構いません。
pause

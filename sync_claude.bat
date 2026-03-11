@echo off
chcp 65001 >nul 2>&1
title MADO - Git Sync

echo ============================================
echo   Claude Code ブランチ → main 同期
echo ============================================
echo.

:: ── Fetch latest ──
echo [1/4] リモートから取得中...
git fetch origin
if %ERRORLEVEL% neq 0 (
    echo [ERROR] fetch に失敗しました。ネットワーク接続を確認してください。
    pause
    exit /b 1
)

:: ── Switch to main ──
echo [2/4] main ブランチに切り替え中...
git checkout main
if %ERRORLEVEL% neq 0 (
    echo [ERROR] main への切り替えに失敗しました。
    pause
    exit /b 1
)

:: ── Merge claude branch ──
echo [3/4] Claude Code ブランチをマージ中...
for /f "tokens=*" %%b in ('git branch -r --list "origin/claude/*" --sort=-committerdate') do (
    set "CLAUDE_BRANCH=%%b"
    goto :found
)
echo [ERROR] claude/ ブランチが見つかりません。
pause
exit /b 1

:found
:: Trim leading spaces
for /f "tokens=*" %%x in ("%CLAUDE_BRANCH%") do set "CLAUDE_BRANCH=%%x"
echo   マージ対象: %CLAUDE_BRANCH%
git merge %CLAUDE_BRANCH% --no-edit
if %ERRORLEVEL% neq 0 (
    echo [ERROR] マージに失敗しました。コンフリクトを確認してください。
    pause
    exit /b 1
)

:: ── Push to remote ──
echo [4/4] リモートに push 中...
git push origin main
if %ERRORLEVEL% neq 0 (
    echo [ERROR] push に失敗しました。
    pause
    exit /b 1
)

echo.
echo ============================================
echo   同期完了！
echo ============================================
echo.

:: ── Clean up merged claude branches ──
echo 不要な claude ブランチを削除中...
for /f "tokens=*" %%b in ('git branch --list "claude/*"') do (
    git branch -d "%%b" >nul 2>&1
)

echo 3秒後に閉じます...
timeout /t 3 /nobreak >nul
exit /b 0

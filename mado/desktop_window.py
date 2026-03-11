"""MADO Desktop Window Launcher using pywebview.

Starts the Next.js dev server, waits for it, then opens a native OS window.
No browser, no Electron — just Python + pywebview.
"""

import atexit
import os
import signal
import subprocess
import sys
import time
import urllib.request
import webview

NEXT_URL = "http://localhost:3001"
MAX_RETRIES = 30
RETRY_INTERVAL = 1  # seconds

MADO_ROOT = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(MADO_ROOT, "frontend")

_nextjs_proc = None


def start_nextjs():
    """Start the Next.js dev server as a subprocess (hidden on Windows)."""
    global _nextjs_proc
    print("[MADO] Next.js dev server を起動中...")

    kwargs = {}
    if sys.platform.startswith("win"):
        # Hide the console window on Windows
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0  # SW_HIDE
        kwargs["startupinfo"] = startupinfo
        kwargs["shell"] = True
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    # Build if .next directory doesn't exist
    next_dir = os.path.join(FRONTEND_DIR, ".next")
    if not os.path.isdir(next_dir):
        print("[MADO] Next.js ビルド中 (初回のみ)...")
        build_kw = {"cwd": FRONTEND_DIR}
        if sys.platform.startswith("win"):
            build_kw["shell"] = True
        subprocess.run(["npm", "run", "build"], **build_kw)

    # Use production server (next start) for stability
    _nextjs_proc = subprocess.Popen(
        ["npm", "run", "start", "--", "-p", "3001"],
        cwd=FRONTEND_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        **kwargs,
    )


def stop_nextjs():
    """Terminate the Next.js dev server on exit."""
    global _nextjs_proc
    if _nextjs_proc and _nextjs_proc.poll() is None:
        print("[MADO] Next.js dev server を停止中...")
        if sys.platform.startswith("win"):
            _nextjs_proc.terminate()
        else:
            os.killpg(os.getpgid(_nextjs_proc.pid), signal.SIGTERM)
        try:
            _nextjs_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _nextjs_proc.kill()


def wait_for_nextjs() -> bool:
    """Wait until the Next.js dev server responds."""
    for _ in range(MAX_RETRIES):
        # Check if process died
        if _nextjs_proc and _nextjs_proc.poll() is not None:
            print("[MADO] Next.js プロセスが異常終了しました。", file=sys.stderr)
            return False
        try:
            req = urllib.request.Request(NEXT_URL)
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status in (200, 304):
                    return True
        except Exception:
            pass
        time.sleep(RETRY_INTERVAL)
    return False


def main() -> int:
    start_nextjs()
    atexit.register(stop_nextjs)

    print("[MADO] Next.js サーバーの起動を待機中...")
    if not wait_for_nextjs():
        print("[MADO] Next.js が起動しませんでした。中止します。", file=sys.stderr)
        return 1

    print("[MADO] デスクトップウィンドウを起動します...")
    webview.create_window(
        title="MADO - Multi-Agent Dev Orchestrator",
        url=NEXT_URL,
        width=1400,
        height=900,
    )
    webview.start()
    return 0


if __name__ == "__main__":
    sys.exit(main())

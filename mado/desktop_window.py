"""MADO Desktop Window Launcher using pywebview.

Waits for the Next.js dev server, then opens a native OS window.
No browser, no Electron — just Python + pywebview.
"""

import sys
import time
import urllib.request
import webview

NEXT_URL = "http://localhost:3000"
MAX_RETRIES = 30
RETRY_INTERVAL = 1  # seconds


def wait_for_nextjs() -> bool:
    """Wait until the Next.js dev server responds."""
    for i in range(MAX_RETRIES):
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

"""MADO E2E Test Runner - Playwright (Python) + FastAPI backend.

Architecture:
  Playwright (headless Chromium)
    -> Next.js frontend (localhost:3000)
      -> FastAPI backend (localhost:8000)

Usage:
  python tests/e2e/run_e2e.py
"""

import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]
SCREENSHOTS_DIR = ROOT / "tests" / "e2e" / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = 8000
BACKEND_URL = f"http://{BACKEND_HOST}:{BACKEND_PORT}"

FRONTEND_HOST = "127.0.0.1"
FRONTEND_PORT = 3000
FRONTEND_URL = f"http://{FRONTEND_HOST}:{FRONTEND_PORT}"

# Use existing Chromium from Playwright cache
CHROMIUM_PATH = str(
    Path.home() / ".cache" / "ms-playwright" / "chromium-1194" / "chrome-linux" / "chrome"
)

# ---------------------------------------------------------------------------
# Test result tracking
# ---------------------------------------------------------------------------
@dataclass
class TestResult:
    name: str
    passed: bool
    detail: str = ""
    screenshot: str = ""


@dataclass
class TestSuite:
    results: list = field(default_factory=list)

    def add(self, result: TestResult):
        self.results.append(result)
        status = "PASS" if result.passed else "FAIL"
        print(f"  [{status}] {result.name}: {result.detail}")

    def summary(self) -> str:
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        lines = [
            "",
            "=" * 60,
            f"  E2E Test Results: {passed}/{total} PASSED",
            "=" * 60,
        ]
        for r in self.results:
            mark = "PASS" if r.passed else "FAIL"
            lines.append(f"  [{mark}] {r.name}")
            if not r.passed:
                lines.append(f"         -> {r.detail}")
            if r.screenshot:
                lines.append(f"         screenshot: {r.screenshot}")
        lines.append("=" * 60)
        return "\n".join(lines)

    @property
    def all_passed(self) -> bool:
        return all(r.passed for r in self.results)


# ---------------------------------------------------------------------------
# Process management
# ---------------------------------------------------------------------------
def start_backend():
    """Start FastAPI backend server."""
    print("[setup] Starting FastAPI backend...")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    # Allow CORS from both localhost and 127.0.0.1 for E2E testing
    env["MADO_CORS_ORIGINS"] = (
        f"http://localhost:{FRONTEND_PORT},"
        f"http://127.0.0.1:{FRONTEND_PORT},"
        f"http://localhost:{BACKEND_PORT},"
        f"http://127.0.0.1:{BACKEND_PORT}"
    )
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn",
            "mado.backend.api.main:app",
            "--host", BACKEND_HOST,
            "--port", str(BACKEND_PORT),
        ],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return proc


def wait_for_server(url: str, timeout: int = 30, label: str = "server") -> bool:
    """Wait for an HTTP server to respond."""
    import urllib.error
    import urllib.request

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            req = urllib.request.Request(f"{url}/api/health")
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    print(f"[setup] {label} is ready at {url}")
                    return True
        except (urllib.error.URLError, ConnectionError, OSError):
            pass
        time.sleep(1)
    print(f"[setup] TIMEOUT waiting for {label} at {url}")
    return False


def kill_proc(proc):
    """Gracefully stop a subprocess."""
    if proc and proc.poll() is None:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


# ---------------------------------------------------------------------------
# Test functions
# ---------------------------------------------------------------------------
def test_health_api(suite: TestSuite):
    """Test 1: Backend /api/health returns ok."""
    import urllib.request
    try:
        with urllib.request.urlopen(f"{BACKEND_URL}/api/health", timeout=5) as resp:
            data = json.loads(resp.read())
            assert data.get("status") == "ok", f"Unexpected: {data}"
            suite.add(TestResult("API Health Check", True, "status=ok"))
    except Exception as e:
        suite.add(TestResult("API Health Check", False, str(e)))


def test_projects_api(suite: TestSuite):
    """Test 2: /api/projects/ returns list."""
    import urllib.request
    try:
        with urllib.request.urlopen(f"{BACKEND_URL}/api/projects/", timeout=10) as resp:
            data = json.loads(resp.read())
            assert "projects" in data, f"Missing 'projects' key: {data.keys()}"
            assert "tree" in data, f"Missing 'tree' key: {data.keys()}"
            suite.add(TestResult(
                "Projects API",
                True,
                f"projects={len(data['projects'])}, tree={len(data['tree'])}",
            ))
    except Exception as e:
        suite.add(TestResult("Projects API", False, str(e)))


def test_models_api(suite: TestSuite):
    """Test 3: /api/models/ returns list."""
    import urllib.request
    try:
        with urllib.request.urlopen(f"{BACKEND_URL}/api/models/", timeout=10) as resp:
            data = json.loads(resp.read())
            assert "models" in data or "roles" in data, f"Unexpected keys: {data.keys()}"
            suite.add(TestResult("Models API", True, f"keys={list(data.keys())}"))
    except Exception as e:
        suite.add(TestResult("Models API", False, str(e)))


def test_frontend_loads(page, suite: TestSuite):
    """Test 4: Frontend loads and shows MADO title."""
    try:
        page.goto(FRONTEND_URL, timeout=30_000)
        page.wait_for_load_state("networkidle", timeout=20_000)

        # Check page title
        title = page.title()
        has_title = "MADO" in title

        # Check body text for key UI elements
        body_text = page.inner_text("body")
        has_mado = "MADO" in body_text

        ss = str(SCREENSHOTS_DIR / "01_frontend_loaded.png")
        page.screenshot(path=ss, full_page=True)

        assert has_title or has_mado, f"MADO not found in title='{title}' or body"
        suite.add(TestResult("Frontend Loads", True, f"title='{title}'", ss))
    except Exception as e:
        ss = str(SCREENSHOTS_DIR / "01_frontend_fail.png")
        try:
            page.screenshot(path=ss, full_page=True)
        except Exception:
            pass
        suite.add(TestResult("Frontend Loads", False, str(e), ss))


def test_sidebar_visible(page, suite: TestSuite):
    """Test 5: Sidebar (project tree) is visible (reuses current page)."""
    try:
        # Don't re-navigate; reuse the page already loaded by test_frontend_loads
        body_text = page.inner_text("body")

        # Look for sidebar element
        sidebar = page.locator("aside.sidebar").first
        visible = sidebar.is_visible()

        # Also check for sidebar-related content
        has_sidebar_content = "MADO" in body_text or "プロジェクト" in body_text or "PROJECTS" in body_text

        ss = str(SCREENSHOTS_DIR / "02_sidebar.png")
        page.screenshot(path=ss, full_page=True)

        assert visible or has_sidebar_content, "Sidebar not visible"
        suite.add(TestResult("Sidebar Visible", True, "sidebar found", ss))
    except Exception as e:
        ss = str(SCREENSHOTS_DIR / "02_sidebar_fail.png")
        try:
            page.screenshot(path=ss, full_page=True)
        except Exception:
            pass
        suite.add(TestResult("Sidebar Visible", False, str(e), ss))


def test_right_panel_tabs(page, suite: TestSuite):
    """Test 6: Right panel tabs (Timeline/Agents/Models/Tasks) exist (reuses current page)."""
    try:
        # Don't re-navigate; reuse the page already loaded by test_frontend_loads
        body_text = page.inner_text("body")

        # Check for tab labels in body text (more robust than CSS selectors)
        tab_keywords_ja = ["タイムライン", "エージェント", "モデル", "タスク"]
        tab_keywords_en = ["Timeline", "Agents", "Models", "Tasks"]
        found_tabs = sum(1 for kw in tab_keywords_ja if kw in body_text)
        if found_tabs < 3:
            found_tabs = sum(1 for kw in tab_keywords_en if kw in body_text)

        # Also try CSS selector as secondary check
        tab_buttons = page.locator("button.right-tab")
        tab_count = tab_buttons.count()

        ss = str(SCREENSHOTS_DIR / "03_right_panel.png")
        page.screenshot(path=ss, full_page=True)

        assert found_tabs >= 3 or tab_count >= 3, f"Expected >= 3 tabs, found text={found_tabs} buttons={tab_count}"
        suite.add(TestResult("Right Panel Tabs", True, f"tabs_text={found_tabs}, buttons={tab_count}", ss))
    except Exception as e:
        ss = str(SCREENSHOTS_DIR / "03_right_panel_fail.png")
        try:
            page.screenshot(path=ss, full_page=True)
        except Exception:
            pass
        suite.add(TestResult("Right Panel Tabs", False, str(e), ss))


def test_no_console_errors(page, suite: TestSuite):
    """Test 7: No critical JS console errors on page load."""
    errors = []

    def on_console(msg):
        if msg.type == "error":
            errors.append(msg.text)

    page.on("console", on_console)
    try:
        # Reload instead of re-navigating (more stable with Next.js dev server)
        page.reload(timeout=30_000)
        page.wait_for_load_state("networkidle", timeout=20_000)
        page.wait_for_timeout(3000)

        # Filter out known benign errors (e.g., WebSocket connection fails without active project)
        critical_errors = [
            e for e in errors
            if "websocket" not in e.lower()
            and "favicon" not in e.lower()
            and "hydration" not in e.lower()
            and "400" not in e
            and "404" not in e
            and "failed to load resource" not in e.lower()
        ]

        ss = str(SCREENSHOTS_DIR / "04_console.png")
        page.screenshot(path=ss, full_page=True)

        if critical_errors:
            suite.add(TestResult(
                "No Console Errors", False,
                f"{len(critical_errors)} errors: {critical_errors[:3]}", ss,
            ))
        else:
            suite.add(TestResult(
                "No Console Errors", True,
                f"0 critical errors ({len(errors)} total logged)", ss,
            ))
    except Exception as e:
        suite.add(TestResult("No Console Errors", False, str(e)))
    finally:
        page.remove_listener("console", on_console)


def test_websocket_endpoint(suite: TestSuite):
    """Test 8: WebSocket endpoint exists (connection test with dummy project)."""
    import asyncio

    async def _test_ws():
        import websockets
        uri = f"ws://{BACKEND_HOST}:{BACKEND_PORT}/api/ws/test-project"
        try:
            async with websockets.connect(uri, open_timeout=5) as ws:
                # If we connect, the endpoint works
                # Server may send initial message or we just verify connection
                return True, "connected"
        except Exception as e:
            return False, str(e)

    try:
        ok, detail = asyncio.run(_test_ws())
        suite.add(TestResult("WebSocket Endpoint", ok, detail))
    except Exception as e:
        suite.add(TestResult("WebSocket Endpoint", False, str(e)))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=" * 60)
    print("  MADO E2E Test Suite")
    print("=" * 60)

    suite = TestSuite()
    backend_proc = None
    browser = None
    playwright_ctx = None

    try:
        # --- Start backend ---
        backend_proc = start_backend()
        if not wait_for_server(BACKEND_URL, timeout=30, label="FastAPI backend"):
            print("[FATAL] Backend failed to start")
            suite.add(TestResult("Backend Startup", False, "timeout"))
            print(suite.summary())
            return 1

        # --- API-only tests (no browser needed) ---
        print("\n--- API Tests ---")
        test_health_api(suite)
        test_projects_api(suite)
        test_models_api(suite)
        test_websocket_endpoint(suite)

        # --- Browser tests ---
        print("\n--- Browser Tests ---")
        if not Path(CHROMIUM_PATH).exists():
            print(f"[WARN] Chromium not found at {CHROMIUM_PATH}, skipping browser tests")
            suite.add(TestResult("Browser Tests", False, "Chromium not available"))
        else:
            from playwright.sync_api import sync_playwright

            playwright_ctx = sync_playwright().start()
            browser = playwright_ctx.chromium.launch(
                headless=True,
                executable_path=CHROMIUM_PATH,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            page = browser.new_page(viewport={"width": 1280, "height": 900})

            # Check if frontend is available (may not be running in CI)
            import urllib.error
            import urllib.request
            frontend_available = False
            try:
                with urllib.request.urlopen(FRONTEND_URL, timeout=5) as resp:
                    frontend_available = resp.status == 200
            except (urllib.error.URLError, ConnectionError, OSError):
                pass

            if frontend_available:
                test_frontend_loads(page, suite)
                test_sidebar_visible(page, suite)
                test_right_panel_tabs(page, suite)
                test_no_console_errors(page, suite)
            else:
                print(f"[WARN] Frontend not available at {FRONTEND_URL}, skipping browser tests")
                print("       Start frontend with: cd mado/frontend && npm run dev")
                suite.add(TestResult(
                    "Frontend Available", False,
                    f"No response from {FRONTEND_URL} (start with 'npm run dev')",
                ))

    except KeyboardInterrupt:
        print("\n[interrupted]")
    except Exception as e:
        print(f"\n[FATAL] {e}")
        suite.add(TestResult("Test Runner", False, str(e)))
    finally:
        if browser:
            browser.close()
        if playwright_ctx:
            playwright_ctx.stop()
        kill_proc(backend_proc)

    print(suite.summary())
    return 0 if suite.all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
